from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import EntityType


class EntityCreate(BaseModel):
    """Request to register a distinct research entity."""

    model_config = ConfigDict(extra="forbid")

    entity_type: EntityType
    canonical_value: str = Field(min_length=1, max_length=2048)
    display_value: str = Field(min_length=1, max_length=2048)
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None

    @field_validator("canonical_value", "display_value")
    @classmethod
    def values_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must not be blank.")
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
    def validate_chronology(self):
        first = self.first_observed_at
        last = self.last_observed_at
        if first is not None and last is not None and last < first:
            raise ValueError(
                "last_observed_at cannot precede first_observed_at."
            )
        return self


class EntityResponse(BaseModel):
    """Public representation of a persisted entity."""

    model_config = ConfigDict(from_attributes=True)

    entity_id: UUID
    entity_type: EntityType
    canonical_value: str
    display_value: str
    first_observed_at: datetime | None
    last_observed_at: datetime | None
    created_at: datetime
class AnalystEntitySearchResult(BaseModel):
    """Entity search result with authorized-data summary counts."""

    entity: EntityResponse
    authorized_observation_count: int
    authorized_source_count: int
    supported_relationship_count: int
    contradicting_evidence_count: int
    last_observed_at: datetime | None


class AnalystEntitySearchResponse(BaseModel):
    """Analyst-oriented entity search response."""

    results: list[AnalystEntitySearchResult]
    result_count: int
    query: str
    limit: int
    offset: int
