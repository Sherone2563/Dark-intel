from collections import defaultdict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EvidencePolarity
from app.models.evidence import EvidenceRecord


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
    methodology: str = (
        "Provisional observation-balanced evidence score; not a probability "
        "of real-world identity or attribution. Each informative observation "
        "contributes at most one vote."
    )


def calculate_linkage_score(
    relationship_id: UUID,
    evidence: list[EvidenceRecord],
) -> LinkageScore:
    """Calculate an explainable score while preventing duplicate observations
    from receiving extra weight.
    """

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
        )

    # Collect polarity per observation so repeated evidence records
    # cannot give that observation additional votes.
    observation_polarities: dict[UUID, set[EvidencePolarity]] = defaultdict(set)

    for item in relevant:
        if item.polarity in (
            EvidencePolarity.SUPPORTS,
            EvidencePolarity.CONTRADICTS,
        ):
            observation_polarities[item.observation_id].add(item.polarity)

    observation_votes: list[float] = []

    for polarities in observation_polarities.values():
        has_support = EvidencePolarity.SUPPORTS in polarities
        has_contradiction = EvidencePolarity.CONTRADICTS in polarities

        if has_support and has_contradiction:
            observation_votes.append(0.5)
        elif has_support:
            observation_votes.append(1.0)
        else:
            observation_votes.append(0.0)

    informative_observation_count = len(observation_votes)

    if informative_observation_count == 0:
        score = None
        band = "insufficient_evidence"
    else:
        score = round(
            100 * sum(observation_votes) / informative_observation_count,
            2,
        )

        # One observation can describe a balance, but cannot establish
        # sufficient independent evidence for a confidence band.
        if informative_observation_count < 2:
            band = "insufficient_evidence"
        elif score < 40:
            band = "weak"
        elif score < 60:
            band = "possible"
        elif score < 80:
            band = "strong"
        else:
            band = "high"

    return LinkageScore(
        relationship_id=relationship_id,
        score=score,
        confidence_band=band,
        supporting_count=supporting,
        contradicting_count=contradicting,
        neutral_count=neutral,
        evidence_ids=tuple(item.evidence_id for item in relevant),
    )
