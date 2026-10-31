from uuid import UUID

import pytest
from sqlalchemy import delete, select
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.db_models import (
    EntityModel,
    ProcessingRunModel,
    ObservationEntityModel,
    ObservationModel,
    SourceModel,
)
from app.models.enums import EntityType
from app.services.ingestion_pipeline import (
    IngestionPipelineError,
    run_ingestion_pipeline,
)
from app.services.entity_extraction import EntityExtractionError


client = TestClient(app)
def get_processing_run(run_id):
    with SessionLocal() as db:
        return db.get(ProcessingRunModel, UUID(run_id))

@pytest.fixture
def pipeline_source():
    response = client.post(
        "/sources",
        json={
            "name": "Synthetic pipeline test source",
            "source_type": "synthetic",
            "reference": None,
            "reliability": "unknown",
            "authorized_for_use": True,
            "authorization_note": "Synthetic-only integration test.",
        },
    )
    assert response.status_code == 201, response.text

    source_id = UUID(response.json()["source_id"])

    yield source_id

    with SessionLocal() as db:
        # Processing runs reference their source, so delete them first.
        db.execute(
            delete(ProcessingRunModel).where(
                ProcessingRunModel.source_id == source_id
            )
        )

        observation_ids = db.scalars(
            select(ObservationModel.observation_id).where(
                ObservationModel.source_id == source_id
            )
        ).all()

        if observation_ids:
            db.execute(
                delete(ObservationEntityModel).where(
                    ObservationEntityModel.observation_id.in_(
                        observation_ids
                    )
                )
            )

        db.execute(
            delete(ObservationModel).where(
                ObservationModel.source_id == source_id
            )
        )

        entity_ids = db.scalars(
            select(EntityModel.entity_id).where(
                EntityModel.entity_type == EntityType.HANDLE.value,
                EntityModel.canonical_value.in_(
                    ["pipeline_synthetic_alpha", "pipeline_synthetic_beta"]
                ),
            )
        ).all()

        if entity_ids:
            db.execute(
                delete(ObservationEntityModel).where(
                    ObservationEntityModel.entity_id.in_(entity_ids)
                )
            )

            db.execute(
                delete(EntityModel).where(
                    EntityModel.entity_id.in_(entity_ids)
                )
            )

        db.execute(
            delete(SourceModel).where(
                SourceModel.source_id == source_id
            )
        )
        db.commit()

def test_pipeline_imports_and_extracts_handles(pipeline_source):
    lines = [
        (
            '{"payload":{"handle":"Pipeline_Synthetic_Alpha"},'
            '"observed_at":"2026-10-15T10:00:00Z"}'
        ),
        (
            '{"payload":{"handle":"pipeline_synthetic_beta"},'
            '"observed_at":"2026-10-16T10:00:00Z"}'
        ),
    ]

    with SessionLocal() as db:
        result = run_ingestion_pipeline(db, pipeline_source, lines)

    assert result["status"] == "completed"
    assert result["import"]["imported_count"] == 2
    assert result["extraction"]["entities_created"] == 2

    run = get_processing_run(result["run_id"])

    assert run is not None
    assert run.source_id == pipeline_source
    assert run.status == "completed"
    assert run.total_lines == 2
    assert run.parsed_count == 2
    assert run.imported_count == 2
    assert run.rejected_count == 0
    assert run.observations_examined == 2
    assert run.entities_created == 2
    assert run.associations_created == 2
    assert run.completed_at is not None
    assert run.error_message is None

    with SessionLocal() as db:
        entities = db.scalars(
            select(EntityModel).where(
                EntityModel.entity_type == EntityType.HANDLE.value,
                EntityModel.canonical_value.in_(
                    ["pipeline_synthetic_alpha", "pipeline_synthetic_beta"]
                ),
            )
        ).all()

        observations = db.scalars(
            select(ObservationModel).where(
                ObservationModel.source_id == pipeline_source
            )
        ).all()

        associations = db.scalars(
            select(ObservationEntityModel).where(
                ObservationEntityModel.observation_id.in_(
                    [item.observation_id for item in observations]
                )
            )
        ).all()

    assert len(entities) == 2
    assert len(observations) == 2
    assert len(associations) == 2


def test_pipeline_reimport_does_not_duplicate_entities(pipeline_source):
    lines = [
        '{"payload":{"handle":"pipeline_synthetic_alpha"}}',
    ]

    with SessionLocal() as db:
        first = run_ingestion_pipeline(db, pipeline_source, lines)

    with SessionLocal() as db:
        second = run_ingestion_pipeline(db, pipeline_source, lines)

    assert first["import"]["imported_count"] == 1
    assert second["import"]["imported_count"] == 0
    assert second["import"]["skipped_duplicate_count"] == 1
    assert second["extraction"]["entities_created"] == 0

    first_run = get_processing_run(first["run_id"])
    second_run = get_processing_run(second["run_id"])

    assert first_run.status == "completed"
    assert first_run.imported_count == 1

    assert second_run.status == "completed"
    assert second_run.imported_count == 0
    assert second_run.skipped_duplicate_count == 1

    with SessionLocal() as db:
        entities = db.scalars(
            select(EntityModel).where(
                EntityModel.entity_type == EntityType.HANDLE.value,
                EntityModel.canonical_value == "pipeline_synthetic_alpha",
            )
        ).all()

        associations = db.scalars(
            select(ObservationEntityModel).join(
                ObservationModel,
                ObservationEntityModel.observation_id
                == ObservationModel.observation_id,
            ).where(
                ObservationModel.source_id == pipeline_source
            )
        ).all()

    assert len(entities) == 1
    assert len(associations) == 1


def test_pipeline_reports_import_rejections(pipeline_source):
    lines = [
        '{"payload":{"handle":"pipeline_synthetic_alpha"}}',
        '{"payload":',
    ]

    with SessionLocal() as db:
        result = run_ingestion_pipeline(db, pipeline_source, lines)

    assert result["status"] == "completed_with_rejections"
    assert result["import"]["imported_count"] == 1
    assert result["import"]["rejected_count"] == 1
    assert result["extraction"]["entities_created"] == 1

    run = get_processing_run(result["run_id"])

    assert run.status == "completed_with_rejections"
    assert run.total_lines == 2
    assert run.imported_count == 1
    assert run.rejected_count == 1
    assert run.completed_at is not None


def test_pipeline_preserves_import_result_on_extraction_failure(
    pipeline_source, monkeypatch
):
    import app.services.ingestion_pipeline as pipeline

    def fail_extraction(db, source_id):
        raise EntityExtractionError("Simulated extraction failure")

    monkeypatch.setattr(
        pipeline,
        "extract_handles_from_source",
        fail_extraction,
    )

    with SessionLocal() as db:
        with pytest.raises(IngestionPipelineError) as captured:
            run_ingestion_pipeline(
                db,
                pipeline_source,
                ['{"payload":{"handle":"pipeline_synthetic_alpha"}}'],
            )

    assert captured.value.import_result is not None
    assert captured.value.import_result.imported_count == 1
    assert captured.value.run_id is not None

    run = get_processing_run(str(captured.value.run_id))

    assert run is not None
    assert run.status == "failed"
    assert run.imported_count == 1
    assert run.completed_at is not None
    assert run.error_message is not None

    with SessionLocal() as db:
        observations = db.scalars(
            select(ObservationModel).where(
                ObservationModel.source_id == pipeline_source
            )
        ).all()

    assert len(observations) == 1