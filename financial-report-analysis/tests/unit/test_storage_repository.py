from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from financial_report_analysis.p5.artifact_repository import P5JsonArtifactRepository
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
from financial_report_analysis.storage.repositories import SqlAlchemyP5ArtifactRepository

if TYPE_CHECKING:
    from financial_report_analysis.p5.artifact_repository import P5ArtifactRepository


def _entry(tmp_path: Path, *, issuer_id: str, stock_code: str, fiscal_year: int) -> P5ManifestEntry:
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
        document_metadata={"working_capital_missing_status": {"notes_receiv": "absent"}},
        candidate_facts=({"fact_id": f"candidate-{entry.artifact_id}"},),
        canonical_facts=({"fact_id": f"canonical-{entry.artifact_id}", "metric_id": "revenue"},),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={"working_capital_missing_status": {"notes_receiv": "absent"}},
        created_at="2026-04-23T00:00:00+00:00",
    )


def _dataset(artifact_id: str) -> P5DatasetArtifact:
    return P5DatasetArtifact(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00+00:00",
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
                source_artifact_id=artifact_id,
                evidence_bundle_id="bundle-1",
            ),
        ),
        quality_summary={"missing_by_metric": {}, "unknown_count": 0},
        source_artifacts=(artifact_id,),
    )


def _turtle_export() -> P5TurtleExport:
    return P5TurtleExport(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00+00:00",
        rows=(
            {
                "issuer_id": "CN_601919",
                "fiscal_year": 2025,
                "metric_id": "revenue",
                "value": 100.0,
            },
        ),
        alias_map={"revenue": "revenue"},
    )


def _recompute_plan() -> P5RecomputePlan:
    return P5RecomputePlan(
        manifest_id="p5_seed_manifest",
        dataset_id="p5_seed",
        target_artifact_ids=("CN_601919_2025",),
        rebuild_dataset=True,
        rebuild_turtle_export=True,
        reason="pipeline_version_changed",
    )


def _recompute_result() -> P5RecomputeResult:
    return P5RecomputeResult(
        manifest_id="p5_seed_manifest",
        extracted_artifact_ids=("CN_601919_2025",),
        dataset_path=Path("data/p5/datasets/p5_seed.json"),
        turtle_export_path=Path("data/p5/datasets/p5_seed_turtle_export.json"),
        diff_summary=P5RecomputeDiffSummary(
            reason="pipeline_version_changed",
            target_artifact_ids=("CN_601919_2025",),
            dataset_changed=True,
            turtle_export_changed=True,
            rebuilt_dataset=True,
            rebuilt_turtle_export=True,
        ),
    )


@pytest.fixture(params=("json", "db"))
def repository(request: pytest.FixtureRequest, tmp_path: Path) -> P5ArtifactRepository:
    if request.param == "json":
        return P5JsonArtifactRepository(tmp_path / "data" / "p5")

    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    return SqlAlchemyP5ArtifactRepository(engine)


def test_repository_round_trips_p5_artifacts(repository: P5ArtifactRepository, tmp_path: Path) -> None:
    entry = _entry(tmp_path, issuer_id="CN_601919", stock_code="601919", fiscal_year=2025)
    artifact = _artifact(entry)
    dataset = _dataset(artifact.artifact_id)
    turtle_export = _turtle_export()

    repository.save_extracted_artifact(artifact)
    repository.save_dataset_artifact(dataset)
    repository.save_turtle_export(turtle_export)

    assert repository.load_extracted_artifact(artifact.artifact_id) == artifact
    assert repository.load_dataset_artifact(dataset.dataset_id) == dataset
    assert repository.load_turtle_export(turtle_export.dataset_id) == turtle_export


def test_repository_lists_extracted_artifacts_by_issuer_and_year(
    repository: P5ArtifactRepository,
    tmp_path: Path,
) -> None:
    current_entry = _entry(tmp_path, issuer_id="CN_601919", stock_code="601919", fiscal_year=2025)
    prior_entry = _entry(tmp_path, issuer_id="CN_601919", stock_code="601919", fiscal_year=2024)
    other_entry = _entry(tmp_path, issuer_id="CN_600519", stock_code="600519", fiscal_year=2025)

    repository.save_extracted_artifact(_artifact(current_entry))
    repository.save_extracted_artifact(_artifact(prior_entry))
    repository.save_extracted_artifact(_artifact(other_entry))

    assert repository.list_extracted_artifact_ids() == (
        "CN_600519_2025",
        "CN_601919_2024",
        "CN_601919_2025",
    )
    assert repository.list_extracted_artifact_ids(issuer_id="CN_601919") == (
        "CN_601919_2024",
        "CN_601919_2025",
    )
    assert repository.list_extracted_artifact_ids(
        issuer_id="CN_601919",
        fiscal_year=2025,
    ) == ("CN_601919_2025",)


def test_db_repository_round_trips_review_surfaces_lineage_and_recompute(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)
    entry = _entry(tmp_path, issuer_id="CN_601919", stock_code="601919", fiscal_year=2025)
    artifact = _artifact(entry)
    dataset = _dataset(artifact.artifact_id)
    turtle_export = _turtle_export()

    repository.save_extracted_artifact(artifact)
    repository.save_dataset_artifact(dataset)
    repository.save_turtle_export(turtle_export)

    extracted_surface = build_extracted_review_surface(artifact)
    dataset_surface = build_dataset_review_surface(
        dataset,
        extracted_artifacts=(artifact,),
    )
    turtle_surface = build_turtle_export_review_surface(
        turtle_export,
        dataset=dataset,
    )
    lineage = build_dataset_lineage(
        dataset=dataset,
        extracted_artifacts=(artifact,),
        turtle_export=turtle_export,
    )
    plan = _recompute_plan()
    result = _recompute_result()

    repository.save_extracted_review_surface(extracted_surface)
    repository.save_dataset_review_surface(dataset_surface)
    repository.save_turtle_export_review_surface(turtle_surface)
    repository.save_lineage_records(lineage)
    repository.save_recompute_result(run_id="run-1", plan=plan, result=result)

    assert repository.load_extracted_review_surface(artifact.artifact_id) == extracted_surface
    assert repository.load_dataset_review_surface(dataset.dataset_id) == dataset_surface
    assert repository.load_turtle_export_review_surface(dataset.dataset_id) == turtle_surface
    assert repository.list_lineage_records(dataset_id=dataset.dataset_id) == lineage
    assert repository.list_lineage_records(source_artifact_id=artifact.artifact_id) == lineage
    assert repository.load_recompute_result("run-1") == result
