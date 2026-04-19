from financial_report_analysis.ingestion.table_semantics import normalize_table_semantics
from financial_report_analysis.models import ParsedCell, ParsedColumn, ParsedRow, ParsedTable


def test_normalize_table_semantics_keeps_row_hint_separate_from_metric_mapping() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:1",
            document_id="doc",
            page_range=(1, 1),
            table_kind="income_statement",
            title_text="Consolidated Income Statement",
            statement_scope_guess="consolidated",
            table_unit="thousand",
            table_currency="HKD",
            body_rows=[
                ParsedRow(
                    row_id="row-1",
                    row_index=1,
                    label_raw="Revenue",
                    normalized_label_hint="revenue",
                    value_cells=[
                        ParsedCell(
                            row_index=1,
                            column_index=1,
                            text_raw="1,234",
                            numeric_value=1234.0,
                            page_index=1,
                        )
                    ],
                )
            ],
            period_columns=[
                ParsedColumn(
                    column_id="column-1",
                    column_index=1,
                    header_text="2024",
                    period_id="2024FY",
                    value_time_shape="duration",
                    comparison_axis="current",
                    is_current=True,
                    is_comparison=False,
                )
            ],
        )
    )

    revenue_row = semantics.rows[0]
    assert revenue_row.normalized_row_label == "revenue"
    assert not hasattr(revenue_row, "metric_id")


def test_normalize_table_semantics_emits_period_value_context() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:q3",
            document_id="doc",
            page_range=(2, 2),
            table_kind="income_statement",
            title_text="Condensed Consolidated Statement of Profit or Loss",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-1",
                    row_index=1,
                    label_raw="Revenue",
                    normalized_label_hint="revenue",
                    value_cells=[
                        ParsedCell(
                            row_index=1,
                            column_index=1,
                            text_raw="1,234",
                            numeric_value=1234.0,
                            page_index=2,
                        )
                    ],
                )
            ],
            period_columns=[
                ParsedColumn(
                    column_id="column-1",
                    column_index=1,
                    header_text="Three months ended 30 September 2025",
                    period_id="2025Q3_YTD",
                    value_time_shape="duration",
                    comparison_axis="current",
                    is_current=True,
                    is_comparison=False,
                )
            ],
        )
    )

    assert semantics.columns[0].value_time_shape == "duration"
    assert semantics.columns[0].comparison_axis == "current"
    assert semantics.columns[0].period_id == "2025Q3_YTD"
    assert semantics.rows[0].values[0].period_id == "2025Q3_YTD"
    assert semantics.rows[0].values[0].value_time_shape == "duration"


def test_normalize_table_semantics_keeps_comparison_columns_and_cell_context() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:comparison",
            document_id="doc",
            page_range=(3, 3),
            table_kind="income_statement",
            title_text="Condensed Consolidated Statement of Profit or Loss",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-1",
                    row_index=1,
                    label_raw="Revenue",
                    normalized_label_hint="revenue",
                    value_cells=[
                        ParsedCell(
                            row_index=1,
                            column_index=1,
                            text_raw="1,234",
                            numeric_value=1234.0,
                            page_index=3,
                        ),
                        ParsedCell(
                            row_index=1,
                            column_index=2,
                            text_raw="1,111",
                            numeric_value=1111.0,
                            page_index=3,
                        ),
                    ],
                )
            ],
            period_columns=[
                ParsedColumn(
                    column_id="column-1",
                    column_index=1,
                    header_text="Nine months ended 30 September 2025",
                    period_id="2025Q3_YTD",
                    value_time_shape="duration",
                    comparison_axis="current",
                    is_current=True,
                    is_comparison=False,
                )
            ],
            comparison_columns=[
                ParsedColumn(
                    column_id="column-2",
                    column_index=2,
                    header_text="Nine months ended 30 September 2024",
                    period_id="2024Q3_YTD",
                    value_time_shape="duration",
                    comparison_axis="prior",
                    is_current=False,
                    is_comparison=True,
                )
            ],
        )
    )

    assert [column.column_id for column in semantics.columns] == ["column-1", "column-2"]
    assert semantics.columns[1].comparison_axis == "prior"
    assert semantics.columns[1].period_id == "2024Q3_YTD"
    assert semantics.rows[0].values[1].period_id == "2024Q3_YTD"
    assert semantics.rows[0].values[1].comparison_axis == "prior"
    assert semantics.rows[0].values[1].value_time_shape == "duration"
