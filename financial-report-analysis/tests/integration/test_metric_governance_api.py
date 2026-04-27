from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from financial_report_analysis.api.app import create_app
from financial_report_analysis.api.runtime import build_api_runtime
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.services.metric_governance_review import (
    build_review_item_id,
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
        candidate_facts=(
            {
                "fact_id": "/tmp/report.pdf:candidate:1",
                "metric_id": "custom::cn::general::income-statement::root::contract-assets",
                "raw_label": "Contract assets",
                "normalized_label": "contract assets",
                "statement_type": "income_statement",
                "value": 125.0,
                "evidence_bundle_id": "bundle-1",
                "extensions": {
                    "table_id": "table-7",
                    "page_number": 88,
                    "period_label": "FY2025",
                    "metric_governance": {
                        "registry_status": "provisional",
                        "metric_namespace": "custom",
                        "review_required": True,
                        "auto_analysis_allowed": False,
                        "governance_reason": "provisional_custom_metric",
                    },
                },
            },
            {
                "fact_id": "candidate-2",
                "metric_id": "revenue",
                "raw_label": "Revenue",
                "normalized_label": "revenue",
                "statement_type": "income_statement",
                "value": 500.0,
                "evidence_bundle_id": "bundle-2",
                "extensions": {
                    "table_id": "table-8",
                    "page_number": 89,
                    "period_label": "FY2025",
                    "metric_governance": {
                        "registry_status": "standard",
                        "metric_namespace": "standard",
                        "review_required": False,
                        "auto_analysis_allowed": True,
                        "governance_reason": "standard_metric",
                    },
                },
            },
        ),
        canonical_facts=(),
        derived_facts=(),
        validation_report={"overall_status": "review_required", "issues": []},
        review_packets=(),
        quality_gate="review",
        missing_status={},
        created_at="2026-04-27T12:00:00+00:00",
    )


def test_metric_governance_review_list_and_write_flow(tmp_path: Path) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))

    list_response = client.get(
        "/api/v1/metric-governance/review-items",
        params={"issuer_id": "CN_601919"},
    )

    assert list_response.status_code == 200
    payload = list_response.json()
    assert len(payload["items"]) == 1
    review_item_id = payload["items"][0]["review_item_id"]

    write_response = client.post(
        "/api/v1/metric-governance/review-items/decision",
        json={
            "review_item_id": review_item_id,
            "decision_type": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "maps to supported receivables metric",
            "actor": "reviewer@example.com",
        },
    )

    assert write_response.status_code == 200
    assert write_response.json()["decision"]["decision_type"] == "map_to_standard"

    detail_response = client.get(
        f"/api/v1/metric-governance/review-items/{review_item_id}",
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["latest_decision"]["target_metric_id"] == (
        "accounts_receiv"
    )


def test_metric_governance_rejects_unknown_review_item(tmp_path: Path) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    client = TestClient(create_app(runtime=runtime))

    response = client.post(
        "/api/v1/metric-governance/review-items/decision",
        json={
            "review_item_id": "missing:item",
            "decision_type": "keep_provisional",
            "reason": "not enough evidence",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 404


def test_metric_governance_rejects_unknown_target_metric_id(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))

    list_response = client.get(
        "/api/v1/metric-governance/review-items",
        params={"issuer_id": "CN_601919"},
    )

    assert list_response.status_code == 200
    payload = list_response.json()
    assert len(payload["items"]) == 1
    review_item_id = payload["items"][0]["review_item_id"]

    response = client.post(
        "/api/v1/metric-governance/review-items/decision",
        json={
            "review_item_id": review_item_id,
            "decision_type": "map_to_standard",
            "target_metric_id": "custom::bad",
            "reason": "unsupported custom metric id",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 422


def test_metric_governance_rejects_non_provisional_review_item(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))

    review_item_id = build_review_item_id(artifact.artifact_id, "candidate-2")
    response = client.post(
        "/api/v1/metric-governance/review-items/decision",
        json={
            "review_item_id": review_item_id,
            "decision_type": "keep_provisional",
            "reason": "should be rejected for standard candidate",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 422
