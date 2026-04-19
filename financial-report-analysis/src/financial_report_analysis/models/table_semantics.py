from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class NormalizedTableCellValue:
    row_index: int
    column_index: int
    raw_text: str
    numeric_value: float | None
    period_id: str | None
    comparison_axis: str | None
    value_time_shape: str | None


@dataclass(frozen=True, slots=True)
class NormalizedTableColumn:
    column_id: str
    header_text: str
    period_id: str | None
    comparison_axis: str | None
    value_time_shape: str | None
    is_current: bool
    is_comparison: bool


@dataclass(frozen=True, slots=True)
class NormalizedTableRow:
    row_id: str
    label_raw: str
    normalized_row_label: str | None
    values: list[NormalizedTableCellValue] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class NormalizedTableSemantics:
    table_id: str
    document_id: str
    table_kind: str
    title_text: str
    statement_scope_guess: str
    table_unit: str | None
    table_currency: str | None
    columns: list[NormalizedTableColumn] = field(default_factory=list)
    rows: list[NormalizedTableRow] = field(default_factory=list)
