from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from financial_report_analysis.models.facts import CandidateFact
from financial_report_analysis.registries.metric_registry import MetricRegistry
from financial_report_analysis.unit_policy import UnitPolicy

_DEFAULT_STANDARD_METRICS: dict[str, list[str]] = {
    "revenue": ["Revenue", "营业收入", "turnover"],
    "operating_cost": ["Cost of sales", "Cost of revenue", "营业成本"],
    "operating_profit": ["Operating profit", "Profit from operations", "营业利润"],
    "gross_profit": [
        "Gross profit",
        "Gross profit for the period",
        "Gross profit attributable to operations",
        "营业毛利",
        "毛利润",
        "毛利",
    ],
    "operating_cash_flow": [
        "Operating cash flow",
        "Net cash from operating activities",
        "Net cash generated from operating activities",
        "Net cash used in operating activities",
        "经营活动产生的现金流量净额",
    ],
    "investing_cash_flow": [
        "Investing cash flow",
        "Net cash from investing activities",
        "Net cash generated from investing activities",
        "Net cash used in investing activities",
        "投资活动产生的现金流量净额",
    ],
    "financing_cash_flow": [
        "Financing cash flow",
        "Net cash from financing activities",
        "Net cash generated from financing activities",
        "Net cash used in financing activities",
        "筹资活动产生的现金流量净额",
    ],
    "equity": ["Total equity", "Total shareholders' equity", "所有者权益合计", "股东权益合计"],
    "equity_attributable_to_owners": [
        "Equity attributable to owners of the parent",
        "Equity attributable to equity holders of the company",
        "归属于母公司股东权益",
        "归属于母公司所有者权益",
    ],
    "net_profit": [
        "Net profit",
        "Profit for the period",
        "Profit attributable to shareholders",
        "Profit attributable to equity holders",
        "净利润",
    ],
}


class FactNormalizer:
    def __init__(
        self,
        metric_registry: MetricRegistry | None = None,
        unit_policy: UnitPolicy | None = None,
    ) -> None:
        self._metric_registry = metric_registry or MetricRegistry(
            standard_metrics=_DEFAULT_STANDARD_METRICS,
        )
        self._unit_policy = unit_policy or UnitPolicy()

    def normalize_candidates(
        self,
        candidates: Iterable[CandidateFact],
    ) -> list[CandidateFact]:
        normalized_candidates: list[CandidateFact] = []
        for candidate in candidates:
            metric_entry = self._metric_registry.resolve_metric(
                raw_label=candidate.metric_label_raw,
                statement_type=candidate.statement_type,
                accounting_standard=self._accounting_standard(candidate),
                industry_slug=self._industry_slug(candidate),
                parent_metric_id=self._parent_metric_id(candidate),
            )
            normalized_value = self._unit_policy.normalize_report_value(
                candidate.numeric_value,
                candidate.raw_unit,
                candidate.currency,
            )
            normalized_candidates.append(
                replace(
                    candidate,
                    metric_id=metric_entry.metric_id,
                    numeric_value=normalized_value.normalized_value,
                    currency=normalized_value.normalized_currency or candidate.currency,
                    normalized_unit=normalized_value.normalized_unit,
                )
            )
        return normalized_candidates

    @staticmethod
    def _accounting_standard(candidate: CandidateFact) -> str:
        value = candidate.extensions.get("accounting_standard", "OTHER")
        return str(value)

    @staticmethod
    def _industry_slug(candidate: CandidateFact) -> str:
        value = candidate.extensions.get("industry_slug", "general")
        return str(value)

    @staticmethod
    def _parent_metric_id(candidate: CandidateFact) -> str | None:
        value = candidate.extensions.get("parent_metric_id")
        return None if value is None else str(value)
