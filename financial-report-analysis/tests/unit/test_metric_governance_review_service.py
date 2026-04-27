from datetime import datetime, timezone

from financial_report_analysis.models import (
    MetricGovernanceDecision,
    MetricGovernanceDecisionAnnotation,
    MetricGovernanceReviewItem,
)


def test_metric_governance_review_item_records_latest_mapping_decision() -> None:
    created_at = datetime(2026, 4, 27, tzinfo=timezone.utc)
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
        created_at=created_at,
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
        created_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
    )

    annotation = MetricGovernanceDecisionAnnotation.from_decision(decision)

    assert annotation.decision_type == "keep_provisional"
    assert annotation.target_metric_id is None
