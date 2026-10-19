from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.db_models import EntityModel

client = TestClient(app)


@pytest.fixture
def entity_factory():
    created_entity_ids = []

    def create_entity(value: str | None = None) -> dict:
        value = value or f"test_handle_{uuid4().hex}"
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

    yield create_entity

    with SessionLocal() as db:
        if created_entity_ids:
            db.execute(
                delete(EntityModel).where(
                    EntityModel.entity_id.in_(created_entity_ids)
                )
            )
            db.commit()


def test_create_and_get_entity(entity_factory):
    entity = entity_factory(f"api_test_{uuid4().hex}")

    response = client.get(f"/entities/{entity['entity_id']}")

    assert response.status_code == 200, response.text
    fetched = response.json()
    assert fetched["entity_id"] == entity["entity_id"]
    assert fetched["entity_type"] == "handle"
    assert fetched["canonical_value"] == entity["canonical_value"]


def test_similar_handles_are_not_merged(entity_factory):
    suffix = uuid4().hex[:10]
    first = entity_factory(f"shadow_x_{suffix}")
    second = entity_factory(f"shadowx_{suffix}")

    assert first["entity_id"] != second["entity_id"]

    response = client.get("/entities/search", params={"value": suffix})

    assert response.status_code == 200, response.text
    found_ids = {item["entity_id"] for item in response.json()}
    assert first["entity_id"] in found_ids
    assert second["entity_id"] in found_ids


def test_get_unknown_entity_returns_404():
    response = client.get(f"/entities/{uuid4()}")

    assert response.status_code == 404


def test_blank_entity_values_are_rejected():
    response = client.post(
        "/entities",
        json={
            "entity_type": "handle",
            "canonical_value": "   ",
            "display_value": "shadow_x",
        },
    )

    assert response.status_code == 422


def test_invalid_observation_chronology_is_rejected():
    response = client.post(
        "/entities",
        json={
            "entity_type": "handle",
            "canonical_value": "api_test_chronology",
            "display_value": "api_test_chronology",
            "first_observed_at": "2026-10-12T12:00:00Z",
            "last_observed_at": "2026-10-11T12:00:00Z",
        },
    )

    assert response.status_code == 422
