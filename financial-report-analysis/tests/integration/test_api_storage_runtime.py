from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from financial_report_analysis.api.app import create_app
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


def _seed_runtime(client: TestClient, tmp_path: Path) -> None:
    runtime = client.app.state.runtime
    repository = runtime.storage_repository
    service = runtime.historical_ingestion_service
    assert repository is not None
    assert service is not None

    entries = (
        _entry(tmp_path, issuer_id="CN_601919", stock_code="601919", fiscal_year=2024),
        _entry(tmp_path, issuer_id="CN_601919", stock_code="601919", fiscal_year=2025),
        _entry(tmp_path, issuer_id="CN_600519", stock_code="600519", fiscal_year=2024),
        _entry(tmp_path, issuer_id="CN_600519", stock_code="600519", fiscal_year=2025),
        _entry(tmp_path, issuer_id="CN_000333", stock_code="000333", fiscal_year=2024),
        _entry(tmp_path, issuer_id="CN_000333", stock_code="000333", fiscal_year=2025),
    )
    for entry in entries:
        service.register_report(entry)

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
    repository.save_extracted_review_surface(build_extracted_review_surface(artifacts[0]))
    repository.save_dataset_review_surface(
        build_dataset_review_surface(dataset, extracted_artifacts=artifacts)
    )
    repository.save_turtle_export_review_surface(
        build_turtle_export_review_surface(turtle_export, dataset=dataset)
    )
    repository.save_lineage_records(
        build_dataset_lineage(
            dataset=dataset,
            extracted_artifacts=artifacts,
            turtle_export=turtle_export,
        )
    )
    repository.save_recompute_result(
        run_id="recompute-run-1",
        plan=P5RecomputePlan(
            manifest_id="p5_seed_manifest",
            dataset_id=dataset.dataset_id,
            target_artifact_ids=(artifacts[0].artifact_id,),
            rebuild_dataset=True,
            rebuild_turtle_export=True,
            reason="pipeline_version_changed",
        ),
        result=P5RecomputeResult(
            manifest_id="p5_seed_manifest",
            extracted_artifact_ids=tuple(artifact.artifact_id for artifact in artifacts),
            dataset_path=Path("data/p5/datasets/p5_seed_3_issuers_2_years.json"),
            turtle_export_path=Path(
                "data/p5/datasets/p5_seed_3_issuers_2_years_turtle_export.json"
            ),
            diff_summary=P5RecomputeDiffSummary(
                reason="pipeline_version_changed",
                target_artifact_ids=(artifacts[0].artifact_id,),
                dataset_changed=True,
                turtle_export_changed=True,
                rebuilt_dataset=True,
                rebuilt_turtle_export=True,
            ),
        ),
    )


def test_storage_backed_routes_return_503_without_runtime_storage() -> None:
    client = TestClient(create_app())

    response = client.get("/issuers/CN_601919/reports")

    assert response.status_code == 503
    assert response.json()["detail"] == "storage repository is not configured"


def test_storage_backed_routes_return_seeded_objects(tmp_path: Path) -> None:
    client = TestClient(create_app(storage_db_path=tmp_path / "runtime.db"))
    _seed_runtime(client, tmp_path)

    reports_response = client.get("/issuers/CN_601919/reports")
    assert reports_response.status_code == 200
    assert reports_response.json()["issuer_id"] == "CN_601919"
    assert [record["fiscal_year"] for record in reports_response.json()["reports"]] == [
        2024,
        2025,
    ]

    coverage_response = client.get("/reports/CN_601919/2025/annual")
    assert coverage_response.status_code == 200
    assert coverage_response.json()["extracted_artifact_available"] is True
    assert coverage_response.json()["extracted_artifact_ids"] == ["CN_601919_2025"]

    artifact_response = client.get("/artifacts/CN_601919_2025")
    assert artifact_response.status_code == 200
    assert artifact_response.json()["artifact_id"] == "CN_601919_2025"
    assert artifact_response.json()["manifest_entry"]["issuer_id"] == "CN_601919"

    dataset_response = client.get("/datasets/p5_seed_3_issuers_2_years")
    assert dataset_response.status_code == 200
    assert dataset_response.json()["dataset_id"] == "p5_seed_3_issuers_2_years"
    assert len(dataset_response.json()["rows"]) == 3

    audit_response = client.get("/datasets/p5_seed_3_issuers_2_years/audit")
    assert audit_response.status_code == 200
    assert audit_response.json()["latest_recompute_run_id"] == "recompute-run-1"
    assert len(audit_response.json()["source_artifacts"]) == 3

    recompute_response = client.get("/recompute-runs/recompute-run-1")
    assert recompute_response.status_code == 200
    assert recompute_response.json()["run_id"] == "recompute-run-1"
    assert recompute_response.json()["diff_summary"]["reason"] == "pipeline_version_changed"


def test_storage_backed_routes_return_404_for_missing_objects(tmp_path: Path) -> None:
    client = TestClient(create_app(storage_db_path=tmp_path / "runtime.db"))

    artifact_response = client.get("/artifacts/missing-artifact")
    assert artifact_response.status_code == 404
    assert "missing extracted artifact in DB repository" in artifact_response.json()["detail"]

    dataset_response = client.get("/datasets/missing-dataset")
    assert dataset_response.status_code == 404
    assert "missing dataset artifact in DB repository" in dataset_response.json()["detail"]

    audit_response = client.get("/datasets/missing-dataset/audit")
    assert audit_response.status_code == 404
    assert "missing dataset artifact in DB repository" in audit_response.json()["detail"]

    recompute_response = client.get("/recompute-runs/missing-run")
    assert recompute_response.status_code == 404
    assert "missing recompute result in DB repository" in recompute_response.json()["detail"]
