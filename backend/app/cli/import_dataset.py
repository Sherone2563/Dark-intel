
"""Command-line interface for importing authorized JSONL datasets."""

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from app.services.ingestion_pipeline import (
    IngestionPipelineError,
    run_ingestion_pipeline,
)
from app.core.database import SessionLocal
from app.models.dataset_ingestion import DatasetImportError
from app.services.dataset_importer import import_jsonl_lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Import a local JSONL research dataset into Dark-Intel "
            "for an authorized source."
        )
    )
    parser.add_argument(
        "--file",
        required=True,
        type=Path,
        help="Path to the local UTF-8 JSONL file.",
    )
    parser.add_argument(
        "--source-id",
        required=True,
        type=UUID,
        help="UUID of an existing authorized source.",
    )
    parser.add_argument(
            "--full-pipeline",
        action="store_true",
        help=(
            "Run import, handle extraction, and provenance processing "
            "instead of import only."
        ),
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.file.is_file():
        print(f"Error: input file does not exist: {args.file}", file=sys.stderr)
        return 1

    try:
        with args.file.open("r", encoding="utf-8") as dataset_file:
            lines = dataset_file.read().splitlines()
    except (OSError, UnicodeError) as exc:
        print(f"Error reading dataset: {exc}", file=sys.stderr)
        return 1

    try:
        with SessionLocal() as db:
            if args.full_pipeline:
                output = run_ingestion_pipeline(
                    db=db,
                    source_id=args.source_id,
                    lines=lines,
                )
                rejected_count = output["import"]["rejected_count"]
            else:
                result = import_jsonl_lines(
                    db=db,
                    source_id=args.source_id,
                    lines=lines,
                )
                output = result.model_dump(mode="json")
                rejected_count = result.rejected_count

    except IngestionPipelineError as exc:
        failure_output = {
            "status": "failed",
            "error": str(exc),
        }

        if exc.import_result is not None:
            failure_output["import"] = (
                exc.import_result.model_dump(mode="json")
            )

        print(
            json.dumps(
                failure_output,
                indent=2,
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1

    except DatasetImportError as exc:
        print(f"Import stopped: {exc}", file=sys.stderr)
        return 1

    except SQLAlchemyError:
        print(
            "Import stopped: an unexpected database error occurred.",
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )
    )

    # Exit 2 signals a completed operation with rejected records.
    return 2 if rejected_count else 0

    print(
        json.dumps(
            result.model_dump(mode="json"),
            indent=2,
            ensure_ascii=False,
        )
    )

    # Exit 2 signals a completed import that contains rejected records.
    return 2 if result.rejected_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
