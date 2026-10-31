
import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from datetime import datetime, timezone
from app.models.db_models import ProcessingRunModel
from app.core.database import SessionLocal
from app.main import app
from app.models.db_models import (
    EntityModel,
    EvidenceModel,
    ObservationEntityModel,
    ObservationModel,
    RelationshipModel,
    SourceModel,
)
from app.services.ingestion_pipeline import run_ingestion_pipeline


client = TestClient(app)


@pytest.fixture
def intelligence_e2e_setup():
    """Create and clean up isolated records for the intelligence E2E test."""
    token = uuid4().hex[:12]
    handle_a = f"e2e_actor_a_{token}"
    handle_b = f"e2e_actor_b_{token}"

    source_id = None
    observation_ids = []
    entity_ids = []
    relationship_ids = []
    evidence_ids = []

    try:
        source_response = client.post(
            "/sources",
            json={
                "name": f"E2E Synthetic Source {token}",
                "source_type": "synthetic",
                "reference": f"synthetic://intelligence-e2e/{token}",
                "reliability": "unknown",
                "authorized_for_use": True,
                "authorization_note": (
                    "Authorized synthetic data for an automated integration test."
                ),
            },
        )
        assert source_response.status_code == 201, source_response.text
        source_id = UUID(source_response.json()["source_id"])

        lines = [
            json.dumps(
                {
                    "payload": {
                        "handle": handle_a,
                        "record_type": "synthetic_profile",
                        "test_run": token,
                    },
                    "observed_at": "2026-10-15T10:00:00Z",
                    "processing_version": "0.1.0",
                }
            ),
            json.dumps(
                {
                    "payload": {
                        "handle": handle_b,
                        "record_type": "synthetic_profile",
                        "test_run": token,
                    },
                    "observed_at": "2026-10-16T10:00:00Z",
                    "processing_version": "0.1.0",
                }
            ),
        ]

        with SessionLocal() as db:
            pipeline_result = run_ingestion_pipeline(
                db=db,
                source_id=source_id,
                lines=lines,
            )

        assert pipeline_result["status"] == "completed"
        assert pipeline_result["import"]["imported_count"] == 2
        assert pipeline_result["extraction"]["entities_created"] == 2

        with SessionLocal() as db:
            observations = db.scalars(
                select(ObservationModel).where(
                    ObservationModel.source_id == source_id
                )
            ).all()
            observation_ids.extend(
                item.observation_id for item in observations
            )

            entities = db.scalars(
                select(EntityModel).where(
                    EntityModel.entity_type == "handle",
                    EntityModel.canonical_value.in_([handle_a, handle_b]),
                )
            ).all()
            entity_by_handle = {
                item.canonical_value: item for item in entities
            }
            entity_ids.extend(item.entity_id for item in entities)

            associations = db.scalars(
                select(ObservationEntityModel).where(
                    ObservationEntityModel.observation_id.in_(
                        observation_ids
                    )
                )
            ).all()

        assert len(observations) == 2
        assert len(entity_by_handle) == 2
        assert len(associations) == 2

        # Each extracted handle must have provenance to an imported observation.
        association_pairs = {
            (item.observation_id, item.entity_id)
            for item in associations
        }
        expected_pairs = {
            (
                observation.observation_id,
                entity_by_handle[observation.payload["handle"]].entity_id,
            )
            for observation in observations
        }
        assert association_pairs == expected_pairs

        relationship_response = client.post(
            "/relationships",
            json={
                "source_entity_id": str(entity_by_handle[handle_a].entity_id),
                "target_entity_id": str(entity_by_handle[handle_b].entity_id),
                "relationship_type": "associated_with",
                "description": (
                    "Synthetic test relationship; not a claim of real-world identity."
                ),
            },
        )
        assert relationship_response.status_code == 201, (
            relationship_response.text
        )
        relationship = relationship_response.json()
        relationship_id = UUID(relationship["relationship_id"])
        relationship_ids.append(relationship_id)

        # Use an observation from the same authorized source as the evidence basis.
        observation = next(
            item for item in observations
            if item.payload.get("handle") == handle_a
        )

        evidence_response = client.post(
            "/evidence",
            json={
                "relationship_id": str(relationship_id),
                "observation_id": str(observation.observation_id),
                "polarity": "supports",
                "evidence_description": (
                    "Synthetic observation records one handle in this test relationship."
                ),
                "limitations": (
                    "One synthetic observation is not independent corroboration "
                    "and does not establish common identity."
                ),
            },
        )
        assert evidence_response.status_code == 201, evidence_response.text
        evidence = evidence_response.json()
        evidence_id = UUID(evidence["evidence_id"])
        evidence_ids.append(evidence_id)

        yield {
            "source_id": source_id,
            "handle_a": handle_a,
            "handle_b": handle_b,
            "entity_a_id": str(entity_by_handle[handle_a].entity_id),
            "entity_b_id": str(entity_by_handle[handle_b].entity_id),
            "observation_ids": [str(item) for item in observation_ids],
            "relationship_id": str(relationship_id),
            "evidence_id": str(evidence_id),
        }

    finally:
        # Delete only records created by this fixture, in foreign-key-safe order.
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
                    delete(ObservationEntityModel).where(
                        ObservationEntityModel.observation_id.in_(
                            observation_ids
                        )
                    )
                )
                db.execute(
                    delete(ObservationModel).where(
                        ObservationModel.observation_id.in_(observation_ids)
                    )
                )

            if entity_ids:
                db.execute(
                    delete(ObservationEntityModel).where(
                        ObservationEntityModel.entity_id.in_(entity_ids)
                    )
                )
                db.execute(
                    delete(RelationshipModel).where(
                        (RelationshipModel.source_entity_id.in_(entity_ids))
                        | (RelationshipModel.target_entity_id.in_(entity_ids))
                    )
                )
                db.execute(
                    delete(EntityModel).where(
                        EntityModel.entity_id.in_(entity_ids)
                    )
                )

                if source_id is not None:
                    db.execute(
                        delete(ProcessingRunModel).where(
                            ProcessingRunModel.source_id == source_id
                        )
                    )
                db.execute(
                    delete(SourceModel).where(SourceModel.source_id == source_id)
                )

            db.commit()


def test_full_intelligence_pipeline_reaches_analysis_investigation_and_graph(
    intelligence_e2e_setup,
):
    setup = intelligence_e2e_setup
    relationship_id = setup["relationship_id"]

    # 1. Verify persisted evidence can be retrieved.
    evidence_response = client.get(f"/evidence/{setup['evidence_id']}")
    assert evidence_response.status_code == 200, evidence_response.text
    assert evidence_response.json()["relationship_id"] == relationship_id
    assert evidence_response.json()["polarity"] == "supports"

    # 2. Verify analysts can retrieve extraction provenance through the API.
    for entity_id in (setup["entity_a_id"], setup["entity_b_id"]):
        provenance_response = client.get(
            f"/entities/{entity_id}/provenance"
        )
        assert provenance_response.status_code == 200, (
            provenance_response.text
        )

        provenance = provenance_response.json()
        assert provenance["entity"]["entity_id"] == entity_id
        assert provenance["record_count"] == 1

        record = provenance["records"][0]
        assert record["source_id"] == str(setup["source_id"])
        assert record["authorized_for_use"] is True
        assert record["field_name"] == "handle"
        assert record["association_type"] == "extracted_handle"
        assert record["observation_id"] in setup["observation_ids"]
        assert "payload" not in record

    # 3. Verify the relationship analysis uses stored evidence.
    analysis_response = client.get(
        f"/relationships/{relationship_id}/analysis"
    )
    assert analysis_response.status_code == 200, analysis_response.text
    analysis = analysis_response.json()

    assert analysis["relationship_id"] == relationship_id
    assert analysis["supporting_count"] == 1
    assert setup["evidence_id"] in analysis["evidence_ids"]
    assert analysis["score"] == 100.0

    # One evidence item must not imply high-confidence attribution.
    assert analysis["confidence_band"] == "insufficient_evidence"

    # 4. Verify the investigation returns the same relationship and evidence.
    investigation_response = client.get(
        f"/entities/{setup['entity_a_id']}/investigation"
    )
    assert investigation_response.status_code == 200, (
        investigation_response.text
    )
    investigation = investigation_response.json()

    assert investigation["entity"]["entity_id"] == setup["entity_a_id"]
    assert investigation["relationship_count"] == 1
    assert investigation["evidence_record_count"] == 1

    investigation_relationship = investigation["relationships"][0]
    assert (
        investigation_relationship["relationship"]["relationship_id"]
        == relationship_id
    )
    assert investigation_relationship["connected_entity"]["entity_id"] == (
        setup["entity_b_id"]
    )
    assert [
        item["evidence"]["evidence_id"]
        for item in investigation_relationship["evidence_records"]
    ] == [setup["evidence_id"]]

    # 5. Verify the graph returns the same entities, relationship and evidence.
    graph_response = client.get(
        f"/entities/{setup['entity_a_id']}/graph",
        params={"depth": 1},
    )
    assert graph_response.status_code == 200, graph_response.text
    graph = graph_response.json()

    node_ids = {item["entity_id"] for item in graph["nodes"]}
    assert node_ids == {setup["entity_a_id"], setup["entity_b_id"]}
    assert graph["node_count"] == 2
    assert graph["edge_count"] == 1

    edge = next(
        item for item in graph["edges"]
        if item["relationship"]["relationship_id"] == relationship_id
    )
    assert setup["evidence_id"] in {
        item["evidence_id"] for item in edge["evidence"]
    }
    assert edge["analysis"]["relationship_id"] == relationship_id
    assert edge["analysis"]["confidence_band"] == "insufficient_evidence"
def test_analyst_search_returns_authorized_evidence_summaries(
    intelligence_e2e_setup,
):
    setup = intelligence_e2e_setup
    token = setup["handle_a"].split("_")[-1]

    response = client.get(
        "/entities/search/analyst",
        params={"value": token},
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["result_count"] == 2
    assert data["query"] == token
    assert len(data["results"]) == 2

    results = {
        item["entity"]["entity_id"]: item
        for item in data["results"]
    }

    for entity_id in (setup["entity_a_id"], setup["entity_b_id"]):
        item = results[entity_id]
        assert item["authorized_observation_count"] == 1
        assert item["authorized_source_count"] == 1
        assert item["supported_relationship_count"] == 1
        assert item["contradicting_evidence_count"] == 0


def test_analyst_search_pagination_and_empty_results(
    intelligence_e2e_setup,
):
    setup = intelligence_e2e_setup
    token = setup["handle_a"].split("_")[-1]

    first = client.get(
        "/entities/search/analyst",
        params={"value": token, "limit": 1, "offset": 0},
    )
    second = client.get(
        "/entities/search/analyst",
        params={"value": token, "limit": 1, "offset": 1},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["result_count"] == 2
    assert second.json()["result_count"] == 2
    assert len(first.json()["results"]) == 1
    assert len(second.json()["results"]) == 1

    assert (
        first.json()["results"][0]["entity"]["entity_id"]
        != second.json()["results"][0]["entity"]["entity_id"]
    )

    empty = client.get(
        "/entities/search/analyst",
        params={"value": f"no_match_{token}"},
    )

    assert empty.status_code == 200, empty.text
    assert empty.json()["result_count"] == 0
    assert empty.json()["results"] == []


def test_analyst_search_excludes_unauthorized_source_data(
    intelligence_e2e_setup,
):
    setup = intelligence_e2e_setup
    token = setup["handle_a"].split("_")[-1]

    # Temporarily revoke authorization for this fixture's source.
    with SessionLocal() as db:
        source = db.get(SourceModel, setup["source_id"])
        assert source is not None
        source.authorized_for_use = False
        db.commit()

    try:
        response = client.get(
            "/entities/search/analyst",
            params={"value": token},
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["result_count"] == 2

        for item in data["results"]:
            assert item["authorized_observation_count"] == 0
            assert item["authorized_source_count"] == 0
            assert item["supported_relationship_count"] == 0
            assert item["contradicting_evidence_count"] == 0
            assert item["last_observed_at"] is None
    finally:
        # Restore the fixture source so its normal teardown can proceed.
        with SessionLocal() as db:
            source = db.get(SourceModel, setup["source_id"])
            if source is not None:
                source.authorized_for_use = True
                db.commit()

def test_analyst_search_filters_by_entity_type(intelligence_e2e_setup):
    setup = intelligence_e2e_setup
    token = setup["handle_a"].split("_")[-1]

    # Search for matching handles only.
    response = client.get(
        "/entities/search/analyst",
        params={
            "value": token,
            "entity_type": "handle",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["result_count"] == 2
    assert len(data["results"]) == 2
    assert all(
        item["entity"]["entity_type"] == "handle"
        for item in data["results"]
    )

    # An unsupported entity type must be rejected.
    invalid_response = client.get(
        "/entities/search/analyst",
        params={
            "value": token,
            "entity_type": "invalid_type",
        },
    )

    assert invalid_response.status_code == 422

def test_analyst_search_sorts_by_latest_authorized_observation(
    intelligence_e2e_setup,
):
    setup = intelligence_e2e_setup
    token = setup["handle_a"].split("_")[-1]

    # Make handle A's observation newer than handle B's.
    # The entity creation order remains unchanged.
    with SessionLocal() as db:
        observations = db.scalars(
            select(ObservationModel).where(
                ObservationModel.observation_id.in_(
                    [UUID(item) for item in setup["observation_ids"]]
                )
            )
        ).all()

        observation_by_handle = {
            item.payload["handle"]: item for item in observations
        }

        observation_by_handle[setup["handle_a"]].observed_at = (
            datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        )
        observation_by_handle[setup["handle_b"]].observed_at = (
            datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
        )
        db.commit()

    response = client.get(
        "/entities/search/analyst",
        params={"value": token, "entity_type": "handle"},
    )

    assert response.status_code == 200, response.text
    results = response.json()["results"]

    assert len(results) == 2
    assert results[0]["entity"]["entity_id"] == setup["entity_a_id"]
    assert results[1]["entity"]["entity_id"] == setup["entity_b_id"]