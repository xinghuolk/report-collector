from financial_report_analysis import models
from financial_report_analysis.models.table import (
    ParsedCell,
    ParsedColumn,
    ParsedRow,
    ParsedTable,
)


def test_parsed_table_exposes_statement_scope_and_continuation_metadata() -> None:
    table = ParsedTable(
        table_id="doc-1:table:income:1",
        document_id="doc-1",
        page_range=(10, 11),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        statement_scope_guess="consolidated",
        continuation_confidence=0.75,
        continued_from_table_id="doc-1:table:income:0",
        header_rows=[["Item", "2024", "2023"]],
        body_rows=[],
        table_unit="thousand",
        table_currency="CNY",
        period_columns=[
            ParsedColumn(
                column_id="col-current",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
                is_comparison=False,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    assert table.page_range == (10, 11)
    assert table.statement_scope_guess == "consolidated"
    assert table.continued_from_table_id == "doc-1:table:income:0"
    assert table.continuation_confidence == 0.75
    assert table.period_columns[0].period_id == "2024FY"
    assert table.period_columns[0].value_time_shape == "duration"
    assert not hasattr(table.period_columns[0], "period_scope")
    assert models.ParsedTable is ParsedTable
    assert models.ParsedColumn is ParsedColumn


def test_parsed_table_defaults_statement_scope_guess_to_unknown() -> None:
    table = ParsedTable(
        table_id="doc-1:table:income:2",
        document_id="doc-1",
        page_range=(10, 10),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
    )

    assert table.statement_scope_guess == "unknown"
    assert table.continued_from_table_id is None
    assert table.continuation_confidence is None


def test_parsed_row_tracks_totals_and_value_cells() -> None:
    row = ParsedRow(
        row_id="row-revenue",
        row_index=5,
        label_raw="Revenue",
        normalized_label_hint="revenue",
        value_cells=[
            ParsedCell(
                row_index=5,
                column_index=1,
                text_raw="3,638,911,068.29",
                numeric_value=3638911068.29,
                bbox=None,
                page_index=0,
            )
        ],
        indent_level=0,
        is_subtotal=False,
        is_total=True,
    )

    assert row.is_total is True
    assert row.value_cells[0].numeric_value == 3638911068.29
    assert models.ParsedRow is ParsedRow
    assert models.ParsedCell is ParsedCell
    assert models.PageTextBlock.__name__ == "PageTextBlock"
