"""Orchestrate authorized dataset imports and entity extraction."""

from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.dataset_ingestion import (
    DatasetImportError,
    DatasetImportResult,
)
from app.models.db_models import ProcessingRunModel
from app.models.enums import ProcessingRunStatus
from app.services.dataset_importer import import_jsonl_lines
from app.services.entity_extraction import (
    EntityExtractionError,
    extract_handles_from_source,
)


PIPELINE_PROCESSING_VERSION = "0.1.0"


class IngestionPipelineError(Exception):
    """Raised when the ingestion pipeline cannot complete safely."""

    def __init__(
        self,
        message: str,
        *,
        run_id: UUID | None = None,
        import_result: DatasetImportResult | None = None,
    ) -> None:
        super().__init__(message)
        self.run_id = run_id
        self.import_result = import_result


def _update_processing_run(
    db: Session,
    run_id: UUID,
    **values,
) -> None:
    """Persist a processing-run update independently of import transactions."""

    try:
        db.execute(
            update(ProcessingRunModel)
            .where(ProcessingRunModel.run_id == run_id)
            .values(**values)
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def _mark_run_failed(
    db: Session,
    run_id: UUID,
    error_message: str,
) -> None:
    """Best-effort persistence of a failed processing state."""

    try:
        _update_processing_run(
            db,
            run_id,
            status=ProcessingRunStatus.FAILED.value,
            completed_at=datetime.now(timezone.utc),
            error_message=error_message[:4000],
        )
    except SQLAlchemyError:
        # A database outage may prevent recording the final status.
        # Do not hide the original pipeline failure.
        pass


def run_ingestion_pipeline(
    db: Session,
    source_id: UUID,
    lines: list[str],
) -> dict:
    """Import records and extract entities for an authorized source.

    The processing-run record is committed before importing begins.
    Observation imports retain their existing per-record commit behavior.
    Extraction remains a separate transaction.
    """

    run_id = uuid4()

    processing_run = ProcessingRunModel(
        run_id=run_id,
        source_id=source_id,
        status=ProcessingRunStatus.STARTED.value,
        total_lines=len(lines),
        processing_version=PIPELINE_PROCESSING_VERSION,
    )

    try:
        db.add(processing_run)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise IngestionPipelineError(
            "Unable to create the processing-run record."
        ) from exc

    try:
        _update_processing_run(
            db,
            run_id,
            status=ProcessingRunStatus.IMPORTING.value,
        )

        import_result = import_jsonl_lines(
            db=db,
            source_id=source_id,
            lines=lines,
        )

    except (DatasetImportError, SQLAlchemyError) as exc:
        db.rollback()

        error_message = f"Dataset import failed: {exc}"

        _mark_run_failed(
            db,
            run_id,
            error_message,
        )

        raise IngestionPipelineError(
            error_message,
            run_id=run_id,
        ) from exc

    try:
        _update_processing_run(
            db,
            run_id,
            status=ProcessingRunStatus.EXTRACTING.value,
            parsed_count=import_result.parsed_count,
            imported_count=import_result.imported_count,
            skipped_duplicate_count=(
                import_result.skipped_duplicate_count
            ),
            rejected_count=import_result.rejected_count,
        )

        extraction_result = extract_handles_from_source(
            db=db,
            source_id=source_id,
        )

    except EntityExtractionError as exc:
        error_message = (
            "Dataset import finished, but entity extraction failed. "
            "Previously committed observations remain stored."
        )

        _mark_run_failed(
            db,
            run_id,
            error_message,
        )

        raise IngestionPipelineError(
            error_message,
            run_id=run_id,
            import_result=import_result,
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()

        error_message = (
            "Dataset import finished, but processing-run or extraction "
            "persistence failed. Previously committed observations "
            "remain stored."
        )

        _mark_run_failed(
            db,
            run_id,
            error_message,
        )

        raise IngestionPipelineError(
            error_message,
            run_id=run_id,
            import_result=import_result,
        ) from exc

    final_status = (
        ProcessingRunStatus.COMPLETED_WITH_REJECTIONS.value
        if import_result.rejected_count
        else ProcessingRunStatus.COMPLETED.value
    )

    try:
        _update_processing_run(
            db,
            run_id,
            status=final_status,
            parsed_count=import_result.parsed_count,
            imported_count=import_result.imported_count,
            skipped_duplicate_count=(
                import_result.skipped_duplicate_count
            ),
            rejected_count=import_result.rejected_count,
            observations_examined=(
                extraction_result["observations_examined"]
            ),
            entities_created=extraction_result["entities_created"],
            existing_entities_matched=(
                extraction_result["existing_entities_matched"]
            ),
            associations_created=(
                extraction_result["associations_created"]
            ),
            handles_processed=extraction_result["handles_processed"],
            pgp_keys_processed=extraction_result["pgp_keys_processed"],
            completed_at=datetime.now(timezone.utc),
        )

    except SQLAlchemyError as exc:
        db.rollback()

        error_message = (
            "Import and extraction completed, but the final processing-run "
            "status could not be saved."
        )

        _mark_run_failed(
            db,
            run_id,
            error_message,
        )

        raise IngestionPipelineError(
            error_message,
            run_id=run_id,
            import_result=import_result,
        ) from exc

    return {
        "run_id": str(run_id),
        "source_id": str(source_id),
        "import": import_result.model_dump(mode="json"),
        "extraction": extraction_result,
        "status": final_status,
    }