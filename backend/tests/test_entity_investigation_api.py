
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
def investigation_setup():
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
            "name": "Synthetic Investigation Source",
            "source_type": "synthetic",
            "reference": "synthetic://investigation-tests",
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
            "payload": {
                "synthetic_test": True,
                "handle": "investigation_test_actor_a",
            },
        },
    )
    assert observation_response.status_code == 201, observation_response.text
    observation = observation_response.json()
    observation_ids.append(UUID(observation["observation_id"]))

    source_entity = create_entity("investigation_test_actor_a")
    target_entity = create_entity("investigation_test_actor_b")

    relationship_response = client.post(
        "/relationships",
        json={
            "source_entity_id": source_entity["entity_id"],
            "target_entity_id": target_entity["entity_id"],
            "relationship_type": "associated_with",
            "description": "Synthetic investigation test relationship.",
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
        "observation": observation,
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


def add_evidence(setup, polarity, description):
    response = client.post(
        "/evidence",
        json={
            "relationship_id": setup["relationship"]["relationship_id"],
            "observation_id": setup["observation"]["observation_id"],
            "polarity": polarity,
            "evidence_description": description,
            "limitations": "Synthetic test evidence; not real-world attribution.",
        },
    )
    assert response.status_code == 201, response.text
    setup["evidence_ids"].append(UUID(response.json()["evidence_id"]))
    return response.json()


def test_unknown_entity_returns_404():
    response = client.get(
        "/entities/00000000-0000-0000-0000-000000000099/investigation"
    )

    assert response.status_code == 404


def test_entity_without_relationships_returns_empty_investigation(
    investigation_setup,
):
    setup = investigation_setup

    unrelated = client.post(
        "/entities",
        json={
            "entity_type": "handle",
            "canonical_value": "investigation_test_unrelated",
            "display_value": "investigation_test_unrelated",
        },
    )
    assert unrelated.status_code == 201, unrelated.text
    unrelated_id = unrelated.json()["entity_id"]

    try:
        response = client.get(
            f"/entities/{unrelated_id}/investigation"
        )

        assert response.status_code == 200
        result = response.json()
        assert result["entity"]["entity_id"] == unrelated_id
        assert result["relationships"] == []
        assert result["relationship_count"] == 0
        assert result["evidence_record_count"] == 0
    finally:
        with SessionLocal() as db:
            db.execute(
                delete(EntityModel).where(
                    EntityModel.entity_id == UUID(unrelated_id)
                )
            )
            db.commit()


def test_investigation_includes_relationship_and_connected_entity(
    investigation_setup,
):
    setup = investigation_setup

    response = client.get(
        f"/entities/{setup['source_entity']['entity_id']}/investigation"
    )

    assert response.status_code == 200
    result = response.json()

    assert result["entity"]["entity_id"] == setup["source_entity"]["entity_id"]
    assert result["relationship_count"] == 1

    item = result["relationships"][0]
    assert item["relationship"]["relationship_id"] == (
        setup["relationship"]["relationship_id"]
    )
    assert item["connected_entity"]["entity_id"] == (
        setup["target_entity"]["entity_id"]
    )
    assert item["analysis"]["confidence_band"] == "insufficient_evidence"
    assert item["evidence_records"] == []


def test_investigation_includes_full_evidence_and_provenance(
    investigation_setup,
):
    setup = investigation_setup
    evidence = add_evidence(
        setup,
        "supports",
        "Synthetic evidence linking the two test handles.",
    )

    response = client.get(
        f"/entities/{setup['source_entity']['entity_id']}/investigation"
    )

    assert response.status_code == 200
    result = response.json()
    item = result["relationships"][0]

    assert result["evidence_record_count"] == 1
    assert item["analysis"]["supporting_count"] == 1
    assert item["analysis"]["distinct_source_count"] == 1
    assert item["analysis"]["distinct_observation_count"] == 1
    assert item["analysis"]["source_reliability_evidence_counts"] == {
        "unknown": 1
    }

    record = item["evidence_records"][0]
    assert record["evidence"]["evidence_id"] == evidence["evidence_id"]
    assert record["evidence"]["limitations"] == (
        "Synthetic test evidence; not real-world attribution."
    )

    assert record["observation"]["observation_id"] == (
        setup["observation"]["observation_id"]
    )
    assert record["observation"]["payload"]["synthetic_test"] is True
    assert record["observation"]["content_sha256"] == (
        setup["observation"]["content_sha256"]
    )

    assert record["source"]["source_id"] == setup["source"]["source_id"]
    assert record["source"]["authorized_for_use"] is True
    assert record["source"]["name"] == "Synthetic Investigation Source"


def test_investigation_includes_contradictory_evidence(
    investigation_setup,
):
    setup = investigation_setup

    add_evidence(setup, "supports", "Synthetic supporting evidence.")
    add_evidence(setup, "contradicts", "Synthetic contradictory evidence.")

    response = client.get(
        f"/entities/{setup['target_entity']['entity_id']}/investigation"
    )

    assert response.status_code == 200
    result = response.json()
    item = result["relationships"][0]

    # The relationship must be found from either endpoint.
    assert item["connected_entity"]["entity_id"] == (
        setup["source_entity"]["entity_id"]
    )
    assert item["analysis"]["supporting_count"] == 1
    assert item["analysis"]["contradicting_count"] == 1
    assert item["analysis"]["score"] == 50.0
    assert item["analysis"]["confidence_band"] == "insufficient_evidence"
    assert len(item["evidence_records"]) == 2
    assert result["evidence_record_count"] == 2
