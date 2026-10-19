
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
def evidence_setup():
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
            "name": "Synthetic Evidence Test Source",
            "source_type": "synthetic",
            "reference": "synthetic://evidence-api-tests",
            "reliability": "unknown",
            "authorized_for_use": True,
            "authorization_note": "Synthetic data created for API testing.",
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
                "test_case": "evidence-api",
                "text": "Synthetic observation for evidence API tests.",
            },
        },
    )
    assert observation_response.status_code == 201, observation_response.text
    observation = observation_response.json()
    observation_ids.append(UUID(observation["observation_id"]))

    source_entity = create_entity("evidence_test_actor_a")
    target_entity = create_entity("evidence_test_actor_b")

    relationship_response = client.post(
        "/relationships",
        json={
            "source_entity_id": source_entity["entity_id"],
            "target_entity_id": target_entity["entity_id"],
            "relationship_type": "associated_with",
            "description": "Synthetic relationship for evidence API tests.",
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
        "relationship": relationship,
        "observation": observation,
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


def test_create_and_get_evidence(evidence_setup):
    setup = evidence_setup
    relationship = setup["relationship"]
    observation = setup["observation"]

    response = client.post(
        "/evidence",
        json={
            "relationship_id": relationship["relationship_id"],
            "observation_id": observation["observation_id"],
            "polarity": "supports",
            "evidence_description": "Synthetic test evidence supports this link.",
            "limitations": "Synthetic data; not real-world attribution.",
        },
    )

    assert response.status_code == 201, response.text
    evidence = response.json()
    setup["evidence_ids"].append(UUID(evidence["evidence_id"]))

    assert evidence["relationship_id"] == relationship["relationship_id"]
    assert evidence["observation_id"] == observation["observation_id"]
    assert evidence["polarity"] == "supports"

    get_response = client.get(f"/evidence/{evidence['evidence_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["evidence_id"] == evidence["evidence_id"]


def test_list_evidence_for_relationship(evidence_setup):
    setup = evidence_setup
    relationship_id = setup["relationship"]["relationship_id"]
    observation_id = setup["observation"]["observation_id"]

    response = client.post(
        "/evidence",
        json={
            "relationship_id": relationship_id,
            "observation_id": observation_id,
            "polarity": "contradicts",
            "evidence_description": "Synthetic contradictory evidence.",
        },
    )
    assert response.status_code == 201, response.text
    setup["evidence_ids"].append(UUID(response.json()["evidence_id"]))

    list_response = client.get(f"/relationships/{relationship_id}/evidence")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["polarity"] == "contradicts"


def test_missing_relationship_returns_404(evidence_setup):
    response = client.post(
        "/evidence",
        json={
            "relationship_id": "00000000-0000-0000-0000-000000000001",
            "observation_id": evidence_setup["observation"]["observation_id"],
            "polarity": "supports",
            "evidence_description": "Test evidence.",
        },
    )
    assert response.status_code == 404


def test_missing_observation_returns_404(evidence_setup):
    response = client.post(
        "/evidence",
        json={
            "relationship_id": evidence_setup["relationship"]["relationship_id"],
            "observation_id": "00000000-0000-0000-0000-000000000002",
            "polarity": "supports",
            "evidence_description": "Test evidence.",
        },
    )
    assert response.status_code == 404


def test_missing_evidence_returns_404():
    response = client.get(
        "/evidence/00000000-0000-0000-0000-000000000003"
    )
    assert response.status_code == 404


def test_missing_relationship_evidence_list_returns_404():
    response = client.get(
        "/relationships/00000000-0000-0000-0000-000000000004/evidence"
    )
    assert response.status_code == 404


@pytest.mark.parametrize("polarity", ["supports", "contradicts", "neutral"])
def test_all_evidence_polarities_are_accepted(evidence_setup, polarity):
    setup = evidence_setup
    response = client.post(
        "/evidence",
        json={
            "relationship_id": setup["relationship"]["relationship_id"],
            "observation_id": setup["observation"]["observation_id"],
            "polarity": polarity,
            "evidence_description": f"Synthetic {polarity} evidence.",
        },
    )
    assert response.status_code == 201, response.text
    setup["evidence_ids"].append(UUID(response.json()["evidence_id"]))


def test_blank_evidence_description_is_rejected(evidence_setup):
    setup = evidence_setup
    response = client.post(
        "/evidence",
        json={
            "relationship_id": setup["relationship"]["relationship_id"],
            "observation_id": setup["observation"]["observation_id"],
            "polarity": "supports",
            "evidence_description": "   ",
        },
    )
    assert response.status_code == 422


def test_invalid_polarity_is_rejected(evidence_setup):
    setup = evidence_setup
    response = client.post(
        "/evidence",
        json={
            "relationship_id": setup["relationship"]["relationship_id"],
            "observation_id": setup["observation"]["observation_id"],
            "polarity": "unverified",
            "evidence_description": "Synthetic test evidence.",
        },
    )
    assert response.status_code == 422


def test_evidence_list_pagination(evidence_setup):
    setup = evidence_setup
    relationship_id = setup["relationship"]["relationship_id"]
    observation_id = setup["observation"]["observation_id"]

    for index in range(2):
        response = client.post(
            "/evidence",
            json={
                "relationship_id": relationship_id,
                "observation_id": observation_id,
                "polarity": "neutral",
                "evidence_description": f"Synthetic pagination evidence {index}.",
            },
        )
        assert response.status_code == 201, response.text
        setup["evidence_ids"].append(UUID(response.json()["evidence_id"]))

    response = client.get(
        f"/relationships/{relationship_id}/evidence?limit=1&offset=1"
    )
    assert response.status_code == 200
    assert len(response.json()) == 1

    invalid_response = client.get(
        f"/relationships/{relationship_id}/evidence?limit=0"
    )
    assert invalid_response.status_code == 422
