from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.db_models import (
    EntityModel,
    ObservationEntityModel,
    ObservationModel,
    SourceModel,
)

client = TestClient(app)


@pytest.fixture
def provenance_setup():
    entity_ids = []
    source_ids = []
    observation_ids = []

    source_response = client.post(
        "/sources",
        json={
            "name": "Synthetic Provenance Test Source",
            "source_type": "synthetic",
            "reference": "synthetic://entity-provenance-tests",
            "reliability": "unknown",
            "authorized_for_use": True,
            "authorization_note": "Synthetic automated test data.",
        },
    )
    assert source_response.status_code == 201, source_response.text
    source = source_response.json()
    source_ids.append(UUID(source["source_id"]))

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

    def create_observation(handle):
        response = client.post(
            "/observations",
            json={
                "source_id": source["source_id"],
                "payload": {"handle": handle, "synthetic_test": True},
            },
        )
        assert response.status_code == 201, response.text
        observation = response.json()
        observation_ids.append(UUID(observation["observation_id"]))
        return observation

    setup = {
        "entity_ids": entity_ids,
        "source_ids": source_ids,
        "observation_ids": observation_ids,
        "source": source,
        "create_entity": create_entity,
        "create_observation": create_observation,
    }

    yield setup

    with SessionLocal() as db:
        if observation_ids or entity_ids:
            conditions = []
            if observation_ids:
                conditions.append(
                    ObservationEntityModel.observation_id.in_(
                        observation_ids
                    )
                )
            if entity_ids:
                conditions.append(
                    ObservationEntityModel.entity_id.in_(entity_ids)
                )

            from sqlalchemy import or_

            db.execute(
                delete(ObservationEntityModel).where(or_(*conditions))
            )

        if observation_ids:
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


def test_unknown_entity_returns_404():
    response = client.get(
        f"/entities/{uuid4()}/provenance"
    )

    assert response.status_code == 404


def test_entity_without_provenance_returns_empty_records(provenance_setup):
    setup = provenance_setup
    entity = setup["create_entity"]("synthetic_provenance_empty")

    response = client.get(
        f"/entities/{entity['entity_id']}/provenance"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entity"]["entity_id"] == entity["entity_id"]
    assert body["records"] == []
    assert body["record_count"] == 0


def test_provenance_returns_extraction_metadata(provenance_setup):
    setup = provenance_setup
    entity = setup["create_entity"]("synthetic_provenance_alpha")
    observation = setup["create_observation"](
        "synthetic_provenance_alpha"
    )

    with SessionLocal() as db:
        db.add(
            ObservationEntityModel(
                observation_id=UUID(observation["observation_id"]),
                entity_id=UUID(entity["entity_id"]),
                association_type="extracted_handle",
                field_name="handle",
                normalization_method="strip_casefold_v1",
            )
        )
        db.commit()

    response = client.get(
        f"/entities/{entity['entity_id']}/provenance"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["record_count"] == 1

    record = body["records"][0]
    assert record["observation_id"] == observation["observation_id"]
    assert record["source_id"] == setup["source"]["source_id"]
    assert record["source_name"] == setup["source"]["name"]
    assert record["authorized_for_use"] is True
    assert record["content_sha256"] == observation["content_sha256"]
    assert record["association_type"] == "extracted_handle"
    assert record["field_name"] == "handle"
    assert record["normalization_method"] == "strip_casefold_v1"

def test_provenance_retains_unauthorized_source_audit_flag(
    provenance_setup,
):
    setup = provenance_setup
    entity = setup["create_entity"]("synthetic_provenance_unauthorized")
    observation = setup["create_observation"](
        "synthetic_provenance_unauthorized"
    )

    with SessionLocal() as db:
        db.add(
            ObservationEntityModel(
                observation_id=UUID(observation["observation_id"]),
                entity_id=UUID(entity["entity_id"]),
                association_type="extracted_handle",
                field_name="handle",
                normalization_method="strip_casefold_v1",
            )
        )
        source = db.get(SourceModel, UUID(setup["source"]["source_id"]))
        assert source is not None
        source.authorized_for_use = False
        db.commit()

    response = client.get(
        f"/entities/{entity['entity_id']}/provenance"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["record_count"] == 1

    record = body["records"][0]
    assert record["authorized_for_use"] is False
    assert record["observation_id"] == observation["observation_id"]
    assert "payload" not in record