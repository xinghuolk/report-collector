from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from financial_report_analysis.p5.lineage import build_dataset_lineage
from financial_report_analysis.p5.models import (
    P5DatasetArtifact,
    P5DatasetRow,
    P5ExtractedArtifact,
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
from financial_report_analysis.storage.models import ReportRecord
from financial_report_analysis.storage.repositories import SqlAlchemyP5ArtifactRepository
from financial_report_analysis.p5.artifact_repository import P5ArtifactRepositoryError


def _entry(
    tmp_path: Path,
    *,
    issuer_id: str = "CN_601919",
    stock_code: str = "601919",
    fiscal_year: int = 2025,
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


def _dataset(*artifact_ids: str) -> P5DatasetArtifact:
    rows = tuple(
        P5DatasetRow(
            issuer_id="CN_601919" if artifact_id.startswith("CN_601919") else "CN_600519",
            market="CN",
            stock_code="601919" if artifact_id.startswith("CN_601919") else "600519",
            fiscal_year=int(artifact_id.rsplit("_", 1)[1]),
            metric_id="revenue",
            entity_scope="consolidated",
            period_scope="duration",
            statement_type="income_statement",
            value=100.0 + index,
            currency="CNY",
            unit="currency_amount",
            quality_status="ok",
            missing_status="present",
            source_fact_id=f"canonical-{artifact_id}",
            source_artifact_id=artifact_id,
            evidence_bundle_id=f"bundle-{artifact_id}",
        )
        for index, artifact_id in enumerate(artifact_ids)
    )
    periods = tuple(sorted({row.fiscal_year for row in rows}))
    return P5DatasetArtifact(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-24T00:00:00+00:00",
        issuer_count=len({row.issuer_id for row in rows}),
        periods=periods,
        metrics=("revenue",),
        rows=rows,
        quality_summary={"present_row_count": len(rows), "missing_row_count": 0},
        source_artifacts=artifact_ids,
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


def _recompute_plan(*artifact_ids: str) -> P5RecomputePlan:
    return P5RecomputePlan(
        manifest_id="p5_seed_manifest",
        dataset_id="p5_seed",
        target_artifact_ids=artifact_ids,
        rebuild_dataset=True,
        rebuild_turtle_export=True,
        reason="pipeline_version_changed",
    )


def _recompute_result(*artifact_ids: str) -> P5RecomputeResult:
    return P5RecomputeResult(
        manifest_id="p5_seed_manifest",
        extracted_artifact_ids=artifact_ids,
        dataset_path=Path("data/p5/datasets/p5_seed.json"),
        turtle_export_path=Path("data/p5/datasets/p5_seed_turtle_export.json"),
        diff_summary=P5RecomputeDiffSummary(
            reason="pipeline_version_changed",
            target_artifact_ids=artifact_ids,
            dataset_changed=True,
            turtle_export_changed=True,
            rebuilt_dataset=True,
            rebuilt_turtle_export=True,
        ),
    )


def test_list_available_fiscal_years_and_report_coverage(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    service = HistoricalIngestionService(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)

    entry_2024 = _entry(tmp_path, fiscal_year=2024)
    entry_2025 = _entry(tmp_path, fiscal_year=2025)
    service.register_report(entry_2024)
    service.register_report(entry_2025)
    repository.save_extracted_artifact(_artifact(entry_2025))

    assert repository.list_available_fiscal_years("CN_601919") == (2024, 2025)

    missing_coverage = repository.get_report_coverage("CN_601919", 2024, "annual")
    assert missing_coverage.report_registered is True
    assert missing_coverage.extracted_artifact_available is False
    assert missing_coverage.extracted_artifact_ids == ()
    assert missing_coverage.pdf_path == str(entry_2024.pdf_path)

    available_coverage = repository.get_report_coverage("CN_601919", 2025, "annual")
    assert available_coverage.report_registered is True
    assert available_coverage.extracted_artifact_available is True
    assert available_coverage.extracted_artifact_ids == (entry_2025.artifact_id,)
    assert available_coverage.pdf_path == str(entry_2025.pdf_path)

    absent_coverage = repository.get_report_coverage("CN_600519", 2025, "annual")
    assert absent_coverage.report_registered is False
    assert absent_coverage.report_id is None
    assert absent_coverage.extracted_artifact_available is False


def test_load_dataset_audit_view_returns_source_artifacts_review_surfaces_and_recompute(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    service = HistoricalIngestionService(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)

    first_entry = _entry(tmp_path, fiscal_year=2024)
    second_entry = _entry(tmp_path, fiscal_year=2025)
    service.register_report(first_entry)
    service.register_report(second_entry)

    first_artifact = _artifact(first_entry)
    second_artifact = _artifact(second_entry)
    dataset = _dataset(first_artifact.artifact_id, second_artifact.artifact_id)
    turtle_export = _turtle_export(dataset)

    repository.save_extracted_artifact(first_artifact)
    repository.save_extracted_artifact(second_artifact)
    repository.save_dataset_artifact(dataset)
    repository.save_turtle_export(turtle_export)

    first_surface = build_extracted_review_surface(first_artifact)
    second_surface = build_extracted_review_surface(second_artifact)
    dataset_surface = build_dataset_review_surface(
        dataset,
        extracted_artifacts=(first_artifact, second_artifact),
    )
    turtle_surface = build_turtle_export_review_surface(
        turtle_export,
        dataset=dataset,
    )
    lineage = build_dataset_lineage(
        dataset=dataset,
        extracted_artifacts=(first_artifact, second_artifact),
        turtle_export=turtle_export,
    )
    repository.save_extracted_review_surface(first_surface)
    repository.save_extracted_review_surface(second_surface)
    repository.save_dataset_review_surface(dataset_surface)
    repository.save_turtle_export_review_surface(turtle_surface)
    repository.save_lineage_records(lineage)
    repository.save_recompute_result(
        run_id="run-1",
        plan=_recompute_plan(first_artifact.artifact_id, second_artifact.artifact_id),
        result=_recompute_result(first_artifact.artifact_id, second_artifact.artifact_id),
    )

    audit_view = repository.load_dataset_audit_view(dataset.dataset_id)

    assert audit_view.dataset_id == dataset.dataset_id
    assert audit_view.source_artifact_ids == dataset.source_artifacts
    assert audit_view.dataset_review_surface == dataset_surface
    assert audit_view.turtle_export_review_surface == turtle_surface
    assert audit_view.latest_recompute_run_id == "run-1"
    assert audit_view.latest_recompute_reason == "pipeline_version_changed"
    assert tuple(record.source_artifact_id for record in audit_view.source_artifacts) == (
        first_artifact.artifact_id,
        second_artifact.artifact_id,
    )
    assert tuple(record.source_pdf_path for record in audit_view.source_artifacts) == (
        str(first_entry.pdf_path),
        str(second_entry.pdf_path),
    )
    assert tuple(record.extracted_review_surface for record in audit_view.source_artifacts) == (
        first_surface,
        second_surface,
    )


def test_existing_persisted_surface_queries_remain_available(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    service = HistoricalIngestionService(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)
    entry = _entry(tmp_path, fiscal_year=2025)
    service.register_report(entry)

    artifact = _artifact(entry)
    dataset = _dataset(artifact.artifact_id)
    turtle_export = _turtle_export(dataset)
    repository.save_extracted_artifact(artifact)
    repository.save_dataset_artifact(dataset)
    repository.save_turtle_export(turtle_export)

    extracted_surface = build_extracted_review_surface(artifact)
    dataset_surface = build_dataset_review_surface(dataset, extracted_artifacts=(artifact,))
    turtle_surface = build_turtle_export_review_surface(turtle_export, dataset=dataset)
    lineage = build_dataset_lineage(
        dataset=dataset,
        extracted_artifacts=(artifact,),
        turtle_export=turtle_export,
    )
    recompute_result = _recompute_result(artifact.artifact_id)

    repository.save_extracted_review_surface(extracted_surface)
    repository.save_dataset_review_surface(dataset_surface)
    repository.save_turtle_export_review_surface(turtle_surface)
    repository.save_lineage_records(lineage)
    repository.save_recompute_result(
        run_id="run-1",
        plan=_recompute_plan(artifact.artifact_id),
        result=recompute_result,
    )

    assert repository.load_extracted_review_surface(artifact.artifact_id) == extracted_surface
    assert repository.load_dataset_review_surface(dataset.dataset_id) == dataset_surface
    assert repository.load_turtle_export_review_surface(dataset.dataset_id) == turtle_surface
    assert repository.list_lineage_records(dataset_id=dataset.dataset_id) == lineage
    assert repository.load_recompute_result("run-1") == recompute_result


def test_load_dataset_audit_view_fails_fast_when_source_artifact_is_missing(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)

    dataset = _dataset("CN_601919_2025")
    repository.save_dataset_artifact(dataset)

    with pytest.raises(P5ArtifactRepositoryError, match="missing source artifact"):
        repository.load_dataset_audit_view(dataset.dataset_id)


def test_load_dataset_audit_view_uses_immutable_artifact_pdf_path(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    service = HistoricalIngestionService(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)
    entry = _entry(tmp_path, fiscal_year=2025)
    service.register_report(entry)

    artifact = _artifact(entry)
    dataset = _dataset(artifact.artifact_id)
    repository.save_extracted_artifact(artifact)
    repository.save_dataset_artifact(dataset)

    rewritten_path = tmp_path / "rewritten_CN_601919_2025.pdf"
    rewritten_path.write_bytes(b"%PDF-1.4\n")
    with Session(engine) as session:
        report = session.scalar(
            select(ReportRecord).where(ReportRecord.issuer_id == entry.issuer_id)
        )
        assert report is not None
        report.pdf_path = str(rewritten_path)
        session.commit()

    audit_view = repository.load_dataset_audit_view(dataset.dataset_id)

    assert audit_view.source_artifacts[0].source_pdf_path == str(entry.pdf_path)
