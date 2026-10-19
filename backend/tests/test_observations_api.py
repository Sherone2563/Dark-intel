from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.main import app
from app.models.db_models import ObservationModel, SourceModel
from app.models.observations import calculate_payload_sha256

client = TestClient(app)


@pytest.fixture
def source_factory():
    created_source_ids = []

    def create_source(*, authorized: bool = True) -> dict:
        name = f"Observation API test {uuid4()}"
        response = client.post(
            "/sources",
            json={
                "name": name,
                "source_type": "synthetic",
                "reference": None,
                "reliability": "unknown",
                "authorized_for_use": authorized,
                "authorization_note": (
                    "Synthetic-only integration test source."
                    if authorized
                    else "Documentation only; not authorized for ingestion."
                ),
            },
        )
        assert response.status_code == 201, response.text
        source = response.json()
        created_source_ids.append(UUID(source["source_id"]))
        return source

    yield create_source

    with SessionLocal() as db:
        for source_id in created_source_ids:
            db.execute(
                delete(ObservationModel).where(
                    ObservationModel.source_id == source_id
                )
            )
            db.execute(
                delete(SourceModel).where(SourceModel.source_id == source_id)
            )
        db.commit()


def test_create_observation_persists_payload_and_server_hash(source_factory):
    source = source_factory()
    payload = {
        "handle": "shadow_x",
        "forum": "synthetic_research_forum",
    }

    response = client.post(
        "/observations",
        json={
            "source_id": source["source_id"],
            "payload": payload,
            "processing_version": "0.1.0",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source_id"] == source["source_id"]
    assert body["payload"] == payload
    assert body["content_sha256"] == calculate_payload_sha256(payload)
    assert body["status"] == "ingested"
    assert body["processing_version"] == "0.1.0"
    assert body["collected_at"]
    assert body["created_at"]

    observation_id = UUID(body["observation_id"])
    with SessionLocal() as db:
        saved = db.get(ObservationModel, observation_id)
        assert saved is not None
        assert saved.payload == payload
        assert saved.content_sha256 == calculate_payload_sha256(payload)


def test_unknown_source_is_rejected():
    response = client.post(
        "/observations",
        json={
            "source_id": str(uuid4()),
            "payload": {"handle": "synthetic_handle"},
        },
    )

    assert response.status_code == 404


def test_unauthorized_source_is_rejected(source_factory):
    source = source_factory(authorized=False)

    response = client.post(
        "/observations",
        json={
            "source_id": source["source_id"],
            "payload": {"handle": "synthetic_handle"},
        },
    )

    assert response.status_code == 403


def test_naive_collected_timestamp_is_rejected(source_factory):
    source = source_factory()

    response = client.post(
        "/observations",
        json={
            "source_id": source["source_id"],
            "payload": {"handle": "synthetic_handle"},
            "collected_at": "2026-10-15T10:00:00",
        },
    )

    assert response.status_code == 422


def test_naive_observed_timestamp_is_rejected(source_factory):
    source = source_factory()

    response = client.post(
        "/observations",
        json={
            "source_id": source["source_id"],
            "payload": {"handle": "synthetic_handle"},
            "observed_at": "2026-10-15T10:00:00",
        },
    )

    assert response.status_code == 422


def test_observation_uses_supplied_timezone_aware_timestamps(source_factory):
    source = source_factory()

    response = client.post(
        "/observations",
        json={
            "source_id": source["source_id"],
            "payload": {"handle": "synthetic_handle"},
            "collected_at": "2026-10-15T10:00:00+05:30",
            "observed_at": "2026-10-14T18:30:00Z",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["collected_at"]
    assert body["observed_at"]


def test_extra_request_fields_are_rejected(source_factory):
    source = source_factory()

    response = client.post(
        "/observations",
        json={
            "source_id": source["source_id"],
            "payload": {"handle": "synthetic_handle"},
            "client_supplied_hash": "0" * 64,
        },
    )

    assert response.status_code == 422

def test_get_observation_returns_persisted_provenance(source_factory):
    source = source_factory()
    payload = {
        "handle": "shadow_x",
        "dataset": "synthetic_research",
    }

    create_response = client.post(
        "/observations",
        json={
            "source_id": source["source_id"],
            "payload": payload,
            "processing_version": "0.1.0",
        },
    )

    assert create_response.status_code == 201, create_response.text
    created = create_response.json()

    response = client.get(
        f"/observations/{created['observation_id']}"
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["observation_id"] == created["observation_id"]
    assert body["source_id"] == source["source_id"]
    assert body["payload"] == payload
    assert body["content_sha256"] == calculate_payload_sha256(payload)
    assert body["status"] == "ingested"
    assert body["processing_version"] == "0.1.0"
    assert body["collected_at"] == created["collected_at"]
    assert body["created_at"] == created["created_at"]


def test_get_unknown_observation_returns_404():
    response = client.get(f"/observations/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Observation not found."

def test_list_observations_returns_empty_list_for_no_matches():
    response = client.get(
        "/observations",
        params={"source_id": str(uuid4())},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_observations_filters_by_source(source_factory):
    source_a = source_factory()
    source_b = source_factory()

    created_ids = []

    for source in (source_a, source_a, source_b):
        response = client.post(
            "/observations",
            json={
                "source_id": source["source_id"],
                "payload": {"test_record": str(uuid4())},
            },
        )
        assert response.status_code == 201, response.text
        created_ids.append(response.json()["observation_id"])

    response = client.get(
        "/observations",
        params={"source_id": source_a["source_id"]},
    )

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2
    assert all(item["source_id"] == source_a["source_id"] for item in results)


def test_list_observations_respects_limit_and_offset(source_factory):
    source = source_factory()

    for index in range(3):
        response = client.post(
            "/observations",
            json={
                "source_id": source["source_id"],
                "payload": {"sequence": index},
            },
        )
        assert response.status_code == 201, response.text

    params = {"source_id": source["source_id"], "limit": 1, "offset": 1}
    response = client.get("/observations", params=params)

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_observations_rejects_invalid_pagination():
    response = client.get("/observations", params={"limit": 0})
    assert response.status_code == 422

    response = client.get("/observations", params={"offset": -1})
    assert response.status_code == 422