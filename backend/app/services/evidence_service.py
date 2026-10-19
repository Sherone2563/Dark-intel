
from uuid import UUID

from app.models.evidence import EvidenceRecord
from app.models.relationships import RelationshipRecord
from app.services.provenance_service import (
    ProvenanceService,
)


class EvidenceServiceError(ValueError):
    """Raised when evidence fails cross-record validation."""


class EvidenceService:
    """Validates and stores evidence against known records."""

    def __init__(self, provenance_service: ProvenanceService) -> None:
        self._provenance_service = provenance_service
        self._relationships: dict[UUID, RelationshipRecord] = {}
        self._evidence: dict[UUID, EvidenceRecord] = {}

    def register_relationship(
        self, relationship: RelationshipRecord
    ) -> RelationshipRecord:
        relationship_id = relationship.relationship_id

        if relationship_id in self._relationships:
            raise EvidenceServiceError(
                f"Relationship already registered: {relationship_id}"
            )

        self._relationships[relationship_id] = relationship
        return relationship

    def record_evidence(
        self, evidence: EvidenceRecord
    ) -> EvidenceRecord:
        relationship = self._relationships.get(
            evidence.relationship_id
        )

        if relationship is None:
            raise EvidenceServiceError(
                f"Unknown relationship: {evidence.relationship_id}"
            )

        observation = self._provenance_service.get_observation(
            evidence.observation_id
        )

        if observation is None:
            raise EvidenceServiceError(
                f"Unknown observation: {evidence.observation_id}"
            )

        if evidence.evidence_id in self._evidence:
            raise EvidenceServiceError(
                f"Evidence already recorded: {evidence.evidence_id}"
            )

        self._evidence[evidence.evidence_id] = evidence
        return evidence

    def get_relationship(
        self, relationship_id: UUID
    ) -> RelationshipRecord | None:
        return self._relationships.get(relationship_id)

    def get_evidence(
        self, evidence_id: UUID
    ) -> EvidenceRecord | None:
        return self._evidence.get(evidence_id)

    def list_evidence(self) -> tuple[EvidenceRecord, ...]:
        return tuple(self._evidence.values())
