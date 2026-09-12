from __future__ import annotations

from pathlib import Path

from financial_report_analysis.models import (
    MetricGovernanceReviewItem,
    MetricLifecycleCandidateLink,
    MetricLifecycleConceptIdentity,
    MetricLifecycleDecision,
    MetricLifecycleEntry,
    MetricLifecycleState,
    MetricLifecycleStatus,
)
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.services.metric_governance_review import (
    build_review_item_id,
)
from financial_report_analysis.services.metric_lifecycle_recompute import (
    build_metric_lifecycle_recompute_audit,
)


def test_audit_returns_empty_summary_without_links() -> None:
    audit = build_metric_lifecycle_recompute_audit(
        review_items=(),
        lifecycle_state_loader=lambda _review_item_id: MetricLifecycleState(
            entry=None,
            latest_decision=None,
            candidate_link=None,
            decision_history=(),
        ),
    )

    assert audit.items == ()
    assert audit.summary.review_item_count == 0
    assert audit.summary.artifact_count == 0
    assert audit.summary.recompute_needed_count == 0
    assert audit.summary.dry_run_conflict_count == 0


def test_audit_marks_mapped_and_blacklisted_items_recompute_needed() -> None:
    mapped_id = build_review_item_id("CN_601919_2025", "candidate-mapped")
    blacklisted_id = build_review_item_id("CN_601919_2025", "candidate-blacklisted")
    mapped_item = _review_item(
        mapped_id,
        artifact_id="CN_601919_2025",
        metric_id="custom::cn::general::balance-sheet::root::deposit",
    )
    blacklisted_item = _review_item(
        blacklisted_id,
        artifact_id="CN_601919_2025",
        metric_id="custom::cn::general::income-statement::root::bad",
    )

    audit = build_metric_lifecycle_recompute_audit(
        review_items=(mapped_item, blacklisted_item),
        lifecycle_state_loader=lambda review_item_id: {
            mapped_id: _state(
                mapped_id,
                "mapped_to_standard",
                action="map_to_standard",
                target_metric_id="accounts_receiv",
            ),
            blacklisted_id: _state(
                blacklisted_id,
                "blacklisted",
                action="blacklist",
            ),
        }[review_item_id],
    )

    assert [item.consumption_action for item in audit.items] == [
        "map_to_standard",
        "suppress_blacklisted",
    ]
    assert all(item.recompute_needed for item in audit.items)
    assert audit.summary.artifact_count == 1
    assert audit.summary.recompute_needed_count == 2


def test_audit_leaves_non_output_states_not_recompute_needed() -> None:
    approved_id = build_review_item_id("CN_601919_2025", "candidate-approved")
    deprecated_id = build_review_item_id("CN_601919_2025", "candidate-deprecated")
    provisional_id = build_review_item_id("CN_601919_2025", "candidate-provisional")
    items = (
        _review_item(approved_id),
        _review_item(deprecated_id),
        _review_item(provisional_id),
    )

    audit = build_metric_lifecycle_recompute_audit(
        review_items=items,
        lifecycle_state_loader=lambda review_item_id: {
            approved_id: _state(
                approved_id,
                "approved_custom",
                action="approve_custom",
            ),
            deprecated_id: _state(
                deprecated_id,
                "deprecated",
                action="deprecate",
            ),
            provisional_id: _state_without_decision(provisional_id, "provisional"),
        }[review_item_id],
    )

    assert [item.recompute_needed for item in audit.items] == [False, False, False]
    assert [item.consumption_action for item in audit.items] == [
        "none",
        "none",
        "none",
    ]


def test_dry_run_reports_already_present_and_conflict() -> None:
    same_value_id = build_review_item_id("CN_601919_2025", "candidate-same")
    conflict_id = build_review_item_id("CN_601919_2025", "candidate-conflict")
    artifact = _artifact(
        artifact_id="CN_601919_2025",
        candidate_facts=(
            _candidate_fact("candidate-same", numeric_value=100),
            _candidate_fact("candidate-conflict", numeric_value=200),
        ),
        canonical_facts=(
            _canonical_fact("accounts_receiv", numeric_value=100),
            _canonical_fact("accounts_receiv", numeric_value=999),
        ),
    )

    audit = build_metric_lifecycle_recompute_audit(
        review_items=(
            _review_item(same_value_id),
            _review_item(conflict_id),
        ),
        lifecycle_state_loader=lambda review_item_id: _state(
            review_item_id,
            "mapped_to_standard",
            action="map_to_standard",
            target_metric_id="accounts_receiv",
        ),
        dry_run_artifact_loader=lambda _artifact_id: artifact,
    )

    assert [item.consumption_action for item in audit.items] == [
        "already_present",
        "conflict",
    ]
    assert [item.conflict_state for item in audit.items] == [
        "already_present",
        "conflict",
    ]
    assert audit.summary.dry_run_conflict_count == 1


def test_dry_run_reports_missing_target_and_missing_candidate() -> None:
    missing_target_id = build_review_item_id("CN_601919_2025", "candidate-target")
    missing_candidate_id = build_review_item_id("CN_601919_2025", "candidate-missing")
    artifact = _artifact(
        artifact_id="CN_601919_2025",
        candidate_facts=(_candidate_fact("candidate-target", numeric_value=100),),
        canonical_facts=(),
    )

    audit = build_metric_lifecycle_recompute_audit(
        review_items=(
            _review_item(missing_target_id),
            _review_item(missing_candidate_id),
        ),
        lifecycle_state_loader=lambda review_item_id: {
            missing_target_id: _state(
                missing_target_id,
                "mapped_to_standard",
                action="map_to_standard",
                target_metric_id=None,
            ),
            missing_candidate_id: _state(
                missing_candidate_id,
                "mapped_to_standard",
                action="map_to_standard",
                target_metric_id="accounts_receiv",
            ),
        }[review_item_id],
        dry_run_artifact_loader=lambda _artifact_id: artifact,
    )

    assert [item.consumption_action for item in audit.items] == [
        "conflict",
        "conflict",
    ]
    assert [item.conflict_state for item in audit.items] == [
        "missing_target",
        "missing_candidate",
    ]


def test_dry_run_reports_blacklisted_suppression() -> None:
    review_item_id = build_review_item_id("CN_601919_2025", "candidate-blacklisted")
    artifact = _artifact(
        artifact_id="CN_601919_2025",
        candidate_facts=(_candidate_fact("candidate-blacklisted", numeric_value=100),),
        canonical_facts=(
            _canonical_fact(
                "custom::cn::general::income-statement::root::bad",
                numeric_value=100,
                statement_type="income_statement",
            ),
        ),
    )

    audit = build_metric_lifecycle_recompute_audit(
        review_items=(
            _review_item(
                review_item_id,
                metric_id="custom::cn::general::income-statement::root::bad",
                statement_type="income_statement",
            ),
        ),
        lifecycle_state_loader=lambda _review_item_id: _state(
            review_item_id,
            "blacklisted",
            action="blacklist",
        ),
        dry_run_artifact_loader=lambda _artifact_id: artifact,
    )

    assert audit.items[0].consumption_action == "suppress_blacklisted"
    assert audit.items[0].conflict_state == "none"


def _review_item(
    review_item_id: str,
    *,
    artifact_id: str = "CN_601919_2025",
    metric_id: str = "custom::cn::general::balance-sheet::root::deposit",
    statement_type: str = "balance_sheet",
) -> MetricGovernanceReviewItem:
    return MetricGovernanceReviewItem(
        review_item_id=review_item_id,
        artifact_id=artifact_id,
        issuer_id="CN_601919",
        fiscal_year=2025,
        report_type="annual",
        metric_id=metric_id,
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type=statement_type,
        candidate_value=100,
        period_label="FY2025",
        source_page=12,
        source_table_id="table-1",
        evidence_bundle_id="bundle-1",
        metric_governance={"registry_status": "provisional"},
    )


def _state(
    review_item_id: str,
    status: MetricLifecycleStatus,
    *,
    action: str,
    target_metric_id: str | None = None,
) -> MetricLifecycleState:
    entry = _entry(status=status, target_metric_id=target_metric_id)
    decision = MetricLifecycleDecision(
        decision_id=f"decision:{status}",
        lifecycle_entry_id=entry.lifecycle_entry_id,
        action=action,  # type: ignore[arg-type]
        previous_status="provisional",
        new_status=status,
        target_metric_id=target_metric_id,
        actor="reviewer@example.com",
        reason="reviewed lifecycle state",
        evidence_bundle_id="bundle-1",
        source_review_item_id=review_item_id,
        source_artifact_id="CN_601919_2025",
        created_at="2026-04-28T10:00:00+00:00",
        effective_at="2026-04-28T10:00:00+00:00",
    )
    return MetricLifecycleState(
        entry=entry,
        latest_decision=decision,
        candidate_link=_link(review_item_id, entry.lifecycle_entry_id),
        decision_history=(decision,),
    )


def _state_without_decision(
    review_item_id: str,
    status: MetricLifecycleStatus,
) -> MetricLifecycleState:
    entry = _entry(status=status, target_metric_id=None)
    return MetricLifecycleState(
        entry=entry,
        latest_decision=None,
        candidate_link=_link(review_item_id, entry.lifecycle_entry_id),
        decision_history=(),
    )


def _entry(
    *,
    status: MetricLifecycleStatus,
    target_metric_id: str | None,
) -> MetricLifecycleEntry:
    return MetricLifecycleEntry(
        lifecycle_entry_id=f"lifecycle:{status}",
        concept=MetricLifecycleConceptIdentity(
            issuer_id="CN_601919",
            metric_id="custom::cn::general::balance-sheet::root::deposit",
            raw_label="Customer deposits",
            normalized_label="customer deposits",
            statement_type="balance_sheet",
            accounting_standard="CAS",
            industry_slug="general",
            parent_metric_id=None,
        ),
        current_status=status,
        mapped_standard_metric_id=target_metric_id,
        created_at="2026-04-28T09:00:00+00:00",
        updated_at="2026-04-28T10:00:00+00:00",
        created_by="reviewer@example.com",
    )


def _link(review_item_id: str, lifecycle_entry_id: str) -> MetricLifecycleCandidateLink:
    return MetricLifecycleCandidateLink(
        candidate_link_id=f"link:{review_item_id}",
        lifecycle_entry_id=lifecycle_entry_id,
        review_item_id=review_item_id,
        artifact_id="CN_601919_2025",
        issuer_id="CN_601919",
        fiscal_year=2025,
        report_type="annual",
        candidate_metric_id="custom::cn::general::balance-sheet::root::deposit",
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type="balance_sheet",
        evidence_bundle_id="bundle-1",
        created_at="2026-04-28T09:05:00+00:00",
        created_by="reviewer@example.com",
    )


def _artifact(
    *,
    artifact_id: str,
    candidate_facts: tuple[dict[str, object], ...],
    canonical_facts: tuple[dict[str, object], ...],
) -> P5ExtractedArtifact:
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=Path("/tmp/CN_601919_2025.pdf"),
        source="fixture",
    )
    return P5ExtractedArtifact(
        artifact_id=artifact_id,
        artifact_version="p5-v1",
        pipeline_version="pipeline-v1",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={},
        document_metadata={},
        candidate_facts=candidate_facts,
        canonical_facts=canonical_facts,
        derived_facts=(),
        validation_report={},
        review_packets=(),
        quality_gate="pass",
        missing_status={},
        created_at="2026-04-28T10:00:00+00:00",
    )


def _candidate_fact(
    fact_id: str,
    *,
    numeric_value: int,
    metric_id: str = "custom::cn::general::balance-sheet::root::deposit",
    statement_type: str = "balance_sheet",
) -> dict[str, object]:
    return {
        "fact_id": fact_id,
        "metric_id": metric_id,
        "numeric_value": numeric_value,
        "entity_scope": "consolidated",
        "extensions": {"period_scope": "fy"},
        "statement_type": statement_type,
    }


def _canonical_fact(
    metric_id: str,
    *,
    numeric_value: int,
    statement_type: str = "balance_sheet",
) -> dict[str, object]:
    return {
        "fact_id": f"canonical-{metric_id}-{numeric_value}",
        "metric_id": metric_id,
        "numeric_value": numeric_value,
        "entity_scope": "consolidated",
        "extensions": {"period_scope": "fy"},
        "statement_type": statement_type,
    }
