"""Extract explicitly observed entities and record their provenance."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.db_models import (
    EntityModel,
    ObservationEntityModel,
    ObservationModel,
    SourceModel,
)
from app.models.enums import EntityType


class EntityExtractionError(Exception):
    """Raised when extraction cannot safely complete."""


def normalize_handle(value: str) -> str:
    """Normalize a handle for exact matching, not attribution."""
    return value.strip().casefold()


def normalize_identifier(value: str) -> str:
    """Normalize an explicitly identified research identifier."""
    return value.strip().casefold()


def _extract_candidates(payload: dict) -> list[tuple]:
    """Return explicitly identified entity values from an observation."""

    candidates = []

    # Support the existing singular handle field.
    handle = payload.get("handle")

    if isinstance(handle, str) and handle.strip():
        candidates.append(
            (
                EntityType.HANDLE,
                handle,
                "handle",
                "extracted_handle",
                "strip_casefold_v1",
            )
        )

    # Support observations containing multiple explicitly named handles.
    handles = payload.get("handles")

    if isinstance(handles, list):
        for handle_value in handles:
            if isinstance(handle_value, str) and handle_value.strip():
                candidates.append(
                    (
                        EntityType.HANDLE,
                        handle_value,
                        "handles",
                        "extracted_handle",
                        "strip_casefold_v1",
                    )
                )

    # Extract a PGP key only when the payload explicitly identifies
    # the shared identifier as a PGP key.
    shared_identifier = payload.get("shared_identifier")
    identifier_type = payload.get("identifier_type")

    if (
        identifier_type == EntityType.PGP_KEY.value
        and isinstance(shared_identifier, str)
        and shared_identifier.strip()
    ):
        candidates.append(
            (
                EntityType.PGP_KEY,
                shared_identifier,
                "shared_identifier",
                "extracted_pgp_key",
                "strip_casefold_v1",
            )
        )

    return candidates


def extract_handles_from_source(
    db: Session,
    source_id: UUID,
) -> dict[str, int]:
    """Extract supported entities from observations of an authorized source.

    Despite the legacy function name, this extracts explicitly identified
    handles and PGP keys. It never creates relationships or merges entities.
    """

    try:
        source = db.get(SourceModel, source_id)

        if source is None:
            raise EntityExtractionError(
                "Cannot extract entities: source does not exist."
            )

        if not source.authorized_for_use:
            raise EntityExtractionError(
                "Cannot extract entities: source is not authorized for use."
            )

        observations = db.scalars(
            select(ObservationModel)
            .where(ObservationModel.source_id == source_id)
            .order_by(
                ObservationModel.collected_at,
                ObservationModel.observation_id,
            )
        ).all()

        entities_created = 0
        entities_matched = 0
        observations_skipped = 0
        associations_created = 0
        handles_processed = 0
        pgp_keys_processed = 0

        for observation in observations:
            candidates = _extract_candidates(observation.payload)

            if not candidates:
                observations_skipped += 1
                continue

            observed_at: datetime | None = observation.observed_at

            for (
                entity_type,
                raw_value,
                field_name,
                association_type,
                normalization_method,
            ) in candidates:

                if entity_type == EntityType.HANDLE:
                    canonical_value = normalize_handle(raw_value)
                else:
                    canonical_value = normalize_identifier(raw_value)

                if not canonical_value:
                    continue

                display_value = raw_value.strip()

                insert_stmt = (
                    pg_insert(EntityModel)
                    .values(
                        entity_type=entity_type.value,
                        canonical_value=canonical_value,
                        display_value=display_value,
                        first_observed_at=observed_at,
                        last_observed_at=observed_at,
                    )
                    .on_conflict_do_nothing(
                        constraint="uq_entities_type_canonical_value"
                    )
                    .returning(EntityModel.entity_id)
                )

                inserted_entity_id = db.execute(
                    insert_stmt
                ).scalar_one_or_none()

                if inserted_entity_id is not None:
                    existing = db.get(EntityModel, inserted_entity_id)

                    if existing is None:
                        raise EntityExtractionError(
                            "Inserted entity could not be retrieved."
                        )

                    entities_created += 1

                else:
                    existing = db.scalar(
                        select(EntityModel).where(
                            EntityModel.entity_type == entity_type.value,
                            EntityModel.canonical_value == canonical_value,
                        )
                    )

                    if existing is None:
                        raise EntityExtractionError(
                            "Entity conflict occurred, but the existing "
                            "entity could not be retrieved."
                        )

                    entities_matched += 1

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

                association_stmt = (
                    pg_insert(ObservationEntityModel)
                    .values(
                        observation_id=observation.observation_id,
                        entity_id=existing.entity_id,
                        association_type=association_type,
                        field_name=field_name,
                        normalization_method=normalization_method,
                    )
                    .on_conflict_do_nothing(
                        constraint=(
                            "uq_observation_entities_observation_entity_field"
                        )
                    )
                    .returning(ObservationEntityModel.association_id)
                )

                association_id = db.execute(
                    association_stmt
                ).scalar_one_or_none()

                if association_id is not None:
                    associations_created += 1

                if entity_type == EntityType.HANDLE:
                    handles_processed += 1
                elif entity_type == EntityType.PGP_KEY:
                    pgp_keys_processed += 1

        db.commit()

        return {
            "observations_examined": len(observations),
            "entities_created": entities_created,
            "existing_entities_matched": entities_matched,
            "observations_skipped": observations_skipped,
            "associations_created": associations_created,
            "handles_processed": handles_processed,
            "pgp_keys_processed": pgp_keys_processed,
        }

    except EntityExtractionError:
        try:
            db.rollback()
        except SQLAlchemyError:
            pass
        raise

    except SQLAlchemyError as exc:
        try:
            db.rollback()
        except SQLAlchemyError:
            pass

        raise EntityExtractionError(
            "Database error during handle extraction; changes from this "
            "extraction transaction were rolled back where possible."
        ) from exc