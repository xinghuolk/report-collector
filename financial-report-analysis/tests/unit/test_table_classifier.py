from financial_report_analysis.ingestion.table_classifier import (
    classify_table_kind,
    normalize_table_title,
)


def test_normalize_table_title_removes_whitespace_and_case_noise() -> None:
    assert normalize_table_title("  Condensed  Balance Sheet  ") == "condensedbalancesheet"


def test_classify_chinese_income_statement_title() -> None:
    assert classify_table_kind("合并利润表", market="CN") == "income_statement"


def test_classify_english_balance_sheet_title() -> None:
    assert (
        classify_table_kind(
            "Condensed Consolidated Statement of Financial Position",
            market="HK",
        )
        == "balance_sheet"
    )


def test_classify_key_metrics_table_as_p1() -> None:
    assert classify_table_kind("主要财务数据", market="CN") == "key_metrics"


def test_classify_chinese_cash_flow_statement_title() -> None:
    assert classify_table_kind("合并现金流量表", market="CN") == "cash_flow_statement"


def test_normalize_table_title_removes_continuation_markers() -> None:
    assert normalize_table_title("合并现金流量表（续）") == "合并现金流量表"
    assert normalize_table_title("Statement of Cash Flows (continued)") == "statementofcashflows"


def test_unknown_title_falls_back_to_unknown() -> None:
    assert classify_table_kind("董事会报告", market="CN") == "unknown"
