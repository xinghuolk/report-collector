from __future__ import annotations

from pathlib import Path

from financial_report_analysis.p5.artifact_repository import P5JsonArtifactRepository
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
        company_name=f"Company {stock_code}",
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
        candidate_facts=({"fact_id": f"candidate-{entry.artifact_id}"},),
        canonical_facts=({"fact_id": f"canonical-{entry.artifact_id}", "metric_id": "revenue"},),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={},
        created_at="2026-04-23T00:00:00+00:00",
    )


def _dataset(artifacts: tuple[P5ExtractedArtifact, ...]) -> P5DatasetArtifact:
    return P5DatasetArtifact(
        dataset_id="p5_seed_3_issuers_2_years",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00+00:00",
        issuer_count=2,
        periods=(2024, 2025),
        metrics=("revenue",),
        rows=tuple(
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
        ),
        quality_summary={"present_row_count": len(artifacts), "missing_row_count": 0},
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
                "canonical_metric_id": row.metric_id,
                "entity_scope": row.entity_scope,
                "period_scope": row.period_scope,
                "statement_type": row.statement_type,
                "source_artifact_id": row.source_artifact_id,
                "source_fact_id": row.source_fact_id,
                "missing_status": row.missing_status,
                "turtle_field": row.metric_id,
                "value": row.value,
            }
            for row in dataset.rows
        ),
        alias_map={"revenue": "revenue"},
    )


def test_storage_backed_p5_parity_and_historical_ingestion(tmp_path: Path) -> None:
    entries = (
        _entry(tmp_path, issuer_id="CN_600519", stock_code="600519", fiscal_year=2024),
        _entry(tmp_path, issuer_id="CN_600519", stock_code="600519", fiscal_year=2025),
        _entry(tmp_path, issuer_id="CN_601919", stock_code="601919", fiscal_year=2024),
        _entry(tmp_path, issuer_id="CN_601919", stock_code="601919", fiscal_year=2025),
        _entry(tmp_path, issuer_id="CN_688008", stock_code="688008", fiscal_year=2024),
        _entry(tmp_path, issuer_id="CN_688008", stock_code="688008", fiscal_year=2025),
    )
    manifest = P5Manifest(
        manifest_id="p5_seed_3_issuers_2_years",
        manifest_version="1.0",
        entries=entries,
    )

    json_repository = P5JsonArtifactRepository(tmp_path / "data" / "p5")
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    db_repository = SqlAlchemyP5ArtifactRepository(engine)
    ingestion_service = HistoricalIngestionService(engine)

    registrations = ingestion_service.register_manifest(manifest)

    assert len(registrations) == 6
    assert {registration.artifact_status for registration in registrations} == {"missing"}

    artifacts = (
        _artifact(entries[1]),
        _artifact(entries[3]),
    )
    dataset = _dataset(artifacts)
    turtle_export = _turtle_export(dataset)

    for artifact in artifacts:
        json_repository.save_extracted_artifact(artifact)
        db_repository.save_extracted_artifact(artifact)
    json_repository.save_dataset_artifact(dataset)
    db_repository.save_dataset_artifact(dataset)
    json_repository.save_turtle_export(turtle_export)
    db_repository.save_turtle_export(turtle_export)

    assert db_repository.load_extracted_artifact(artifacts[0].artifact_id) == json_repository.load_extracted_artifact(artifacts[0].artifact_id)
    assert db_repository.load_dataset_artifact(dataset.dataset_id) == json_repository.load_dataset_artifact(dataset.dataset_id)
    assert db_repository.load_turtle_export(dataset.dataset_id) == json_repository.load_turtle_export(dataset.dataset_id)

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

    db_repository.save_extracted_review_surface(extracted_surface)
    db_repository.save_dataset_review_surface(dataset_surface)
    db_repository.save_turtle_export_review_surface(turtle_surface)
    db_repository.save_lineage_records(lineage)
    db_repository.save_recompute_result(
        run_id="recompute-run-1",
        plan=recompute_plan,
        result=recompute_result,
    )

    assert db_repository.load_extracted_review_surface(artifacts[0].artifact_id) == extracted_surface
    assert db_repository.load_dataset_review_surface(dataset.dataset_id) == dataset_surface
    assert db_repository.load_turtle_export_review_surface(dataset.dataset_id) == turtle_surface
    assert db_repository.list_lineage_records(dataset_id=dataset.dataset_id) == lineage
    assert db_repository.load_recompute_result("recompute-run-1") == recompute_result
