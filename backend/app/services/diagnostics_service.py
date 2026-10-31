from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.db_models import ProcessingRunModel, SourceModel
from app.models.monitoring_api import (
    ProcessingDiagnosticResponse,
    ProcessingDiagnosticsListResponse,
)


def classify_processing_run(
    status: str,
    error_message: str | None,
) -> tuple[str, str, str | None]:
    """Classify a processing run using its persisted status and error."""

    if status == "completed_with_rejections":
        return "warning", "ingestion_rejections", None

    message = (error_message or "").lower()

    if message.startswith("dataset import failed:"):
        return "error", "dataset_import", "import"

    if "entity extraction failed" in message:
        return "error", "entity_extraction", "entity_extraction"

    if (
        "persistence failed" in message
        or "status could not be saved" in message
    ):
        return "error", "persistence", "persistence"

    return "error", "unknown", "unknown"


def generate_processing_diagnostics(
    db: Session,
    days: int = 30,
    limit: int = 20,
    offset: int = 0,
) -> ProcessingDiagnosticsListResponse:
    """Return failed and rejected processing runs with diagnostic context."""

    period_start = datetime.now(timezone.utc) - timedelta(days=days)

    statement = (
        select(ProcessingRunModel, SourceModel)
        .join(
            SourceModel,
            ProcessingRunModel.source_id == SourceModel.source_id,
        )
        .where(
            ProcessingRunModel.started_at >= period_start,
            ProcessingRunModel.status.in_(
                ["failed", "completed_with_rejections"]
            ),
        )
        .order_by(
            ProcessingRunModel.started_at.desc(),
            ProcessingRunModel.run_id.desc(),
        )
    )

    count_statement = (
        select(ProcessingRunModel.run_id)
        .where(
            ProcessingRunModel.started_at >= period_start,
            ProcessingRunModel.status.in_(
                ["failed", "completed_with_rejections"]
            ),
        )
    )

    result_count = len(db.scalars(count_statement).all())
    rows = db.execute(
        statement.offset(offset).limit(limit)
    ).all()

    results = []

    for run, source in rows:
        severity, category, failure_stage = classify_processing_run(
            run.status,
            run.error_message,
        )

        duration_seconds = None

        if (
            run.completed_at is not None
            and run.completed_at >= run.started_at
        ):
            duration_seconds = round(
                (
                    run.completed_at - run.started_at
                ).total_seconds(),
                2,
            )

        results.append(
            ProcessingDiagnosticResponse(
                run_id=run.run_id,
                source_id=run.source_id,
                source_name=source.name,
                source_type=source.source_type,
                source_authorized_for_use=source.authorized_for_use,
                status=run.status,
                severity=severity,
                category=category,
                failure_stage=failure_stage,
                error_message=run.error_message,
                started_at=run.started_at,
                failed_at=(
                    run.completed_at
                    if run.status == "failed"
                    else None
                ),
                duration_seconds=duration_seconds,
                total_lines=run.total_lines,
                parsed_count=run.parsed_count,
                imported_count=run.imported_count,
                rejected_count=run.rejected_count,
                skipped_duplicate_count=run.skipped_duplicate_count,
                observations_examined=run.observations_examined,
                entities_created=run.entities_created,
                existing_entities_matched=(
                    run.existing_entities_matched
                ),
                associations_created=run.associations_created,
            )
        )

    return ProcessingDiagnosticsListResponse(
        results=results,
        result_count=result_count,
        limit=limit,
        offset=offset,
    )