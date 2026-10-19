
from uuid import UUID

from app.models.observations import ObservationRecord
from app.models.sources import SourceRecord


class ProvenanceError(ValueError):
    """Raised when source-to-observation provenance rules are violated."""


class ProvenanceService:
    """In-memory registry for authorized sources and their observations."""

    def __init__(self) -> None:
        self._sources: dict[UUID, SourceRecord] = {}
        self._observations: dict[UUID, ObservationRecord] = {}

    def register_source(self, source: SourceRecord) -> SourceRecord:
        if source.source_id in self._sources:
            raise ProvenanceError(
                f"Source already registered: {source.source_id}"
            )

        self._sources[source.source_id] = source
        return source

    def record_observation(
        self, observation: ObservationRecord
    ) -> ObservationRecord:
        source = self._sources.get(observation.source_id)

        if source is None:
            raise ProvenanceError(
                f"Unknown source: {observation.source_id}"
            )

        if not source.authorized_for_use:
            raise ProvenanceError(
                f"Source is not authorized for use: {source.source_id}"
            )

        if observation.observation_id in self._observations:
            raise ProvenanceError(
                f"Observation already recorded: {observation.observation_id}"
            )

        self._observations[observation.observation_id] = observation
        return observation

    def get_source(self, source_id: UUID) -> SourceRecord | None:
        return self._sources.get(source_id)

    def get_observation(
        self, observation_id: UUID
    ) -> ObservationRecord | None:
        return self._observations.get(observation_id)

    def list_observations(self) -> tuple[ObservationRecord, ...]:
        return tuple(self._observations.values())
