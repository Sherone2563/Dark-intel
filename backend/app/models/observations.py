
import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ObservationStatus


class ObservationRecord(BaseModel):
    """A source-linked, integrity-checkable research observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    observed_at: datetime | None = None
    payload: dict[str, Any]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: ObservationStatus = ObservationStatus.INGESTED
    processing_version: str = Field(default="0.1.0", min_length=1, max_length=64)

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

    @field_validator("payload")
    @classmethod
    def payload_must_be_json_serializable(
        cls, value: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("Payload must contain valid JSON data.") from exc
        return value

    @model_validator(mode="after")
    def payload_hash_must_match(self) -> "ObservationRecord":
        canonical_payload = json.dumps(
            self.payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        expected_hash = hashlib.sha256(canonical_payload).hexdigest()

        if self.content_sha256 != expected_hash:
            raise ValueError("content_sha256 does not match the payload.")
        return self


def calculate_payload_sha256(payload: dict[str, Any]) -> str:
    """Hash a deterministic JSON representation of a payload."""
    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical_payload).hexdigest()
