
from uuid import UUID

from app.models.relationships import RelationshipRecord
from app.services.entity_service import EntityService


class RelationshipServiceError(ValueError):
    """Raised when relationship registry rules are violated."""


class RelationshipService:
    """Registers relationships between known entities."""

    def __init__(self, entity_service: EntityService) -> None:
        self._entity_service = entity_service
        self._relationships: dict[UUID, RelationshipRecord] = {}

    def register_relationship(
        self, relationship: RelationshipRecord
    ) -> RelationshipRecord:
        relationship_id = relationship.relationship_id

        if relationship_id in self._relationships:
            raise RelationshipServiceError(
                f"Relationship already registered: {relationship_id}"
            )

        if self._entity_service.get_entity(
            relationship.source_entity_id
        ) is None:
            raise RelationshipServiceError(
                f"Unknown source entity: {relationship.source_entity_id}"
            )

        if self._entity_service.get_entity(
            relationship.target_entity_id
        ) is None:
            raise RelationshipServiceError(
                f"Unknown target entity: {relationship.target_entity_id}"
            )

        self._relationships[relationship_id] = relationship
        return relationship

    def get_relationship(
        self, relationship_id: UUID
    ) -> RelationshipRecord | None:
        return self._relationships.get(relationship_id)

    def list_relationships(self) -> tuple[RelationshipRecord, ...]:
        return tuple(self._relationships.values())
