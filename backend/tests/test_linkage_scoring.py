from uuid import uuid4

import pytest

from app.models.enums import EvidencePolarity, SourceReliability
from app.models.evidence import EvidenceRecord
from app.services.linkage_scoring import (
    ObservationSourceContext,
    calculate_linkage_score,
)


@pytest.fixture
def relationship_id():
    return uuid4()


def make_evidence(
    relationship_id,
    polarity,
    observation_id=None,
):
    return EvidenceRecord(
        relationship_id=relationship_id,
        observation_id=observation_id or uuid4(),
        polarity=polarity,
        evidence_description=f"Synthetic {polarity.value} test evidence.",
    )


def make_source_context(
    evidence,
    reliability=SourceReliability.VERY_RELIABLE.value,
    shared_source_id=None,
):
    """Create source context for each distinct observation."""

    contexts = {}

    for item in evidence:
        if item.observation_id not in contexts:
            contexts[item.observation_id] = ObservationSourceContext(
                source_id=shared_source_id or uuid4(),
                reliability=reliability,
            )

    return contexts


def calculate(relationship_id, evidence, source_contexts=None):
    return calculate_linkage_score(
        relationship_id,
        evidence,
        observation_sources=(
            source_contexts
            if source_contexts is not None
            else make_source_context(evidence)
        ),
    )


def test_empty_evidence_returns_insufficient_evidence(relationship_id):
    result = calculate(relationship_id, [])

    assert result.score is None
    assert result.confidence_band == "insufficient_evidence"
    assert result.evidence_ids == ()


def test_supporting_evidence_from_two_sources_returns_high_band(
    relationship_id,
):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
    ]

    result = calculate(relationship_id, evidence)

    assert result.score == 100.0
    assert result.confidence_band == "high"
    assert result.supporting_count == 2
    assert result.qualifying_source_count == 2


def test_one_supporting_observation_is_insufficient(relationship_id):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
    ]

    result = calculate(relationship_id, evidence)

    assert result.score == 100.0
    assert result.confidence_band == "insufficient_evidence"
    assert result.qualifying_source_count == 1


def test_contradictory_evidence_only_returns_zero(relationship_id):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.CONTRADICTS),
    ]

    result = calculate(relationship_id, evidence)

    assert result.score == 0.0
    assert result.confidence_band == "insufficient_evidence"
    assert result.contradicting_count == 1


def test_balanced_evidence_returns_possible_band(relationship_id):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
        make_evidence(relationship_id, EvidencePolarity.CONTRADICTS),
    ]

    result = calculate(relationship_id, evidence)

    assert result.score == 50.0
    assert result.confidence_band == "possible"


def test_neutral_evidence_does_not_change_score(relationship_id):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
        make_evidence(relationship_id, EvidencePolarity.NEUTRAL),
    ]

    result = calculate(relationship_id, evidence)

    assert result.score == 100.0
    assert result.neutral_count == 1
    assert len(result.evidence_ids) == 2
    assert result.confidence_band == "insufficient_evidence"


def test_neutral_evidence_only_is_insufficient(relationship_id):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.NEUTRAL),
    ]

    result = calculate(relationship_id, evidence)

    assert result.score is None
    assert result.confidence_band == "insufficient_evidence"


def test_unrelated_evidence_is_excluded(relationship_id):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
        make_evidence(uuid4(), EvidencePolarity.CONTRADICTS),
    ]

    result = calculate(relationship_id, evidence)

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

    result = calculate(relationship_id, evidence)

    assert result.score == expected_score
    assert result.confidence_band == expected_band


def test_repeated_evidence_for_same_observation_does_not_strengthen_score(
    relationship_id,
):
    observation_id = uuid4()

    evidence = [
        make_evidence(
            relationship_id,
            EvidencePolarity.SUPPORTS,
            observation_id,
        ),
        make_evidence(
            relationship_id,
            EvidencePolarity.SUPPORTS,
            observation_id,
        ),
    ]

    result = calculate(relationship_id, evidence)

    assert result.score == 100.0
    assert result.confidence_band == "insufficient_evidence"
    assert result.qualifying_source_count == 1


def test_two_polarities_for_one_observation_are_not_independent_evidence(
    relationship_id,
):
    observation_id = uuid4()

    evidence = [
        make_evidence(
            relationship_id,
            EvidencePolarity.SUPPORTS,
            observation_id,
        ),
        make_evidence(
            relationship_id,
            EvidencePolarity.CONTRADICTS,
            observation_id,
        ),
    ]

    result = calculate(relationship_id, evidence)

    assert result.score == 50.0
    assert result.confidence_band == "insufficient_evidence"


def test_two_observations_from_same_source_are_not_independent(
    relationship_id,
):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
    ]

    shared_source_id = uuid4()

    contexts = make_source_context(
        evidence,
        shared_source_id=shared_source_id,
    )

    result = calculate(relationship_id, evidence, contexts)

    assert result.score == 100.0
    assert result.qualifying_source_count == 1
    assert result.confidence_band == "insufficient_evidence"


@pytest.mark.parametrize(
    "reliability",
    [
        SourceReliability.NOT_USUALLY_RELIABLE.value,
        SourceReliability.UNRELIABLE.value,
        SourceReliability.UNKNOWN.value,
    ],
)
def test_nonqualifying_sources_do_not_establish_confidence(
    relationship_id,
    reliability,
):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
    ]

    contexts = make_source_context(evidence, reliability)

    result = calculate(relationship_id, evidence, contexts)

    assert result.score == 100.0
    assert result.qualifying_source_count == 0
    assert result.confidence_band == "insufficient_evidence"


def test_two_qualifying_reliability_levels_are_accepted(relationship_id):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
    ]

    contexts = {
        evidence[0].observation_id: ObservationSourceContext(
            source_id=uuid4(),
            reliability=SourceReliability.VERY_RELIABLE.value,
        ),
        evidence[1].observation_id: ObservationSourceContext(
            source_id=uuid4(),
            reliability=SourceReliability.FAIRLY_RELIABLE.value,
        ),
    }

    result = calculate(relationship_id, evidence, contexts)

    assert result.qualifying_source_count == 2
    assert result.confidence_band == "high"


def test_unknown_source_context_does_not_count_as_qualifying(
    relationship_id,
):
    evidence = [
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
        make_evidence(relationship_id, EvidencePolarity.SUPPORTS),
    ]

    contexts = {
        evidence[0].observation_id: ObservationSourceContext(
            source_id=uuid4(),
            reliability=SourceReliability.VERY_RELIABLE.value,
        ),
    }

    result = calculate(relationship_id, evidence, contexts)

    assert result.qualifying_source_count == 1
    assert result.confidence_band == "insufficient_evidence"