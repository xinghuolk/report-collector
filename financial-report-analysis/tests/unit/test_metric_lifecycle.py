from __future__ import annotations

from financial_report_analysis.models import (
    MetricLifecycleCandidateLink,
    MetricLifecycleConceptIdentity,
    MetricLifecycleDecision,
    MetricLifecycleEntry,
    MetricLifecycleState,
)


def _identity() -> MetricLifecycleConceptIdentity:
    return MetricLifecycleConceptIdentity(
        issuer_id="HK_09987",
        metric_id="custom::ifrs::ecommerce::balance-sheet::root::customer-deposits",
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type="balance_sheet",
        accounting_standard="IFRS",
        industry_slug="ecommerce",
        parent_metric_id=None,
    )


def test_lifecycle_entry_keeps_concept_identity_and_status() -> None:
    entry = MetricLifecycleEntry(
        lifecycle_entry_id="lifecycle:001",
        concept=_identity(),
        current_status="provisional",
        mapped_standard_metric_id=None,
        created_at="2026-04-27T10:00:00+00:00",
        updated_at="2026-04-27T10:00:00+00:00",
        created_by="reviewer@example.com",
    )

    assert entry.concept.issuer_id == "HK_09987"
    assert entry.current_status == "provisional"
    assert entry.mapped_standard_metric_id is None


def test_lifecycle_decision_records_transition_and_evidence() -> None:
    decision = MetricLifecycleDecision(
        decision_id="decision:001",
        lifecycle_entry_id="lifecycle:001",
        action="map_to_standard",
        previous_status="provisional",
        new_status="mapped_to_standard",
        target_metric_id="accounts_receiv",
        actor="reviewer@example.com",
        reason="Matches standard accounts receivable.",
        evidence_bundle_id="bundle:001",
        source_review_item_id="review:001",
        source_artifact_id="artifact:001",
        created_at="2026-04-27T10:01:00+00:00",
        effective_at="2026-04-27T10:01:00+00:00",
    )

    assert decision.action == "map_to_standard"
    assert decision.previous_status == "provisional"
    assert decision.new_status == "mapped_to_standard"
    assert decision.target_metric_id == "accounts_receiv"


def test_candidate_link_bridges_review_item_to_lifecycle_entry() -> None:
    link = MetricLifecycleCandidateLink(
        candidate_link_id="link:001",
        lifecycle_entry_id="lifecycle:001",
        review_item_id="review:001",
        artifact_id="artifact:001",
        issuer_id="HK_09987",
        fiscal_year=2025,
        report_type="annual",
        candidate_metric_id="custom::ifrs::ecommerce::balance-sheet::root::customer-deposits",
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type="balance_sheet",
        evidence_bundle_id="bundle:001",
        created_at="2026-04-27T10:02:00+00:00",
        created_by="reviewer@example.com",
    )

    assert link.review_item_id == "review:001"
    assert link.lifecycle_entry_id == "lifecycle:001"


def test_lifecycle_state_can_represent_missing_state() -> None:
    state = MetricLifecycleState(
        entry=None,
        latest_decision=None,
        candidate_link=None,
        decision_history=(),
    )

    assert state.entry is None
    assert state.latest_decision is None
    assert state.decision_history == ()
