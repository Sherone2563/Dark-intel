from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.db_models import EvidenceModel, EntityModel, RelationshipModel

client = TestClient(app)


@pytest.fixture
def relationship_factory():
    created_entity_ids = []
    created_relationship_ids = []

    def create_entity(value: str | None = None) -> dict:
        value = value or f"relationship_test_{uuid4().hex}"
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
        created_entity_ids.append(UUID(entity["entity_id"]))
        return entity

    def create_relationship(source: dict, target: dict) -> dict:
        response = client.post(
            "/relationships",
            json={
                "source_entity_id": source["entity_id"],
                "target_entity_id": target["entity_id"],
                "relationship_type": "associated_with",
                "description": "Synthetic test relationship",
            },
        )
        assert response.status_code == 201, response.text
        relationship = response.json()
        created_relationship_ids.append(
            UUID(relationship["relationship_id"])
        )
        return relationship

    yield create_entity, create_relationship

    with SessionLocal() as db:
        if created_relationship_ids:
            db.execute(
                delete(EvidenceModel).where(
                    EvidenceModel.relationship_id.in_(
                        created_relationship_ids
                    )
                )
            )
            db.execute(
                delete(RelationshipModel).where(
                    RelationshipModel.relationship_id.in_(
                        created_relationship_ids
                    )
                )
            )

        if created_entity_ids:
            db.execute(
                delete(EntityModel).where(
                    EntityModel.entity_id.in_(created_entity_ids)
                )
            )

        db.commit()


def test_create_and_get_relationship(relationship_factory):
    create_entity, create_relationship = relationship_factory
    source = create_entity()
    target = create_entity()

    relationship = create_relationship(source, target)

    response = client.get(
        f"/relationships/{relationship['relationship_id']}"
    )

    assert response.status_code == 200, response.text
    fetched = response.json()
    assert fetched["relationship_id"] == relationship["relationship_id"]
    assert fetched["source_entity_id"] == source["entity_id"]
    assert fetched["target_entity_id"] == target["entity_id"]
    assert fetched["relationship_type"] == "associated_with"


def test_list_relationships(relationship_factory):
    create_entity, create_relationship = relationship_factory
    source = create_entity()
    target = create_entity()

    relationship = create_relationship(source, target)

    response = client.get("/relationships")

    assert response.status_code == 200, response.text
    relationship_ids = {
        item["relationship_id"] for item in response.json()
    }
    assert relationship["relationship_id"] in relationship_ids


def test_filter_relationships_by_either_endpoint(relationship_factory):
    create_entity, create_relationship = relationship_factory
    source = create_entity()
    target = create_entity()
    unrelated = create_entity()

    relationship = create_relationship(source, target)

    source_response = client.get(
        "/relationships", params={"entity_id": source["entity_id"]}
    )
    target_response = client.get(
        "/relationships", params={"entity_id": target["entity_id"]}
    )
    unrelated_response = client.get(
        "/relationships", params={"entity_id": unrelated["entity_id"]}
    )

    assert source_response.status_code == 200
    assert target_response.status_code == 200
    assert unrelated_response.status_code == 200

    assert relationship["relationship_id"] in {
        item["relationship_id"] for item in source_response.json()
    }
    assert relationship["relationship_id"] in {
        item["relationship_id"] for item in target_response.json()
    }
    assert relationship["relationship_id"] not in {
        item["relationship_id"] for item in unrelated_response.json()
    }


def test_missing_source_entity_returns_404(relationship_factory):
    create_entity, _ = relationship_factory
    target = create_entity()

    response = client.post(
        "/relationships",
        json={
            "source_entity_id": str(uuid4()),
            "target_entity_id": target["entity_id"],
            "relationship_type": "associated_with",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Source entity not found."


def test_missing_target_entity_returns_404(relationship_factory):
    create_entity, _ = relationship_factory
    source = create_entity()

    response = client.post(
        "/relationships",
        json={
            "source_entity_id": source["entity_id"],
            "target_entity_id": str(uuid4()),
            "relationship_type": "associated_with",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Target entity not found."


def test_unknown_relationship_returns_404():
    response = client.get(f"/relationships/{uuid4()}")

    assert response.status_code == 404


def test_self_relationship_is_rejected(relationship_factory):
    create_entity, _ = relationship_factory
    entity = create_entity()

    response = client.post(
        "/relationships",
        json={
            "source_entity_id": entity["entity_id"],
            "target_entity_id": entity["entity_id"],
            "relationship_type": "associated_with",
        },
    )

    assert response.status_code == 422


def test_invalid_relationship_chronology_is_rejected(relationship_factory):
    create_entity, _ = relationship_factory
    source = create_entity()
    target = create_entity()

    response = client.post(
        "/relationships",
        json={
            "source_entity_id": source["entity_id"],
            "target_entity_id": target["entity_id"],
            "relationship_type": "associated_with",
            "first_observed_at": "2026-10-12T12:00:00Z",
            "last_observed_at": "2026-10-11T12:00:00Z",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize("limit", [0, 101])
def test_invalid_relationship_limit_is_rejected(limit):
    response = client.get("/relationships", params={"limit": limit})

    assert response.status_code == 422


def test_relationship_pagination(relationship_factory):
    create_entity, create_relationship = relationship_factory
    source = create_entity()
    target = create_entity()

    first = create_relationship(source, target)
    second = create_relationship(target, source)

    response = client.get(
        "/relationships",
        params={"limit": 1, "offset": 0},
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1

    returned_id = response.json()[0]["relationship_id"]
    assert returned_id in {
        first["relationship_id"],
        second["relationship_id"],
    }