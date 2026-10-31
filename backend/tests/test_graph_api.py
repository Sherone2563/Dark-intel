from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.db_models import (
    EntityModel,
    EvidenceModel,
    RelationshipModel,
)


client = TestClient(app)


@pytest.fixture
def graph_factory():
    created_entity_ids = []
    created_relationship_ids = []

    def create_entity(value: str | None = None) -> dict:
        value = value or f"graph_test_{uuid4().hex}"

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
                "description": "Synthetic graph test relationship",
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


def test_graph_returns_root_and_direct_neighbors(graph_factory):
    create_entity, create_relationship = graph_factory

    root = create_entity()
    neighbor = create_entity()
    distant = create_entity()

    create_relationship(root, neighbor)
    create_relationship(neighbor, distant)

    response = client.get(
        f"/entities/{root['entity_id']}/graph",
        params={"depth": 1},
    )

    assert response.status_code == 200, response.text

    graph = response.json()
    node_ids = {node["entity_id"] for node in graph["nodes"]}

    assert graph["root_entity_id"] == root["entity_id"]
    assert graph["depth"] == 1
    assert node_ids == {
        root["entity_id"],
        neighbor["entity_id"],
    }
    assert graph["node_count"] == 2
    assert graph["edge_count"] == 1


def test_graph_depth_two_includes_second_hop(graph_factory):
    create_entity, create_relationship = graph_factory

    root = create_entity()
    neighbor = create_entity()
    distant = create_entity()

    create_relationship(root, neighbor)
    create_relationship(neighbor, distant)

    response = client.get(
        f"/entities/{root['entity_id']}/graph",
        params={"depth": 2},
    )

    assert response.status_code == 200, response.text

    graph = response.json()
    node_ids = {node["entity_id"] for node in graph["nodes"]}

    assert node_ids == {
        root["entity_id"],
        neighbor["entity_id"],
        distant["entity_id"],
    }
    assert graph["node_count"] == 3
    assert graph["edge_count"] == 2


def test_graph_traverses_relationships_in_either_direction(
    graph_factory,
):
    create_entity, create_relationship = graph_factory

    original_source = create_entity()
    root = create_entity()

    relationship = create_relationship(original_source, root)

    response = client.get(
        f"/entities/{root['entity_id']}/graph",
        params={"depth": 1},
    )

    assert response.status_code == 200, response.text

    graph = response.json()
    node_ids = {node["entity_id"] for node in graph["nodes"]}
    edge_ids = {
        edge["relationship"]["relationship_id"]
        for edge in graph["edges"]
    }

    assert node_ids == {
        original_source["entity_id"],
        root["entity_id"],
    }
    assert relationship["relationship_id"] in edge_ids

    edge = next(
        edge
        for edge in graph["edges"]
        if edge["relationship"]["relationship_id"]
        == relationship["relationship_id"]
    )

    assert "evidence" in edge
    assert isinstance(edge["evidence"], list)

    assert "analysis" in edge
    assert (
        edge["analysis"]["relationship_id"]
        == relationship["relationship_id"]
    )
    assert "confidence_band" in edge["analysis"]
    assert "distinct_source_count" in edge["analysis"]
    assert "distinct_observation_count" in edge["analysis"]


def test_graph_does_not_duplicate_nodes_or_edges_in_a_cycle(
    graph_factory,
):
    create_entity, create_relationship = graph_factory

    first = create_entity()
    second = create_entity()
    third = create_entity()

    first_edge = create_relationship(first, second)
    second_edge = create_relationship(second, third)
    third_edge = create_relationship(third, first)

    response = client.get(
        f"/entities/{first['entity_id']}/graph",
        params={"depth": 3},
    )

    assert response.status_code == 200, response.text

    graph = response.json()
    node_ids = [node["entity_id"] for node in graph["nodes"]]
    edge_ids = [
        edge["relationship"]["relationship_id"]
        for edge in graph["edges"]
    ]

    assert len(node_ids) == len(set(node_ids)) == 3
    assert len(edge_ids) == len(set(edge_ids)) == 3

    assert set(edge_ids) == {
        first_edge["relationship_id"],
        second_edge["relationship_id"],
        third_edge["relationship_id"],
    }

    assert graph["node_count"] == len(graph["nodes"])
    assert graph["edge_count"] == len(graph["edges"])


def test_graph_rejects_unknown_root_entity():
    response = client.get(
        f"/entities/{uuid4()}/graph",
        params={"depth": 1},
    )

    assert response.status_code == 404


@pytest.mark.parametrize("depth", [0, 4])
def test_graph_rejects_invalid_depth(depth):
    response = client.get(
        f"/entities/{uuid4()}/graph",
        params={"depth": depth},
    )

    assert response.status_code == 422


def test_graph_never_exceeds_100_nodes(graph_factory):
    create_entity, create_relationship = graph_factory

    root = create_entity()
    neighbors = [create_entity() for _ in range(101)]

    for neighbor in neighbors:
        create_relationship(root, neighbor)

    response = client.get(
        f"/entities/{root['entity_id']}/graph",
        params={"depth": 1},
    )

    assert response.status_code == 200, response.text

    graph = response.json()
    node_ids = {node["entity_id"] for node in graph["nodes"]}

    assert graph["node_count"] <= 100
    assert len(graph["nodes"]) == graph["node_count"]
    assert graph["edge_count"] == len(graph["edges"])

    assert all(
        edge["relationship"]["source_entity_id"] in node_ids
        and edge["relationship"]["target_entity_id"] in node_ids
        for edge in graph["edges"]
    )


def test_graph_returns_isolated_root_with_no_edges(graph_factory):
    create_entity, _ = graph_factory
    root = create_entity()

    response = client.get(
        f"/entities/{root['entity_id']}/graph",
        params={"depth": 1},
    )

    assert response.status_code == 200, response.text

    graph = response.json()

    assert graph["root_entity_id"] == root["entity_id"]
    assert graph["node_count"] == 1
    assert graph["edge_count"] == 0
    assert len(graph["nodes"]) == 1
    assert graph["edges"] == []