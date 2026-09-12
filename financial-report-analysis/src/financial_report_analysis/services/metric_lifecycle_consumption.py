from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import replace
from typing import Any

from financial_report_analysis.models import (
    MetricLifecycleRecomputeAudit,
    MetricLifecycleRecomputeAuditItem,
)
from financial_report_analysis.p5.models import P5ExtractedArtifact
from financial_report_analysis.services.metric_governance_review import (
    parse_review_item_id,
)


def apply_metric_lifecycle_consumption(
    *,
    artifact: P5ExtractedArtifact,
    audit: MetricLifecycleRecomputeAudit,
) -> P5ExtractedArtifact:
    canonical_facts = list(artifact.canonical_facts)

    for item in audit.items:
        if item.artifact_id != artifact.artifact_id:
            continue
        if item.consumption_action == "suppress_blacklisted":
            canonical_facts = _suppress_blacklisted(canonical_facts, item)
            continue
        if item.consumption_action != "map_to_standard":
            continue
        if item.target_metric_id is None:
            continue

        candidate = _candidate_fact_for_review_item(item.review_item_id, artifact)
        if candidate is None:
            continue
        if _matching_canonical_facts(
            candidate=candidate,
            target_metric_id=item.target_metric_id,
            canonical_facts=canonical_facts,
        ):
            continue

        canonical_facts.append(_governed_canonical_fact(candidate, item))

    return replace(artifact, canonical_facts=tuple(canonical_facts))


def _suppress_blacklisted(
    canonical_facts: Sequence[dict[str, Any]],
    item: MetricLifecycleRecomputeAuditItem,
) -> list[dict[str, Any]]:
    return [
        fact
        for fact in canonical_facts
        if fact.get("metric_id") != item.candidate_metric_id
    ]


def _candidate_fact_for_review_item(
    review_item_id: str,
    artifact: P5ExtractedArtifact,
) -> Mapping[str, Any] | None:
    artifact_id, fact_id = parse_review_item_id(review_item_id)
    if artifact_id != artifact.artifact_id or fact_id is None:
        return None
    for candidate in artifact.candidate_facts:
        if str(candidate.get("fact_id", "")) == fact_id:
            return candidate
    return None


def _matching_canonical_facts(
    *,
    candidate: Mapping[str, Any],
    target_metric_id: str,
    canonical_facts: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        fact
        for fact in canonical_facts
        if fact.get("metric_id") == target_metric_id
        and fact.get("entity_scope") == candidate.get("entity_scope")
        and _period_scope(fact) == _period_scope(candidate)
        and fact.get("statement_type") == candidate.get("statement_type")
    )


def _governed_canonical_fact(
    candidate: Mapping[str, Any],
    item: MetricLifecycleRecomputeAuditItem,
) -> dict[str, Any]:
    governed = deepcopy(dict(candidate))
    governed["metric_id"] = item.target_metric_id
    extensions = _deepcopy_mapping(governed.get("extensions"))
    metric_governance = _deepcopy_mapping(extensions.get("metric_governance"))
    metric_governance["lifecycle_consumption"] = {
        "source_review_item_id": item.review_item_id,
        "lifecycle_entry_id": item.lifecycle_entry_id,
        "decision_id": item.latest_decision_id,
        "decision_action": item.latest_decision_action,
        "source_candidate_metric_id": item.candidate_metric_id,
        "target_metric_id": item.target_metric_id,
        "consumption_action": "map_to_standard",
    }
    extensions["metric_governance"] = metric_governance
    governed["extensions"] = extensions
    return governed


def _deepcopy_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return deepcopy(dict(value))


def _period_scope(fact: Mapping[str, Any]) -> object:
    extensions = fact.get("extensions")
    if not isinstance(extensions, Mapping):
        return None
    return extensions.get("period_scope")
