from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.models.enums import EvidencePolarity


class EvidenceCreate(BaseModel):
    """Request to attach evidence to a relationship."""

    model_config = ConfigDict(extra="forbid")

    relationship_id: UUID
    observation_id: UUID
    polarity: EvidencePolarity
    evidence_description: str = Field(min_length=1, max_length=2048)
    limitations: str | None = Field(default=None, max_length=2048)
    observed_at: datetime | None = None

    @field_validator("evidence_description", "limitations")
    @classmethod
    def reject_blank_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Text must not be blank.")
        return value

    @field_validator("observed_at")
    @classmethod
    def timestamp_must_be_timezone_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("Datetime must include a timezone.")
        return value


class EvidenceResponse(BaseModel):
    """Public representation of persisted evidence."""

    model_config = ConfigDict(from_attributes=True)

    evidence_id: UUID
    relationship_id: UUID
    observation_id: UUID
    polarity: EvidencePolarity
    evidence_description: str
    limitations: str | None
    observed_at: datetime | None
    created_at: datetime