from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import RelationshipType


class RelationshipCreate(BaseModel):
    """Request to register a relationship between two known entities."""

    model_config = ConfigDict(extra="forbid")

    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: RelationshipType
    description: str | None = Field(default=None, max_length=2048)
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(
        cls, value: str | None
    ) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Description must not be blank.")
        return value

    @field_validator("first_observed_at", "last_observed_at")
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("Datetime must include a timezone.")
        return value

    @model_validator(mode="after")
    def validate_relationship(self) -> "RelationshipCreate":
        if self.source_entity_id == self.target_entity_id:
            raise ValueError(
                "A relationship must connect two distinct entities."
            )

        if (
            self.first_observed_at is not None
            and self.last_observed_at is not None
            and self.last_observed_at < self.first_observed_at
        ):
            raise ValueError(
                "last_observed_at cannot precede first_observed_at."
            )

        return self


class RelationshipResponse(BaseModel):
    """Public representation of a persisted relationship."""

    model_config = ConfigDict(from_attributes=True)

    relationship_id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: RelationshipType
    description: str | None
    first_observed_at: datetime | None
    last_observed_at: datetime | None
    created_at: datetime