
from uuid import UUID

from app.models.entities import EntityRecord


class EntityServiceError(ValueError):
    """Raised when entity registry rules are violated."""


class EntityService:
    """In-memory registry for distinct entity records."""

    def __init__(self) -> None:
        self._entities: dict[UUID, EntityRecord] = {}

    def register_entity(self, entity: EntityRecord) -> EntityRecord:
        if entity.entity_id in self._entities:
            raise EntityServiceError(
                f"Entity already registered: {entity.entity_id}"
            )

        self._entities[entity.entity_id] = entity
        return entity

    def get_entity(self, entity_id: UUID) -> EntityRecord | None:
        return self._entities.get(entity_id)

    def list_entities(self) -> tuple[EntityRecord, ...]:
        return tuple(self._entities.values())
