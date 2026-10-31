from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.entity_api import EntityResponse


class EntityProvenanceRecord(BaseModel):
    """Extraction association with its originating observation and source."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    association_id: UUID
    association_type: str
    field_name: str
    normalization_method: str
    association_created_at: datetime

    observation_id: UUID
    collected_at: datetime
    observed_at: datetime | None
    content_sha256: str
    processing_version: str

    source_id: UUID
    source_name: str
    source_type: str
    authorized_for_use: bool


class EntityProvenanceResponse(BaseModel):
    """Read-only extraction provenance for one entity."""

    model_config = ConfigDict(extra="forbid")

    entity: EntityResponse
    records: list[EntityProvenanceRecord]
    record_count: int