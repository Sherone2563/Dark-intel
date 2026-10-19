
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import EvidencePolarity
from app.models.evidence import EvidenceRecord


def make_evidence(**overrides) -> EvidenceRecord:
    values = {
        "relationship_id": uuid4(),
        "observation_id": uuid4(),
        "polarity": EvidencePolarity.SUPPORTS,
        "evidence_description": (
            "Both records contain the same research-observed identifier."
        ),
    }
    values.update(overrides)
    return EvidenceRecord(**values)


def test_evidence_has_uuid_and_utc_creation_time() -> None:
    evidence = make_evidence()

    assert evidence.evidence_id is not None
    assert evidence.created_at.tzinfo is not None
    assert evidence.created_at.utcoffset().total_seconds() == 0


@pytest.mark.parametrize(
    "polarity",
    [
        EvidencePolarity.SUPPORTS,
        EvidencePolarity.CONTRADICTS,
        EvidencePolarity.NEUTRAL,
    ],
)
def test_evidence_accepts_each_polarity(
    polarity: EvidencePolarity,
) -> None:
    evidence = make_evidence(polarity=polarity)

    assert evidence.polarity == polarity


def test_evidence_rejects_blank_description() -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        make_evidence(evidence_description="   ")


def test_evidence_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        make_evidence(observed_at=datetime(2025, 1, 1))


def test_evidence_accepts_timezone_aware_timestamp() -> None:
    observed_at = datetime(2025, 1, 1, tzinfo=UTC)

    evidence = make_evidence(observed_at=observed_at)

    assert evidence.observed_at == observed_at


def test_evidence_is_immutable() -> None:
    evidence = make_evidence()

    with pytest.raises(ValidationError):
        evidence.polarity = EvidencePolarity.CONTRADICTS


def test_evidence_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        make_evidence(unexpected_field="not allowed")
