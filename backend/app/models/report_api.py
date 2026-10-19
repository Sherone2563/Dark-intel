from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.entity_api import EntityResponse
from app.models.investigation_api import EntityInvestigationResponse
from app.models.timeline_api import EntityTimelineResponse


class IntelligenceReportMetadata(BaseModel):
    """Metadata describing one generated intelligence report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: UUID
    report_version: str = "1.0"
    generated_at: datetime
    report_type: str = "entity_investigation"


class IntelligenceReportSummary(BaseModel):
    """Counts and high-level findings derived from stored records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relationship_count: int = Field(ge=0)
    evidence_record_count: int = Field(ge=0)
    timeline_event_count: int = Field(ge=0)
    distinct_source_count: int = Field(ge=0)
    supporting_evidence_count: int = Field(ge=0)
    contradicting_evidence_count: int = Field(ge=0)
    neutral_evidence_count: int = Field(ge=0)


class IntelligenceReportResponse(BaseModel):
    """Structured, evidence-backed report for an investigated entity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metadata: IntelligenceReportMetadata
    subject: EntityResponse
    summary: IntelligenceReportSummary
    investigation: EntityInvestigationResponse
    timeline: EntityTimelineResponse
    methodology: list[str]
    limitations: list[str]