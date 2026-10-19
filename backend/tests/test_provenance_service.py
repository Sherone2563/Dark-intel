
from uuid import uuid4

import pytest

from app.models.enums import SourceType
from app.models.observations import (
    ObservationRecord,
    calculate_payload_sha256,
)
from app.models.sources import SourceRecord
from app.services.provenance_service import (
    ProvenanceError,
    ProvenanceService,
)


def make_source(*, authorized: bool = True) -> SourceRecord:
    return SourceRecord(
        name="Synthetic research fixture",
        source_type=SourceType.SYNTHETIC,
        authorized_for_use=authorized,
    )


def make_observation(source_id) -> ObservationRecord:
    payload = {"handle": "shadow_x"}
    return ObservationRecord(
        source_id=source_id,
        payload=payload,
        content_sha256=calculate_payload_sha256(payload),
    )


def test_authorized_source_can_record_observation() -> None:
    service = ProvenanceService()
    source = make_source()
    service.register_source(source)

    observation = make_observation(source.source_id)
    recorded = service.record_observation(observation)

    assert recorded == observation
    assert service.get_observation(observation.observation_id) == observation


def test_unknown_source_is_rejected() -> None:
    service = ProvenanceService()
    observation = make_observation(uuid4())

    with pytest.raises(ProvenanceError, match="Unknown source"):
        service.record_observation(observation)


def test_unauthorized_source_is_rejected() -> None:
    service = ProvenanceService()
    source = make_source(authorized=False)
    service.register_source(source)

    with pytest.raises(ProvenanceError, match="not authorized"):
        service.record_observation(make_observation(source.source_id))


def test_duplicate_source_registration_is_rejected() -> None:
    service = ProvenanceService()
    source = make_source()
    service.register_source(source)

    with pytest.raises(ProvenanceError, match="already registered"):
        service.register_source(source)


def test_duplicate_observation_is_rejected() -> None:
    service = ProvenanceService()
    source = make_source()
    service.register_source(source)
    observation = make_observation(source.source_id)

    service.record_observation(observation)

    with pytest.raises(ProvenanceError, match="already recorded"):
        service.record_observation(observation)


def test_observations_can_be_listed() -> None:
    service = ProvenanceService()
    source = make_source()
    service.register_source(source)
    observation = make_observation(source.source_id)

    service.record_observation(observation)

    assert service.list_observations() == (observation,)
