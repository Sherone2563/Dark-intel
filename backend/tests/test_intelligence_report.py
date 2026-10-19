from datetime import UTC, datetime
from uuid import uuid4

from app.models.entity_api import EntityResponse
from app.models.enums import EvidencePolarity
from app.models.investigation_api import (
    EntityInvestigationResponse,
    InvestigationAnalysis,
    InvestigationEvidence,
    InvestigationObservation,
    InvestigationRelationship,
    InvestigationSource,
)
from app.models.report_api import (
    IntelligenceReportMetadata,
    IntelligenceReportSummary,
)
from app.models.timeline_api import (
    EntityTimelineResponse,
    TimelineEvent,
)
from app.models.relationship_api import RelationshipResponse
from app.models.evidence_api import EvidenceResponse
from app.services.intelligence_report import generate_intelligence_report


def make_empty_results():
    entity_id = uuid4()

    entity = EntityResponse(
        entity_id=entity_id,
        entity_type="handle",
        canonical_value="report_test_actor",
        display_value="Report Test Actor",
        first_observed_at=None,
        last_observed_at=None,
        created_at=datetime.now(UTC),
    )

    investigation = EntityInvestigationResponse(
        entity=entity,
        relationships=[],
        relationship_count=0,
        evidence_record_count=0,
    )

    timeline = EntityTimelineResponse(
        entity=entity,
        events=[],
        event_count=0,
    )

    return investigation, timeline


def test_empty_investigation_generates_empty_report():
    investigation, timeline = make_empty_results()

    report = generate_intelligence_report(investigation, timeline)

    assert report.subject.entity_id == investigation.entity.entity_id
    assert report.summary.relationship_count == 0
    assert report.summary.evidence_record_count == 0
    assert report.summary.timeline_event_count == 0
    assert report.summary.distinct_source_count == 0
    assert report.summary.supporting_evidence_count == 0
    assert report.summary.contradicting_evidence_count == 0
    assert report.summary.neutral_evidence_count == 0
    assert report.metadata.report_type == "entity_investigation"
    assert report.metadata.generated_at.tzinfo is not None
    assert report.methodology
    assert report.limitations


def test_report_uses_a_new_id_for_each_generation():
    investigation, timeline = make_empty_results()

    first = generate_intelligence_report(investigation, timeline)
    second = generate_intelligence_report(investigation, timeline)

    assert first.metadata.report_id != second.metadata.report_id


def test_report_schema_rejects_negative_summary_counts():
    try:
        IntelligenceReportSummary(
            relationship_count=-1,
            evidence_record_count=0,
            timeline_event_count=0,
            distinct_source_count=0,
            supporting_evidence_count=0,
            contradicting_evidence_count=0,
            neutral_evidence_count=0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Negative counts should be rejected")