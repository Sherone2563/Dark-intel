from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DatasetObservationInput(BaseModel):
    """One validated observation record from a JSONL research dataset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("Timestamps must include a timezone.")
        return value


class DatasetLineError(BaseModel):
    """Validation or persistence failure associated with an input line."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    line_number: int = Field(ge=1)
    error: str = Field(min_length=1)


class ParsedDatasetRecord(BaseModel):
    """A validated record retaining its original JSONL line number."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    line_number: int = Field(ge=1)
    record: DatasetObservationInput


class DatasetParseResult(BaseModel):
    """Results of parsing JSONL without database writes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    records: tuple[ParsedDatasetRecord, ...]
    errors: tuple[DatasetLineError, ...]

    @property
    def accepted_count(self) -> int:
        return len(self.records)

    @property
    def rejected_count(self) -> int:
        return len(self.errors)


class DatasetImportResult(BaseModel):
    """Summary of one dataset import attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: UUID
    total_lines: int = Field(ge=0)
    parsed_count: int = Field(ge=0)
    imported_count: int = Field(ge=0)
    skipped_duplicate_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    errors: tuple[DatasetLineError, ...] = ()


class DatasetImportError(Exception):
    """Raised when a source cannot be used for dataset ingestion."""