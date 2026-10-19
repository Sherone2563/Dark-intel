from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.database import SessionLocal
from app.main import app
from app.models.db_models import EntityModel

client = TestClient(app)


@pytest.fixture
def entity_factory():
    created_entity_ids = []

    def create_entity(
        value: str | None = None,
        entity_type: str = "handle",
    ) -> dict:
        value = value or f"resolution_test_{uuid4().hex}"
        response = client.post(
            "/entities",
            json={
                "entity_type": entity_type,
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


def test_candidates_return_similar_handles_in_rank_order(entity_factory):
    suffix = uuid4().hex[:10]
    query = entity_factory(f"shadow_x_{suffix}")
    near_match = entity_factory(f"shadowx_{suffix}")
    unrelated = entity_factory(f"unrelated_{uuid4().hex}")

    response = client.get(
        f"/entities/{query['entity_id']}/candidates",
        params={"min_similarity": 0.4},
    )

    assert response.status_code == 200, response.text
    candidates = response.json()
    candidate_ids = [item["entity_id"] for item in candidates]

    assert query["entity_id"] not in candidate_ids
    assert candidate_ids[0] == near_match["entity_id"]
    assert unrelated["entity_id"] not in candidate_ids


def test_candidates_respect_limit(entity_factory):
    suffix = uuid4().hex[:10]
    query = entity_factory(f"shadow_x_{suffix}")
    entity_factory(f"shadowx_{suffix}")
    entity_factory(f"shadow_xx_{suffix}")

    response = client.get(
        f"/entities/{query['entity_id']}/candidates",
        params={"limit": 1, "min_similarity": 0.0},
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) <= 1


def test_candidates_respect_similarity_threshold(entity_factory):
    suffix = uuid4().hex[:10]
    query = entity_factory(f"shadow_x_{suffix}")

    response = client.get(
        f"/entities/{query['entity_id']}/candidates",
        params={"min_similarity": 1.0},
    )

    assert response.status_code == 200, response.text
    assert all(
        item["similarity_score"] >= 1.0
        for item in response.json()
    )
    assert all(
        item["entity_id"] != query["entity_id"]
        for item in response.json()
    )


def test_candidates_for_unknown_entity_return_404():
    response = client.get(
        f"/entities/{uuid4()}/candidates"
    )

    assert response.status_code == 404


def test_candidates_for_non_handle_entity_return_422(entity_factory):
    actor = entity_factory(
        f"resolution_actor_{uuid4().hex}",
        entity_type="actor",
    )

    response = client.get(
        f"/entities/{actor['entity_id']}/candidates"
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("params", "expected_status"),
    [
        ({"limit": 0}, 422),
        ({"limit": 101}, 422),
        ({"min_similarity": -0.1}, 422),
        ({"min_similarity": 1.1}, 422),
    ],
)
def test_candidates_reject_invalid_parameters(
    entity_factory,
    params,
    expected_status,
):
    query = entity_factory()

    response = client.get(
        f"/entities/{query['entity_id']}/candidates",
        params=params,
    )

    assert response.status_code == expected_status


def test_candidate_matching_does_not_change_entity_count(entity_factory):
    query = entity_factory(f"shadow_x_{uuid4().hex[:10]}")
    entity_factory(f"shadowx_{uuid4().hex[:10]}")

    with SessionLocal() as db:
        count_before = db.scalar(
            select(func.count()).select_from(EntityModel)
        )

    response = client.get(
        f"/entities/{query['entity_id']}/candidates",
        params={"min_similarity": 0.0},
    )

    assert response.status_code == 200, response.text

    with SessionLocal() as db:
        count_after = db.scalar(
            select(func.count()).select_from(EntityModel)
        )

    assert count_after == count_before