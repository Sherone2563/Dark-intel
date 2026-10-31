from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.entity_api import EntityResponse
from app.models.evidence_api import EvidenceResponse
from app.models.investigation_api import InvestigationAnalysis
from app.models.relationship_api import RelationshipResponse


class EntityGraphEdge(BaseModel):
    """A stored relationship with its evidence and analytical assessment."""

    model_config = ConfigDict(extra="forbid")

    relationship: RelationshipResponse
    evidence: list[EvidenceResponse]
    analysis: InvestigationAnalysis


class EntityGraphResponse(BaseModel):
    """Read-only graph of entities connected by stored relationships."""

    model_config = ConfigDict(extra="forbid")

    root_entity_id: UUID
    depth: int = Field(ge=1, le=3)
    nodes: list[EntityResponse]
    edges: list[EntityGraphEdge]
    node_count: int = Field(ge=1)
    edge_count: int = Field(ge=0)