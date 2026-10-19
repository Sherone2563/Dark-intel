
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import RelationshipType
from app.models.relationships import RelationshipRecord


def make_relationship(**overrides) -> RelationshipRecord:
    values = {
        "source_entity_id": uuid4(),
        "target_entity_id": uuid4(),
        "relationship_type": RelationshipType.RELATED_TO,
        "description": "Observed association in a research dataset",
    }
    values.update(overrides)
    return RelationshipRecord(**values)


def test_relationship_has_uuid_and_utc_creation_time() -> None:
    relationship = make_relationship()

    assert relationship.relationship_id is not None
    assert relationship.created_at.tzinfo is not None
    assert relationship.created_at.utcoffset().total_seconds() == 0


def test_relationship_connects_distinct_entities() -> None:
    entity_id = uuid4()

    with pytest.raises(ValidationError, match="distinct entities"):
        make_relationship(
            source_entity_id=entity_id,
            target_entity_id=entity_id,
        )


def test_relationship_accepts_valid_observation_timeline() -> None:
    first = datetime(2025, 1, 1, tzinfo=UTC)
    last = datetime(2025, 2, 1, tzinfo=UTC)

    relationship = make_relationship(
        first_observed_at=first,
        last_observed_at=last,
    )

    assert relationship.first_observed_at == first
    assert relationship.last_observed_at == last


def test_relationship_rejects_reversed_timeline() -> None:
    first = datetime(2025, 2, 1, tzinfo=UTC)
    last = datetime(2025, 1, 1, tzinfo=UTC)

    with pytest.raises(ValidationError, match="cannot precede"):
        make_relationship(
            first_observed_at=first,
            last_observed_at=last,
        )


def test_relationship_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        make_relationship(
            first_observed_at=datetime(2025, 1, 1),
        )


def test_relationship_is_immutable() -> None:
    relationship = make_relationship()

    with pytest.raises(ValidationError):
        relationship.description = "Changed description"


def test_relationship_rejects_blank_description() -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        make_relationship(description="   ")


def test_relationship_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        make_relationship(unexpected_field="not allowed")
