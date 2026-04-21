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


def test_normalized_table_semantics_preserve_statement_scope_and_ambiguity() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:annual-bs",
            document_id="doc",
            page_range=(10, 10),
            table_kind="balance_sheet",
            title_text="Consolidated Balance Sheet",
            statement_scope_guess="consolidated",
            semantic_ambiguity_reason="numeric_only_statement_block",
            body_rows=[
                ParsedRow(
                    row_id="row-1",
                    row_index=1,
                    label_raw="Monetary funds VII.1",
                    normalized_label_hint=None,
                    value_cells=[],
                )
            ],
        )
    )

    assert semantics.statement_scope_guess == "consolidated"
    assert semantics.semantic_source == "deterministic"
    assert semantics.semantic_ambiguity_reason == "numeric_only_statement_block"


def test_normalized_table_semantics_emit_deterministic_unit_currency_provenance() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:unit-currency",
            document_id="doc",
            page_range=(12, 12),
            table_kind="balance_sheet",
            title_text="Consolidated Balance Sheet",
            statement_scope_guess="consolidated",
            table_unit="million",
            table_currency="HKD",
            body_rows=[],
        )
    )

    assert semantics.table_unit == "million"
    assert semantics.table_currency == "HKD"
    assert semantics.unit_semantic_source == "deterministic"
    assert semantics.currency_semantic_source == "deterministic"


def test_normalized_table_semantics_emit_unknown_sentinels_for_unresolved_unit_currency() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:unknown-unit-currency",
            document_id="doc",
            page_range=(13, 13),
            table_kind="income_statement",
            title_text="Consolidated Income Statement",
            statement_scope_guess="consolidated",
            table_unit=None,
            table_currency=None,
            body_rows=[],
        )
    )

    assert semantics.table_unit == "unknown"
    assert semantics.table_currency == "unknown"
    assert semantics.unit_semantic_source == "deterministic"
    assert semantics.currency_semantic_source == "deterministic"


def test_cn_annual_row_label_normalization_strips_numbering_prefixes() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:cn-annual",
            document_id="doc",
            page_range=(11, 11),
            table_kind="income_statement",
            title_text="合并利润表",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-1",
                    row_index=1,
                    label_raw="一、营业收入",
                    normalized_label_hint=None,
                    value_cells=[],
                )
            ],
        )
    )

    assert semantics.rows[0].normalized_row_label == "营业收入"
    assert semantics.rows[0].semantic_source == "deterministic"


def test_balance_sheet_equity_rows_normalize_to_separate_metrics() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:equity",
            document_id="doc",
            page_range=(14, 14),
            table_kind="balance_sheet",
            title_text="Consolidated Statement of Financial Position",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-equity",
                    row_index=1,
                    label_raw="所有者权益合计",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-attributable-equity",
                    row_index=2,
                    label_raw="归属于母公司股东权益",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-equity-ratio",
                    row_index=3,
                    label_raw="权益比率",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-per-share",
                    row_index=4,
                    label_raw="每股净资产",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-book-value",
                    row_index=5,
                    label_raw="book value per share",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert semantics.rows[0].normalized_row_label == "equity"
    assert semantics.rows[1].normalized_row_label == "equity attributable to owners of the parent"
    assert semantics.rows[2].normalized_row_label is None
    assert semantics.rows[3].normalized_row_label is None
    assert semantics.rows[4].normalized_row_label is None


def test_balance_sheet_english_attributable_equity_maps_to_registered_phrase() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:equity-en",
            document_id="doc",
            page_range=(15, 15),
            table_kind="balance_sheet",
            title_text="Consolidated Statement of Financial Position",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-attributable-equity",
                    row_index=1,
                    label_raw="Equity attributable to owners of the parent",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-attributable-equity-alt",
                    row_index=2,
                    label_raw="Equity attributable to equity holders of the company",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        "equity attributable to owners of the parent",
        "equity attributable to equity holders of the company",
    ]


def test_normalize_table_semantics_maps_operating_cost_variants() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:hk-income-costs",
            document_id="doc",
            page_range=(14, 14),
            table_kind="income_statement",
            title_text="Consolidated Statement of Profit or Loss",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-1",
                    row_index=1,
                    label_raw="Cost of Sales",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-2",
                    row_index=2,
                    label_raw="Cost of Revenue",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        "operating cost",
        "operating cost",
    ]


def test_normalize_table_semantics_maps_gross_profit_variants() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:gross-profit",
            document_id="doc",
            page_range=(16, 16),
            table_kind="income_statement",
            title_text="Consolidated Statement of Profit or Loss",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-1",
                    row_index=1,
                    label_raw="Gross profit for the period",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-2",
                    row_index=2,
                    label_raw="毛利润",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        "gross profit",
        "gross profit",
    ]


def test_normalize_table_semantics_maps_phase1_income_statement_variants() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:phase1-income",
            document_id="doc",
            page_range=(16, 16),
            table_kind="income_statement",
            title_text="Consolidated Statement of Profit or Loss",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-attributable-profit",
                    row_index=1,
                    label_raw="归属于母公司股东的净利润",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-basic-eps",
                    row_index=2,
                    label_raw="Basic earnings per share",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-finance-costs",
                    row_index=3,
                    label_raw="Finance costs",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-profit-before-tax",
                    row_index=4,
                    label_raw="Profit before tax",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-tax",
                    row_index=5,
                    label_raw="所得税费用",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-minority",
                    row_index=6,
                    label_raw="Profit attributable to non-controlling interests",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        "net profit attributable to owners of the parent",
        "basic earnings per share",
        "finance expense",
        "total profit",
        "income tax",
        "minority interest profit",
    ]


def test_normalize_table_semantics_maps_phase1_cash_flow_detail_variants() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:phase1-cash-flow",
            document_id="doc",
            page_range=(17, 17),
            table_kind="cash_flow_statement",
            title_text="Consolidated Statement of Cash Flows",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-capex",
                    row_index=1,
                    label_raw="购建固定资产、无形资产和其他长期资产支付的现金",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-depreciation",
                    row_index=2,
                    label_raw="Depreciation of property, plant and equipment",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-amort-intang",
                    row_index=3,
                    label_raw="Amortisation of intangible assets",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-amort-deferred",
                    row_index=4,
                    label_raw="长期待摊费用摊销",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-dividends",
                    row_index=5,
                    label_raw="Dividends paid",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        "capital expenditure cash outflow",
        "depreciation of fixed assets",
        "amortisation of intangible assets",
        "amortisation of long-term deferred expenses",
        "cash paid for dividends or interest",
    ]


def test_normalize_table_semantics_maps_cash_flow_primary_section_variants() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:cash-flow-primary",
            document_id="doc",
            page_range=(16, 16),
            table_kind="cash_flow_statement",
            title_text="Consolidated Statement of Cash Flows",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-operating",
                    row_index=1,
                    label_raw="Net cash generated from operating activities",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-investing",
                    row_index=2,
                    label_raw="net cash from investing activities",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-financing",
                    row_index=3,
                    label_raw="net cash from financing activities",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        "operating cash flow",
        "investing cash flow",
        "financing cash flow",
    ]


def test_normalize_table_semantics_suppresses_diluted_and_adjusted_eps_rows() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:eps-false-positives",
            document_id="doc",
            page_range=(18, 18),
            table_kind="income_statement",
            title_text="Consolidated Statement of Profit or Loss",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-diluted",
                    row_index=1,
                    label_raw="Diluted earnings per share",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-adjusted",
                    row_index=2,
                    label_raw="Adjusted EPS",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-non-gaap",
                    row_index=3,
                    label_raw="Non-GAAP earnings per share",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-basic-cn",
                    row_index=4,
                    label_raw="基本每股收益",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        None,
        None,
        None,
        "basic earnings per share",
    ]


def test_normalize_table_semantics_suppresses_gross_profit_summary_rows() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:gross-profit-summary",
            document_id="doc",
            page_range=(16, 16),
            table_kind="income_statement",
            title_text="Consolidated Statement of Profit or Loss",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-1",
                    row_index=1,
                    label_raw="Gross profit summary",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [None]


def test_normalize_table_semantics_suppresses_cash_flow_false_positive_rows() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:cash-flow-false-positives",
            document_id="doc",
            page_range=(18, 18),
            table_kind="cash_flow_statement",
            title_text="Consolidated Statement of Cash Flows",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-free-cash-flow",
                    row_index=1,
                    label_raw="Free cash flow",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-net-increase",
                    row_index=2,
                    label_raw="Net increase/decrease in cash and cash equivalents",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-ratio",
                    row_index=3,
                    label_raw="Cash flow ratio",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-trend",
                    row_index=4,
                    label_raw="Cash flow trend",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-other-trend",
                    row_index=5,
                    label_raw="Revenue trend",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-subtotal",
                    row_index=6,
                    label_raw="小计",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        None,
        None,
        None,
        None,
        "revenue trend",
        None,
    ]


def test_normalize_table_semantics_suppresses_narrative_cash_flow_rows() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:cash-flow-narrative",
            document_id="doc",
            page_range=(19, 19),
            table_kind="cash_flow_statement",
            title_text="Consolidated Statement of Cash Flows",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-analysis",
                    row_index=1,
                    label_raw="Analysis of balances of cash and cash equivalents",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-before-working-capital",
                    row_index=2,
                    label_raw="Cash flows before movements in working capital",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-dividends",
                    row_index=3,
                    label_raw="Dividends paid",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        None,
        None,
        "cash paid for dividends or interest",
    ]


def test_normalize_table_semantics_keeps_non_metric_summary_labels() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:non-metric-summary",
            document_id="doc",
            page_range=(17, 17),
            table_kind="balance_sheet",
            title_text="Consolidated Statement of Financial Position",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-1",
                    row_index=1,
                    label_raw="Annual summary of operations",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert semantics.rows[0].normalized_row_label == "annual summary of operations"


def test_normalize_table_semantics_suppresses_growth_and_ratio_rows() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:hk-key-metrics",
            document_id="doc",
            page_range=(15, 15),
            table_kind="key_metrics",
            title_text="Key Financial Metrics",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-1",
                    row_index=1,
                    label_raw="Revenue growth",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-2",
                    row_index=2,
                    label_raw="Operating profit margin",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [None, None]
