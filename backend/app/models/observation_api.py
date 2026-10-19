from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ObservationStatus


class ObservationCreate(BaseModel):
    """Request to ingest an observation from a registered source."""

    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    payload: dict[str, Any]
    collected_at: datetime | None = None
    observed_at: datetime | None = None
    processing_version: str = Field(
        default="0.1.0",
        min_length=1,
        max_length=64,
    )

    @field_validator("collected_at", "observed_at")
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("Timestamps must include a timezone.")
        return value


class ObservationResponse(BaseModel):
    """Public representation of a persisted observation."""

    model_config = ConfigDict(from_attributes=True)

    observation_id: UUID
    source_id: UUID
    collected_at: datetime
    observed_at: datetime | None
    payload: dict[str, Any]
    content_sha256: str
    status: ObservationStatus
    processing_version: str
    created_at: datetime