from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.sql.dml import Insert
from threading import Barrier
from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.orm import Session
from app.core.database import Base, engine
from app.models.db_models import (
    EntityModel,
    ObservationEntityModel,
    ObservationModel,
    SourceModel,
)
from app.models.enums import EntityType
from app.services.entity_extraction import (
    EntityExtractionError,
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
            connection.commit()

            # The fixture owns the outer transaction. Session commits use
            # savepoints so test data can be rolled back during teardown.
            outer_transaction = connection.begin()
            db = Session(
                bind=connection,
                autoflush=False,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
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

        finally:
            if "db" in locals():
                db.close()

            if (
                "outer_transaction" in locals()
                and outer_transaction.is_active
            ):
                outer_transaction.rollback()

            connection.rollback()
            connection.exec_driver_sql("SET search_path TO public")
            connection.commit()
            connection.exec_driver_sql(
                f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE"
            )
            connection.commit()


def test_normalize_handle_trims_and_casefolds():
    assert normalize_handle("  Shadow_X  ") == "shadow_x"


def test_entity_identity_includes_entity_type(isolated_db):
    db, _ = isolated_db

    handle = EntityModel(
        entity_type=EntityType.HANDLE.value,
        canonical_value="shared-synthetic-value",
        display_value="shared-synthetic-value",
    )
    domain = EntityModel(
        entity_type=EntityType.DOMAIN.value,
        canonical_value="shared-synthetic-value",
        display_value="shared-synthetic-value",
    )

    db.add_all([handle, domain])
    db.commit()

    entities = db.scalars(
        select(EntityModel).where(
            EntityModel.canonical_value == "shared-synthetic-value"
        )
    ).all()

    assert len(entities) == 2
    assert {entity.entity_type for entity in entities} == {
        EntityType.HANDLE.value,
        EntityType.DOMAIN.value,
    }


def test_duplicate_entity_identity_is_rejected(isolated_db):
    db, _ = isolated_db

    first = EntityModel(
        entity_type=EntityType.HANDLE.value,
        canonical_value="duplicate-synthetic-handle",
        display_value="duplicate-synthetic-handle",
    )
    second = EntityModel(
        entity_type=EntityType.HANDLE.value,
        canonical_value="duplicate-synthetic-handle",
        display_value="duplicate-synthetic-handle",
    )

    db.add(first)
    db.commit()

    db.add(second)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()

def test_extraction_rolls_back_on_application_error(
    isolated_db, monkeypatch
):
    db, source_id = isolated_db
    original_execute = db.execute

    def fail_on_second_provenance_insert(statement, *args, **kwargs):
        if (
            isinstance(statement, Insert)
            and statement.table.name == "observation_entities"
        ):
            count = getattr(
                fail_on_second_provenance_insert,
                "count",
                0,
            ) + 1
            fail_on_second_provenance_insert.count = count

            if count == 2:
                raise EntityExtractionError(
                    "Simulated application-level extraction failure"
                )

        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db, "execute", fail_on_second_provenance_insert)

    with pytest.raises(
        EntityExtractionError,
        match="Simulated application-level extraction failure",
    ):
        extract_handles_from_source(db, source_id)

    monkeypatch.setattr(db, "execute", original_execute)

    assert db.scalars(select(EntityModel)).all() == []
    assert db.scalars(select(ObservationEntityModel)).all() == []

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

    associations = db.scalars(
        select(ObservationEntityModel).order_by(
            ObservationEntityModel.observation_id
        )
    ).all()

    assert len(associations) == 3
    assert all(
        association.association_type == "extracted_handle"
        for association in associations
    )
    assert all(
        association.field_name == "handle"
        for association in associations
    )
    assert all(
        association.normalization_method == "strip_casefold_v1"
        for association in associations
    )
    assert len({a.observation_id for a in associations}) == 3


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

    associations = db.scalars(
        select(ObservationEntityModel)
    ).all()

    assert len(associations) == 3
    assert len(
        {
            (a.observation_id, a.entity_id, a.field_name)
            for a in associations
        }
    ) == 3

def test_extraction_rolls_back_on_provenance_database_error(
    isolated_db, monkeypatch
):
    db, source_id = isolated_db
    original_execute = db.execute
    def fail_on_provenance_insert(statement, *args, **kwargs):
        if (
            isinstance(statement, Insert)
            and statement.table.name == "observation_entities"
        ):
            raise SQLAlchemyError(
                "simulated provenance database failure"
            )

        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db, "execute", fail_on_provenance_insert)

    with pytest.raises(
        EntityExtractionError,
        match="Database error during handle extraction",
    ):
        extract_handles_from_source(db, source_id)

    monkeypatch.setattr(db, "execute", original_execute)

    entities = db.scalars(select(EntityModel)).all()
    associations = db.scalars(
        select(ObservationEntityModel)
    ).all()

    assert entities == []
    assert associations == []


def test_extraction_rejects_unauthorized_source(isolated_db):
    db, source_id = isolated_db

    source = db.get(SourceModel, source_id)
    assert source is not None

    source.authorized_for_use = False
    db.commit()

    with pytest.raises(
        EntityExtractionError,
        match="source is not authorized for use",
    ):
        extract_handles_from_source(db, source_id)

    entities = db.scalars(select(EntityModel)).all()
    associations = db.scalars(
        select(ObservationEntityModel)
    ).all()

    assert entities == []
    assert associations == []


def test_extraction_rejects_nonexistent_source(isolated_db):
    db, _ = isolated_db
    nonexistent_source_id = uuid4()

    with pytest.raises(
        EntityExtractionError,
        match="source does not exist",
    ):
        extract_handles_from_source(db, nonexistent_source_id)

    entities = db.scalars(select(EntityModel)).all()
    associations = db.scalars(
        select(ObservationEntityModel)
    ).all()

    assert entities == []
    assert associations == []

def test_concurrent_extraction_creates_no_duplicate_entities_or_associations():
    schema = f"test_entity_extraction_concurrent_{uuid4().hex}"
    quoted_schema = f'"{schema}"'
    source_id = uuid4()

    with engine.connect() as connection:
        connection.exec_driver_sql(f"CREATE SCHEMA {quoted_schema}")
        connection.commit()

        try:
            connection.exec_driver_sql(
                f"SET search_path TO {quoted_schema}"
            )
            connection.commit()

            Base.metadata.create_all(bind=connection)
            connection.commit()

            setup_db = Session(
                bind=connection,
                autoflush=False,
                expire_on_commit=False,
            )

            now = datetime.now(timezone.utc)

            setup_db.add(
                SourceModel(
                    source_id=source_id,
                    name="Concurrent synthetic extraction test",
                    source_type="synthetic",
                    reliability="unknown",
                    authorized_for_use=True,
                    authorization_note="Synthetic test data only",
                )
            )
            setup_db.flush()

            setup_db.add_all(
                [
                    ObservationModel(
                        source_id=source_id,
                        collected_at=now,
                        observed_at=now,
                        payload={"handle": "Concurrent_Shadow_Alpha"},
                        content_sha256="d" * 64,
                        status="ingested",
                        processing_version="test",
                    ),
                    ObservationModel(
                        source_id=source_id,
                        collected_at=now,
                        observed_at=now,
                        payload={"handle": "concurrent_shadow_alpha"},
                        content_sha256="e" * 64,
                        status="ingested",
                        processing_version="test",
                    ),
                ]
            )
            setup_db.commit()
            setup_db.close()

            barrier = Barrier(2)

            def run_extraction():
                with engine.connect() as worker_connection:
                    worker_connection.exec_driver_sql(
                        f"SET search_path TO {quoted_schema}"
                    )
                    worker_connection.commit()

                    with Session(
                        bind=worker_connection,
                        autoflush=False,
                        expire_on_commit=False,
                    ) as worker_db:
                        barrier.wait(timeout=10)
                        return extract_handles_from_source(
                            worker_db,
                            source_id,
                        )

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(run_extraction),
                    executor.submit(run_extraction),
                ]
                results = [future.result(timeout=30) for future in futures]

            # Verify the final database state independently.
            with engine.connect() as verify_connection:
                verify_connection.exec_driver_sql(
                    f"SET search_path TO {quoted_schema}"
                )
                verify_connection.commit()

                with Session(
                    bind=verify_connection,
                    autoflush=False,
                    expire_on_commit=False,
                ) as verify_db:
                    entities = verify_db.scalars(
                        select(EntityModel).where(
                            EntityModel.entity_type
                            == EntityType.HANDLE.value,
                            EntityModel.canonical_value
                            == "concurrent_shadow_alpha",
                        )
                    ).all()

                    associations = verify_db.scalars(
                        select(ObservationEntityModel)
                    ).all()

                    assert len(entities) == 1
                    assert len(associations) == 2
                    assert len(
                        {
                            (
                                association.observation_id,
                                association.entity_id,
                                association.field_name,
                            )
                            for association in associations
                        }
                    ) == 2

                    assert sum(
                        result["entities_created"] for result in results
                    ) == 1

        finally:
            with engine.connect() as cleanup_connection:
                cleanup_connection.exec_driver_sql(
                    f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE"
                )
                cleanup_connection.commit()

                engine.dispose()

def test_extracts_multiple_handles_and_pgp_key(isolated_db):
    db, source_id = isolated_db

    now = datetime(2026, 10, 16, 14, 30, tzinfo=timezone.utc)

    observation = ObservationModel(
        source_id=source_id,
        collected_at=now,
        observed_at=now,
        payload={
            "dataset": "cli_smoke_test",
            "handles": [
                "synthetic_shadow_alpha",
                "synthetic_shadow_beta",
            ],
            "identifier_type": "pgp_key",
            "shared_identifier": "synthetic_pgp_key_001",
        },
        content_sha256="f" * 64,
        status="ingested",
        processing_version="test",
    )

    db.add(observation)
    db.commit()

    result = extract_handles_from_source(db, source_id)

    assert result["handles_processed"] == 5
    assert result["pgp_keys_processed"] == 1
    assert result["entities_created"] == 3
    assert result["existing_entities_matched"] == 3
    assert result["observations_skipped"] == 0
    assert result["associations_created"] == 6

    entities = db.scalars(
        select(EntityModel)
    ).all()

    extracted_entities = {
        (entity.entity_type, entity.canonical_value)
        for entity in entities
    }

    assert (
        EntityType.HANDLE.value,
        "synthetic_shadow_alpha",
    ) in extracted_entities

    assert (
        EntityType.HANDLE.value,
        "synthetic_shadow_beta",
    ) in extracted_entities

    assert (
        EntityType.PGP_KEY.value,
        "synthetic_pgp_key_001",
    ) in extracted_entities

    associations = db.scalars(
        select(ObservationEntityModel).where(
            ObservationEntityModel.observation_id
            == observation.observation_id
        )
    ).all()

    assert len(associations) == 3

    assert {
        (association.field_name, association.association_type)
        for association in associations
    } == {
        ("handles", "extracted_handle"),
        ("shared_identifier", "extracted_pgp_key"),
    } - set()


def test_new_entity_extraction_is_idempotent(isolated_db):
    db, source_id = isolated_db

    now = datetime.now(timezone.utc)

    observation = ObservationModel(
        source_id=source_id,
        collected_at=now,
        observed_at=now,
        payload={
            "handles": [
                "synthetic_shadow_alpha",
                "synthetic_shadow_beta",
            ],
            "identifier_type": "pgp_key",
            "shared_identifier": "synthetic_pgp_key_001",
        },
        content_sha256="9" * 64,
        status="ingested",
        processing_version="test",
    )

    db.add(observation)
    db.commit()

    first_result = extract_handles_from_source(db, source_id)
    second_result = extract_handles_from_source(db, source_id)

    assert first_result["entities_created"] == 3
    assert first_result["associations_created"] == 6

    assert second_result["entities_created"] == 0
    assert second_result["associations_created"] == 0

    pgp_entities = db.scalars(
        select(EntityModel).where(
            EntityModel.entity_type == EntityType.PGP_KEY.value,
            EntityModel.canonical_value == "synthetic_pgp_key_001",
        )
    ).all()

    assert len(pgp_entities) == 1