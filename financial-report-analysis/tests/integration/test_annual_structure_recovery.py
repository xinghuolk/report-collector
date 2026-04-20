from __future__ import annotations

from pathlib import Path

import pytest

from financial_report_analysis.ingestion import PdfTableStructureAdapter


REPO_ROOT = Path(__file__).resolve().parents[3]
MAIN_REPO_ROOT = REPO_ROOT.parent.parent


def _resolve_sample(*relative_parts: str) -> Path:
    for root in (REPO_ROOT, MAIN_REPO_ROOT):
        candidate = root / "report" / "downloads" / Path(*relative_parts)
        if candidate.exists():
            return candidate
    raise AssertionError(f"Sample PDF not found for {relative_parts}")


def _cn_primary_anchor() -> Path:
    return _resolve_sample("cn_stocks", "601919", "annual", "2024_年度报告.pdf")


@pytest.mark.parametrize(
    ("stock_code", "filename", "expected_kinds", "expect_income_rows"),
    [
        (
            "02498",
            "2022_annual_en.pdf",
            {"balance_sheet", "cash_flow_statement"},
            False,
        ),
        (
            "06862",
            "2024_annual_en.pdf",
            {"income_statement", "balance_sheet", "cash_flow_statement"},
            True,
        ),
        (
            "09987",
            "2024_annual_en.pdf",
            {"income_statement", "balance_sheet", "cash_flow_statement"},
            True,
        ),
    ],
)
def test_hk_annual_anchor_exposes_non_empty_statement_rows(
    stock_code: str,
    filename: str,
    expected_kinds: set[str],
    expect_income_rows: bool,
) -> None:
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(_resolve_sample("hk_stocks", stock_code, "annual", filename)),
        pdf_url=None,
        market="HK",
    )

    assert {table.table_kind for table in tables} >= expected_kinds
    assert any(table.statement_scope_guess == "consolidated" for table in tables)
    income_tables = [table for table in tables if table.table_kind == "income_statement"]
    if expect_income_rows:
        assert income_tables
        assert any(table.body_rows for table in income_tables)
        assert any(
            any(row.label_raw.strip() for row in table.body_rows)
            for table in income_tables
        )
    else:
        assert not income_tables
    if stock_code == "02498":
        assert any(
            getattr(table, "continued_from_table_id", None) for table in tables
        )


def test_hk_quarterly_anchor_preserves_page_level_context_in_source_block() -> None:
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(
            _resolve_sample("hk_stocks", "09987", "quarterly", "2025_quarterly_q3_en.pdf")
        ),
        pdf_url=None,
        market="HK",
    )

    income_statement = next(table for table in tables if table.table_kind == "income_statement")
    assert income_statement.source_blocks
    assert income_statement.source_blocks[0].raw_text.startswith("Yum China Holdings, Inc.")
    assert "Condensed Consolidated Statements of Income" in income_statement.source_blocks[0].raw_text


def test_cn_annual_anchor_exposes_non_empty_period_columns() -> None:
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(_cn_primary_anchor()),
        pdf_url=None,
        market="CN",
    )

    assert any(table.statement_scope_guess == "consolidated" for table in tables)
    assert any(table.period_columns for table in tables)
