from collections import defaultdict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EvidencePolarity, SourceReliability
from app.models.evidence import EvidenceRecord


QUALIFYING_RELIABILITIES = {
    SourceReliability.VERY_RELIABLE.value,
    SourceReliability.USUALLY_RELIABLE.value,
    SourceReliability.FAIRLY_RELIABLE.value,
}


class ObservationSourceContext(BaseModel):
    """Source metadata associated with one observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: UUID
    reliability: str = SourceReliability.UNKNOWN.value


class LinkageScore(BaseModel):
    """Explainable, provisional score for a relationship claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relationship_id: UUID
    score: float | None = Field(default=None, ge=0, le=100)
    confidence_band: str
    supporting_count: int = Field(ge=0)
    contradicting_count: int = Field(ge=0)
    neutral_count: int = Field(ge=0)
    evidence_ids: tuple[UUID, ...]

    qualifying_source_count: int = Field(default=0, ge=0)
    confidence_reason: str = (
        "Insufficient source metadata or independent corroboration."
    )

    methodology: str = (
        "Provisional observation-balanced evidence score; not a probability "
        "of real-world identity or attribution. Each informative observation "
        "contributes at most one vote. A confidence band requires at least "
        "two distinct qualifying sources."
    )


def calculate_linkage_score(
    relationship_id: UUID,
    evidence: list[EvidenceRecord],
    observation_sources: dict[UUID, ObservationSourceContext] | None = None,
) -> LinkageScore:
    """Calculate evidence balance and source-aware corroboration."""

    relevant = [
        item
        for item in evidence
        if item.relationship_id == relationship_id
    ]

    supporting = sum(
        item.polarity == EvidencePolarity.SUPPORTS
        for item in relevant
    )
    contradicting = sum(
        item.polarity == EvidencePolarity.CONTRADICTS
        for item in relevant
    )
    neutral = sum(
        item.polarity == EvidencePolarity.NEUTRAL
        for item in relevant
    )

    if not relevant:
        return LinkageScore(
            relationship_id=relationship_id,
            score=None,
            confidence_band="insufficient_evidence",
            supporting_count=0,
            contradicting_count=0,
            neutral_count=0,
            evidence_ids=(),
            confidence_reason="No evidence is available for this relationship.",
        )

    # Group polarity by observation to prevent duplicate evidence
    # records from giving an observation additional voting weight.
    observation_polarities: dict[UUID, set[EvidencePolarity]] = defaultdict(set)

    for item in relevant:
        if item.polarity in (
            EvidencePolarity.SUPPORTS,
            EvidencePolarity.CONTRADICTS,
        ):
            observation_polarities[item.observation_id].add(item.polarity)

    observation_votes: list[tuple[UUID, float]] = []

    for observation_id, polarities in observation_polarities.items():
        has_support = EvidencePolarity.SUPPORTS in polarities
        has_contradiction = EvidencePolarity.CONTRADICTS in polarities

        if has_support and has_contradiction:
            vote = 0.5
        elif has_support:
            vote = 1.0
        else:
            vote = 0.0

        observation_votes.append((observation_id, vote))

    informative_observation_count = len(observation_votes)

    if informative_observation_count == 0:
        score = None
    else:
        score = round(
            100
            * sum(vote for _, vote in observation_votes)
            / informative_observation_count,
            2,
        )

    # Count distinct sources only among informative observations.
    observation_sources = observation_sources or {}

    distinct_source_ids = set()
    qualifying_source_ids = set()

    for observation_id, _ in observation_votes:
        context = observation_sources.get(observation_id)

        if context is None:
            continue

        distinct_source_ids.add(context.source_id)

        if context.reliability in QUALIFYING_RELIABILITIES:
            qualifying_source_ids.add(context.source_id)

    qualifying_source_count = len(qualifying_source_ids)

    if score is None:
        band = "insufficient_evidence"
        reason = "No informative supporting or contradicting observations exist."

    elif qualifying_source_count < 2:
        band = "insufficient_evidence"
        reason = (
            "At least two distinct sources with qualifying reliability "
            "are required. Current qualifying source count: "
            f"{qualifying_source_count}."
        )

    elif score < 40:
        band = "weak"
        reason = "Independent source requirement met; evidence balance is below 40."

    elif score < 60:
        band = "possible"
        reason = "Independent source requirement met; evidence balance is possible."

    elif score < 80:
        band = "strong"
        reason = "Independent source requirement met; evidence balance is strong."

    else:
        band = "high"
        reason = (
            "Independent source requirement met; evidence balance is high. "
            "This is not proof of real-world identity or attribution."
        )

    return LinkageScore(
        relationship_id=relationship_id,
        score=score,
        confidence_band=band,
        supporting_count=supporting,
        contradicting_count=contradicting,
        neutral_count=neutral,
        evidence_ids=tuple(item.evidence_id for item in relevant),
        qualifying_source_count=qualifying_source_count,
        confidence_reason=reason,
    )