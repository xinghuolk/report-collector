from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace

from financial_report_analysis.models import (
    MetricGovernanceReviewItem,
    MetricLifecycleConsumptionAction,
    MetricLifecycleRecomputeAudit,
    MetricLifecycleRecomputeAuditItem,
    MetricLifecycleRecomputeAuditSummary,
    MetricLifecycleState,
)
from financial_report_analysis.p5.models import P5ExtractedArtifact
from financial_report_analysis.services.metric_governance_review import (
    parse_review_item_id,
)


def build_metric_lifecycle_recompute_audit(
    *,
    review_items: tuple[MetricGovernanceReviewItem, ...],
    lifecycle_state_loader: Callable[[str], MetricLifecycleState],
    dry_run_artifact_loader: Callable[[str], P5ExtractedArtifact | None] | None = None,
) -> MetricLifecycleRecomputeAudit:
    items: list[MetricLifecycleRecomputeAuditItem] = []
    for review_item in review_items:
        state = lifecycle_state_loader(review_item.review_item_id)
        if state.candidate_link is None:
            continue

        item = _audit_item(review_item, state)
        if dry_run_artifact_loader is not None:
            artifact = dry_run_artifact_loader(item.artifact_id)
            if artifact is not None:
                item = _with_dry_run_consumption(item, artifact)
        items.append(item)

    return MetricLifecycleRecomputeAudit(
        items=tuple(items),
        summary=MetricLifecycleRecomputeAuditSummary(
            review_item_count=len(items),
            artifact_count=len({item.artifact_id for item in items}),
            recompute_needed_count=sum(1 for item in items if item.recompute_needed),
            dry_run_conflict_count=sum(
                1 for item in items if item.conflict_state == "conflict"
            ),
        ),
    )


def _audit_item(
    review_item: MetricGovernanceReviewItem,
    state: MetricLifecycleState,
) -> MetricLifecycleRecomputeAuditItem:
    status = state.entry.current_status if state.entry is not None else None
    decision = state.latest_decision
    consumption_action: MetricLifecycleConsumptionAction = "none"
    recompute_needed = False
    reason = "lifecycle decision does not affect automatic outputs"
    if status == "mapped_to_standard":
        consumption_action = "map_to_standard"
        recompute_needed = True
        reason = "lifecycle decision affects automatic outputs"
    elif status == "blacklisted":
        consumption_action = "suppress_blacklisted"
        recompute_needed = True
        reason = "lifecycle decision affects automatic outputs"

    return MetricLifecycleRecomputeAuditItem(
        review_item_id=review_item.review_item_id,
        artifact_id=review_item.artifact_id,
        issuer_id=review_item.issuer_id,
        fiscal_year=review_item.fiscal_year,
        report_type=review_item.report_type,
        candidate_metric_id=review_item.metric_id,
        raw_label=review_item.raw_label,
        lifecycle_entry_id=(
            state.entry.lifecycle_entry_id if state.entry is not None else None
        ),
        current_status=status,
        latest_decision_id=decision.decision_id if decision is not None else None,
        latest_decision_action=decision.action if decision is not None else None,
        target_metric_id=decision.target_metric_id if decision is not None else None,
        recompute_needed=recompute_needed,
        consumption_action=consumption_action,
        conflict_state="none",
        reason=reason,
    )


def _with_dry_run_consumption(
    item: MetricLifecycleRecomputeAuditItem,
    artifact: P5ExtractedArtifact,
) -> MetricLifecycleRecomputeAuditItem:
    if item.consumption_action == "suppress_blacklisted":
        return item
    if item.consumption_action != "map_to_standard":
        return item
    if item.target_metric_id is None:
        return replace(
            item,
            consumption_action="conflict",
            conflict_state="missing_target",
        )

    candidate = _candidate_fact_for_review_item(item.review_item_id, artifact)
    if candidate is None:
        return replace(
            item,
            consumption_action="conflict",
            conflict_state="missing_candidate",
        )

    target_fact = _matching_canonical_fact(
        candidate=candidate,
        target_metric_id=item.target_metric_id,
        canonical_facts=artifact.canonical_facts,
    )
    if target_fact is None:
        return item

    if _numeric_value(target_fact) == _numeric_value(candidate):
        return replace(
            item,
            consumption_action="already_present",
            conflict_state="already_present",
        )

    return replace(
        item,
        consumption_action="conflict",
        conflict_state="conflict",
    )


def _candidate_fact_for_review_item(
    review_item_id: str,
    artifact: P5ExtractedArtifact,
) -> Mapping[str, object] | None:
    _artifact_id, fact_id = parse_review_item_id(review_item_id)
    if fact_id is None:
        return None
    for candidate in artifact.candidate_facts:
        if str(candidate.get("fact_id", "")) == fact_id:
            return candidate
    return None


def _matching_canonical_fact(
    *,
    candidate: Mapping[str, object],
    target_metric_id: str,
    canonical_facts: tuple[dict[str, object], ...],
) -> Mapping[str, object] | None:
    same_scope_facts = (
        fact
        for fact in canonical_facts
        if fact.get("metric_id") == target_metric_id
        and fact.get("entity_scope") == candidate.get("entity_scope")
        and _period_scope(fact) == _period_scope(candidate)
        and fact.get("statement_type") == candidate.get("statement_type")
    )
    candidate_value = _numeric_value(candidate)
    first_conflict: Mapping[str, object] | None = None
    for fact in same_scope_facts:
        if _numeric_value(fact) == candidate_value:
            return fact
        if first_conflict is None:
            first_conflict = fact
    return first_conflict


def _period_scope(fact: Mapping[str, object]) -> object:
    extensions = fact.get("extensions")
    if not isinstance(extensions, dict):
        return None
    return extensions.get("period_scope")


def _numeric_value(fact: Mapping[str, object]) -> object:
    return fact.get("numeric_value")
