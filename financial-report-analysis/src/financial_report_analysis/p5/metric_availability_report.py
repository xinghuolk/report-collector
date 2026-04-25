from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

MetricAvailabilityStatus = Literal[
    "present",
    "absent",
    "not_surfaced",
    "out_of_scope",
    "unknown",
]

_MISSING_STATUS_KEYS = (
    "working_capital_missing_status",
    "debt_missing_status",
    "asset_missing_status",
    "cash_health_missing_status",
)


@dataclass(frozen=True, slots=True)
class PdfMetricAvailability:
    metric_id: str
    status: MetricAvailabilityStatus
    value: int | float | None = None
    currency: str | None = None
    unit: str | None = None
    source: str | None = None
    semantic_source: str | None = None
    fact_id: str | None = None
    recovered_by_fallback: bool = False


@dataclass(frozen=True, slots=True)
class PdfMetricAvailabilityReport:
    pdf_path: str
    market: str
    metric_profile: str
    semantic_fallback_enabled: bool
    semantic_fallback_call_counts: dict[str, int]
    metrics: tuple[PdfMetricAvailability, ...]
    summary: dict[str, int]


def build_metric_availability_report(
    *,
    payload: dict[str, Any],
    expected_metric_ids: tuple[str, ...],
    metric_profile: str,
    pdf_path: str,
    market: str,
) -> PdfMetricAvailabilityReport:
    metadata = _dict_value(payload.get("document_metadata"))
    candidates = [
        candidate
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict)
    ]
    metrics = tuple(
        _availability_for_metric(
            metric_id=metric_id,
            candidates=candidates,
            metadata=metadata,
        )
        for metric_id in expected_metric_ids
    )
    return PdfMetricAvailabilityReport(
        pdf_path=pdf_path,
        market=market,
        metric_profile=metric_profile,
        semantic_fallback_enabled=bool(metadata.get("semantic_fallback_enabled")),
        semantic_fallback_call_counts=_fallback_call_counts(metadata),
        metrics=metrics,
        summary=_summary(metrics),
    )


def render_metric_availability_markdown(
    report: PdfMetricAvailabilityReport,
) -> str:
    counts = ", ".join(
        f"{key}={value}"
        for key, value in report.semantic_fallback_call_counts.items()
    )
    lines = [
        "# Metric Availability Report",
        "",
        f"pdf_path: {report.pdf_path}",
        f"market: {report.market}",
        f"metric_profile: {report.metric_profile}",
        (
            "semantic_fallback_enabled: "
            f"{str(report.semantic_fallback_enabled).lower()}"
        ),
        f"semantic_fallback_call_counts: {counts}",
        "",
        "| metric_id | status | value | currency | unit | source | semantic_source | recovered_by_fallback |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for metric in report.metrics:
        lines.append(
            "| "
            + " | ".join(
                [
                    metric.metric_id,
                    metric.status,
                    _display_value(metric.value),
                    metric.currency or "-",
                    metric.unit or "-",
                    metric.source or "-",
                    metric.semantic_source or "-",
                    str(metric.recovered_by_fallback).lower(),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _availability_for_metric(
    *,
    metric_id: str,
    candidates: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> PdfMetricAvailability:
    matches = [
        candidate
        for candidate in candidates
        if candidate.get("metric_id") == metric_id
    ]
    if matches:
        return _present_metric(metric_id, _best_candidate(matches))

    return PdfMetricAvailability(
        metric_id=metric_id,
        status=_missing_status(metric_id, metadata),
    )


def _present_metric(
    metric_id: str,
    candidate: dict[str, Any],
) -> PdfMetricAvailability:
    extensions = _dict_value(candidate.get("extensions"))
    semantic_source = _optional_str(extensions.get("semantic_source"))
    unit = (
        _optional_str(candidate.get("normalized_unit"))
        or _optional_str(candidate.get("raw_unit"))
    )
    value = candidate.get("numeric_value")
    if not isinstance(value, (int, float)):
        value = None
    return PdfMetricAvailability(
        metric_id=metric_id,
        status="present",
        value=value,
        currency=_optional_str(candidate.get("currency")),
        unit=unit,
        source=_optional_str(candidate.get("extraction_method")),
        semantic_source=semantic_source,
        fact_id=_optional_str(candidate.get("fact_id")),
        recovered_by_fallback=semantic_source == "llm_fallback",
    )


def _best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        candidates,
        key=lambda candidate: (
            _dict_value(candidate.get("extensions")).get("semantic_source")
            != "llm_fallback",
            -float(candidate.get("confidence", 0.0) or 0.0),
        ),
    )[0]


def _missing_status(
    metric_id: str,
    metadata: dict[str, Any],
) -> MetricAvailabilityStatus:
    found_status: MetricAvailabilityStatus | None = None
    for key in _MISSING_STATUS_KEYS:
        group = _dict_value(metadata.get(key))
        status = group.get(metric_id)
        if status == "out_of_scope":
            return "out_of_scope"
        if status in {"absent", "not_surfaced", "unknown"}:
            found_status = status
    return found_status or "absent"


def _fallback_call_counts(metadata: dict[str, Any]) -> dict[str, int]:
    raw_counts = _dict_value(metadata.get("semantic_fallback_call_counts"))
    return {
        "table_kind": _int_value(raw_counts.get("table_kind")),
        "row_label": _int_value(raw_counts.get("row_label")),
        "currency": _int_value(raw_counts.get("currency")),
        "unit": _int_value(raw_counts.get("unit")),
    }


def _summary(metrics: tuple[PdfMetricAvailability, ...]) -> dict[str, int]:
    summary = {
        "present": 0,
        "absent": 0,
        "not_surfaced": 0,
        "out_of_scope": 0,
    }
    for metric in metrics:
        if metric.status in summary:
            summary[metric.status] += 1
    return summary


def _dict_value(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _optional_str(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    return 0


def _display_value(value: int | float | None) -> str:
    if value is None:
        return "-"
    return str(value)
