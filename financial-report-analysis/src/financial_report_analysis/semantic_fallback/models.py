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
    "net_profit",
    "operating_cash_flow",
    "cash",
    "total_assets",
    "total_liabilities",
    "none",
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
class SemanticFallbackResult:
    value: str
    semantic_source: str
    semantic_confidence: float | None
    fallback_reason: str | None


def supported_table_kind_outputs() -> tuple[str, ...]:
    return _TABLE_KIND_OUTPUTS


def supported_row_label_outputs() -> tuple[str, ...]:
    return _ROW_LABEL_OUTPUTS
