from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.db_models import ProcessingRunModel
from app.models.monitoring_api import MonitoringSummaryResponse


def generate_monitoring_summary(
    db: Session,
    days: int = 30,
) -> MonitoringSummaryResponse:
    """Aggregate processing-run metrics over a reporting period."""

    generated_at = datetime.now(timezone.utc)
    period_start = generated_at - timedelta(days=days)

    period_filter = ProcessingRunModel.started_at >= period_start

    metrics = db.execute(
        select(
            func.count(ProcessingRunModel.run_id).label("total_runs"),

            func.sum(
                case(
                    (ProcessingRunModel.status == "completed", 1),
                    else_=0,
                )
            ).label("successful_runs"),

            func.sum(
                case(
                    (
                        ProcessingRunModel.status
                        == "completed_with_rejections",
                        1,
                    ),
                    else_=0,
                )
            ).label("runs_with_rejections"),

            func.sum(
                case(
                    (ProcessingRunModel.status == "failed", 1),
                    else_=0,
                )
            ).label("failed_runs"),

            func.sum(
                case(
                    (
                        ProcessingRunModel.status.in_(
                            ["started", "importing", "extracting"]
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("active_runs"),

            func.coalesce(
                func.sum(ProcessingRunModel.total_lines), 0
            ).label("total_lines"),

            func.coalesce(
                func.sum(ProcessingRunModel.parsed_count), 0
            ).label("parsed_records"),

            func.coalesce(
                func.sum(ProcessingRunModel.imported_count), 0
            ).label("imported_records"),

            func.coalesce(
                func.sum(ProcessingRunModel.rejected_count), 0
            ).label("rejected_records"),

            func.coalesce(
                func.sum(ProcessingRunModel.skipped_duplicate_count), 0
            ).label("duplicate_records"),

            func.coalesce(
                func.sum(ProcessingRunModel.observations_examined), 0
            ).label("observations_examined"),

            func.coalesce(
                func.sum(ProcessingRunModel.entities_created), 0
            ).label("entities_created"),

            func.coalesce(
                func.sum(ProcessingRunModel.existing_entities_matched), 0
            ).label("existing_entities_matched"),

            func.coalesce(
                func.sum(ProcessingRunModel.associations_created), 0
            ).label("associations_created"),
        ).where(period_filter)
    ).one()

    average_duration = db.scalar(
        select(
            func.avg(
                func.extract(
                    "epoch",
                    ProcessingRunModel.completed_at
                    - ProcessingRunModel.started_at,
                )
            )
        ).where(
            period_filter,
            ProcessingRunModel.status.in_(
                ["completed", "completed_with_rejections", "failed"]
            ),
            ProcessingRunModel.completed_at.is_not(None),
            ProcessingRunModel.completed_at
            >= ProcessingRunModel.started_at,
        )
    )

    return MonitoringSummaryResponse(
        reporting_period_days=days,
        generated_at=generated_at,
        total_runs=metrics.total_runs or 0,
        successful_runs=metrics.successful_runs or 0,
        runs_with_rejections=metrics.runs_with_rejections or 0,
        failed_runs=metrics.failed_runs or 0,
        active_runs=metrics.active_runs or 0,
        total_lines=metrics.total_lines,
        parsed_records=metrics.parsed_records,
        imported_records=metrics.imported_records,
        rejected_records=metrics.rejected_records,
        duplicate_records=metrics.duplicate_records,
        observations_examined=metrics.observations_examined,
        entities_created=metrics.entities_created,
        existing_entities_matched=metrics.existing_entities_matched,
        associations_created=metrics.associations_created,
        average_processing_time_seconds=(
            round(float(average_duration), 2)
            if average_duration is not None
            else None
        ),
    )