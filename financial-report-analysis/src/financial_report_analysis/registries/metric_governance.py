from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from financial_report_analysis.registries.metric_registry import MetricRegistryEntry

STANDARD_STATUS = "standard"
PROVISIONAL_STATUS = "provisional"
STANDARD_NAMESPACE = "standard"
CUSTOM_NAMESPACE = "custom"
METRIC_GOVERNANCE_EXTENSION_KEY = "metric_governance"


def standard_governance_metadata(reason: str = "standard_metric") -> dict[str, object]:
    return {
        "registry_status": STANDARD_STATUS,
        "metric_namespace": STANDARD_NAMESPACE,
        "review_required": False,
        "auto_analysis_allowed": True,
        "governance_reason": reason,
    }


def governance_metadata_from_registry_entry(
    entry: MetricRegistryEntry,
) -> dict[str, object]:
    if not entry.is_custom and entry.registry_status == STANDARD_STATUS:
        return standard_governance_metadata()

    return {
        "registry_status": entry.registry_status or PROVISIONAL_STATUS,
        "metric_namespace": CUSTOM_NAMESPACE if entry.is_custom else STANDARD_NAMESPACE,
        "review_required": True,
        "auto_analysis_allowed": False,
        "governance_reason": (
            "provisional_custom_metric" if entry.is_custom else "non_standard_metric"
        ),
    }


def automatic_governance_metadata(
    extensions: Mapping[str, Any],
) -> dict[str, object]:
    metadata = extensions.get(METRIC_GOVERNANCE_EXTENSION_KEY)
    if not isinstance(metadata, Mapping):
        return {}

    return dict(metadata)


def is_auto_analysis_allowed(extensions: Mapping[str, Any]) -> bool:
    metadata = automatic_governance_metadata(extensions)
    return metadata.get("auto_analysis_allowed") is True


def is_provisional_custom_metric(extensions: Mapping[str, Any]) -> bool:
    metadata = automatic_governance_metadata(extensions)
    return (
        metadata.get("metric_namespace") == CUSTOM_NAMESPACE
        and metadata.get("registry_status") == PROVISIONAL_STATUS
    )
