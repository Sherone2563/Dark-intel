import json
from collections.abc import Iterable

from pydantic import ValidationError

from app.models.dataset_ingestion import (
    DatasetLineError,
    DatasetObservationInput,
    DatasetParseResult,
    ParsedDatasetRecord,
)


def parse_jsonl_lines(lines: Iterable[str]) -> DatasetParseResult:
    """Parse records independently while preserving original line numbers."""

    records: list[ParsedDatasetRecord] = []
    errors: list[DatasetLineError] = []

    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue

        try:
            value = json.loads(raw_line)

            if not isinstance(value, dict):
                raise ValueError("Each line must contain a JSON object.")

            record = DatasetObservationInput.model_validate(value)
            records.append(
                ParsedDatasetRecord(
                    line_number=line_number,
                    record=record,
                )
            )

        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            errors.append(
                DatasetLineError(
                    line_number=line_number,
                    error=str(exc),
                )
            )

    return DatasetParseResult(
        records=tuple(records),
        errors=tuple(errors),
    )