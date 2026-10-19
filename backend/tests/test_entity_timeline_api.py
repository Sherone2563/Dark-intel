
from datetime import datetime, timezone
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
def timeline_setup():
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
            "name": "Synthetic Timeline Source",
            "source_type": "synthetic",
            "reference": "synthetic://timeline-tests",
            "reliability": "unknown",
            "authorized_for_use": True,
            "authorization_note": "Synthetic data for automated testing.",
        },
    )
    assert source_response.status_code == 201, source_response.text
    source = source_response.json()
    source_ids.append(UUID(source["source_id"]))

    source_entity = create_entity("timeline_test_actor_a")
    target_entity = create_entity("timeline_test_actor_b")

    relationship_response = client.post(
        "/relationships",
        json={
            "source_entity_id": source_entity["entity_id"],
            "target_entity_id": target_entity["entity_id"],
            "relationship_type": "associated_with",
            "description": "Synthetic timeline relationship.",
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


def add_observation(setup, collected_at, observed_at=None):
    payload = {
        "synthetic_test": True,
        "sequence": len(setup["observation_ids"]) + 1,
    }
    request_data = {
        "source_id": setup["source"]["source_id"],
        "payload": payload,
        "collected_at": collected_at.isoformat(),
    }
    if observed_at is not None:
        request_data["observed_at"] = observed_at.isoformat()

    response = client.post("/observations", json=request_data)
    assert response.status_code == 201, response.text

    observation = response.json()
    setup["observation_ids"].append(UUID(observation["observation_id"]))
    return observation


def add_evidence(setup, observation, description, observed_at=None):
    request_data = {
        "relationship_id": setup["relationship"]["relationship_id"],
        "observation_id": observation["observation_id"],
        "polarity": "supports",
        "evidence_description": description,
        "limitations": "Synthetic test evidence only.",
    }
    if observed_at is not None:
        request_data["observed_at"] = observed_at.isoformat()

    response = client.post("/evidence", json=request_data)
    assert response.status_code == 201, response.text

    evidence = response.json()
    setup["evidence_ids"].append(UUID(evidence["evidence_id"]))
    return evidence


def test_unknown_entity_returns_404():
    response = client.get(
        "/entities/00000000-0000-0000-0000-000000000099/timeline"
    )

    assert response.status_code == 404


def test_entity_without_evidence_has_empty_timeline(timeline_setup):
    setup = timeline_setup

    response = client.get(
        f"/entities/{setup['source_entity']['entity_id']}/timeline"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["events"] == []
    assert result["event_count"] == 0


def test_timeline_includes_evidence_from_either_relationship_direction(
    timeline_setup,
):
    setup = timeline_setup
    now = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
    observation = add_observation(setup, collected_at=now)
    add_evidence(setup, observation, "Synthetic supporting evidence.")

    response = client.get(
        f"/entities/{setup['target_entity']['entity_id']}/timeline"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["event_count"] == 1

    event = result["events"][0]
    assert event["connected_entity"]["entity_id"] == (
        setup["source_entity"]["entity_id"]
    )
    assert event["evidence_polarity"] == "supports"
    assert event["timestamp_basis"] == "observation_collected_at"
    assert event["source"]["source_id"] == setup["source"]["source_id"]


def test_timestamp_precedence_and_chronological_order(timeline_setup):
    setup = timeline_setup

    # Event 1 uses the evidence timestamp: January 1.
    evidence_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    observation_one = add_observation(
        setup,
        collected_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
        observed_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
    )
    evidence_one = add_evidence(
        setup,
        observation_one,
        "Event timestamp comes from evidence.",
        observed_at=evidence_time,
    )

    # Event 2 falls back to the observation timestamp: January 2.
    observation_time = datetime(2026, 1, 2, tzinfo=timezone.utc)
    observation_two = add_observation(
        setup,
        collected_at=datetime(2026, 1, 11, tzinfo=timezone.utc),
        observed_at=observation_time,
    )
    evidence_two = add_evidence(
        setup,
        observation_two,
        "Event timestamp comes from observation.",
    )

    # Event 3 falls back to collection time: January 3.
    collection_time = datetime(2026, 1, 3, tzinfo=timezone.utc)
    observation_three = add_observation(
        setup,
        collected_at=collection_time,
    )
    evidence_three = add_evidence(
        setup,
        observation_three,
        "Event timestamp comes from collection.",
    )

    response = client.get(
        f"/entities/{setup['source_entity']['entity_id']}/timeline"
    )

    assert response.status_code == 200
    events = response.json()["events"]

    assert [event["evidence_id"] for event in events] == [
        evidence_one["evidence_id"],
        evidence_two["evidence_id"],
        evidence_three["evidence_id"],
    ]
    assert [event["timestamp_basis"] for event in events] == [
        "evidence_observed_at",
        "observation_observed_at",
        "observation_collected_at",
    ]
    assert [
        event["event_timestamp"]
        for event in events
    ] == [
        "2026-01-01T00:00:00Z",
        "2026-01-02T00:00:00Z",
        "2026-01-03T00:00:00Z",
    ]


def test_timeline_preserves_provenance_and_limitations(timeline_setup):
    setup = timeline_setup
    collected_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    observation = add_observation(setup, collected_at=collected_at)
    evidence = add_evidence(
        setup,
        observation,
        "Synthetic evidence with documented limitations.",
    )

    response = client.get(
        f"/entities/{setup['source_entity']['entity_id']}/timeline"
    )

    assert response.status_code == 200
    event = response.json()["events"][0]

    assert event["evidence_id"] == evidence["evidence_id"]
    assert event["observation_id"] == observation["observation_id"]
    assert event["content_sha256"] == observation["content_sha256"]
    assert event["evidence_limitations"] == "Synthetic test evidence only."
    assert event["source"]["authorized_for_use"] is True
    assert event["relationship_type"] == "associated_with"
