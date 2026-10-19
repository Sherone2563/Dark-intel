
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.entity_api import EntityResponse
from app.models.enums import EvidencePolarity, RelationshipType
from app.models.investigation_api import InvestigationSource


class TimelineEvent(BaseModel):
    """One evidence-backed event in an entity's activity timeline."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    event_timestamp: datetime
    timestamp_basis: str
    relationship_id: UUID
    relationship_type: RelationshipType
    relationship_description: str | None
    connected_entity: EntityResponse
    evidence_id: UUID
    evidence_polarity: EvidencePolarity
    evidence_description: str
    evidence_limitations: str | None
    observation_id: UUID
    observation_observed_at: datetime | None
    observation_collected_at: datetime
    content_sha256: str
    source: InvestigationSource


class EntityTimelineResponse(BaseModel):
    """Chronological evidence-backed activity for one entity."""

    entity: EntityResponse
    events: list[TimelineEvent]
    event_count: int
