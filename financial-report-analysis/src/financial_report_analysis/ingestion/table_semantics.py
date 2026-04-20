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
        table_unit=table.table_unit,
        table_currency=table.table_currency,
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
    return normalized or None
