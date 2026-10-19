
from uuid import uuid4

import pytest

from app.models.enums import (
    EvidencePolarity,
    RelationshipType,
    SourceType,
)
from app.models.evidence import EvidenceRecord
from app.models.observations import (
    ObservationRecord,
    calculate_payload_sha256,
)
from app.models.relationships import RelationshipRecord
from app.models.sources import SourceRecord
from app.services.evidence_service import (
    EvidenceService,
    EvidenceServiceError,
)
from app.services.provenance_service import ProvenanceService


def make_test_context():
    provenance = ProvenanceService()
    source = SourceRecord(
        name="Synthetic research fixture",
        source_type=SourceType.SYNTHETIC,
        authorized_for_use=True,
    )
    provenance.register_source(source)

    payload = {"handle": "shadow_x"}
    observation = ObservationRecord(
        source_id=source.source_id,
        payload=payload,
        content_sha256=calculate_payload_sha256(payload),
    )
    provenance.record_observation(observation)

    relationship = RelationshipRecord(
        source_entity_id=uuid4(),
        target_entity_id=uuid4(),
        relationship_type=RelationshipType.RELATED_TO,
        description="Synthetic test relationship",
    )

    service = EvidenceService(provenance)
    service.register_relationship(relationship)

    return service, relationship, observation


def make_evidence(relationship_id, observation_id):
    return EvidenceRecord(
        relationship_id=relationship_id,
        observation_id=observation_id,
        polarity=EvidencePolarity.SUPPORTS,
        evidence_description="Synthetic observation supports the claim.",
    )


def test_evidence_is_recorded_for_known_records() -> None:
    service, relationship, observation = make_test_context()
    evidence = make_evidence(
        relationship.relationship_id,
        observation.observation_id,
    )

    recorded = service.record_evidence(evidence)

    assert recorded == evidence
    assert service.get_evidence(evidence.evidence_id) == evidence


def test_unknown_relationship_is_rejected() -> None:
    service, _, observation = make_test_context()
    evidence = make_evidence(uuid4(), observation.observation_id)

    with pytest.raises(EvidenceServiceError, match="Unknown relationship"):
        service.record_evidence(evidence)


def test_unknown_observation_is_rejected() -> None:
    service, relationship, _ = make_test_context()
    evidence = make_evidence(relationship.relationship_id, uuid4())

    with pytest.raises(EvidenceServiceError, match="Unknown observation"):
        service.record_evidence(evidence)


def test_duplicate_relationship_registration_is_rejected() -> None:
    service, relationship, _ = make_test_context()

    with pytest.raises(
        EvidenceServiceError,
        match="Relationship already registered",
    ):
        service.register_relationship(relationship)


def test_duplicate_evidence_is_rejected() -> None:
    service, relationship, observation = make_test_context()
    evidence = make_evidence(
        relationship.relationship_id,
        observation.observation_id,
    )
    service.record_evidence(evidence)

    with pytest.raises(EvidenceServiceError, match="Evidence already recorded"):
        service.record_evidence(evidence)


def test_evidence_can_be_listed() -> None:
    service, relationship, observation = make_test_context()
    evidence = make_evidence(
        relationship.relationship_id,
        observation.observation_id,
    )
    service.record_evidence(evidence)

    assert service.list_evidence() == (evidence,)
