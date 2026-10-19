
from uuid import uuid4

import pytest

from app.models.enums import EvidencePolarity
from app.models.evidence import EvidenceRecord
from app.services.linkage_scoring import calculate_linkage_score


@pytest.fixture
def relationship_id():
    return uuid4()


def make_evidence(relationship_id, polarity):
    return EvidenceRecord(
        relationship_id=relationship_id,
        observation_id=uuid4(),
        polarity=polarity,
        evidence_description=f"Synthetic {polarity.value} test evidence.",
    )


def test_empty_evidence_returns_insufficient_evidence(relationship_id):
    result = calculate_linkage_score(relationship_id, [])

    assert result.score is None
    assert result.confidence_band == "insufficient_evidence"
    assert result.evidence_ids == ()


def test_supporting_evidence_only_returns_high_band(relationship_id):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
    ]

    result = calculate_linkage_score(relationship_id, evidence)

    assert result.score == 100.0
    assert result.confidence_band == "high"
    assert result.supporting_count == 2
    assert result.contradicting_count == 0


def test_contradictory_evidence_only_returns_zero(relationship_id):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.CONTRADICTS),
    ]

    result = calculate_linkage_score(relationship_id, evidence)

    assert result.score == 0.0
    assert result.confidence_band == "insufficient_evidence"
    assert result.contradicting_count == 1


def test_balanced_evidence_returns_possible_band(relationship_id):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
        make_evidence(relationship_id, EvidencePolarity.CONTRADICTS),
    ]

    result = calculate_linkage_score(relationship_id, evidence)

    assert result.score == 50.0
    assert result.confidence_band == "possible"


def test_neutral_evidence_does_not_change_score(relationship_id):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
        make_evidence(relationship_id, EvidencePolarity.NEUTRAL),
    ]

    result = calculate_linkage_score(relationship_id, evidence)

    assert result.score == 100.0
    assert result.neutral_count == 1
    assert len(result.evidence_ids) == 2


def test_neutral_evidence_only_is_insufficient(relationship_id):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.NEUTRAL),
    ]

    result = calculate_linkage_score(relationship_id, evidence)

    assert result.score is None
    assert result.confidence_band == "insufficient_evidence"


def test_unrelated_evidence_is_excluded(relationship_id):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
        make_evidence(uuid4(), EvidencePolarity.CONTRADICTS),
    ]

    result = calculate_linkage_score(relationship_id, evidence)

    assert result.score == 100.0
    assert result.supporting_count == 1
    assert result.contradicting_count == 0
    assert len(result.evidence_ids) == 1


@pytest.mark.parametrize(
    ("supporting", "contradicting", "expected_score", "expected_band"),
    [
        (1, 4, 20.0, "weak"),
        (2, 3, 40.0, "possible"),
        (3, 2, 60.0, "strong"),
        (4, 1, 80.0, "high"),
    ],
)
def test_confidence_band_boundaries(
    relationship_id,
    supporting,
    contradicting,
    expected_score,
    expected_band,
):
    evidence = (
        [
            make_evidence(relationship_id, EvidencePolarity.SUPPORTS)
            for _ in range(supporting)
        ]
        + [
            make_evidence(relationship_id, EvidencePolarity.CONTRADICTS)
            for _ in range(contradicting)
        ]
    )

    result = calculate_linkage_score(relationship_id, evidence)

    assert result.score == expected_score
    assert result.confidence_band == expected_band

def test_repeated_evidence_for_same_observation_does_not_strengthen_score(
    relationship_id,
):
    observation_id = uuid4()
    evidence = [
        EvidenceRecord(
            relationship_id=relationship_id,
            observation_id=observation_id,
            polarity=EvidencePolarity.SUPPORTS,
            evidence_description="First interpretation of one observation.",
        ),
        EvidenceRecord(
            relationship_id=relationship_id,
            observation_id=observation_id,
            polarity=EvidencePolarity.SUPPORTS,
            evidence_description="Repeated interpretation of the same observation.",
        ),
    ]

    result = calculate_linkage_score(relationship_id, evidence)

    assert result.score == 100.0
    assert result.confidence_band == "insufficient_evidence"


def test_two_polarities_for_one_observation_are_not_independent_evidence(
    relationship_id,
):
    observation_id = uuid4()
    evidence = [
        EvidenceRecord(
            relationship_id=relationship_id,
            observation_id=observation_id,
            polarity=EvidencePolarity.SUPPORTS,
            evidence_description="Supporting interpretation.",
        ),
        EvidenceRecord(
            relationship_id=relationship_id,
            observation_id=observation_id,
            polarity=EvidencePolarity.CONTRADICTS,
            evidence_description="Contradictory interpretation of the same observation.",
        ),
    ]

    result = calculate_linkage_score(relationship_id, evidence)

    assert result.score == 50.0
    assert result.confidence_band == "insufficient_evidence"
