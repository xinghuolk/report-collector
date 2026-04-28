from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from financial_report_analysis.registries.metric_governance import (
    METRIC_GOVERNANCE_EXTENSION_KEY,
)

_BLOCKED_REGISTRY_STATUSES = {"blacklisted", "deprecated"}
_ALLOWED_CONSUMPTION_ACTIONS = {"map_to_standard"}


@dataclass(frozen=True, slots=True)
class DownstreamGovernanceDecision:
    allowed: bool
    reason: str
    governance_metadata: dict[str, Any]


def evaluate_downstream_fact_consumption(
    fact: Mapping[str, Any],
) -> DownstreamGovernanceDecision:
    extensions = fact.get("extensions")
    if not isinstance(extensions, Mapping):
        return DownstreamGovernanceDecision(
            allowed=False,
            reason="missing_extensions",
            governance_metadata={},
        )

    metadata = extensions.get(METRIC_GOVERNANCE_EXTENSION_KEY)
    if metadata is None:
        return DownstreamGovernanceDecision(
            allowed=False,
            reason="missing_metric_governance",
            governance_metadata={},
        )
    if not isinstance(metadata, Mapping):
        return DownstreamGovernanceDecision(
            allowed=False,
            reason="malformed_metric_governance",
            governance_metadata={},
        )

    governance_metadata = dict(metadata)
    registry_status = governance_metadata.get("registry_status")
    if registry_status in _BLOCKED_REGISTRY_STATUSES:
        return DownstreamGovernanceDecision(
            allowed=False,
            reason=f"blocked_registry_status:{registry_status}",
            governance_metadata=governance_metadata,
        )

    lifecycle_consumption = governance_metadata.get("lifecycle_consumption")
    if isinstance(lifecycle_consumption, Mapping):
        consumption_action = lifecycle_consumption.get("consumption_action")
        if consumption_action in _ALLOWED_CONSUMPTION_ACTIONS:
            return DownstreamGovernanceDecision(
                allowed=True,
                reason=f"controlled_consumption:{consumption_action}",
                governance_metadata=governance_metadata,
            )

    if governance_metadata.get("auto_analysis_allowed") is not True:
        return DownstreamGovernanceDecision(
            allowed=False,
            reason="auto_analysis_not_allowed",
            governance_metadata=governance_metadata,
        )

    if governance_metadata.get("metric_namespace") == "custom":
        return DownstreamGovernanceDecision(
            allowed=False,
            reason="custom_namespace_without_controlled_consumption",
            governance_metadata=governance_metadata,
        )

    return DownstreamGovernanceDecision(
        allowed=True,
        reason="auto_analysis_allowed",
        governance_metadata=governance_metadata,
    )


def is_downstream_consumable_fact(fact: Mapping[str, Any]) -> bool:
    return evaluate_downstream_fact_consumption(fact).allowed
