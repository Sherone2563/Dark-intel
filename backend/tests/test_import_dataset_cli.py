import json
import sys
from contextlib import nullcontext
from unittest.mock import Mock

import app.cli.import_dataset as cli
from app.models.dataset_ingestion import DatasetImportResult


def test_full_pipeline_cli_reports_success(tmp_path, monkeypatch, capsys):
    dataset = tmp_path / "sample.jsonl"
    dataset.write_text('{"payload":{"handle":"synthetic_test"}}\n')

    run_pipeline = Mock(return_value={
        "source_id": "00000000-0000-0000-0000-000000000001",
        "import": {
            "imported_count": 1,
            "rejected_count": 0,
        },
        "extraction": {
            "entities_created": 1,
        },
        "status": "completed",
    })

    monkeypatch.setattr(cli, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(cli, "run_ingestion_pipeline", run_pipeline)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_dataset",
            "--file", str(dataset),
            "--source-id", "00000000-0000-0000-0000-000000000001",
            "--full-pipeline",
        ],
    )

    assert cli.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "completed"
    assert output["extraction"]["entities_created"] == 1
    run_pipeline.assert_called_once()


def test_import_only_cli_does_not_run_extraction(
    tmp_path, monkeypatch, capsys
):
    dataset = tmp_path / "sample.jsonl"
    dataset.write_text('{"payload":{"handle":"synthetic_test"}}\n')

    import_result = DatasetImportResult(
        source_id="00000000-0000-0000-0000-000000000001",
        total_lines=1,
        parsed_count=1,
        imported_count=1,
        skipped_duplicate_count=0,
        rejected_count=0,
        errors=[],
    )

    import_records = Mock(return_value=import_result)
    run_pipeline = Mock()

    monkeypatch.setattr(cli, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(cli, "import_jsonl_lines", import_records)
    monkeypatch.setattr(cli, "run_ingestion_pipeline", run_pipeline)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_dataset",
            "--file", str(dataset),
            "--source-id", "00000000-0000-0000-0000-000000000001",
        ],
    )

    assert cli.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["imported_count"] == 1
    import_records.assert_called_once()
    run_pipeline.assert_not_called()


def test_full_pipeline_cli_reports_extraction_failure(
    tmp_path, monkeypatch, capsys
):
    dataset = tmp_path / "sample.jsonl"
    dataset.write_text('{"payload":{"handle":"synthetic_test"}}\n')

    from app.services.ingestion_pipeline import IngestionPipelineError

    error = IngestionPipelineError(
        "Handle extraction failed",
        import_result=DatasetImportResult(
            source_id="00000000-0000-0000-0000-000000000001",
            total_lines=1,
            parsed_count=1,
            imported_count=1,
            skipped_duplicate_count=0,
            rejected_count=0,
            errors=[],
        ),
    )

    monkeypatch.setattr(cli, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(
        cli, "run_ingestion_pipeline", Mock(side_effect=error)
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_dataset",
            "--file", str(dataset),
            "--source-id", "00000000-0000-0000-0000-000000000001",
            "--full-pipeline",
        ],
    )

    assert cli.main() == 1
    output = json.loads(capsys.readouterr().err)
    assert output["status"] == "failed"
    assert output["import"]["imported_count"] == 1