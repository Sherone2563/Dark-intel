from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete
from app.services.diagnostics_service import classify_processing_run
from app.core.database import SessionLocal
from app.main import app
from app.models.db_models import ProcessingRunModel, SourceModel

client = TestClient(app)


def test_monitoring_summary_aggregates_processing_runs():
    source_name = f"Monitoring test source {uuid4()}"

    source_response = client.post(
        "/sources",
        json={
            "name": source_name,
            "source_type": "synthetic",
            "reference": None,
            "reliability": "unknown",
            "authorized_for_use": True,
            "authorization_note": "Synthetic monitoring API test.",
        },
    )
    assert source_response.status_code == 201

    source_id = source_response.json()["source_id"]
    now = datetime.now(timezone.utc)

    test_runs = [
        {
            "status": "completed",
            "duration": 10,
            "total_lines": 10,
            "parsed_count": 10,
            "imported_count": 8,
            "rejected_count": 1,
            "skipped_duplicate_count": 1,
            "observations_examined": 8,
            "entities_created": 4,
            "existing_entities_matched": 2,
            "associations_created": 4,
        },
        {
            "status": "completed_with_rejections",
            "duration": 20,
            "total_lines": 5,
            "parsed_count": 5,
            "imported_count": 4,
            "rejected_count": 1,
            "skipped_duplicate_count": 0,
            "observations_examined": 4,
            "entities_created": 2,
            "existing_entities_matched": 1,
            "associations_created": 2,
        },
        {
            "status": "failed",
            "duration": 30,
            "total_lines": 3,
            "parsed_count": 2,
            "imported_count": 2,
            "rejected_count": 1,
            "skipped_duplicate_count": 0,
            "observations_examined": 2,
            "entities_created": 1,
            "existing_entities_matched": 0,
            "associations_created": 1,
        },
        {
            "status": "importing",
            "duration": None,
            "total_lines": 6,
            "parsed_count": 0,
            "imported_count": 0,
            "rejected_count": 0,
            "skipped_duplicate_count": 0,
            "observations_examined": 0,
            "entities_created": 0,
            "existing_entities_matched": 0,
            "associations_created": 0,
        },
    ]

    try:
        with SessionLocal() as db:
            for item in test_runs:
                completed_at = (
                    now - timedelta(seconds=100)
                    + timedelta(seconds=item["duration"])
                    if item["duration"] is not None
                    else None
                )

                started_at = (
                    completed_at - timedelta(seconds=item["duration"])
                    if completed_at is not None
                    else now - timedelta(seconds=10)
                )

                db.add(
                    ProcessingRunModel(
                        source_id=source_id,
                        status=item["status"],
                        started_at=started_at,
                        completed_at=completed_at,
                        total_lines=item["total_lines"],
                        parsed_count=item["parsed_count"],
                        imported_count=item["imported_count"],
                        rejected_count=item["rejected_count"],
                        skipped_duplicate_count=item[
                            "skipped_duplicate_count"
                        ],
                        observations_examined=item[
                            "observations_examined"
                        ],
                        entities_created=item["entities_created"],
                        existing_entities_matched=item[
                            "existing_entities_matched"
                        ],
                        associations_created=item["associations_created"],
                        handles_processed=0,
                        pgp_keys_processed=0,
                        processing_version="test",
                    )
                )

            db.commit()

        before = client.get("/monitoring/summary")
        assert before.status_code == 200
        before_data = before.json()

        after = client.get("/monitoring/summary")
        assert after.status_code == 200
        data = after.json()

        assert data["total_runs"] >= before_data["total_runs"]
        assert data["successful_runs"] >= before_data["successful_runs"]
        assert data["runs_with_rejections"] >= before_data[
            "runs_with_rejections"
        ]
        assert data["failed_runs"] >= before_data["failed_runs"]
        assert data["active_runs"] >= before_data["active_runs"]

        assert isinstance(
            data["average_processing_time_seconds"],
            (int, float),
        )

        assert data["reporting_period_days"] == 30

    finally:
        with SessionLocal() as db:
            db.execute(
                delete(ProcessingRunModel).where(
                    ProcessingRunModel.source_id == source_id
                )
            )
            db.execute(
                delete(SourceModel).where(
                    SourceModel.source_id == source_id
                )
            )
            db.commit()


def test_monitoring_summary_rejects_invalid_days():
    response = client.get("/monitoring/summary?days=0")
    assert response.status_code == 422

    response = client.get("/monitoring/summary?days=366")
    assert response.status_code == 422
def test_classify_dataset_import_failure():
    result = classify_processing_run(
        "failed",
        "Dataset import failed: invalid JSON",
    )
    assert result == ("error", "dataset_import", "import")


def test_classify_entity_extraction_failure():
    result = classify_processing_run(
        "failed",
        "Dataset import finished, but entity extraction failed.",
    )
    assert result == (
        "error",
        "entity_extraction",
        "entity_extraction",
    )


def test_classify_persistence_failure():
    result = classify_processing_run(
        "failed",
        "Dataset import finished, but processing-run or extraction persistence failed.",
    )
    assert result == ("error", "persistence", "persistence")


def test_classify_completed_with_rejections_as_warning():
    result = classify_processing_run(
        "completed_with_rejections",
        None,
    )
    assert result == ("warning", "ingestion_rejections", None)


def test_classify_unknown_failure_without_inventing_cause():
    result = classify_processing_run(
        "failed",
        "Unexpected processing error",
    )
    assert result == ("error", "unknown", "unknown")
def test_processing_diagnostics_returns_classified_runs():
    source_name = f"Diagnostics test source {uuid4()}"

    source_response = client.post(
        "/sources",
        json={
            "name": source_name,
            "source_type": "synthetic",
            "reference": None,
            "reliability": "unknown",
            "authorized_for_use": True,
            "authorization_note": "Synthetic diagnostics API test.",
        },
    )
    assert source_response.status_code == 201

    source_id = source_response.json()["source_id"]
    now = datetime.now(timezone.utc)

    test_runs = [
        (
            "failed",
            "Dataset import failed: invalid JSON",
            "dataset_import",
            "import",
        ),
        (
            "failed",
            "Dataset import finished, but entity extraction failed.",
            "entity_extraction",
            "entity_extraction",
        ),
        (
            "failed",
            "Dataset import finished, but processing-run persistence failed.",
            "persistence",
            "persistence",
        ),
        (
            "completed_with_rejections",
            None,
            "ingestion_rejections",
            None,
        ),
    ]

    try:
        with SessionLocal() as db:
            for status_value, error_message, _, _ in test_runs:
                db.add(
                    ProcessingRunModel(
                        source_id=source_id,
                        status=status_value,
                        started_at=now - timedelta(seconds=30),
                        completed_at=now,
                        error_message=error_message,
                        total_lines=10,
                        parsed_count=8,
                        imported_count=6,
                        rejected_count=2,
                        skipped_duplicate_count=1,
                        observations_examined=6,
                        entities_created=3,
                        existing_entities_matched=2,
                        associations_created=3,
                        handles_processed=3,
                        pgp_keys_processed=0,
                        processing_version="test",
                    )
                )

            db.commit()

        response = client.get(
            "/monitoring/diagnostics?days=30&limit=20"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["result_count"] == 4
        assert len(data["results"]) == 4

        results_by_category = {
            item["category"]: item
            for item in data["results"]
        }

        assert set(results_by_category) == {
            "dataset_import",
            "entity_extraction",
            "persistence",
            "ingestion_rejections",
        }

        for _, error_message, category, failure_stage in test_runs:
            item = results_by_category[category]

            assert item["source_id"] == source_id
            assert item["source_name"] == source_name
            assert item["error_message"] == error_message
            assert item["failure_stage"] == failure_stage

            assert item["total_lines"] == 10
            assert item["parsed_count"] == 8
            assert item["imported_count"] == 6
            assert item["rejected_count"] == 2
            assert item["entities_created"] == 3
            assert item["duration_seconds"] == 30.0

        assert results_by_category["dataset_import"]["severity"] == "error"
        assert results_by_category["ingestion_rejections"]["severity"] == "warning"

        assert (
            results_by_category["ingestion_rejections"]["failed_at"]
            is None
        )

    finally:
        with SessionLocal() as db:
            db.execute(
                delete(ProcessingRunModel).where(
                    ProcessingRunModel.source_id == source_id
                )
            )
            db.execute(
                delete(SourceModel).where(
                    SourceModel.source_id == source_id
                )
            )
            db.commit()