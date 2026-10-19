
from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import (
    ObservationStatus,
    SourceReliability,
    SourceType,
)
from app.models.observations import (
    ObservationRecord,
    calculate_payload_sha256,
)
from app.models.sources import SourceRecord


def test_source_defaults_to_unknown_reliability_and_not_authorized() -> None:
    source = SourceRecord(
        name="Sanitized research dataset",
        source_type=SourceType.RESEARCH_DATASET,
    )

    assert source.reliability == SourceReliability.UNKNOWN
    assert source.authorized_for_use is False


def test_blank_source_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceRecord(
            name="  ",
            source_type=SourceType.SYNTHETIC,
        )


def test_observation_accepts_matching_payload_hash() -> None:
    payload = {"handle": "shadow_x", "forum": "research_forum"}

    observation = ObservationRecord(
        source_id=uuid4(),
        payload=payload,
        content_sha256=calculate_payload_sha256(payload),
    )

    assert observation.status == ObservationStatus.INGESTED
    assert observation.content_sha256 == calculate_payload_sha256(payload)


def test_observation_rejects_incorrect_payload_hash() -> None:
    with pytest.raises(ValidationError, match="does not match"):
        ObservationRecord(
            source_id=uuid4(),
            payload={"handle": "shadow_x"},
            content_sha256="0" * 64,
        )


def test_payload_hash_is_independent_of_dictionary_key_order() -> None:
    first = {"handle": "shadow_x", "forum": "research_forum"}
    second = {"forum": "research_forum", "handle": "shadow_x"}

    assert calculate_payload_sha256(first) == calculate_payload_sha256(second)


def test_observation_rejects_naive_collection_timestamp() -> None:
    payload = {"handle": "shadow_x"}

    with pytest.raises(ValidationError):
        ObservationRecord(
            source_id=uuid4(),
            collected_at=datetime(2026, 10, 15, 10, 0),
            payload=payload,
            content_sha256=calculate_payload_sha256(payload),
        )


def test_observation_rejects_non_json_payload() -> None:
    payload = {"unsupported": object()}

    with pytest.raises(ValidationError, match="valid JSON"):
        ObservationRecord(
            source_id=uuid4(),
            payload=payload,
            content_sha256="0" * 64,
        )
