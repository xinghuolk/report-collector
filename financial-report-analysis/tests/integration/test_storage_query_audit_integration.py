from __future__ import annotations

from pathlib import Path

from financial_report_analysis.p5.lineage import build_dataset_lineage
from financial_report_analysis.p5.models import (
    P5DatasetArtifact,
    P5DatasetRow,
    P5ExtractedArtifact,
    P5Manifest,
    P5ManifestEntry,
    P5RecomputeDiffSummary,
    P5RecomputePlan,
    P5RecomputeResult,
    P5TurtleExport,
)
from financial_report_analysis.p5.review import (
    build_dataset_review_surface,
    build_extracted_review_surface,
    build_turtle_export_review_surface,
)
from financial_report_analysis.storage.database import create_sqlite_engine, initialize_database
from financial_report_analysis.storage.historical_ingestion import HistoricalIngestionService
from financial_report_analysis.storage.repositories import SqlAlchemyP5ArtifactRepository


def _entry(
    tmp_path: Path,
    *,
    issuer_id: str,
    stock_code: str,
    fiscal_year: int,
) -> P5ManifestEntry:
    pdf_path = tmp_path / f"{issuer_id}_{fiscal_year}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    return P5ManifestEntry(
        issuer_id=issuer_id,
        market="CN",
        stock_code=stock_code,
        fiscal_year=fiscal_year,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
        company_name="测试公司",
        report_language="zh",
    )


def _artifact(entry: P5ManifestEntry) -> P5ExtractedArtifact:
    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={"document_id": str(entry.pdf_path), "pdf_path": str(entry.pdf_path)},
        document_metadata={},
        candidate_facts=(),
        canonical_facts=({"fact_id": f"canonical-{entry.artifact_id}", "metric_id": "revenue"},),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={},
        created_at="2026-04-24T00:00:00+00:00",
    )


def _dataset(artifacts: tuple[P5ExtractedArtifact, ...]) -> P5DatasetArtifact:
    rows = tuple(
        P5DatasetRow(
            issuer_id=artifact.manifest_entry.issuer_id,
            market=artifact.manifest_entry.market,
            stock_code=artifact.manifest_entry.stock_code,
            fiscal_year=artifact.manifest_entry.fiscal_year,
            metric_id="revenue",
            entity_scope="consolidated",
            period_scope="duration",
            statement_type="income_statement",
            value=100.0 + index,
            currency="CNY",
            unit="currency_amount",
            quality_status="ok",
            missing_status="present",
            source_fact_id=f"canonical-{artifact.artifact_id}",
            source_artifact_id=artifact.artifact_id,
            evidence_bundle_id=f"bundle-{artifact.artifact_id}",
        )
        for index, artifact in enumerate(artifacts)
    )
    return P5DatasetArtifact(
        dataset_id="p5_seed_3_issuers_2_years",
        dataset_version="1.0",
        created_at="2026-04-24T00:00:00+00:00",
        issuer_count=len({artifact.manifest_entry.issuer_id for artifact in artifacts}),
        periods=tuple(sorted({artifact.manifest_entry.fiscal_year for artifact in artifacts})),
        metrics=("revenue",),
        rows=rows,
        quality_summary={"present_row_count": len(rows), "missing_row_count": 0},
        source_artifacts=tuple(artifact.artifact_id for artifact in artifacts),
    )


def _turtle_export(dataset: P5DatasetArtifact) -> P5TurtleExport:
    return P5TurtleExport(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        created_at=dataset.created_at,
        rows=tuple(
            {
                "issuer_id": row.issuer_id,
                "fiscal_year": row.fiscal_year,
                "metric_id": row.metric_id,
                "value": row.value,
                "source_artifact_id": row.source_artifact_id,
            }
            for row in dataset.rows
        ),
        alias_map={"revenue": "revenue"},
    )


def test_storage_backed_query_and_audit_contracts_work_on_seed_dataset(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)
    service = HistoricalIngestionService(engine)

    entries = (
        _entry(tmp_path, issuer_id="CN_601919", stock_code="601919", fiscal_year=2024),
        _entry(tmp_path, issuer_id="CN_601919", stock_code="601919", fiscal_year=2025),
        _entry(tmp_path, issuer_id="CN_600519", stock_code="600519", fiscal_year=2024),
        _entry(tmp_path, issuer_id="CN_600519", stock_code="600519", fiscal_year=2025),
        _entry(tmp_path, issuer_id="CN_000333", stock_code="000333", fiscal_year=2024),
        _entry(tmp_path, issuer_id="CN_000333", stock_code="000333", fiscal_year=2025),
    )
    manifest = P5Manifest(
        manifest_id="p5_seed_manifest",
        manifest_version="1.0",
        entries=entries,
    )

    registrations = service.register_manifest(manifest)
    assert len(registrations) == 6
    assert repository.list_available_fiscal_years("CN_601919") == (2024, 2025)

    pre_extract_coverage = repository.get_report_coverage("CN_601919", 2024, "annual")
    assert pre_extract_coverage.report_registered is True
    assert pre_extract_coverage.extracted_artifact_available is False

    artifacts = (
        _artifact(entries[1]),
        _artifact(entries[3]),
        _artifact(entries[5]),
    )
    for artifact in artifacts:
        repository.save_extracted_artifact(artifact)

    dataset = _dataset(artifacts)
    turtle_export = _turtle_export(dataset)
    repository.save_dataset_artifact(dataset)
    repository.save_turtle_export(turtle_export)

    extracted_surface = build_extracted_review_surface(artifacts[0])
    dataset_surface = build_dataset_review_surface(dataset, extracted_artifacts=artifacts)
    turtle_surface = build_turtle_export_review_surface(turtle_export, dataset=dataset)
    lineage = build_dataset_lineage(
        dataset=dataset,
        extracted_artifacts=artifacts,
        turtle_export=turtle_export,
    )
    recompute_plan = P5RecomputePlan(
        manifest_id=manifest.manifest_id,
        dataset_id=dataset.dataset_id,
        target_artifact_ids=(artifacts[0].artifact_id,),
        rebuild_dataset=True,
        rebuild_turtle_export=True,
        reason="pipeline_version_changed",
    )
    recompute_result = P5RecomputeResult(
        manifest_id=manifest.manifest_id,
        extracted_artifact_ids=tuple(artifact.artifact_id for artifact in artifacts),
        dataset_path=Path("data/p5/datasets/p5_seed_3_issuers_2_years.json"),
        turtle_export_path=Path("data/p5/datasets/p5_seed_3_issuers_2_years_turtle_export.json"),
        diff_summary=P5RecomputeDiffSummary(
            reason="pipeline_version_changed",
            target_artifact_ids=(artifacts[0].artifact_id,),
            dataset_changed=True,
            turtle_export_changed=True,
            rebuilt_dataset=True,
            rebuilt_turtle_export=True,
        ),
    )

    repository.save_extracted_review_surface(extracted_surface)
    repository.save_dataset_review_surface(dataset_surface)
    repository.save_turtle_export_review_surface(turtle_surface)
    repository.save_lineage_records(lineage)
    repository.save_recompute_result(
        run_id="recompute-run-1",
        plan=recompute_plan,
        result=recompute_result,
    )

    post_extract_coverage = repository.get_report_coverage("CN_601919", 2025, "annual")
    assert post_extract_coverage.report_registered is True
    assert post_extract_coverage.extracted_artifact_available is True
    assert post_extract_coverage.extracted_artifact_ids == ("CN_601919_2025",)

    assert repository.load_extracted_review_surface(artifacts[0].artifact_id) == extracted_surface
    assert repository.load_dataset_review_surface(dataset.dataset_id) == dataset_surface
    assert repository.load_turtle_export_review_surface(dataset.dataset_id) == turtle_surface
    assert repository.list_lineage_records(dataset_id=dataset.dataset_id) == lineage
    assert repository.load_recompute_result("recompute-run-1") == recompute_result

    audit_view = repository.load_dataset_audit_view(dataset.dataset_id)
    assert audit_view.source_artifact_ids == dataset.source_artifacts
    assert tuple(record.source_pdf_path for record in audit_view.source_artifacts) == (
        str(entries[1].pdf_path),
        str(entries[3].pdf_path),
        str(entries[5].pdf_path),
    )
    assert audit_view.latest_recompute_run_id == "recompute-run-1"
    assert audit_view.latest_recompute_reason == "pipeline_version_changed"
