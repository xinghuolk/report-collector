from pathlib import Path

import pytest

from src.pdf_parser.content_extractor import PDFContentExtractor


ROOT_DIR = Path(__file__).resolve().parents[2]
Q1_PDF = ROOT_DIR / "downloads" / "hk_stocks" / "09987" / "quarterly" / "2025_quarterly_q1_en.pdf"
Q3_PDF = ROOT_DIR / "downloads" / "hk_stocks" / "09987" / "quarterly" / "2025_quarterly_q3_en.pdf"
Q4_PDF = ROOT_DIR / "downloads" / "hk_stocks" / "09987" / "quarterly" / "2025_quarterly_q4_fy_en.pdf"
H1_PDF = ROOT_DIR / "downloads" / "hk_stocks" / "09987" / "semi_annual" / "2025_semi_annual_en.pdf"


def _fact_value(result: dict, statement: str, metric: str, period_id: str) -> float | None:
    for fact in result.get("facts", []):
        if (
            fact.get("statement") == statement
            and fact.get("metric") == metric
            and fact.get("period_id") == period_id
        ):
            return fact.get("value")
    return None


def _assert_close(value: float | None, expected: float, tolerance: float = 1.0) -> None:
    assert value is not None, f"Expected value {expected}, got None"
    assert abs(value - expected) <= tolerance, (
        f"Expected {expected}±{tolerance}, got {value}"
    )


@pytest.mark.integration
def test_hk_09987_q1_key_values() -> None:
    if not Q1_PDF.exists():
        pytest.skip(f"Sample PDF not found: {Q1_PDF}")

    extractor = PDFContentExtractor()
    result = extractor.extract(str(Q1_PDF))
    assert result.get("success") is True
    assert result.get("schema_version") == "v2"
    assert extractor.is_english_report is True

    period_ids = {period["period_id"] for period in result.get("periods", [])}
    assert {"2025Q1_YTD", "BS_2025-03-31"} <= period_ids

    _assert_close(
        _fact_value(result, "income_statement", "revenue", "2025Q1_YTD"),
        2981.0,
    )
    _assert_close(
        _fact_value(result, "income_statement", "operating_profit", "2025Q1_YTD"),
        399.0,
    )


@pytest.mark.integration
def test_hk_09987_q3_period_extraction() -> None:
    if not Q3_PDF.exists():
        pytest.skip(f"Sample PDF not found: {Q3_PDF}")

    result = PDFContentExtractor().extract(str(Q3_PDF))

    assert result.get("success") is True
    assert result.get("schema_version") == "v2"
    period_ids = {period["period_id"] for period in result.get("periods", [])}
    assert "2025Q3_YTD" in period_ids
    assert "2025Q3_SINGLE" in period_ids
    assert any(fact.get("period_id") == "2025Q3_SINGLE" for fact in result.get("facts", []))
    assert any(fact.get("evidence_ids") for fact in result.get("facts", []))

    # Q3 主报表（Quarter Ended 9/30/2025）关键值
    _assert_close(
        _fact_value(result, "income_statement", "revenue", "2025Q3_SINGLE"),
        3206.0,
    )
    _assert_close(
        _fact_value(result, "income_statement", "operating_profit", "2025Q3_SINGLE"),
        400.0,
    )
    _assert_close(
        _fact_value(result, "income_statement", "revenue", "2025Q3_YTD"),
        8974.0,
    )
    _assert_close(
        _fact_value(result, "income_statement", "operating_profit", "2025Q3_YTD"),
        1103.0,
    )
    _assert_close(
        _fact_value(result, "income_statement", "net_profit", "2025Q3_YTD"),
        789.0,
    )


@pytest.mark.integration
def test_hk_09987_h1_key_values() -> None:
    if not H1_PDF.exists():
        pytest.skip(f"Sample PDF not found: {H1_PDF}")

    result = PDFContentExtractor().extract(str(H1_PDF))
    assert result.get("success") is True
    assert result.get("schema_version") == "v2"
    period_ids = {period["period_id"] for period in result.get("periods", [])}
    assert {"2025H1_YTD", "BS_2025-06-30"} <= period_ids

    _assert_close(
        _fact_value(result, "income_statement", "revenue", "2025H1_YTD"),
        5768.0,
    )
    _assert_close(
        _fact_value(result, "income_statement", "operating_profit", "2025H1_YTD"),
        703.0,
    )


@pytest.mark.integration
def test_hk_09987_q4_fy_period_extraction() -> None:
    if not Q4_PDF.exists():
        pytest.skip(f"Sample PDF not found: {Q4_PDF}")

    result = PDFContentExtractor().extract(str(Q4_PDF))

    assert result.get("success") is True
    assert result.get("schema_version") == "v2"
    period_ids = {period["period_id"] for period in result.get("periods", [])}
    assert {"2025FY", "2024FY", "2025Q4_SINGLE"} <= period_ids
    assert any(fact.get("period_id") == "2025Q4_SINGLE" for fact in result.get("facts", []))

    # 来自主报表（Condensed Consolidated Statements）的关键值校验
    _assert_close(
        _fact_value(result, "income_statement", "revenue", "2025FY"),
        11797.0,
    )
    _assert_close(
        _fact_value(result, "income_statement", "revenue", "2024FY"),
        11303.0,
    )
    _assert_close(
        _fact_value(result, "income_statement", "revenue", "2025Q4_SINGLE"),
        2823.0,
    )
    _assert_close(
        _fact_value(result, "income_statement", "operating_profit", "2025Q4_SINGLE"),
        223.0,
    )
    _assert_close(
        _fact_value(result, "cash_flow_statement", "operating_cash_flow", "2025FY"),
        1466.0,
    )
    _assert_close(
        _fact_value(result, "cash_flow_statement", "operating_cash_flow", "2024FY"),
        1419.0,
    )

    comparison_core = [
        fact
        for fact in result.get("facts", [])
        if fact.get("period_id") == "2024FY"
        and (
            (fact.get("statement") == "income_statement" and fact.get("metric") in {"revenue", "net_profit"})
            or (fact.get("statement") == "cash_flow_statement" and fact.get("metric") == "operating_cash_flow")
        )
    ]
    assert len(comparison_core) == 3
