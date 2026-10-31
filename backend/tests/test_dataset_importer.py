from uuid import UUID, uuid4
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from unittest.mock import MagicMock
from sqlalchemy.exc import OperationalError
from app.core.database import SessionLocal
from app.models.observations import calculate_payload_sha256
from app.main import app
from app.models.db_models import ObservationModel, SourceModel
from app.models.dataset_ingestion import DatasetImportError
from app.services.dataset_importer import import_jsonl_lines

client = TestClient(app)


@pytest.fixture
def source_factory():
    created_source_ids = []

    def create_source(*, authorized: bool = True) -> dict:
        response = client.post(
            "/sources",
            json={
                "name": f"Dataset importer test {uuid4()}",
                "source_type": "synthetic",
                "reference": None,
                "reliability": "unknown",
                "authorized_for_use": authorized,
                "authorization_note": (
                    "Synthetic-only integration test."
                    if authorized
                    else "Not authorized for ingestion."
                ),
            },
        )
        assert response.status_code == 201, response.text
        source = response.json()
        created_source_ids.append(UUID(source["source_id"]))
        return source

    yield create_source

    with SessionLocal() as db:
        for source_id in created_source_ids:
            db.execute(
                delete(ObservationModel).where(
                    ObservationModel.source_id == source_id
                )
            )
            db.execute(
                delete(SourceModel).where(
                    SourceModel.source_id == source_id
                )
            )
        db.commit()


def test_imports_valid_records_and_reports_malformed_lines(source_factory):
    source = source_factory()
    source_id = UUID(source["source_id"])

    lines = [
        "",
        '{"payload":{"handle":"synthetic_alpha"}}',
        '{"payload":',
        '{"payload":{"handle":"synthetic_beta"}}',
    ]

    with SessionLocal() as db:
        result = import_jsonl_lines(db, source_id, lines)

    assert result.total_lines == 4
    assert result.parsed_count == 2
    assert result.imported_count == 2
    assert result.skipped_duplicate_count == 0
    assert result.rejected_count == 1
    assert result.errors[0].line_number == 3

    with SessionLocal() as db:
        saved = db.scalars(
            select(ObservationModel).where(
                ObservationModel.source_id == source_id
            )
        ).all()

    assert len(saved) == 2
    assert {item.payload["handle"] for item in saved} == {
        "synthetic_alpha",
        "synthetic_beta",
    }


def test_unknown_source_is_rejected():
    with SessionLocal() as db:
        with pytest.raises(DatasetImportError, match="Unknown source"):
            import_jsonl_lines(db, uuid4(), [])


def test_unauthorized_source_is_rejected(source_factory):
    source = source_factory(authorized=False)

    with SessionLocal() as db:
        with pytest.raises(
            DatasetImportError,
            match="not authorized",
        ):
            import_jsonl_lines(
                db,
                UUID(source["source_id"]),
                ['{"payload":{"handle":"synthetic_alpha"}}'],
            )


def test_duplicate_records_in_same_batch_are_skipped(source_factory):
    source_id = UUID(source_factory()["source_id"])
    line = '{"payload":{"handle":"synthetic_alpha"}}'

    with SessionLocal() as db:
        result = import_jsonl_lines(db, source_id, [line, line])

    assert result.imported_count == 1
    assert result.skipped_duplicate_count == 1
    assert result.rejected_count == 0


def test_existing_duplicate_is_skipped_on_reimport(source_factory):
    source_id = UUID(source_factory()["source_id"])
    line = '{"payload":{"handle":"synthetic_alpha"}}'

    with SessionLocal() as db:
        first = import_jsonl_lines(db, source_id, [line])

    with SessionLocal() as db:
        second = import_jsonl_lines(db, source_id, [line])

    assert first.imported_count == 1
    assert second.imported_count == 0
    assert second.skipped_duplicate_count == 1


def test_same_payload_at_different_observation_times_is_allowed(
    source_factory,
):
    source_id = UUID(source_factory()["source_id"])
    lines = [
        (
            '{"payload":{"handle":"synthetic_alpha"},'
            '"observed_at":"2026-10-18T10:00:00Z"}'
        ),
        (
            '{"payload":{"handle":"synthetic_alpha"},'
            '"observed_at":"2026-10-19T10:00:00Z"}'
        ),
    ]

    with SessionLocal() as db:
        result = import_jsonl_lines(db, source_id, lines)

    assert result.imported_count == 2
    assert result.skipped_duplicate_count == 0
    assert result.rejected_count == 0


def test_connection_failure_during_commit_stops_import(source_factory):
    source_id = UUID(source_factory()["source_id"])
    line = '{"payload":{"handle":"synthetic_connection_failure"}}'

    with SessionLocal() as db:
        db.add = MagicMock()
        db.commit = MagicMock(
            side_effect=OperationalError(
                "INSERT",
                {},
                Exception("simulated connection failure"),
            )
        )
        db.rollback = MagicMock()

        with pytest.raises(
            DatasetImportError,
            match="Database connection failure.*import stopped",
        ):
            import_jsonl_lines(db, source_id, [line])

        db.rollback.assert_called_once()
def test_import_skips_duplicate_records_with_null_observed_at(
    source_factory,
):
    source_id = UUID(str(source_factory()["source_id"]))
    lines = [
        '{"payload":{"handle":"null_timestamp_synthetic"}}',
        '{"payload":{"handle":"null_timestamp_synthetic"}}',
    ]

    with SessionLocal() as db:
        first = import_jsonl_lines(db, source_id, lines)

    with SessionLocal() as db:
        second = import_jsonl_lines(db, source_id, lines)

    assert first.imported_count == 1
    assert first.skipped_duplicate_count == 1
    assert second.imported_count == 0
    assert second.skipped_duplicate_count == 2

def test_duplicate_observation_conflict_is_recognized():
    from app.services.dataset_importer import (
        _is_duplicate_observation_conflict,
    )

    class Diagnostic:
        constraint_name = "uq_observations_source_hash_observed_at"

    class OriginalError(Exception):
        diag = Diagnostic()

    error = IntegrityError("INSERT", {}, OriginalError())

    assert _is_duplicate_observation_conflict(error) is True


def test_unrelated_integrity_error_is_not_duplicate():
    from app.services.dataset_importer import (
        _is_duplicate_observation_conflict,
    )

    class Diagnostic:
        constraint_name = "some_other_constraint"

    class OriginalError(Exception):
        diag = Diagnostic()

    error = IntegrityError("INSERT", {}, OriginalError())

    assert _is_duplicate_observation_conflict(error) is False

def test_concurrent_duplicate_with_null_timestamp_is_skipped(
    source_factory,
    monkeypatch,
):
    source_id = UUID(source_factory()["source_id"])
    line = '{"payload":{"handle":"synthetic_concurrent_duplicate"}}'

    payload = {"handle": "synthetic_concurrent_duplicate"}
    content_hash = calculate_payload_sha256(payload)
    competing_insert_completed = False

    with SessionLocal() as db:
        original_scalar = db.scalar

        def scalar_with_competing_insert(statement):
            nonlocal competing_insert_completed

            existing_id = original_scalar(statement)

            if (
                existing_id is None
                and not competing_insert_completed
            ):
                competing_insert_completed = True

                # Simulate another importer winning the race.
                with SessionLocal() as competing_db:
                    competing_db.add(
                        ObservationModel(
                            source_id=source_id,
                            collected_at=datetime.now(timezone.utc),
                            observed_at=None,
                            payload=payload,
                            content_sha256=content_hash,
                            status="ingested",
                            processing_version="0.1.0",
                        )
                    )
                    competing_db.commit()

            return existing_id

        monkeypatch.setattr(db, "scalar", scalar_with_competing_insert)

        result = import_jsonl_lines(db, source_id, [line])

    assert competing_insert_completed is True
    assert result.imported_count == 0
    assert result.skipped_duplicate_count == 1
    assert result.rejected_count == 0
    assert result.errors == ()

    with SessionLocal() as db:
        saved = db.scalars(
            select(ObservationModel).where(
                ObservationModel.source_id == source_id,
                ObservationModel.content_sha256 == content_hash,
                ObservationModel.observed_at.is_(None),
            )
        ).all()

    assert len(saved) == 1