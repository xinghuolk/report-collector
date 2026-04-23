from __future__ import annotations

from pathlib import Path

from financial_report_analysis.p5.artifact_repository import P5JsonArtifactRepository
from financial_report_analysis.p5.models import (
    P5DatasetArtifact,
    P5DatasetRow,
    P5ExtractedArtifact,
    P5ManifestEntry,
)


def _entry(tmp_path: Path) -> P5ManifestEntry:
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    return P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
        company_name="中远海控",
        report_language="zh",
    )


def test_repository_round_trips_extracted_artifact(tmp_path: Path) -> None:
    repository = P5JsonArtifactRepository(tmp_path / "data" / "p5")
    entry = _entry(tmp_path)
    artifact = P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={"document_id": "doc-1"},
        document_metadata={"working_capital_missing_status": {"notes_receiv": "absent"}},
        candidate_facts=({"fact_id": "candidate-1"},),
        canonical_facts=({"fact_id": "canonical-1", "metric_id": "revenue"},),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={"working_capital_missing_status": {"notes_receiv": "absent"}},
        created_at="2026-04-23T00:00:00",
    )

    repository.save_extracted_artifact(artifact)
    loaded = repository.load_extracted_artifact("CN_601919_2025")

    assert loaded.artifact_id == "CN_601919_2025"
    assert loaded.manifest_entry.company_name == "中远海控"
    assert loaded.manifest_entry.pdf_path == entry.pdf_path
    assert loaded.source_pdf_path == entry.pdf_path
    assert isinstance(loaded.candidate_facts, tuple)
    assert loaded.canonical_facts[0]["metric_id"] == "revenue"
    assert repository.extracted_artifact_exists("CN_601919_2025") is True


def test_repository_round_trips_dataset_artifact(tmp_path: Path) -> None:
    repository = P5JsonArtifactRepository(tmp_path / "data" / "p5")
    dataset = P5DatasetArtifact(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00",
        issuer_count=1,
        periods=(2025,),
        metrics=("revenue",),
        rows=(
            P5DatasetRow(
                issuer_id="CN_601919",
                market="CN",
                stock_code="601919",
                fiscal_year=2025,
                metric_id="revenue",
                entity_scope="consolidated",
                period_scope="duration",
                statement_type="income_statement",
                value=100.0,
                currency="CNY",
                unit="currency_amount",
                quality_status="ok",
                missing_status="present",
                source_fact_id="canonical-1",
                source_artifact_id="CN_601919_2025",
                evidence_bundle_id="bundle-1",
            ),
        ),
        quality_summary={"missing_by_metric": {}, "unknown_count": 0},
        source_artifacts=("CN_601919_2025",),
    )

    repository.save_dataset_artifact(dataset)
    loaded = repository.load_dataset_artifact("p5_seed")

    assert loaded.dataset_id == "p5_seed"
    assert loaded.periods == (2025,)
    assert loaded.metrics == ("revenue",)
    assert isinstance(loaded.rows, tuple)
    assert loaded.rows[0].metric_id == "revenue"
    assert loaded.rows[0].missing_status == "present"
