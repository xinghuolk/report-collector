from pathlib import Path

import pytest

from src.pdf_parser.content_extractor import PDFContentExtractor


ROOT_DIR = Path(__file__).resolve().parents[2]
Q3_PDF = ROOT_DIR / "downloads" / "hk_stocks" / "09987" / "quarterly" / "2025_quarterly_q3_en.pdf"
Q4_PDF = ROOT_DIR / "downloads" / "hk_stocks" / "09987" / "quarterly" / "2025_quarterly_q4_fy_en.pdf"


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
    assert any(fact.get("evidence_ids") for fact in result.get("facts", []))


@pytest.mark.integration
def test_hk_09987_q4_fy_period_extraction() -> None:
    if not Q4_PDF.exists():
        pytest.skip(f"Sample PDF not found: {Q4_PDF}")

    result = PDFContentExtractor().extract(str(Q4_PDF))

    assert result.get("success") is True
    assert result.get("schema_version") == "v2"
    period_ids = {period["period_id"] for period in result.get("periods", [])}
    assert {"2025FY", "2024FY", "2025Q4_SINGLE"} <= period_ids

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
