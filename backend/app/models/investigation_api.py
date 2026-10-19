
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.entity_api import EntityResponse
from app.models.evidence_api import EvidenceResponse
from app.models.relationship_api import RelationshipResponse


class InvestigationSource(BaseModel):
    """Source metadata attached to an evidence record."""

    model_config = ConfigDict(from_attributes=True)

    source_id: UUID
    name: str
    source_type: str
    reference: str | None
    reliability: str
    authorized_for_use: bool
    authorization_note: str | None


class InvestigationObservation(BaseModel):
    """Observation provenance associated with evidence."""

    model_config = ConfigDict(from_attributes=True)

    observation_id: UUID
    source_id: UUID
    collected_at: datetime
    observed_at: datetime | None
    payload: dict
    content_sha256: str
    status: str
    processing_version: str
    created_at: datetime


class InvestigationEvidence(BaseModel):
    """Full evidence record with its observation and source."""

    evidence: EvidenceResponse
    observation: InvestigationObservation
    source: InvestigationSource


class InvestigationAnalysis(BaseModel):
    """Linkage assessment and source-quality diagnostics."""

    relationship_id: UUID
    score: float | None
    confidence_band: str
    supporting_count: int
    contradicting_count: int
    neutral_count: int
    evidence_ids: list[UUID]
    methodology: str
    distinct_source_count: int
    evidence_items_sharing_sources: int
    source_reliability_evidence_counts: dict[str, int]
    source_quality_note: str
    distinct_observation_count: int


class InvestigationRelationship(BaseModel):
    """One connected entity and the evidence for its relationship."""

    relationship: RelationshipResponse
    connected_entity: EntityResponse
    analysis: InvestigationAnalysis
    evidence_records: list[InvestigationEvidence]


class EntityInvestigationResponse(BaseModel):
    """Read-only investigation view for one entity."""

    entity: EntityResponse
    relationships: list[InvestigationRelationship]
    relationship_count: int
    evidence_record_count: int
