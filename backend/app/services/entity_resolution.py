"""Read-only candidate matching for handle entities."""

from difflib import SequenceMatcher
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import EntityRecord
from app.models.enums import EntityType


class HandleCandidate(BaseModel):
    """A possible string-similarity match, not an attribution conclusion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: UUID
    canonical_value: str
    display_value: str
    similarity_score: float = Field(ge=0.0, le=1.0)


class EntityResolutionService:
    """Suggest similar handles without modifying entities or relationships."""

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().casefold()

    def find_handle_candidates(
        self,
        query: EntityRecord,
        entities: list[EntityRecord] | tuple[EntityRecord, ...],
        *,
        min_similarity: float = 0.0,
    ) -> list[HandleCandidate]:
        """Return ranked handle candidates; never merge or persist records."""
        if query.entity_type != EntityType.HANDLE:
            raise ValueError("The query entity must be a handle.")

        if not 0.0 <= min_similarity <= 1.0:
            raise ValueError("min_similarity must be between 0 and 1.")

        normalized_query = self._normalize(query.canonical_value)
        candidates: list[HandleCandidate] = []

        for entity in entities:
            if entity.entity_id == query.entity_id:
                continue
            if entity.entity_type != EntityType.HANDLE:
                continue

            normalized_candidate = self._normalize(entity.canonical_value)
            if not normalized_query or not normalized_candidate:
                continue

            score = SequenceMatcher(
                None,
                normalized_query,
                normalized_candidate,
            ).ratio()

            if score < min_similarity:
                continue

            candidates.append(
                HandleCandidate(
                    entity_id=entity.entity_id,
                    canonical_value=entity.canonical_value,
                    display_value=entity.display_value,
                    similarity_score=score,
                )
            )

        candidates.sort(
            key=lambda candidate: (
                -candidate.similarity_score,
                candidate.canonical_value.casefold(),
                str(candidate.entity_id),
            )
        )
        return candidates
