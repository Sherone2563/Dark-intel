from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import SourceReliability, SourceType


class SourceCreate(BaseModel):
    """Validated request to register a research source."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    source_type: SourceType
    reference: str | None = Field(default=None, max_length=2048)
    reliability: SourceReliability = SourceReliability.UNKNOWN
    authorized_for_use: bool
    authorization_note: str = Field(min_length=1, max_length=1024)

    @field_validator("name", "authorization_note")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("This field must not be blank.")
        return value.strip()


class SourceResponse(BaseModel):
    """Public representation of a persisted source."""

    model_config = ConfigDict(from_attributes=True)

    source_id: UUID
    name: str
    source_type: SourceType
    reference: str | None
    reliability: SourceReliability
    authorized_for_use: bool
    authorization_note: str | None
    created_at: datetime