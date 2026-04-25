from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from financial_report_analysis.models.facts import CandidateFact
from financial_report_analysis.registries.metric_governance import (
    METRIC_GOVERNANCE_EXTENSION_KEY,
    governance_metadata_from_registry_entry,
    standard_governance_metadata,
)
from financial_report_analysis.registries.metric_registry import (
    MetricRegistry,
    MetricRegistryEntry,
)
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
    "total_assets": [
        "Total assets",
        "资产总计",
        "总资产",
    ],
    "total_liabilities": [
        "Total liabilities",
        "负债合计",
        "总负债",
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
        "Net income",
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
    "c_pay_to_staff": [
        "Cash paid to and on behalf of employees",
        "Cash paid to employees",
        "支付给职工以及为职工支付的现金",
    ],
    "c_paid_for_taxes": [
        "Taxes paid",
        "Tax paid",
        "Cash paid for taxes",
        "支付的各项税费",
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
            resolved_metric_id = self._resolved_metric_id(
                candidate=candidate,
                resolved_metric_id=metric_entry.metric_id,
            )
            normalized_value, normalized_currency, normalized_unit = self._normalize_value(
                candidate=candidate,
                metric_id=resolved_metric_id,
            )
            normalized_extensions = dict(candidate.extensions)
            normalized_extensions.setdefault(
                METRIC_GOVERNANCE_EXTENSION_KEY,
                self._governance_metadata(
                    candidate=candidate,
                    resolved_metric_id=resolved_metric_id,
                    registry_metric_id=metric_entry.metric_id,
                    metric_entry=metric_entry,
                ),
            )
            if resolved_metric_id in _PER_SHARE_METRIC_IDS:
                normalized_extensions.setdefault("value_type", "per_share")
                normalized_extensions.setdefault("unit_expectation", _PER_SHARE_UNIT)
            normalized_candidates.append(
                replace(
                    candidate,
                    metric_id=resolved_metric_id,
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
            normalized_numeric_value = self._normalize_per_share_numeric_value(
                numeric_value=candidate.numeric_value,
                raw_unit=candidate.raw_unit,
            )
            return (
                normalized_numeric_value,
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
    def _resolved_metric_id(*, candidate: CandidateFact, resolved_metric_id: str) -> str:
        candidate_metric_id = str(candidate.metric_id or "").strip()
        if FactNormalizer._is_supported_metric_id(candidate_metric_id):
            return candidate_metric_id
        return resolved_metric_id

    @staticmethod
    def _governance_metadata(
        *,
        candidate: CandidateFact,
        resolved_metric_id: str,
        registry_metric_id: str,
        metric_entry: MetricRegistryEntry,
    ) -> dict[str, object]:
        candidate_metric_id = str(candidate.metric_id or "").strip()
        if (
            candidate_metric_id == resolved_metric_id
            and registry_metric_id != resolved_metric_id
            and FactNormalizer._is_supported_metric_id(candidate_metric_id)
        ):
            return standard_governance_metadata(reason="supported_metric_mapping")

        return governance_metadata_from_registry_entry(metric_entry)

    @staticmethod
    def _is_supported_metric_id(metric_id: str) -> bool:
        return (
            bool(metric_id)
            and metric_id != "unknown"
            and not metric_id.startswith("custom::")
            and not metric_id.startswith("raw_")
        )

    @staticmethod
    def _normalize_per_share_numeric_value(
        *,
        numeric_value: float | int | None,
        raw_unit: str | None,
    ) -> float | int | None:
        if numeric_value is None or raw_unit is None:
            return numeric_value

        normalized_unit = raw_unit.strip().casefold()
        normalized_unit = normalized_unit.replace(" ", "")
        if any(
            token in normalized_unit
            for token in (
                "cent/share",
                "cents/share",
                "centpershare",
                "centspershare",
                "hkcent/share",
                "hkcents/share",
                "hkcentpershare",
                "hkcentspershare",
                "港仙/股",
                "仙/股",
                "分/股",
            )
        ):
            return numeric_value / 100.0
        return numeric_value

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
