from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from financial_report_analysis.p5.models import (
    P5ArtifactLineage,
    P5DatasetArtifact,
    P5ExtractedArtifact,
    P5ManifestEntry,
    P5RecomputeDiffSummary,
    P5RecomputeResult,
    P5TurtleExport,
)
from financial_report_analysis.storage.database import create_sqlite_engine, initialize_database
from financial_report_analysis.storage.models import (
    DatasetArtifactRecord,
    ExtractedArtifactRecord,
    IssuerRecord,
    ManifestEntryRecord,
    ManifestRecord,
    RecomputeRunRecord,
    ReportRecord,
    TurtleExportArtifactRecord,
)


def test_manifest_entry_exposes_stable_report_key(tmp_path: Path) -> None:
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
    )

    assert entry.report_key == ("CN_601919", 2025, "annual")
    assert entry.entry_key == entry.report_key
    assert entry.artifact_id == "CN_601919_2025"


def test_storage_contract_models_preserve_minimum_identity_shape(tmp_path: Path) -> None:
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
    )
    extracted = P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=pdf_path,
        document={"document_id": str(pdf_path), "pdf_path": str(pdf_path)},
        document_metadata={},
        candidate_facts=(),
        canonical_facts=(),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={},
        created_at="2026-04-23T00:00:00",
    )
    dataset = P5DatasetArtifact(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00",
        issuer_count=1,
        periods=(2025,),
        metrics=("revenue",),
        rows=(),
        quality_summary={},
        source_artifacts=(extracted.artifact_id,),
    )
    export = P5TurtleExport(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        created_at=dataset.created_at,
        rows=(),
        alias_map={},
    )

    assert extracted.manifest_entry.report_key == ("CN_601919", 2025, "annual")
    assert dataset.source_artifacts == ("CN_601919_2025",)
    assert export.dataset_id == dataset.dataset_id


def test_lineage_and_recompute_models_keep_storage_minimum_fields() -> None:
    lineage = P5ArtifactLineage(
        dataset_id="p5_seed",
        source_artifact_id="CN_601919_2025",
        source_pdf_path="report/downloads/cn_stocks/601919/annual/2025_年度报告.pdf",
        pipeline_version="p5-v1",
        source_fact_id="fact-1",
        evidence_bundle_id="bundle-1",
        manifest_entry_key=("CN_601919", 2025, "annual"),
        export_row_index=3,
        turtle_field="revenue",
    )
    diff_summary = P5RecomputeDiffSummary(
        reason="pipeline_version_changed",
        target_artifact_ids=("CN_601919_2025",),
        dataset_changed=True,
        turtle_export_changed=False,
        rebuilt_dataset=True,
        rebuilt_turtle_export=True,
    )
    result = P5RecomputeResult(
        manifest_id="p5_seed",
        extracted_artifact_ids=("CN_601919_2025",),
        dataset_path=Path("data/p5/datasets/p5_seed.json"),
        turtle_export_path=Path("data/p5/datasets/p5_seed_turtle_export.json"),
        diff_summary=diff_summary,
    )

    assert lineage.manifest_entry_key == ("CN_601919", 2025, "annual")
    assert lineage.source_artifact_id == "CN_601919_2025"
    assert result.diff_summary.reason == "pipeline_version_changed"
    assert result.dataset_path.name == "p5_seed.json"


def test_storage_core_models_create_minimum_tables(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)

    inspector = inspect(engine)

    assert set(inspector.get_table_names()) >= {
        "issuers",
        "reports",
        "manifests",
        "manifest_entries",
        "extracted_artifacts",
        "dataset_artifacts",
        "turtle_export_artifacts",
        "recompute_runs",
    }


def test_storage_core_models_persist_minimum_registry_and_artifact_rows(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)

    with Session(engine) as session:
        issuer = IssuerRecord(
            issuer_id="CN_601919",
            market="CN",
            stock_code="601919",
            company_name="中远海控",
        )
        report = ReportRecord(
            issuer_id="CN_601919",
            fiscal_year=2025,
            report_type="annual",
            source="report",
            report_language="zh",
            pdf_path="report/downloads/cn_stocks/601919/annual/2025_年度报告.pdf",
        )
        manifest = ManifestRecord(
            manifest_id="p5_seed_3_issuers_2_years",
            manifest_version="1.0",
        )
        manifest_entry = ManifestEntryRecord(
            manifest_id="p5_seed_3_issuers_2_years",
            issuer_id="CN_601919",
            fiscal_year=2025,
            report_type="annual",
            artifact_id="CN_601919_2025",
        )
        extracted = ExtractedArtifactRecord(
            artifact_id="CN_601919_2025",
            issuer_id="CN_601919",
            fiscal_year=2025,
            report_type="annual",
            artifact_version="1.0",
            pipeline_version="p5-v1",
            payload_json="{}",
        )
        dataset = DatasetArtifactRecord(
            dataset_id="p5_seed",
            dataset_version="1.0",
            issuer_count=1,
            payload_json="{}",
        )
        export = TurtleExportArtifactRecord(
            dataset_id="p5_seed",
            dataset_version="1.0",
            payload_json="{}",
        )
        recompute = RecomputeRunRecord(
            run_id="recompute:p5_seed:001",
            manifest_id="p5_seed_3_issuers_2_years",
            dataset_id="p5_seed",
            reason="pipeline_version_changed",
            target_artifact_ids_json='["CN_601919_2025"]',
            diff_summary_json='{"dataset_changed": true}',
        )

        session.add_all(
            [
                issuer,
                report,
                manifest,
                manifest_entry,
                extracted,
                dataset,
                export,
                recompute,
            ]
        )
        session.commit()

    with Session(engine) as session:
        assert session.get(IssuerRecord, "CN_601919") is not None
        assert session.get(ManifestRecord, "p5_seed_3_issuers_2_years") is not None
        assert session.get(ExtractedArtifactRecord, "CN_601919_2025") is not None
        assert session.get(DatasetArtifactRecord, "p5_seed") is not None
        assert session.get(RecomputeRunRecord, "recompute:p5_seed:001") is not None
