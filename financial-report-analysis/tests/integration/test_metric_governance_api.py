from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from financial_report_analysis.api.app import create_app
from financial_report_analysis.api.runtime import build_api_runtime
from financial_report_analysis.api.routes import _metric_lifecycle_state_to_response
from financial_report_analysis.models import (
    MetricLifecycleCandidateLink,
    MetricLifecycleConceptIdentity,
    MetricLifecycleDecision,
    MetricLifecycleEntry,
    MetricLifecycleState,
)
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


def _artifact_with_malformed_custom_metric(
    entry: P5ManifestEntry,
    metric_id: str = "custom_accounts_receivable",
) -> P5ExtractedArtifact:
    artifact = _artifact(entry)
    first_candidate = dict(artifact.candidate_facts[0])
    first_candidate["metric_id"] = metric_id
    return replace(
        artifact,
        candidate_facts=(first_candidate, *artifact.candidate_facts[1:]),
    )


def test_metric_governance_lifecycle_entry_endpoint_creates_linked_state(
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
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )

    first_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )
    second_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_state = first_response.json()["review_item"]["lifecycle_state"]
    second_state = second_response.json()["review_item"]["lifecycle_state"]
    assert first_state == second_state
    entry_payload = first_state["entry"]
    assert entry_payload["lifecycle_entry_id"] == (
        second_state["entry"]["lifecycle_entry_id"]
    )
    assert entry_payload["current_status"] == "provisional"
    assert entry_payload["concept"]["accounting_standard"] == "cn"
    assert entry_payload["concept"]["industry_slug"] == "general"
    assert entry_payload["concept"]["statement_type"] == "income_statement"
    assert entry_payload["concept"]["parent_metric_id"] is None
    candidate_link = first_state["candidate_link"]
    assert candidate_link["review_item_id"] == review_item_id
    assert candidate_link["evidence_bundle_id"] == "bundle-1"

    detail_response = client.get(
        f"/api/v1/metric-governance/review-items/{review_item_id}",
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["lifecycle_state"]["entry"][
        "lifecycle_entry_id"
    ] == entry_payload["lifecycle_entry_id"]


@pytest.mark.parametrize(
    "metric_id",
    (
        "custom_accounts_receivable",
        "custom::cn::general::income-statement::root::contract-assets::extra",
        "custom::::income-statement::root::contract-assets",
    ),
)
def test_metric_governance_lifecycle_entry_uses_malformed_custom_defaults(
    tmp_path: Path,
    metric_id: str,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact_with_malformed_custom_metric(entry, metric_id)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )

    response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )

    assert response.status_code == 200
    concept = response.json()["review_item"]["lifecycle_state"]["entry"]["concept"]
    assert concept["accounting_standard"] == "OTHER"
    assert concept["industry_slug"] == "general"
    assert concept["parent_metric_id"] is None


def test_metric_governance_lifecycle_entry_rejects_missing_review_item(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    client = TestClient(create_app(runtime=runtime))

    response = client.post(
        "/api/v1/metric-governance/review-items/missing:item/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )

    assert response.status_code == 404


def test_metric_governance_lifecycle_entry_rejects_non_provisional_review_item(
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
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "review item is not provisional"


def test_metric_governance_lifecycle_entry_rejects_blank_actor(
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
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )

    response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "   "},
    )

    assert response.status_code == 422


def test_metric_governance_lifecycle_entry_requires_storage_runtime() -> None:
    client = TestClient(create_app(runtime=build_api_runtime(None)))

    response = client.post(
        "/api/v1/metric-governance/review-items/missing:item/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "storage repository is not configured"


def test_metric_governance_lifecycle_decision_endpoint_records_mapping(
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
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )
    entry_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )
    assert entry_response.status_code == 200

    decision_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "Matches the supported receivables metric.",
            "actor": "reviewer@example.com",
            "effective_at": "2026-04-27T10:03:00+00:00",
        },
    )

    assert decision_response.status_code == 200
    payload = decision_response.json()
    assert payload["decision"]["action"] == "map_to_standard"
    assert payload["decision"]["previous_status"] == "provisional"
    assert payload["decision"]["new_status"] == "mapped_to_standard"
    assert payload["decision"]["target_metric_id"] == "accounts_receiv"
    assert payload["decision"]["evidence_bundle_id"] == "bundle-1"
    assert payload["decision"]["source_review_item_id"] == review_item_id
    assert payload["decision"]["source_artifact_id"] == artifact.artifact_id
    state = payload["review_item"]["lifecycle_state"]
    assert state["entry"]["current_status"] == "mapped_to_standard"
    assert state["entry"]["mapped_standard_metric_id"] == "accounts_receiv"
    assert state["latest_decision"]["action"] == "map_to_standard"
    assert len(state["decision_history"]) == 1


def test_metric_governance_lifecycle_decision_rejects_missing_review_item(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    client = TestClient(create_app(runtime=runtime))

    response = client.post(
        "/api/v1/metric-governance/review-items/missing:item/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "Missing review item.",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 404


def test_metric_governance_lifecycle_decision_rejects_non_provisional_review_item(
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
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "Standard candidates are not lifecycle review items.",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "review item is not provisional"


def test_metric_governance_lifecycle_decision_requires_candidate_link(
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
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )

    response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "Matches the supported receivables metric.",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "lifecycle candidate link is required"


def test_metric_governance_lifecycle_decision_rejects_target_for_non_mapping_action(
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
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )
    entry_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )
    assert entry_response.status_code == 200

    response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision",
        json={
            "action": "approve_custom",
            "target_metric_id": "accounts_receiv",
            "reason": "Keep as custom metric.",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 422


def test_metric_governance_lifecycle_decision_rejects_blank_actor_and_reason(
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
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )
    entry_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )
    assert entry_response.status_code == 200

    blank_actor_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "Valid reason.",
            "actor": "   ",
        },
    )
    blank_reason_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "   ",
            "actor": "reviewer@example.com",
        },
    )

    assert blank_actor_response.status_code == 422
    assert blank_reason_response.status_code == 422


def test_metric_governance_lifecycle_decision_requires_storage_runtime() -> None:
    client = TestClient(create_app(runtime=build_api_runtime(None)))

    response = client.post(
        "/api/v1/metric-governance/review-items/missing:item/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "Missing storage runtime.",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "storage repository is not configured"


def test_metric_governance_lifecycle_decision_rejects_unknown_standard_target(
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
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )
    entry_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )
    assert entry_response.status_code == 200

    response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "custom::bad",
            "reason": "Unsupported target.",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "target_metric_id must be a supported standard metric"
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
    assert payload["items"][0]["lifecycle_state"] == {
        "entry": None,
        "latest_decision": None,
        "candidate_link": None,
        "decision_history": [],
    }
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
    assert detail_response.json()["lifecycle_state"] == {
        "entry": None,
        "latest_decision": None,
        "candidate_link": None,
        "decision_history": [],
    }
    assert detail_response.json()["latest_decision"]["target_metric_id"] == (
        "accounts_receiv"
    )


def test_metric_governance_phase2_decision_does_not_create_lifecycle_state(
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

    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )

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

    detail_response = client.get(
        f"/api/v1/metric-governance/review-items/{review_item_id}",
    )

    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["latest_decision"]["target_metric_id"] == "accounts_receiv"
    assert payload["lifecycle_state"] == {
        "entry": None,
        "latest_decision": None,
        "candidate_link": None,
        "decision_history": [],
    }


def test_metric_lifecycle_state_response_preserves_non_empty_state() -> None:
    concept = MetricLifecycleConceptIdentity(
        issuer_id="CN_601919",
        metric_id="custom::contract_assets",
        raw_label="Contract assets",
        normalized_label="contract assets",
        statement_type="income_statement",
        accounting_standard="cas",
        industry_slug="shipping",
        parent_metric_id="current_assets",
    )
    entry = MetricLifecycleEntry(
        lifecycle_entry_id="lifecycle-entry-1",
        concept=concept,
        current_status="mapped_to_standard",
        mapped_standard_metric_id="accounts_receiv",
        created_at="2026-04-27T12:00:00+00:00",
        updated_at="2026-04-27T12:05:00+00:00",
        created_by="reviewer@example.com",
    )
    decision = MetricLifecycleDecision(
        decision_id="decision-1",
        lifecycle_entry_id=entry.lifecycle_entry_id,
        action="map_to_standard",
        previous_status="provisional",
        new_status="mapped_to_standard",
        target_metric_id="accounts_receiv",
        actor="reviewer@example.com",
        reason="maps to supported receivables metric",
        evidence_bundle_id="bundle-1",
        source_review_item_id="review-item-1",
        source_artifact_id="artifact-1",
        created_at="2026-04-27T12:06:00+00:00",
        effective_at="2026-04-27T12:06:00+00:00",
    )
    candidate_link = MetricLifecycleCandidateLink(
        candidate_link_id="candidate-link-1",
        lifecycle_entry_id=entry.lifecycle_entry_id,
        review_item_id="review-item-1",
        artifact_id="artifact-1",
        issuer_id="CN_601919",
        fiscal_year=2025,
        report_type="annual",
        candidate_metric_id="custom::contract_assets",
        raw_label="Contract assets",
        normalized_label="contract assets",
        statement_type="income_statement",
        evidence_bundle_id="bundle-1",
        created_at="2026-04-27T12:04:00+00:00",
        created_by="reviewer@example.com",
    )
    state = MetricLifecycleState(
        entry=entry,
        latest_decision=decision,
        candidate_link=candidate_link,
        decision_history=(decision,),
    )

    payload = _metric_lifecycle_state_to_response(state).model_dump()

    assert payload["entry"]["concept"]["parent_metric_id"] == "current_assets"
    assert payload["entry"]["current_status"] == "mapped_to_standard"
    assert payload["latest_decision"]["action"] == "map_to_standard"
    assert payload["candidate_link"]["candidate_metric_id"] == (
        "custom::contract_assets"
    )
    assert payload["decision_history"] == [payload["latest_decision"]]


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
