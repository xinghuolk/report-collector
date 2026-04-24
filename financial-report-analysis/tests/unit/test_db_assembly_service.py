from __future__ import annotations

from pathlib import Path

from financial_report_analysis.api.runtime import build_api_runtime
from financial_report_analysis.p5.db_assembly_service import (
    DbP5AssemblyRequest,
    build_db_p5_outputs_for_artifact,
)
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry


def _artifact(entry: P5ManifestEntry) -> P5ExtractedArtifact:
    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="test",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={"document_id": str(entry.pdf_path), "pdf_path": str(entry.pdf_path)},
        document_metadata={"language": "zh"},
        candidate_facts=(),
        canonical_facts=(
            {
                "fact_id": "fact-revenue",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "numeric_value": 100.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "evidence_bundle_id": "bundle-revenue",
                "extensions": {"period_scope": "fy"},
            },
        ),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={"cash_health_missing_status": {"restricted_cash": "not_surfaced"}},
        created_at="2026-04-24T00:00:00+00:00",
    )


def test_build_db_p5_outputs_for_artifact_persists_dataset_review_and_lineage(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    assert runtime.storage_repository is not None
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=tmp_path / "report.pdf",
        source="test",
    )
    runtime.storage_repository.save_extracted_artifact(_artifact(entry))

    result = build_db_p5_outputs_for_artifact(
        repository=runtime.storage_repository,
        request=DbP5AssemblyRequest(
            artifact_id="CN_601919_2025",
            dataset_id=None,
            dataset_version=None,
            build_turtle=False,
        ),
        now_func=lambda: "2026-04-24T00:00:00+00:00",
    )

    assert result.dataset_id == "single_report_CN_601919_2025_annual_CN_601919_2025"
    assert result.dataset_version == "1.0"
    assert result.turtle_export_id is None
    assert result.source_artifact_ids == ("CN_601919_2025",)
    assert result.lineage_record_count >= 1
    assert result.build_warnings == ()
    dataset = runtime.storage_repository.load_dataset_artifact(result.dataset_id)
    surface = runtime.storage_repository.load_dataset_review_surface(result.dataset_id)
    lineage = runtime.storage_repository.list_lineage_records(dataset_id=result.dataset_id)
    assert dataset.source_artifacts == ("CN_601919_2025",)
    assert surface.dataset_id == result.dataset_id
    assert tuple({record.source_artifact_id for record in lineage}) == ("CN_601919_2025",)


def test_build_db_p5_outputs_for_artifact_persists_turtle_export(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    assert runtime.storage_repository is not None
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=tmp_path / "report.pdf",
        source="test",
    )
    runtime.storage_repository.save_extracted_artifact(_artifact(entry))

    result = build_db_p5_outputs_for_artifact(
        repository=runtime.storage_repository,
        request=DbP5AssemblyRequest(
            artifact_id="CN_601919_2025",
            dataset_id="custom_dataset",
            dataset_version="api-test",
            build_turtle=True,
        ),
        now_func=lambda: "2026-04-24T00:00:00+00:00",
    )

    assert result.dataset_id == "custom_dataset"
    assert result.dataset_version == "api-test"
    assert result.turtle_export_id == "custom_dataset"
    turtle = runtime.storage_repository.load_turtle_export("custom_dataset")
    turtle_surface = runtime.storage_repository.load_turtle_export_review_surface(
        "custom_dataset"
    )
    assert turtle.dataset_id == "custom_dataset"
    assert turtle_surface.dataset_id == "custom_dataset"
