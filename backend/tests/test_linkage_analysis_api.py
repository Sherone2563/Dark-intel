
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
def analysis_setup():
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
            "name": "Synthetic Linkage Analysis Source",
            "source_type": "synthetic",
            "reference": "synthetic://linkage-analysis-tests",
            "reliability": "unknown",
            "authorized_for_use": True,
            "authorization_note": "Synthetic data for automated testing.",
        },
    )
    assert source_response.status_code == 201, source_response.text
    source = source_response.json()
    source_ids.append(UUID(source["source_id"]))

    observation_response = client.post(
        "/observations",
        json={
            "source_id": source["source_id"],
            "payload": {"synthetic_test": True},
        },
    )
    assert observation_response.status_code == 201, observation_response.text
    observation = observation_response.json()
    observation_ids.append(UUID(observation["observation_id"]))

    source_entity = create_entity("analysis_test_actor_a")
    target_entity = create_entity("analysis_test_actor_b")

    relationship_response = client.post(
        "/relationships",
        json={
            "source_entity_id": source_entity["entity_id"],
            "target_entity_id": target_entity["entity_id"],
            "relationship_type": "associated_with",
            "description": "Synthetic analysis test relationship.",
        },
    )
    assert relationship_response.status_code == 201, relationship_response.text
    relationship = relationship_response.json()
    relationship_ids.append(UUID(relationship["relationship_id"]))

    yield {
        "entity_ids": entity_ids,
        "source_ids": source_ids,
        "observation_ids": observation_ids,
        "relationship_ids": relationship_ids,
        "evidence_ids": evidence_ids,
        "observation": observation,
        "relationship": relationship,
    }

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
                delete(SourceModel).where(SourceModel.source_id.in_(source_ids))
            )
        if entity_ids:
            db.execute(
                delete(EntityModel).where(EntityModel.entity_id.in_(entity_ids))
            )
        db.commit()


def add_evidence(setup, polarity, description):
    response = client.post(
        "/evidence",
        json={
            "relationship_id": setup["relationship"]["relationship_id"],
            "observation_id": setup["observation"]["observation_id"],
            "polarity": polarity,
            "evidence_description": description,
        },
    )
    assert response.status_code == 201, response.text
    setup["evidence_ids"].append(UUID(response.json()["evidence_id"]))
    return response.json()


def test_analysis_without_evidence_is_insufficient(analysis_setup):
    relationship_id = analysis_setup["relationship"]["relationship_id"]

    response = client.get(f"/relationships/{relationship_id}/analysis")

    assert response.status_code == 200
    result = response.json()
    assert result["score"] is None
    assert result["confidence_band"] == "insufficient_evidence"
    assert result["evidence_ids"] == []


def test_analysis_with_supporting_evidence(analysis_setup):
    setup = analysis_setup
    add_evidence(setup, "supports", "Synthetic supporting evidence.")

    response = client.get(
        f"/relationships/{setup['relationship']['relationship_id']}/analysis"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["score"] == 100.0
    assert result["confidence_band"] == "insufficient_evidence"
    assert result["supporting_count"] == 1
    assert result["contradicting_count"] == 0
    assert len(result["evidence_ids"]) == 1


def test_analysis_includes_contradictory_evidence(analysis_setup):
    setup = analysis_setup
    add_evidence(setup, "supports", "Synthetic supporting evidence.")
    add_evidence(setup, "contradicts", "Synthetic contradictory evidence.")

    response = client.get(
        f"/relationships/{setup['relationship']['relationship_id']}/analysis"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["score"] == 50.0
    assert result["confidence_band"] == "insufficient_evidence"
    assert result["supporting_count"] == 1
    assert result["contradicting_count"] == 1
    assert len(result["evidence_ids"]) == 2


def test_analysis_reports_neutral_evidence(analysis_setup):
    setup = analysis_setup
    add_evidence(setup, "neutral", "Synthetic neutral evidence.")

    response = client.get(
        f"/relationships/{setup['relationship']['relationship_id']}/analysis"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["score"] is None
    assert result["confidence_band"] == "insufficient_evidence"
    assert result["neutral_count"] == 1


def test_analysis_for_unknown_relationship_returns_404():
    response = client.get(
        "/relationships/00000000-0000-0000-0000-000000000099/analysis"
    )

    assert response.status_code == 404

def test_analysis_reports_source_provenance(analysis_setup):
    setup = analysis_setup
    add_evidence(setup, "supports", "First synthetic supporting item.")
    add_evidence(setup, "supports", "Second item from the same source.")

    relationship_id = setup["relationship"]["relationship_id"]
    response = client.get(f"/relationships/{relationship_id}/analysis")

    assert response.status_code == 200
    result = response.json()

    assert result["distinct_source_count"] == 1
    assert result["distinct_observation_count"] == 1
    assert result["evidence_items_sharing_sources"] == 1
    assert result["source_reliability_evidence_counts"] == {"unknown": 2}
    assert "qualifies toward independent corroboration" in result["source_quality_note"]
    assert "does not change the numeric evidence-balance score" in result["source_quality_note"]

def test_analysis_distinguishes_observations_from_sources(analysis_setup):
    setup = analysis_setup

    # Two distinct observations from the same source.
    second_observation_response = client.post(
        "/observations",
        json={
            "source_id": str(setup["source_ids"][0]),
            "payload": {"synthetic_test": True, "record": 2},
        },
    )
    assert second_observation_response.status_code == 201, (
        second_observation_response.text
    )
    second_observation = second_observation_response.json()
    setup["observation_ids"].append(
        UUID(second_observation["observation_id"])
    )

    # One supporting evidence item per observation.
    add_evidence(setup, "supports", "Support from the first observation.")

    second_evidence_response = client.post(
        "/evidence",
        json={
            "relationship_id": setup["relationship"]["relationship_id"],
            "observation_id": second_observation["observation_id"],
            "polarity": "supports",
            "evidence_description": "Support from the second observation.",
        },
    )
    assert second_evidence_response.status_code == 201, (
        second_evidence_response.text
    )
    setup["evidence_ids"].append(
        UUID(second_evidence_response.json()["evidence_id"])
    )

    relationship_id = setup["relationship"]["relationship_id"]
    response = client.get(f"/relationships/{relationship_id}/analysis")

    assert response.status_code == 200
    result = response.json()

    assert result["score"] == 100.0
    assert result["confidence_band"] == "insufficient_evidence"
    assert result["qualifying_source_count"] == 0
    assert "At least two distinct sources" in result["confidence_reason"]
    assert result["distinct_source_count"] == 1
    assert result["distinct_observation_count"] == 2
    assert result["supporting_count"] == 2
    assert result["evidence_items_sharing_sources"] == 1
def test_analysis_excludes_evidence_from_unauthorized_source(analysis_setup):
    setup = analysis_setup
    add_evidence(setup, "supports", "Synthetic authorization regression test.")

    # Revoke authorization after the evidence has been created.
    with SessionLocal() as db:
        source = db.get(SourceModel, setup["source_ids"][0])
        assert source is not None
        source.authorized_for_use = False
        db.commit()

    response = client.get(
        f"/relationships/{setup['relationship']['relationship_id']}/analysis"
    )

    assert response.status_code == 200
    result = response.json()

    assert result["score"] is None
    assert result["confidence_band"] == "insufficient_evidence"
    assert result["evidence_ids"] == []
    assert result["supporting_count"] == 0
    assert result["contradicting_count"] == 0
    assert result["distinct_source_count"] == 0
    assert result["distinct_observation_count"] == 0