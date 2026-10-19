
"""Extract explicitly observed handles into distinct intelligence entities."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.db_models import EntityModel, ObservationModel
from app.models.enums import EntityType


class EntityExtractionError(Exception):
    """Raised when extraction cannot safely complete."""


def normalize_handle(value: str) -> str:
    """Normalize a handle for exact matching, not attribution."""
    return value.strip().casefold()


def extract_handles_from_source(
    db: Session,
    source_id: UUID,
) -> dict[str, int]:
    """Create or match HANDLE entities from authorized source observations.

    Only an explicit non-empty string in payload['handle'] is extracted.
    Similar handles are never merged, and no relationships are created.
    """

    try:
        observations = db.scalars(
            select(ObservationModel)
            .where(ObservationModel.source_id == source_id)
            .order_by(ObservationModel.collected_at, ObservationModel.observation_id)
        ).all()

        created_count = 0
        matched_count = 0
        skipped_count = 0

        for observation in observations:
            raw_handle = observation.payload.get("handle")

            if not isinstance(raw_handle, str):
                skipped_count += 1
                continue

            display_value = raw_handle.strip()
            canonical_value = normalize_handle(raw_handle)

            if not canonical_value:
                skipped_count += 1
                continue

            existing = db.scalar(
                select(EntityModel).where(
                    EntityModel.entity_type == EntityType.HANDLE.value,
                    EntityModel.canonical_value == canonical_value,
                )
            )
            if existing is None:
                existing = next(
                    (
                        pending
                        for pending in db.new
                        if isinstance(pending,EntityModel)
                        and pending.entity_type == EntityType.HANDLE.value
                        and pending.canonical_value == canonical_value
                    ),
                    None,
                )

            observed_at: datetime | None = observation.observed_at

            if existing is not None:
                matched_count += 1

                # Preserve the earliest/latest known observation timestamps.
                if observed_at is not None:
                    if (
                        existing.first_observed_at is None
                        or observed_at < existing.first_observed_at
                    ):
                        existing.first_observed_at = observed_at

                    if (
                        existing.last_observed_at is None
                        or observed_at > existing.last_observed_at
                    ):
                        existing.last_observed_at = observed_at

                continue

            db.add(
                EntityModel(
                    entity_type=EntityType.HANDLE.value,
                    canonical_value=canonical_value,
                    display_value=display_value,
                    first_observed_at=observed_at,
                    last_observed_at=observed_at,
                )
            )
            created_count += 1

        db.commit()

        return {
            "observations_examined": len(observations),
            "entities_created": created_count,
            "existing_entities_matched": matched_count,
            "observations_skipped": skipped_count,
        }

    except SQLAlchemyError as exc:
        try:
            db.rollback()
        except SQLAlchemyError:
            pass

        raise EntityExtractionError(
            "Database error during handle extraction; changes from this "
            "extraction transaction were rolled back where possible."
        ) from exc
