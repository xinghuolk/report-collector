from pathlib import Path

from financial_report_analysis.models import (
    MetricGovernanceDecision,
    MetricGovernanceDecisionAnnotation,
    MetricGovernanceReviewItem,
)
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.services.metric_governance_review import (
    MetricGovernanceReviewService,
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
                "fact_id": "candidate-1",
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
                "statement_type": "income_statement",
                "value": 500.0,
                "extensions": {
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


class _StubRepository:
    def __init__(
        self,
        artifact: P5ExtractedArtifact,
        decision: MetricGovernanceDecision | None = None,
    ) -> None:
        self._artifact = artifact
        self._decision = decision

    def list_extracted_artifact_ids(
        self,
        issuer_id: str | None = None,
        fiscal_year: int | None = None,
    ) -> tuple[str, ...]:
        return (self._artifact.artifact_id,)

    def load_extracted_artifact(self, artifact_id: str) -> P5ExtractedArtifact:
        assert artifact_id == self._artifact.artifact_id
        return self._artifact

    def load_latest_metric_governance_decision(
        self,
        review_item_id: str,
    ) -> MetricGovernanceDecision | None:
        return self._decision


def test_metric_governance_review_item_records_latest_mapping_decision() -> None:
    decision = MetricGovernanceDecision(
        decision_id="decision-001",
        review_item_id="review-001",
        artifact_id="artifact-001",
        issuer_id="issuer-001",
        fiscal_year=2025,
        report_type="annual",
        metric_id="custom_accounts_receivable",
        raw_label="Accounts receivable",
        normalized_label="accounts receivable",
        statement_type="balance_sheet",
        evidence_bundle_id="evidence-001",
        decision_type="map_to_standard",
        target_metric_id="accounts_receiv",
        reason="Matches the standard receivables metric.",
        actor="analyst@example.com",
        created_at="2026-04-27T12:00:00+00:00",
    )
    annotation = MetricGovernanceDecisionAnnotation.from_decision(decision)
    review_item = MetricGovernanceReviewItem(
        review_item_id="review-001",
        artifact_id="artifact-001",
        issuer_id="issuer-001",
        fiscal_year=2025,
        report_type="annual",
        metric_id="custom_accounts_receivable",
        raw_label="Accounts receivable",
        normalized_label="accounts receivable",
        statement_type="balance_sheet",
        candidate_value=1200.0,
        period_label="2025",
        source_page=12,
        source_table_id="table-001",
        evidence_bundle_id="evidence-001",
        metric_governance={"status": "provisional"},
        latest_decision=annotation,
    )

    assert review_item.latest_decision is not None
    assert review_item.latest_decision.decision_type == "map_to_standard"
    assert review_item.latest_decision.target_metric_id == "accounts_receiv"


def test_metric_governance_decision_annotation_keeps_provisional_metric() -> None:
    decision = MetricGovernanceDecision(
        decision_id="decision-002",
        review_item_id="review-002",
        artifact_id="artifact-002",
        issuer_id="issuer-001",
        fiscal_year=2025,
        report_type="annual",
        metric_id="custom_metric",
        raw_label="Custom metric",
        normalized_label="custom metric",
        statement_type="income_statement",
        evidence_bundle_id="evidence-002",
        decision_type="keep_provisional",
        target_metric_id=None,
        reason="No matching standard metric exists.",
        actor="analyst@example.com",
        created_at="2026-04-27T12:05:00+00:00",
    )

    annotation = MetricGovernanceDecisionAnnotation.from_decision(decision)

    assert annotation.decision_type == "keep_provisional"
    assert annotation.target_metric_id is None


def test_service_lists_only_provisional_review_items(tmp_path: Path) -> None:
    artifact = _artifact(_entry(tmp_path))
    service = MetricGovernanceReviewService(_StubRepository(artifact))

    items = service.list_review_items(issuer_id="CN_601919")

    assert len(items) == 1
    assert items[0].metric_id.startswith("custom::")
    assert items[0].raw_label == "Contract assets"


def test_service_hydrates_latest_decision_annotation(tmp_path: Path) -> None:
    artifact = _artifact(_entry(tmp_path))
    decision = MetricGovernanceDecision(
        decision_id="decision-1",
        review_item_id=f"{artifact.artifact_id}:candidate-1",
        artifact_id=artifact.artifact_id,
        issuer_id="CN_601919",
        fiscal_year=2025,
        report_type="annual",
        metric_id="custom::cn::general::income-statement::root::contract-assets",
        raw_label="Contract assets",
        normalized_label="contract assets",
        statement_type="income_statement",
        evidence_bundle_id="bundle-1",
        decision_type="map_to_standard",
        target_metric_id="accounts_receiv",
        reason="maps to supported receivables field",
        actor="reviewer@example.com",
        created_at="2026-04-27T12:05:00+00:00",
    )
    service = MetricGovernanceReviewService(_StubRepository(artifact, decision))

    item = service.get_review_item(f"{artifact.artifact_id}:candidate-1")

    assert item is not None
    assert item.latest_decision is not None
    assert item.latest_decision.target_metric_id == "accounts_receiv"
