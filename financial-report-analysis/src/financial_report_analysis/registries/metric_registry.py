from __future__ import annotations

from dataclasses import dataclass
import re
from collections.abc import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class StandardMetric:
    metric_id: str
    raw_label: str


@dataclass(frozen=True, slots=True)
class MetricRegistryEntry:
    metric_id: str
    raw_label: str
    statement_type: str
    accounting_standard: str
    industry_slug: str
    parent_metric_id: str | None
    is_custom: bool
    registry_status: str


class MetricRegistry:
    def __init__(
        self,
        standard_metrics: Mapping[str, list[str] | tuple[str, ...]]
        | Iterable[StandardMetric],
    ) -> None:
        self._standard_metrics: dict[str, str] = {}
        if isinstance(standard_metrics, Mapping):
            for metric_id, labels in standard_metrics.items():
                for raw_label in labels:
                    self._standard_metrics[self._normalize_label(raw_label)] = metric_id
            return

        for metric in standard_metrics:
            self._standard_metrics[self._normalize_label(metric.raw_label)] = metric.metric_id

    def resolve_metric(
        self,
        raw_label: str,
        statement_type: str,
        accounting_standard: str,
        industry_slug: str,
        parent_metric_id: str | None,
    ) -> MetricRegistryEntry:
        metric_id = self._standard_metrics.get(self._normalize_label(raw_label))
        if metric_id is not None:
            return MetricRegistryEntry(
                metric_id=metric_id,
                raw_label=raw_label,
                statement_type=statement_type,
                accounting_standard=accounting_standard,
                industry_slug=industry_slug,
                parent_metric_id=parent_metric_id,
                is_custom=False,
                registry_status="standard",
            )

        return MetricRegistryEntry(
            metric_id=self._build_custom_metric_id(
                accounting_standard=accounting_standard,
                industry_slug=industry_slug,
                parent_metric_id=parent_metric_id,
                statement_type=statement_type,
                raw_label=raw_label,
            ),
            raw_label=raw_label,
            statement_type=statement_type,
            accounting_standard=accounting_standard,
            industry_slug=industry_slug,
            parent_metric_id=parent_metric_id,
            is_custom=True,
            registry_status="provisional",
        )

    @staticmethod
    def _normalize_label(raw_label: str) -> str:
        return raw_label.strip().casefold()

    @staticmethod
    def _build_custom_metric_id(
        *,
        accounting_standard: str,
        industry_slug: str,
        parent_metric_id: str | None,
        statement_type: str,
        raw_label: str,
    ) -> str:
        def slugify(value: str) -> str:
            slug = re.sub(r"[^a-z0-9]+", "-", value.strip().casefold()).strip("-")
            return slug or "metric"

        parent_slug = slugify(parent_metric_id) if parent_metric_id else "root"
        return (
            f"custom::{accounting_standard.casefold()}::{industry_slug}::"
            f"{slugify(statement_type)}::{parent_slug}::{slugify(raw_label)}"
        )
