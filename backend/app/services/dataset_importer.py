
"""Persistence service for authorized JSONL dataset imports."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import (
    DBAPIError,
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.orm import Session

from app.models.dataset_ingestion import (
    DatasetImportError,
    DatasetImportResult,
    DatasetLineError,
)
from app.models.db_models import ObservationModel, SourceModel
from app.models.enums import ObservationStatus
from app.models.observations import calculate_payload_sha256
from app.services.dataset_ingestion import parse_jsonl_lines


def _rollback_safely(db: Session) -> None:
    """Attempt rollback without masking the original database error."""
    try:
        db.rollback()
    except SQLAlchemyError:
        pass


def _is_connection_failure(exc: SQLAlchemyError) -> bool:
    """Identify database failures that make continuing unsafe."""
    if isinstance(exc, (OperationalError, InterfaceError)):
        return True

    return isinstance(exc, DBAPIError) and exc.connection_invalidated


def import_jsonl_lines(
    db: Session,
    source_id: UUID,
    lines: list[str],
) -> DatasetImportResult:
    """Import JSONL records for an authorized source.

    Each record is committed independently. Earlier successful records
    remain committed if a later record fails.

    A duplicate is defined by source, canonical payload hash, and
    observed timestamp. Database connection failures stop the import;
    other record-level SQLAlchemy write failures are reported per line.
    """

    try:
        source = db.get(SourceModel, source_id)
    except SQLAlchemyError as exc:
        _rollback_safely(db)
        raise DatasetImportError(
            "Database lookup failed while checking the source; "
            "import stopped. No new records were intentionally written."
        ) from exc

    if source is None:
        raise DatasetImportError("Unknown source.")

    if not source.authorized_for_use:
        raise DatasetImportError("Source is not authorized for use.")

    parsed = parse_jsonl_lines(lines)

    imported_count = 0
    skipped_duplicate_count = 0
    errors = list(parsed.errors)

    # Includes duplicates already stored and earlier records in this batch.
    seen_keys: set[tuple[UUID, str, datetime | None]] = set()

    for parsed_record in parsed.records:
        line_number = parsed_record.line_number
        record = parsed_record.record

        try:
            content_hash = calculate_payload_sha256(record.payload)
        except (TypeError, ValueError) as exc:
            errors.append(
                DatasetLineError(
                    line_number=line_number,
                    error=f"Payload cannot be hashed: {exc}",
                )
            )
            continue

        duplicate_key = (source_id, content_hash, record.observed_at)

        if duplicate_key in seen_keys:
            skipped_duplicate_count += 1
            continue

        seen_keys.add(duplicate_key)

        try:
            existing_id = db.scalar(
                select(ObservationModel.observation_id).where(
                    ObservationModel.source_id == source_id,
                    ObservationModel.content_sha256 == content_hash,
                    ObservationModel.observed_at == record.observed_at,
                )
            )
        except SQLAlchemyError as exc:
            _rollback_safely(db)
            raise DatasetImportError(
                "Database lookup failed; import stopped. "
                "Previously committed records, if any, remain stored."
            ) from exc

        if existing_id is not None:
            skipped_duplicate_count += 1
            continue

        observation = ObservationModel(
            source_id=source_id,
            collected_at=(
                record.collected_at or datetime.now(timezone.utc)
            ),
            observed_at=record.observed_at,
            payload=record.payload,
            content_sha256=content_hash,
            status=ObservationStatus.INGESTED.value,
            processing_version=record.processing_version,
        )

        try:
            db.add(observation)
            db.commit()
            imported_count += 1

        except SQLAlchemyError as exc:
            _rollback_safely(db)

            if _is_connection_failure(exc):
                raise DatasetImportError(
                    "Database connection failure during record write; "
                    "import stopped. Previously committed records remain "
                    "stored, and the status of the failed record may "
                    "require verification."
                ) from exc

            errors.append(
                DatasetLineError(
                    line_number=line_number,
                    error="Database write failed for this record.",
                )
            )

    return DatasetImportResult(
        source_id=source_id,
        total_lines=len(lines),
        parsed_count=parsed.accepted_count,
        imported_count=imported_count,
        skipped_duplicate_count=skipped_duplicate_count,
        rejected_count=len(errors),
        errors=tuple(errors),
    )
