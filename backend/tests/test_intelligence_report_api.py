from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.db_models import (
    EntityModel,
    EvidenceModel,
    ObservationModel,
    RelationshipModel,
    SourceModel,
)

client = TestClient(app)


@pytest.fixture
def report_setup():
    entity_ids = []
    source_ids = []
    observation_ids = []
    relationship_ids = []
    evidence_ids = []

    def create_entity(value):
        response = client.post(
            "/entities",
            json={
                "entity_type": "handle",
                "canonical_value": value,
                "display_value": value,
            },
        )
        assert response.status_code == 201, response.text
        entity = response.json()
        entity_ids.append(UUID(entity["entity_id"]))
        return entity

    source_response = client.post(
        "/sources",
        json={
            "name": "Synthetic Report Test Source",
            "source_type": "synthetic",
            "reference": "synthetic://report-tests",
            "reliability": "unknown",
            "authorized_for_use": True,
            "authorization_note": "Synthetic data for automated testing.",
        },
    )
    assert source_response.status_code == 201, source_response.text
    source = source_response.json()
    source_ids.append(UUID(source["source_id"]))

    source_entity = create_entity("report_test_actor_a")
    target_entity = create_entity("report_test_actor_b")

    relationship_response = client.post(
        "/relationships",
        json={
            "source_entity_id": source_entity["entity_id"],
            "target_entity_id": target_entity["entity_id"],
            "relationship_type": "associated_with",
            "description": "Synthetic report test relationship.",
        },
    )
    assert relationship_response.status_code == 201, relationship_response.text
    relationship = relationship_response.json()
    relationship_ids.append(UUID(relationship["relationship_id"]))

    setup = {
        "entity_ids": entity_ids,
        "source_ids": source_ids,
        "observation_ids": observation_ids,
        "relationship_ids": relationship_ids,
        "evidence_ids": evidence_ids,
        "source": source,
        "source_entity": source_entity,
        "target_entity": target_entity,
        "relationship": relationship,
    }

    yield setup

    with SessionLocal() as db:
        if evidence_ids:
            db.execute(
                delete(EvidenceModel).where(
                    EvidenceModel.evidence_id.in_(evidence_ids)
                )
            )

        if relationship_ids:
            db.execute(
                delete(EvidenceModel).where(
                    EvidenceModel.relationship_id.in_(relationship_ids)
                )
            )
            db.execute(
                delete(RelationshipModel).where(
                    RelationshipModel.relationship_id.in_(relationship_ids)
                )
            )

        if observation_ids:
            db.execute(
                delete(EvidenceModel).where(
                    EvidenceModel.observation_id.in_(observation_ids)
                )
            )
            db.execute(
                delete(ObservationModel).where(
                    ObservationModel.observation_id.in_(observation_ids)
                )
            )

        if source_ids:
            db.execute(
                delete(SourceModel).where(
                    SourceModel.source_id.in_(source_ids)
                )
            )

        if entity_ids:
            db.execute(
                delete(EntityModel).where(
                    EntityModel.entity_id.in_(entity_ids)
                )
            )

        db.commit()


def add_observation(setup):
    response = client.post(
        "/observations",
        json={
            "source_id": setup["source"]["source_id"],
            "payload": {
                "synthetic_test": True,
                "handle": "report_test_actor_a",
            },
        },
    )
    assert response.status_code == 201, response.text

    observation = response.json()
    setup["observation_ids"].append(UUID(observation["observation_id"]))
    return observation


def add_evidence(setup, observation, polarity, description):
    response = client.post(
        "/evidence",
        json={
            "relationship_id": setup["relationship"]["relationship_id"],
            "observation_id": observation["observation_id"],
            "polarity": polarity,
            "evidence_description": description,
            "limitations": "Synthetic test evidence only.",
        },
    )
    assert response.status_code == 201, response.text

    evidence = response.json()
    setup["evidence_ids"].append(UUID(evidence["evidence_id"]))
    return evidence


def test_unknown_entity_returns_404():
    response = client.get(
        "/entities/00000000-0000-0000-0000-000000000099/report"
    )

    assert response.status_code == 404


def test_report_for_entity_without_relationships(report_setup):
    setup = report_setup

    entity = client.post(
        "/entities",
        json={
            "entity_type": "handle",
            "canonical_value": "report_test_unrelated",
            "display_value": "report_test_unrelated",
        },
    )
    assert entity.status_code == 201, entity.text
    unrelated = entity.json()
    setup["entity_ids"].append(UUID(unrelated["entity_id"]))

    response = client.get(
        f"/entities/{unrelated['entity_id']}/report"
    )

    assert response.status_code == 200, response.text
    result = response.json()

    assert result["subject"]["entity_id"] == unrelated["entity_id"]
    assert result["summary"]["relationship_count"] == 0
    assert result["summary"]["evidence_record_count"] == 0
    assert result["summary"]["timeline_event_count"] == 0
    assert result["summary"]["distinct_source_count"] == 0
    assert result["investigation"]["relationships"] == []
    assert result["timeline"]["events"] == []
    assert result["methodology"]
    assert result["limitations"]


def test_report_includes_evidence_counts_and_provenance(report_setup):
    setup = report_setup
    observation = add_observation(setup)

    add_evidence(
        setup, observation, "supports", "Synthetic supporting evidence."
    )
    add_evidence(
        setup, observation, "contradicts", "Synthetic contradictory evidence."
    )
    add_evidence(
        setup, observation, "neutral", "Synthetic neutral evidence."
    )

    response = client.get(
        f"/entities/{setup['source_entity']['entity_id']}/report"
    )

    assert response.status_code == 200, response.text
    result = response.json()

    summary = result["summary"]
    assert summary["relationship_count"] == 1
    assert summary["evidence_record_count"] == 3
    assert summary["timeline_event_count"] == 3
    assert summary["distinct_source_count"] == 1
    assert summary["supporting_evidence_count"] == 1
    assert summary["contradicting_evidence_count"] == 1
    assert summary["neutral_evidence_count"] == 1

    relationship = result["investigation"]["relationships"][0]
    assert relationship["analysis"]["confidence_band"] == "insufficient_evidence"
    assert len(relationship["evidence_records"]) == 3

    for record in relationship["evidence_records"]:
        assert record["observation"]["content_sha256"]
        assert record["source"]["source_id"] == setup["source"]["source_id"]

    assert len(result["timeline"]["events"]) == 3
    assert result["metadata"]["report_type"] == "entity_investigation"
    assert result["metadata"]["report_version"] == "1.0"
    assert result["metadata"]["report_id"]
    assert result["metadata"]["generated_at"]