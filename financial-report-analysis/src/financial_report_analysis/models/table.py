from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(kw_only=True)
class ParsedCell:
    row_index: int
    column_index: int
    text_raw: str
    numeric_value: float | None
    bbox: tuple[float, float, float, float] | None = None
    page_index: int | None = None


@dataclass(kw_only=True)
class ParsedColumn:
    column_id: str
    column_index: int
    header_text: str
    period_id: str | None
    value_time_shape: str | None
    comparison_axis: str | None
    is_current: bool = False
    is_comparison: bool = False


@dataclass(kw_only=True)
class ParsedRow:
    row_id: str
    row_index: int
    label_raw: str
    normalized_label_hint: str | None
    value_cells: list[ParsedCell] = field(default_factory=list)
    indent_level: int = 0
    is_subtotal: bool = False
    is_total: bool = False


@dataclass(kw_only=True)
class PageTextBlock:
    page_index: int
    lines: list[str]
    raw_text: str


@dataclass(kw_only=True)
class ParsedTable:
    table_id: str
    document_id: str
    page_range: tuple[int, int]
    table_kind: str
    title_text: str
    statement_scope_guess: str = "unknown"
    semantic_ambiguity_reason: str | None = None
    continued_from_table_id: str | None = None
    continuation_confidence: float | None = None
    header_rows: list[list[str]] = field(default_factory=list)
    body_rows: list[ParsedRow] = field(default_factory=list)
    table_unit: str | None = None
    table_currency: str | None = None
    period_columns: list[ParsedColumn] = field(default_factory=list)
    comparison_columns: list[ParsedColumn] = field(default_factory=list)
    source_blocks: list[PageTextBlock] = field(default_factory=list)
