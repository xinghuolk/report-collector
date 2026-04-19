import pytest

from financial_report_analysis.ingestion.table_header_parser import (
    detect_table_currency,
    detect_table_unit,
    parse_header_rows,
)
from financial_report_analysis.models.table import ParsedColumn


def test_parse_header_rows_parses_cn_annual_period_columns() -> None:
    columns = parse_header_rows(
        title_text="合并利润表",
        header_rows=[["项目", "2024年度", "2023年度"]],
        market="CN",
    )

    assert columns == [
        ParsedColumn(
            column_id="column-1",
            column_index=1,
            header_text="2024年度",
            period_id="2024FY",
            value_time_shape="duration",
            comparison_axis="current",
            is_current=True,
            is_comparison=False,
        ),
        ParsedColumn(
            column_id="column-2",
            column_index=2,
            header_text="2023年度",
            period_id="2023FY",
            value_time_shape="duration",
            comparison_axis="prior",
            is_current=False,
            is_comparison=True,
        ),
    ]


def test_parse_header_rows_preserves_header_column_positions_with_blanks() -> None:
    columns = parse_header_rows(
        title_text="合并利润表",
        header_rows=[["项目", "", "2024年度", "", "2023年度"]],
        market="CN",
    )

    assert [column.column_index for column in columns] == [2, 4]
    assert [column.column_id for column in columns] == ["column-2", "column-4"]


def test_parse_header_rows_parses_cn_annual_end_date_form() -> None:
    columns = parse_header_rows(
        title_text="合并利润表",
        header_rows=[["项目", "截至2024年12月31日止年度"]],
        market="CN",
    )

    assert columns == [
        ParsedColumn(
            column_id="column-1",
            column_index=1,
            header_text="截至2024年12月31日止年度",
            period_id="2024FY",
            value_time_shape="duration",
            comparison_axis="current",
            is_current=True,
            is_comparison=False,
        )
    ]


@pytest.mark.parametrize(
    ("header_text", "expected_period_id"),
    [
        ("Three months ended 31 March 2025", "2025Q1"),
        ("Three months ended 30 June 2025", "2025Q2"),
        ("Three months ended 30 September 2025", "2025Q3"),
        ("Three months ended 31 December 2025", "2025Q4"),
    ],
)
def test_parse_header_rows_parses_hk_quarter_header(
    header_text: str,
    expected_period_id: str,
) -> None:
    columns = parse_header_rows(
        title_text="Condensed Consolidated Statement of Profit or Loss",
        header_rows=[["", header_text]],
        market="HK",
    )

    assert columns == [
        ParsedColumn(
            column_id="column-1",
            column_index=1,
            header_text=header_text,
            period_id=expected_period_id,
            value_time_shape="duration",
            comparison_axis="current",
            is_current=True,
            is_comparison=False,
        )
    ]


def test_detect_table_currency_uses_local_chinese_context() -> None:
    assert detect_table_currency("单位：万元 币种：人民币", market="CN") == "CNY"


def test_detect_table_unit_uses_local_context() -> None:
    assert detect_table_unit("单位：万元") == "万元"
