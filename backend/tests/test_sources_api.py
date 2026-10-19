from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.main import app
from app.models.db_models import SourceModel

client = TestClient(app)


@pytest.fixture
def synthetic_source_name():
    name = f"API test source {uuid4()}"

    try:
        yield name
    finally:
        with SessionLocal() as db:
            db.execute(
                delete(SourceModel).where(SourceModel.name == name)
            )
            db.commit()


def test_create_and_list_source(synthetic_source_name):
    payload = {
        "name": synthetic_source_name,
        "source_type": "synthetic",
        "reference": None,
        "reliability": "unknown",
        "authorized_for_use": True,
        "authorization_note": "Synthetic-only API integration test.",
    }

    create_response = client.post("/sources", json=payload)

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == synthetic_source_name
    assert created["source_type"] == "synthetic"
    assert created["authorized_for_use"] is True
    assert created["authorization_note"] == payload["authorization_note"]
    assert "source_id" in created
    assert "created_at" in created

    list_response = client.get("/sources")

    assert list_response.status_code == 200
    assert any(
        source["source_id"] == created["source_id"]
        for source in list_response.json()
    )


def test_duplicate_source_returns_conflict(synthetic_source_name):
    payload = {
        "name": synthetic_source_name,
        "source_type": "synthetic",
        "reference": None,
        "reliability": "unknown",
        "authorized_for_use": True,
        "authorization_note": "Synthetic-only duplicate handling test.",
    }

    first = client.post("/sources", json=payload)
    second = client.post("/sources", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_blank_authorization_note_is_rejected():
    response = client.post(
        "/sources",
        json={
            "name": f"Invalid test source {uuid4()}",
            "source_type": "synthetic",
            "authorized_for_use": True,
            "authorization_note": "   ",
        },
    )

    assert response.status_code == 422

def test_unauthorized_source_can_be_documented_without_approval(
    synthetic_source_name,
):
    payload = {
        "name": synthetic_source_name,
        "source_type": "synthetic",
        "reference": None,
        "reliability": "unknown",
        "authorized_for_use": False,
        "authorization_note": (
            "Authorization has not been established; "
            "documentation only, not approved for ingestion."
        ),
    }

    response = client.post("/sources", json=payload)

    assert response.status_code == 201
    source = response.json()
    assert source["authorized_for_use"] is False
    assert "not approved for ingestion" in source["authorization_note"]