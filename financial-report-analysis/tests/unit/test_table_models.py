from financial_report_analysis import models
from financial_report_analysis.models.table import (
    ParsedCell,
    ParsedColumn,
    ParsedRow,
    ParsedTable,
)


def test_parsed_table_preserves_period_columns_and_page_range() -> None:
    table = ParsedTable(
        table_id="doc-1:table:income:1",
        document_id="doc-1",
        page_range=(10, 11),
        table_kind="income_statement",
        title_text="合并利润表",
        header_rows=[["项目", "2024年度", "2023年度"]],
        body_rows=[],
        table_unit="万元",
        table_currency="CNY",
        period_columns=[
            ParsedColumn(
                column_id="col-current",
                column_index=1,
                header_text="2024年度",
                period_id="2024FY",
                period_scope="duration",
                comparison_axis="current",
                is_current=True,
                is_comparison=False,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    assert table.page_range == (10, 11)
    assert table.period_columns[0].period_id == "2024FY"
    assert models.ParsedTable is ParsedTable
    assert models.ParsedColumn is ParsedColumn


def test_parsed_row_tracks_totals_and_value_cells() -> None:
    row = ParsedRow(
        row_id="row-revenue",
        row_index=5,
        label_raw="营业收入",
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
