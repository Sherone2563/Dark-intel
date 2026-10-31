from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import ProcessingRunStatus


class ProcessingRunResponse(BaseModel):
    """Read-only representation of a persisted ingestion processing run."""

    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    source_id: UUID
    source_name: str
    source_type: str
    source_reliability: str
    source_authorized_for_use: bool

    status: ProcessingRunStatus

    started_at: datetime
    completed_at: datetime | None

    total_lines: int
    parsed_count: int
    imported_count: int
    skipped_duplicate_count: int
    rejected_count: int

    observations_examined: int
    entities_created: int
    existing_entities_matched: int
    associations_created: int

    handles_processed: int
    pgp_keys_processed: int

    processing_version: str
    error_message: str | None


class ProcessingRunListResponse(BaseModel):
    """Paginated processing-run history."""

    results: list[ProcessingRunResponse]
    result_count: int
    limit: int
    offset: int