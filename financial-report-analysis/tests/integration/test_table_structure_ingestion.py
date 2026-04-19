from __future__ import annotations

from pathlib import Path

from financial_report_analysis.ingestion import PdfTableStructureAdapter


REPO_ROOT = Path(__file__).resolve().parents[3]
MAIN_REPO_ROOT = REPO_ROOT.parent.parent


def _sample_pdf(*parts: str) -> Path:
    for root in (REPO_ROOT, MAIN_REPO_ROOT):
        candidate = root / "report" / "downloads" / Path(*parts)
        if candidate.exists():
            return candidate
    raise AssertionError(f"Sample PDF not found for {parts}")


def test_cn_annual_sample_exposes_income_statement_and_balance_sheet() -> None:
    adapter = PdfTableStructureAdapter()

    tables = adapter.extract_tables(
        pdf_path=str(
            _sample_pdf("cn_stocks", "688008", "annual", "2024_年度报告.pdf")
        ),
        pdf_url=None,
        market="CN",
    )

    kinds = {table.table_kind for table in tables}
    assert "income_statement" in kinds
    assert "balance_sheet" in kinds


def test_hk_quarter_sample_exposes_non_empty_period_columns() -> None:
    adapter = PdfTableStructureAdapter()

    tables = adapter.extract_tables(
        pdf_path=str(
            _sample_pdf("hk_stocks", "09987", "quarterly", "2025_quarterly_q3_en.pdf")
        ),
        pdf_url=None,
        market="HK",
    )

    income_table = next(table for table in tables if table.table_kind == "income_statement")
    assert income_table.period_columns
    assert income_table.period_columns[0].period_id is not None
