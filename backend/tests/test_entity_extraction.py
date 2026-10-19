
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import Base, engine
from app.models.db_models import EntityModel, ObservationModel, SourceModel
from app.models.enums import EntityType
from app.services.entity_extraction import (
    extract_handles_from_source,
    normalize_handle,
)


@pytest.fixture
def isolated_db():
    schema = f"test_entity_extraction_{uuid4().hex}"
    quoted_schema = f'"{schema}"'

    with engine.connect() as connection:
        connection.exec_driver_sql(f"CREATE SCHEMA {quoted_schema}")
        connection.commit()

        try:
            connection.exec_driver_sql(
                f"SET search_path TO {quoted_schema}"
            )
            connection.commit()

            Base.metadata.create_all(bind=connection)

            # Keep all test transactions inside this connection.
            connection.commit()
            outer_transaction = connection.begin()
            db = Session(
                bind=connection,
                autoflush=False,
                expire_on_commit=False,
            )

            source_id = uuid4()
            now = datetime.now(timezone.utc)

            db.add(
                SourceModel(
                    source_id=source_id,
                    name="Isolated entity extraction test source",
                    source_type="synthetic",
                    reliability="unknown",
                    authorized_for_use=True,
                    authorization_note="Synthetic test data only",
                )
            )
            db.flush()

            db.add_all(
                [
                    ObservationModel(
                        source_id=source_id,
                        collected_at=now,
                        observed_at=datetime(
                            2026, 10, 15, 10, 0, tzinfo=timezone.utc
                        ),
                        payload={"handle": "Synthetic_Shadow_Alpha"},
                        content_sha256="a" * 64,
                        status="ingested",
                        processing_version="test",
                    ),
                    ObservationModel(
                        source_id=source_id,
                        collected_at=now,
                        observed_at=datetime(
                            2026, 10, 16, 12, 30, tzinfo=timezone.utc
                        ),
                        payload={"handle": "synthetic_shadow_beta"},
                        content_sha256="b" * 64,
                        status="ingested",
                        processing_version="test",
                    ),
                    ObservationModel(
                        source_id=source_id,
                        collected_at=now,
                        observed_at=datetime(
                            2026, 10, 16, 14, 0, tzinfo=timezone.utc
                        ),
                        payload={"handle": "synthetic_shadow_alpha"},
                        content_sha256="c" * 64,
                        status="ingested",
                        processing_version="test",
                    ),
                ]
            )
            db.commit()

            yield db, source_id

            db.close()
            outer_transaction.rollback()

        finally:
            connection.rollback()
            connection.exec_driver_sql("SET search_path TO public")
            connection.commit()
            connection.exec_driver_sql(
                f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE"
            )
            connection.commit()


def test_normalize_handle_trims_and_casefolds():
    assert normalize_handle("  Shadow_X  ") == "shadow_x"


def test_extraction_creates_and_matches_synthetic_handles(isolated_db):
    db, source_id = isolated_db

    result = extract_handles_from_source(db, source_id)

    entities = db.scalars(
        select(EntityModel).where(
            EntityModel.entity_type == EntityType.HANDLE.value,
            EntityModel.canonical_value.in_(
                ["synthetic_shadow_alpha", "synthetic_shadow_beta"]
            ),
        )
    ).all()

    assert result["observations_examined"] == 3
    assert result["entities_created"] == 2
    assert result["existing_entities_matched"] == 1
    assert result["observations_skipped"] == 0
    assert len(entities) == 2


def test_extraction_is_idempotent(isolated_db):
    db, source_id = isolated_db

    first = extract_handles_from_source(db, source_id)
    second = extract_handles_from_source(db, source_id)

    assert first["entities_created"] == 2
    assert second["entities_created"] == 0

    entities = db.scalars(
        select(EntityModel).where(
            EntityModel.entity_type == EntityType.HANDLE.value,
            EntityModel.canonical_value.in_(
                ["synthetic_shadow_alpha", "synthetic_shadow_beta"]
            ),
        )
    ).all()

    assert len(entities) == 2
