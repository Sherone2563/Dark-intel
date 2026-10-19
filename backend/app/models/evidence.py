
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.models.enums import EvidencePolarity


class EvidenceRecord(BaseModel):
    """An auditable item of evidence linked to a relationship claim."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    evidence_id: UUID = Field(default_factory=uuid4)

    relationship_id: UUID
    observation_id: UUID

    polarity: EvidencePolarity
    evidence_description: str = Field(
        min_length=1,
        max_length=2048,
    )
    limitations: str | None = Field(
        default=None,
        max_length=2048,
    )

    observed_at: datetime | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )

    @field_validator("evidence_description", "limitations")
    @classmethod
    def reject_blank_text(
        cls, value: str | None
    ) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Text must not be blank.")

        return value

    @field_validator("observed_at", "created_at")
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("Datetime must include a timezone.")

        return value
