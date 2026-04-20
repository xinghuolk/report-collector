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
    annual_dir = _resolve_sample("cn_stocks", "601919", "annual")
    try:
        return next(
            candidate
            for candidate in annual_dir.glob("*.pdf")
            if candidate.is_file()
        )
    except StopIteration as exc:  # pragma: no cover - defensive fixture resolution
        raise AssertionError(f"Sample PDF not found in {annual_dir}") from exc


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


def test_hk_quarterly_anchor_preserves_header_value_binding() -> None:
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(
            _resolve_sample("hk_stocks", "09987", "quarterly", "2025_quarterly_q3_en.pdf")
        ),
        pdf_url=None,
        market="HK",
    )

    income_statement = next(table for table in tables if table.table_kind == "income_statement")
    assert income_statement.header_rows[0][2] == "9/30/2025"
    assert income_statement.header_rows[0][6] == "9/30/2024"

    company_sales = next(
        row for row in income_statement.body_rows if row.label_raw == "Company sales $"
    )
    assert [cell.column_index for cell in company_sales.value_cells] == [1, 2, 3, 4, 5, 6]
    assert [cell.text_raw for cell in company_sales.value_cells] == [
        "2,998",
        "2,895",
        "4",
        "8,412",
        "8,217",
        "2",
    ]
    assert income_statement.period_columns[0].header_text == "9/30/2025"
    assert income_statement.period_columns[1].header_text == "9/30/2024"


def test_cn_annual_anchor_preserves_local_unit_context_without_page_bleed() -> None:
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(_cn_primary_anchor()),
        pdf_url=None,
        market="CN",
    )

    unit_table = next(
        table
        for table in tables
        if table.header_rows
        and table.header_rows[0][:2]
        == ["涉及重要性标准判断的披露事项", "重要性标准确定方法和选择依据"]
    )

    assert unit_table.table_unit == "亿元"
    assert unit_table.table_currency == "CNY"
    assert unit_table.body_rows

