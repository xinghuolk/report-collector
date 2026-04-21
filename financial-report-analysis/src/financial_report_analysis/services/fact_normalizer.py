from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from financial_report_analysis.models.facts import CandidateFact
from financial_report_analysis.registries.metric_registry import MetricRegistry
from financial_report_analysis.unit_policy import UnitPolicy

_PER_SHARE_METRIC_IDS = {"basic_eps"}
_PER_SHARE_UNIT = "per_share_amount"

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
    "n_income_attr_p": [
        "Net profit attributable to shareholders",
        "Net profit attributable to owners of the parent",
        "Profit attributable to owners of the parent",
        "归属于母公司股东的净利润",
        "归属于母公司所有者的净利润",
    ],
    "basic_eps": [
        "Basic EPS",
        "Basic earnings per share",
        "基本每股收益",
    ],
    "finance_exp": [
        "Finance expense",
        "Finance costs",
        "财务费用",
    ],
    "total_profit": [
        "Total profit",
        "Profit before tax",
        "利润总额",
    ],
    "income_tax": [
        "Income tax",
        "Income tax expense",
        "所得税费用",
    ],
    "minority_gain": [
        "Minority gain",
        "Profit attributable to non-controlling interests",
        "少数股东损益",
    ],
    "c_pay_acq_const_fiolta": [
        "Capital expenditure paid",
        "Payments for acquisition and construction of long-term assets",
        "购建固定资产、无形资产和其他长期资产支付的现金",
    ],
    "depr_fa_coga_dpba": [
        "Depreciation of long-lived assets",
        "Depreciation of fixed assets oil and gas assets and productive biological assets",
        "固定资产折旧、油气资产折耗、生产性生物资产折旧",
    ],
    "amort_intang_assets": [
        "Amortisation of intangible assets",
        "Amortization of intangible assets",
        "无形资产摊销",
    ],
    "lt_amort_deferred_exp": [
        "Amortisation of long-term deferred expenses",
        "Amortization of long-term deferred expenses",
        "长期待摊费用摊销",
    ],
    "c_pay_dist_dpcp_int_exp": [
        "Dividends interest paid",
        "Cash paid for distribution of dividends or profits and interest expenses",
        "分配股利、利润或偿付利息支付的现金",
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
            normalized_value, normalized_currency, normalized_unit = self._normalize_value(
                candidate=candidate,
                metric_id=metric_entry.metric_id,
            )
            normalized_extensions = dict(candidate.extensions)
            if metric_entry.metric_id in _PER_SHARE_METRIC_IDS:
                normalized_extensions.setdefault("value_type", "per_share")
                normalized_extensions.setdefault("unit_expectation", _PER_SHARE_UNIT)
            normalized_candidates.append(
                replace(
                    candidate,
                    metric_id=metric_entry.metric_id,
                    numeric_value=normalized_value,
                    currency=normalized_currency,
                    normalized_unit=normalized_unit,
                    extensions=normalized_extensions,
                )
            )
        return normalized_candidates

    def _normalize_value(
        self,
        *,
        candidate: CandidateFact,
        metric_id: str,
    ) -> tuple[float | int | None, str, str | None]:
        if self._is_per_share_candidate(candidate=candidate, metric_id=metric_id):
            return (
                candidate.numeric_value,
                candidate.currency,
                str(candidate.extensions.get("unit_expectation") or _PER_SHARE_UNIT),
            )

        normalized_value = self._unit_policy.normalize_report_value(
            candidate.numeric_value,
            candidate.raw_unit,
            candidate.currency,
        )
        return (
            normalized_value.normalized_value,
            normalized_value.normalized_currency or candidate.currency,
            normalized_value.normalized_unit,
        )

    @staticmethod
    def _is_per_share_candidate(*, candidate: CandidateFact, metric_id: str) -> bool:
        value_type = str(candidate.extensions.get("value_type") or "").strip().casefold()
        unit_expectation = str(candidate.extensions.get("unit_expectation") or "").strip()
        return (
            metric_id in _PER_SHARE_METRIC_IDS
            or value_type == "per_share"
            or unit_expectation == _PER_SHARE_UNIT
        )

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
