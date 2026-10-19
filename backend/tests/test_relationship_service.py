
from uuid import uuid4

import pytest

from app.models.entities import EntityRecord
from app.models.enums import EntityType, RelationshipType
from app.models.relationships import RelationshipRecord
from app.services.entity_service import EntityService
from app.services.relationship_service import (
    RelationshipService,
    RelationshipServiceError,
)


def make_entity(value: str) -> EntityRecord:
    return EntityRecord(
        entity_type=EntityType.HANDLE,
        canonical_value=value,
        display_value=value,
    )


def make_relationship(source_id, target_id) -> RelationshipRecord:
    return RelationshipRecord(
        source_entity_id=source_id,
        target_entity_id=target_id,
        relationship_type=RelationshipType.RELATED_TO,
        description="Synthetic test relationship",
    )


def make_context():
    entities = EntityService()
    source = make_entity("shadow_x")
    target = make_entity("shadowx")
    entities.register_entity(source)
    entities.register_entity(target)

    relationships = RelationshipService(entities)
    return entities, relationships, source, target


def test_entity_service_registers_and_retrieves_entity() -> None:
    service = EntityService()
    entity = make_entity("shadow_x")

    service.register_entity(entity)

    assert service.get_entity(entity.entity_id) == entity
    assert service.list_entities() == (entity,)


def test_entity_service_rejects_duplicate_id() -> None:
    service = EntityService()
    entity = make_entity("shadow_x")
    service.register_entity(entity)

    with pytest.raises(ValueError, match="already registered"):
        service.register_entity(entity)


def test_relationship_service_accepts_known_entities() -> None:
    _, service, source, target = make_context()
    relationship = make_relationship(
        source.entity_id, target.entity_id
    )

    result = service.register_relationship(relationship)

    assert result == relationship
    assert service.get_relationship(relationship.relationship_id) == relationship


def test_unknown_source_entity_is_rejected() -> None:
    _, service, _, target = make_context()
    relationship = make_relationship(uuid4(), target.entity_id)

    with pytest.raises(RelationshipServiceError, match="Unknown source entity"):
        service.register_relationship(relationship)


def test_unknown_target_entity_is_rejected() -> None:
    _, service, source, _ = make_context()
    relationship = make_relationship(source.entity_id, uuid4())

    with pytest.raises(RelationshipServiceError, match="Unknown target entity"):
        service.register_relationship(relationship)


def test_duplicate_relationship_registration_is_rejected() -> None:
    _, service, source, target = make_context()
    relationship = make_relationship(
        source.entity_id, target.entity_id
    )
    service.register_relationship(relationship)

    with pytest.raises(RelationshipServiceError, match="already registered"):
        service.register_relationship(relationship)


def test_similar_handles_remain_distinct_entities() -> None:
    service = EntityService()
    first = make_entity("shadow_x")
    second = make_entity("shadowx")

    service.register_entity(first)
    service.register_entity(second)

    assert first.entity_id != second.entity_id
    assert len(service.list_entities()) == 2
