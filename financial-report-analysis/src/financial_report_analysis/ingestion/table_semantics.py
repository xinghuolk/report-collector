from __future__ import annotations

import re

from financial_report_analysis.models import (
    NormalizedTableCellValue,
    NormalizedTableColumn,
    NormalizedTableRow,
    NormalizedTableSemantics,
    ParsedRow,
    ParsedTable,
)

_SUPPRESSED_SUMMARY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(growth|margin|ratio)\b", re.IGNORECASE),
    re.compile(
        r"\b(free cash flow|cash flow trend|cash flow variance|cash flow ratio)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bper share\b", re.IGNORECASE),
    re.compile(r"\bbook value\b", re.IGNORECASE),
    re.compile(r"\bnet increase(?:/decrease)? in cash(?: and cash equivalents)?\b", re.IGNORECASE),
    re.compile(r"\bsubtotal\b", re.IGNORECASE),
    re.compile(r"(增长率|增长|比率|利润率|毛利率)"),
    re.compile(r"小计"),
    re.compile(r"每股"),
)

_ROW_LABEL_ALIASES: dict[str, str] = {
    "cost of sales": "operating cost",
    "cost of revenue": "operating cost",
    "gross profit for the period": "gross profit",
    "gross profit attributable to operations": "gross profit",
    "net cash from operating activities": "operating cash flow",
    "net cash generated from operating activities": "operating cash flow",
    "net cash used in operating activities": "operating cash flow",
    "经营活动产生的现金流量净额": "operating cash flow",
    "net cash generated from investing activities": "investing cash flow",
    "net cash from investing activities": "investing cash flow",
    "net cash used in investing activities": "investing cash flow",
    "投资活动产生的现金流量净额": "investing cash flow",
    "net cash generated from financing activities": "financing cash flow",
    "net cash from financing activities": "financing cash flow",
    "net cash used in financing activities": "financing cash flow",
    "筹资活动产生的现金流量净额": "financing cash flow",
    "毛利润": "gross profit",
    "毛利": "gross profit",
    "营业毛利": "gross profit",
    "equity attributable to owners of the parent": "equity attributable to owners of the parent",
    "equity attributable to equity holders of the company": "equity attributable to equity holders of the company",
    "所有者权益合计": "equity",
    "股东权益合计": "equity",
    "归属于母公司股东权益": "equity attributable to owners of the parent",
    "归属于母公司所有者权益": "equity attributable to owners of the parent",
    "profit attributable to equity holders": "net profit",
    "profit attributable to shareholders": "net profit",
}


def normalize_table_semantics(table: ParsedTable) -> NormalizedTableSemantics:
    all_columns = [*table.period_columns, *table.comparison_columns]
    normalized_columns = [
        NormalizedTableColumn(
            column_id=column.column_id,
            header_text=column.header_text,
            period_id=column.period_id,
            comparison_axis=column.comparison_axis,
            value_time_shape=column.value_time_shape,
            is_current=column.is_current,
            is_comparison=column.is_comparison,
        )
        for column in all_columns
    ]
    column_by_index = {column.column_index: column for column in all_columns}

    return NormalizedTableSemantics(
        table_id=table.table_id,
        document_id=table.document_id,
        page_range=table.page_range,
        table_kind=table.table_kind,
        title_text=table.title_text,
        statement_scope_guess=table.statement_scope_guess,
        table_unit=_normalized_semantic_value(table.table_unit),
        table_currency=_normalized_semantic_value(table.table_currency),
        unit_semantic_source="deterministic",
        currency_semantic_source="deterministic",
        semantic_source="deterministic",
        semantic_confidence=None,
        semantic_ambiguity_reason=table.semantic_ambiguity_reason,
        columns=normalized_columns,
        rows=[
            _normalize_row(row, column_by_index=column_by_index)
            for row in table.body_rows
        ],
    )


def _normalize_row(
    row: ParsedRow,
    *,
    column_by_index: dict[int, object],
) -> NormalizedTableRow:
    normalized_label = row.normalized_label_hint or _normalize_label(row.label_raw)
    return NormalizedTableRow(
        row_id=row.row_id,
        label_raw=row.label_raw,
        normalized_row_label=normalized_label,
        semantic_source="deterministic",
        semantic_confidence=None,
        fallback_reason=None,
        values=[
            NormalizedTableCellValue(
                row_index=cell.row_index,
                column_index=cell.column_index,
                raw_text=cell.text_raw,
                numeric_value=cell.numeric_value,
                period_id=getattr(column_by_index.get(cell.column_index), "period_id", None),
                comparison_axis=getattr(
                    column_by_index.get(cell.column_index),
                    "comparison_axis",
                    None,
                ),
                value_time_shape=getattr(
                    column_by_index.get(cell.column_index),
                    "value_time_shape",
                    None,
                ),
            )
            for cell in row.value_cells
        ],
    )


def _normalize_label(raw_label: str) -> str | None:
    normalized = raw_label.strip()
    normalized = re.sub(r"^[（(]?[一二三四五六七八九十]+[)）\.、]\s*", "", normalized)
    normalized = re.sub(r"^[（(]?\d+[)）\.、]\s*", "", normalized)
    normalized = re.sub(r"^[IVXLCM]+\.\s*", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip().casefold()
    if not normalized:
        return None

    # Keep ratio / growth style rows fact-agnostic so they do not compete with
    # core statement metrics in summary or key-metrics tables.
    if _is_summary_style_core_metric_row(normalized):
        return None
    if any(pattern.search(normalized) for pattern in _SUPPRESSED_SUMMARY_PATTERNS):
        return None

    return _ROW_LABEL_ALIASES.get(normalized, normalized)


def _is_summary_style_core_metric_row(normalized_label: str) -> bool:
    summary_match = re.fullmatch(
        r"(revenue|gross profit|operating profit|net profit)\s+summary",
        normalized_label,
    )
    if summary_match is not None:
        return True
    return normalized_label == "summary"


def _normalized_semantic_value(value: str | None) -> str:
    if value is None:
        return "unknown"
    normalized = value.strip()
    return normalized or "unknown"
