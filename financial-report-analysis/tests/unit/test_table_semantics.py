import pytest

from financial_report_analysis.ingestion.table_semantics import normalize_table_semantics
from financial_report_analysis.models import ParsedCell, ParsedColumn, ParsedRow, ParsedTable


def _make_balance_sheet_table(
    *,
    table_id: str,
    row_labels: list[str],
) -> ParsedTable:
    return ParsedTable(
        table_id=table_id,
        document_id="doc",
        page_range=(1, 1),
        table_kind="balance_sheet",
        title_text="Consolidated Statement of Financial Position",
        statement_scope_guess="consolidated",
        body_rows=[
            ParsedRow(
                row_id=f"row-{index}",
                row_index=index,
                label_raw=row_label,
                normalized_label_hint=None,
                value_cells=[],
            )
            for index, row_label in enumerate(row_labels, start=1)
        ],
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="As of 31 December 2025",
                period_id="2025FY",
                value_time_shape="point_in_time",
                comparison_axis="current",
                is_current=True,
                is_comparison=False,
            )
        ],
    )


def _balance_sheet_table_with_row(label: str) -> ParsedTable:
    return _make_balance_sheet_table(
        table_id=f"doc:table:{label.replace(' ', '-')}",
        row_labels=[label],
    )


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


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("货币资金", "cash and cash equivalents"),
        ("交易性金融资产", "trading assets"),
        ("存货", "inventories"),
        ("商誉", "goodwill"),
        ("无形资产", "intangible assets"),
        ("Cash and cash equivalents", "cash and cash equivalents"),
        ("Trading assets", "trading assets"),
        ("Inventories", "inventories"),
        ("Goodwill", "goodwill"),
        ("Intangible assets", "intangible assets"),
    ],
)
def test_table_semantics_normalizes_p3_asset_labels(
    label: str,
    expected: str,
) -> None:
    semantics = normalize_table_semantics(_balance_sheet_table_with_row(label))

    assert semantics.rows[0].normalized_row_label == expected


@pytest.mark.parametrize(
    "label",
    [
        "合同资产",
        "其他非流动资产",
        "Contract assets",
        "Other non-current assets",
    ],
)
def test_table_semantics_keeps_p3_note_only_asset_labels_out_of_primary_row_semantics(
    label: str,
) -> None:
    semantics = normalize_table_semantics(_balance_sheet_table_with_row(label))

    assert semantics.rows[0].normalized_row_label is None


@pytest.mark.parametrize(
    "label",
    [
        "assets held for sale",
        "investment properties",
        "prepayments",
        "right-of-use assets",
        "deferred tax assets",
        "capitalized development costs",
        "total non-current assets",
        "受限资金",
        "持有待售资产",
        "投资性房地产",
        "预付款项",
        "使用权资产",
        "递延所得税资产",
        "开发支出",
    ],
)
def test_table_semantics_suppresses_p3_asset_negative_controls(label: str) -> None:
    semantics = normalize_table_semantics(_balance_sheet_table_with_row(label))

    assert semantics.rows[0].normalized_row_label is None


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

    assert semantics.rows[0].normalized_row_label == "revenue"
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


def test_balance_sheet_p4c_total_rows_keep_owner_scope_distinct() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:p4c-balance-sheet",
            document_id="doc",
            page_range=(15, 15),
            table_kind="balance_sheet",
            title_text="Consolidated Statement of Financial Position",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-total-assets",
                    row_index=1,
                    label_raw="资产总计",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-total-liabilities",
                    row_index=2,
                    label_raw="Total liabilities",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-total-equity",
                    row_index=3,
                    label_raw="Total equity",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-owner-equity",
                    row_index=4,
                    label_raw="归属于母公司股东权益",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        "total assets",
        "total liabilities",
        "equity",
        "equity attributable to owners of the parent",
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


def test_normalize_table_semantics_maps_p4c_income_statement_variants() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:p4c-income",
            document_id="doc",
            page_range=(14, 14),
            table_kind="income_statement",
            title_text="Consolidated Statement of Profit or Loss",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-revenue",
                    row_index=1,
                    label_raw="Turnover",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-operating-profit",
                    row_index=2,
                    label_raw="Profit from operations",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-net-profit",
                    row_index=3,
                    label_raw="净利润",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        "revenue",
        "operating profit",
        "net profit",
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


def test_normalize_table_semantics_preserves_p4c_negative_control_boundaries() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:p4c-negative-controls",
            document_id="doc",
            page_range=(16, 16),
            table_kind="income_statement",
            title_text="Consolidated Statement of Profit or Loss",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-gross-profit",
                    row_index=1,
                    label_raw="Gross profit",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-profit-before-tax",
                    row_index=2,
                    label_raw="Profit before tax",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-owner-profit",
                    row_index=3,
                    label_raw="Profit attributable to owners of the parent",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        "gross profit",
        "total profit",
        "net profit attributable to owners of the parent",
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
                    label_raw="Payments for acquisition and construction of long-term assets",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-depreciation",
                    row_index=2,
                    label_raw=(
                        "Depreciation of fixed assets oil and gas assets and "
                        "productive biological assets"
                    ),
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
                    label_raw="Cash paid for distribution of dividends or profits and interest expenses",
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


def test_normalize_table_semantics_maps_p4c_cash_flow_detail_variants() -> None:
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:p4c-cash-flow-details",
            document_id="doc",
            page_range=(17, 17),
            table_kind="cash_flow_statement",
            title_text="Consolidated Statement of Cash Flows",
            statement_scope_guess="consolidated",
            body_rows=[
                ParsedRow(
                    row_id="row-staff",
                    row_index=1,
                    label_raw="Cash paid to and on behalf of employees",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-taxes",
                    row_index=2,
                    label_raw="支付的各项税费",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-cash",
                    row_index=3,
                    label_raw="Cash and cash equivalents",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert [row.normalized_row_label for row in semantics.rows] == [
        "cash paid to and on behalf of employees",
        "taxes paid",
        "cash and cash equivalents",
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


@pytest.mark.parametrize(
    ("raw_label", "normalized_row_label"),
    [
        ("应收账款 七、", "accounts receivables"),
        ("应收票据", "notes receivable"),
        ("其他应收款 十九、", "other receivables"),
        ("合同负债", "contract liabilities"),
        ("预收款项", "advances from customers"),
        ("应付账款", "accounts payable"),
        ("应付票据", "notes payable"),
        ("Accounts receivable, net", "accounts receivable"),
        ("Accounts payable", "accounts payable"),
        ("Contract liabilities", "contract liabilities"),
    ],
)
def test_balance_sheet_row_labels_normalize_deterministically(
    raw_label: str,
    normalized_row_label: str,
) -> None:
    semantics = normalize_table_semantics(
        _make_balance_sheet_table(
            table_id=f"doc:table:{normalized_row_label.replace(' ', '-')}",
            row_labels=[raw_label],
        )
    )

    assert semantics.rows[0].normalized_row_label == normalized_row_label


@pytest.mark.parametrize(
    "raw_label",
    [
        "accounts receivable financing",
        "long-term receivables",
        "employee compensation payable",
        "taxes payable",
        "Changes in accounts receivable",
        "应收款项融资",
        "长期应收款",
        "应付职工薪酬",
        "应交税费",
        "经营性应收项目的减少（增加以“－”号填列）",
    ],
)
def test_balance_sheet_working_capital_false_positives_are_suppressed(
    raw_label: str,
) -> None:
    semantics = normalize_table_semantics(
        _make_balance_sheet_table(
            table_id=f"doc:table:{raw_label}",
            row_labels=[raw_label],
        )
    )

    assert semantics.rows[0].normalized_row_label is None


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("\u77ed\u671f\u501f\u6b3e", "short-term borrowings"),
        ("\u957f\u671f\u501f\u6b3e", "long-term borrowings"),
        ("\u5e94\u4ed8\u503a\u5238", "bonds payable"),
        (
            "\u4e00\u5e74\u5185\u5230\u671f\u7684\u975e\u6d41\u52a8\u8d1f\u503a",
            "current portion of long-term debt",
        ),
        ("Short-term borrowings", "short-term borrowings"),
        ("Long-term borrowings", "long-term borrowings"),
        ("Bonds payable", "bonds payable"),
        ("Current portion of long-term debt", "current portion of long-term debt"),
    ],
)
def test_table_semantics_normalizes_p2b_debt_labels(
    label: str,
    expected: str,
) -> None:
    semantics = normalize_table_semantics(_balance_sheet_table_with_row(label))

    assert semantics.rows[0].normalized_row_label == expected


@pytest.mark.parametrize(
    "label",
    [
        "lease liabilities",
        "total borrowings",
        "\u79df\u8d41\u8d1f\u503a",
        "\u501f\u6b3e\u53ca\u5176\u4ed6\u8d1f\u503a",
    ],
)
def test_table_semantics_suppresses_p2b_negative_controls(label: str) -> None:
    semantics = normalize_table_semantics(_balance_sheet_table_with_row(label))

    assert semantics.rows[0].normalized_row_label is None


def test_table_semantics_suppresses_p2b_cn_aggregate_borrowings() -> None:
    semantics = normalize_table_semantics(_balance_sheet_table_with_row("借款合计"))

    assert semantics.rows[0].normalized_row_label is None


def test_table_semantics_keeps_more_specific_debt_rows_with_covered_phrase() -> None:
    semantics = normalize_table_semantics(
        _balance_sheet_table_with_row("Lease liabilities and other borrowings")
    )

    assert semantics.rows[0].normalized_row_label == "lease liabilities and other borrowings"


@pytest.mark.parametrize(
    ("raw_label", "market", "expected"),
    [
        ("Restricted cash", "HK", "restricted cash"),
        (
            "Restricted cash and cash equivalents",
            "HK",
            "restricted cash and cash equivalents",
        ),
        ("Cash paid for interest", "HK", "cash paid for interest"),
        ("Time deposits", "HK", "time deposits"),
        ("Wealth management products", "HK", "wealth management products"),
        ("\u53d7\u9650\u8d27\u5e01\u8d44\u91d1", "CN", "\u53d7\u9650\u8d27\u5e01\u8d44\u91d1"),
        ("\u652f\u4ed8\u7684\u5229\u606f", "CN", "\u652f\u4ed8\u7684\u5229\u606f"),
        ("\u7ed3\u6784\u6027\u5b58\u6b3e", "CN", "\u7ed3\u6784\u6027\u5b58\u6b3e"),
    ],
)
def test_normalize_row_label_supports_p4b_cash_health_families(
    raw_label: str,
    market: str,
    expected: str,
) -> None:
    del market
    semantics = normalize_table_semantics(_balance_sheet_table_with_row(raw_label))

    assert semantics.rows[0].normalized_row_label == expected
