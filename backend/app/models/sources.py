
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import SourceReliability, SourceType


class SourceRecord(BaseModel):
    """Provenance metadata for an authorized research source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=256)
    source_type: SourceType
    reference: str | None = Field(default=None, max_length=2048)
    reliability: SourceReliability = SourceReliability.UNKNOWN
    authorized_for_use: bool = False
    authorization_note: str | None = Field(default=None, max_length=1024)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Source name must not be blank.")
        return value

    @field_validator("created_at")
    @classmethod
    def creation_time_must_be_timezone_aware(
        cls, value: datetime
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include a timezone.")
        return value
