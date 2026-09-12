from __future__ import annotations

from financial_report_analysis.p5.ollama_fallback_e2e import (
    DEFAULT_OLLAMA_FALLBACK_E2E_CASE,
    selected_ollama_fallback_e2e_case,
)


def test_selected_ollama_fallback_e2e_case_defaults_to_known_q3_sample(
    monkeypatch,
) -> None:
    monkeypatch.delenv("FRA_OLLAMA_FALLBACK_E2E_STOCK_CODE", raising=False)

    case = selected_ollama_fallback_e2e_case()

    assert case == DEFAULT_OLLAMA_FALLBACK_E2E_CASE
    assert case.relative_pdf_parts == (
        "hk_stocks",
        "09987",
        "quarterly",
        "2025_quarterly_q3_en.pdf",
    )


def test_selected_ollama_fallback_e2e_case_can_be_replaced_from_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv("FRA_OLLAMA_FALLBACK_E2E_MARKET", "CN")
    monkeypatch.setenv("FRA_OLLAMA_FALLBACK_E2E_STOCK_CODE", "601919")
    monkeypatch.setenv("FRA_OLLAMA_FALLBACK_E2E_REPORT_TYPE", "annual")
    monkeypatch.setenv("FRA_OLLAMA_FALLBACK_E2E_FISCAL_YEAR", "2025")
    monkeypatch.setenv("FRA_OLLAMA_FALLBACK_E2E_FILENAME", "2025_年度报告.pdf")
    monkeypatch.setenv(
        "FRA_OLLAMA_FALLBACK_E2E_EXPECTED_METRIC_IDS",
        "revenue,total_assets",
    )
    monkeypatch.setenv(
        "FRA_OLLAMA_FALLBACK_E2E_EXPECTED_FALLBACK_METRIC_IDS",
        "total_assets",
    )

    case = selected_ollama_fallback_e2e_case()

    assert case.market == "CN"
    assert case.stock_code == "601919"
    assert case.report_type == "annual"
    assert case.fiscal_year == 2025
    assert case.filename == "2025_年度报告.pdf"
    assert case.expected_metric_ids == ("revenue", "total_assets")
    assert case.expected_fallback_metric_ids == ("total_assets",)
    assert case.relative_pdf_parts == (
        "cn_stocks",
        "601919",
        "annual",
        "2025_年度报告.pdf",
    )
