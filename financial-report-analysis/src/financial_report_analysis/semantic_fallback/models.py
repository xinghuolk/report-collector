from __future__ import annotations

from dataclasses import dataclass


_TABLE_KIND_OUTPUTS = (
    "income_statement",
    "balance_sheet",
    "cash_flow_statement",
    "key_metrics",
    "unknown",
)

_ROW_LABEL_OUTPUTS = (
    "revenue",
    "operating_profit",
    "gross_profit",
    "net_profit",
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "cash",
    "total_assets",
    "total_liabilities",
    "equity",
    "equity_attributable_to_owners",
    "accounts_receiv",
    "notes_receiv",
    "oth_receiv",
    "contract_liab",
    "adv_receipts",
    "acct_payable",
    "notes_payable",
    "none",
)

_CURRENCY_OUTPUTS = (
    "CNY",
    "HKD",
    "USD",
    "unknown",
)

_DISCLOSURE_METRIC_OUTPUTS = (
    "accounts_receiv",
    "notes_receiv",
    "oth_receiv",
    "contract_liab",
    "adv_receipts",
    "acct_payable",
    "notes_payable",
    "none",
)

_UNIT_OUTPUTS = (
    "yuan",
    "thousand",
    "million",
    "billion",
    "percent",
    "unknown",
)


@dataclass(frozen=True, slots=True)
class TableKindFallbackRequest:
    title_text: str
    local_context: str
    deterministic_candidates: tuple[str, ...]
    ambiguity_reason: str | None


@dataclass(frozen=True, slots=True)
class RowLabelFallbackRequest:
    raw_label: str
    table_kind: str
    local_context: str
    deterministic_candidates: tuple[str, ...]
    ambiguity_reason: str | None


@dataclass(frozen=True, slots=True)
class CurrencyFallbackRequest:
    raw_text: str
    local_context: str
    deterministic_candidates: tuple[str, ...]
    ambiguity_reason: str | None


@dataclass(frozen=True, slots=True)
class UnitFallbackRequest:
    raw_text: str
    local_context: str
    deterministic_candidates: tuple[str, ...]
    ambiguity_reason: str | None


@dataclass(frozen=True, slots=True)
class DisclosureLocatorRequest:
    target_metric_ids: tuple[str, ...]
    local_context: str
    deterministic_candidates: tuple[str, ...]
    ambiguity_reason: str | None


@dataclass(frozen=True, slots=True)
class SemanticFallbackResult:
    value: str
    semantic_source: str
    semantic_confidence: float | None
    fallback_reason: str | None


@dataclass(frozen=True, slots=True)
class DisclosureLocatorResult:
    metric_id: str
    matched_label: str
    source_text_span: str
    semantic_source: str
    semantic_confidence: float | None
    fallback_reason: str | None


def supported_table_kind_outputs() -> tuple[str, ...]:
    return _TABLE_KIND_OUTPUTS


def supported_row_label_outputs() -> tuple[str, ...]:
    return _ROW_LABEL_OUTPUTS


def supported_currency_outputs() -> tuple[str, ...]:
    return _CURRENCY_OUTPUTS


def supported_disclosure_metric_outputs() -> tuple[str, ...]:
    return _DISCLOSURE_METRIC_OUTPUTS


def supported_unit_outputs() -> tuple[str, ...]:
    return _UNIT_OUTPUTS
