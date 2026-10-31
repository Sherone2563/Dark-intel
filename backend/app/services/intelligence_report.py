from datetime import UTC, datetime
from uuid import uuid4

from app.models.enums import EvidencePolarity
from app.models.investigation_api import EntityInvestigationResponse
from app.models.report_api import (
    IntelligenceReportMetadata,
    IntelligenceReportResponse,
    IntelligenceReportSummary,
)
from app.models.timeline_api import EntityTimelineResponse


METHODOLOGY = [
    (
        "Relationship scores use a provisional observation-balanced "
        "evidence method based on supporting and contradicting evidence."
    ),
    (
        "Each informative observation contributes at most one vote: "
        "supporting evidence contributes 1, contradicting evidence "
        "contributes 0, and both polarities in one observation contribute "
        "0.5. Neutral evidence does not affect the score."
    ),
    (
        "A relationship score is not a probability of real-world identity "
        "or attribution."
    ),
    (
        "Only very_reliable, usually_reliable, and fairly_reliable sources "
        "qualify toward independent corroboration."
    ),
    (
        "At least two distinct qualifying sources are required for a "
        "confidence band. Multiple observations from one source count "
        "as one source."
    ),
    (
        "Source reliability determines corroboration eligibility but does "
        "not change the numeric evidence-balance score."
    ),
]

LIMITATIONS = [
    (
        "Findings are analytical assessments of recorded evidence, "
        "not proof of a person's real-world identity."
    ),
    (
        "The report reflects the records available when it is generated. "
        "It is not a permanently stored or digitally signed report."
    ),
    (
        "Timeline entries represent evidence records and may refer to "
        "the same underlying observation or event."
    ),
    (
        "Distinct sources do not automatically guarantee independent "
        "underlying information or corroboration."
    ),
    (
        "Source reliability classifications and corroboration thresholds "
        "are provisional policy choices and have not been scientifically "
        "validated as attribution probabilities."
    ),
    (
        "Collection coverage, source bias, evidence quality, and other "
        "contextual factors may affect the interpretation of findings."
    ),
]


def generate_intelligence_report(
    investigation: EntityInvestigationResponse,
    timeline: EntityTimelineResponse,
) -> IntelligenceReportResponse:
    """Build a read-only intelligence report from existing API results."""

    evidence_records = [
        record
        for relationship in investigation.relationships
        for record in relationship.evidence_records
    ]

    source_ids = {
        record.source.source_id
        for record in evidence_records
    }

    supporting_count = sum(
        record.evidence.polarity == EvidencePolarity.SUPPORTS
        for record in evidence_records
    )
    contradicting_count = sum(
        record.evidence.polarity == EvidencePolarity.CONTRADICTS
        for record in evidence_records
    )
    neutral_count = sum(
        record.evidence.polarity == EvidencePolarity.NEUTRAL
        for record in evidence_records
    )

    summary = IntelligenceReportSummary(
        relationship_count=investigation.relationship_count,
        evidence_record_count=len(evidence_records),
        timeline_event_count=timeline.event_count,
        distinct_source_count=len(source_ids),
        supporting_evidence_count=supporting_count,
        contradicting_evidence_count=contradicting_count,
        neutral_evidence_count=neutral_count,
    )

    return IntelligenceReportResponse(
        metadata=IntelligenceReportMetadata(
            report_id=uuid4(),
            report_version="1.0",
            generated_at=datetime.now(UTC),
            report_type="entity_investigation",
        ),
        subject=investigation.entity,
        summary=summary,
        investigation=investigation,
        timeline=timeline,
        methodology=METHODOLOGY,
        limitations=LIMITATIONS,
    )