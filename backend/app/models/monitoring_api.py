from uuid import UUID
from datetime import datetime


from pydantic import BaseModel

class ProcessingDiagnosticResponse(BaseModel):
    run_id: UUID
    source_id: UUID
    source_name: str
    source_type: str
    source_authorized_for_use: bool

    status: str
    severity: str
    category: str
    failure_stage: str | None

    error_message: str | None

    started_at: datetime
    failed_at: datetime | None
    duration_seconds: float | None

    total_lines: int
    parsed_count: int
    imported_count: int
    rejected_count: int
    skipped_duplicate_count: int

    observations_examined: int
    entities_created: int
    existing_entities_matched: int
    associations_created: int


class ProcessingDiagnosticsListResponse(BaseModel):
    results: list[ProcessingDiagnosticResponse]
    result_count: int
    limit: int
    offset: int

class MonitoringSummaryResponse(BaseModel):
    reporting_period_days: int
    generated_at: datetime

    total_runs: int
    successful_runs: int
    runs_with_rejections: int
    failed_runs: int
    active_runs: int

    total_lines: int
    parsed_records: int
    imported_records: int
    rejected_records: int
    duplicate_records: int

    observations_examined: int
    entities_created: int
    existing_entities_matched: int
    associations_created: int

    average_processing_time_seconds: float | None