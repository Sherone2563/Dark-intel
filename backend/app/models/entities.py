
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import EntityType


class EntityRecord(BaseModel):
    """A distinct object identified in authorized research data."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    entity_id: UUID = Field(default_factory=uuid4)
    entity_type: EntityType
    canonical_value: str = Field(min_length=1, max_length=2048)
    display_value: str = Field(min_length=1, max_length=2048)
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )

    @field_validator("canonical_value", "display_value")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must not be blank.")
        return value

    @field_validator(
        "first_observed_at",
        "last_observed_at",
        "created_at",
    )
    @classmethod
    def require_timezone_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("Datetime must include a timezone.")
        return value

    @field_validator("last_observed_at")
    @classmethod
    def last_observation_not_before_first(
        cls, value: datetime | None, info
    ) -> datetime | None:
        first = info.data.get("first_observed_at")
        if value is not None and first is not None and value < first:
            raise ValueError(
                "last_observed_at cannot precede first_observed_at."
            )
        return value
