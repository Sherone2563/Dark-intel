from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.entities import EntityRecord
from app.models.enums import EntityType


def test_entity_record_has_uuid_and_utc_creation_time() -> None:
    entity = EntityRecord(
        entity_type=EntityType.HANDLE,
        canonical_value="shadow_x",
        display_value="shadow_x",
    )

    assert entity.entity_id is not None
    assert entity.created_at.tzinfo is not None


def test_similar_handles_remain_distinct_records() -> None:
    first = EntityRecord(
        entity_type=EntityType.HANDLE,
        canonical_value="shadow_x",
        display_value="shadow_x",
    )
    second = EntityRecord(
        entity_type=EntityType.HANDLE,
        canonical_value="shadowx",
        display_value="shadowx",
    )

    assert first.entity_id != second.entity_id
    assert first.canonical_value != second.canonical_value


def test_blank_entity_value_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EntityRecord(
            entity_type=EntityType.HANDLE,
            canonical_value="   ",
            display_value="shadow_x",
        )


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EntityRecord(
            entity_type=EntityType.HANDLE,
            canonical_value="shadow_x",
            display_value="shadow_x",
            first_observed_at=datetime(2026, 10, 11, 10, 0),
        )


def test_last_observation_cannot_precede_first() -> None:
    with pytest.raises(ValidationError):
        EntityRecord(
            entity_type=EntityType.HANDLE,
            canonical_value="shadow_x",
            display_value="shadow_x",
            first_observed_at=datetime(2026, 10, 11, 12, 0, tzinfo=UTC),
            last_observed_at=datetime(2026, 10, 10, 12, 0, tzinfo=UTC),
        )


def test_entity_record_is_immutable() -> None:
    entity = EntityRecord(
        entity_type=EntityType.HANDLE,
        canonical_value="shadow_x",
        display_value="shadow_x",
    )

    with pytest.raises(ValidationError):
        entity.canonical_value = "shadowx"