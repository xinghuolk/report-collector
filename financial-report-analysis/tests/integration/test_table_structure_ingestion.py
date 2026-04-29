from __future__ import annotations

from pathlib import Path

import pytest

from financial_report_analysis.ingestion import (
    PdfTableStructureAdapter,
    normalize_table_semantics,
)
from financial_report_analysis.ingestion.table_source import RawTableBlock
from financial_report_analysis.models import ParsedTable


REPO_ROOT = Path(__file__).resolve().parents[3]
MAIN_REPO_ROOT = REPO_ROOT.parent.parent


def _sample_pdf(*parts: str) -> Path:
    for root in (REPO_ROOT, MAIN_REPO_ROOT):
        candidate = root / "report" / "downloads" / Path(*parts)
        if candidate.exists():
            return candidate
    raise AssertionError(f"Sample PDF not found for {parts}")


def _cn_primary_anchor() -> Path:
    return _sample_pdf("cn_stocks", "601919", "annual", "2024_年度报告.pdf")


def _hk_annual_anchor(stock_code: str, filename: str) -> Path:
    return _sample_pdf("hk_stocks", stock_code, "annual", filename)


def _labels_for_table(table: ParsedTable) -> set[str]:
    return {
        " ".join(row.label_raw.lower().split())
        for row in table.body_rows
        if row.label_raw
    }


def _flatten_labels(tables: list[ParsedTable]) -> set[str]:
    labels: set[str] = set()
    for table in tables:
        labels.update(_labels_for_table(table))
    return labels


@pytest.mark.real_pdf
@pytest.mark.slow
def test_cn_primary_annual_anchor_exposes_income_statement_and_balance_sheet() -> None:
    adapter = PdfTableStructureAdapter()

    tables = adapter.extract_tables(
        pdf_path=str(_cn_primary_anchor()),
        pdf_url=None,
        market="CN",
    )

    kinds = {table.table_kind for table in tables}
    assert "income_statement" in kinds
    assert "balance_sheet" in kinds


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
        (
            "00001",
            "2025_annual_en.pdf",
            {"income_statement", "balance_sheet", "cash_flow_statement"},
            True,
        ),
    ],
)
@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_annual_anchors_expose_non_empty_statement_rows(
    stock_code: str,
    filename: str,
    expected_kinds: set[str],
    expect_income_rows: bool,
) -> None:
    adapter = PdfTableStructureAdapter()

    tables = adapter.extract_tables(
        pdf_path=str(_hk_annual_anchor(stock_code, filename)),
        pdf_url=None,
        market="HK",
    )

    assert {table.table_kind for table in tables} >= expected_kinds
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


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk00001_2025_dual_currency_main_statement_labels_are_recovered() -> None:
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(_hk_annual_anchor("00001", "2025_annual_en.pdf")),
        pdf_url=None,
        market="HK",
    )

    income_tables = [table for table in tables if table.table_kind == "income_statement"]
    balance_tables = [table for table in tables if table.table_kind == "balance_sheet"]
    cash_flow_tables = [
        table for table in tables if table.table_kind == "cash_flow_statement"
    ]

    assert any(table.body_rows for table in income_tables)
    assert any(table.body_rows for table in balance_tables)
    assert any(table.body_rows for table in cash_flow_tables)
    assert {
        "revenue",
        "cost of inventories sold",
    } <= _flatten_labels(income_tables)
    assert {
        "fixed assets",
        "total assets less current liabilities",
    } <= _flatten_labels(balance_tables)
    assert {
        "cash generated from operating activities before interest expenses, other finance costs, tax paid, and changes in working capital",
        "interest expenses and other finance costs paid (net of capitalisation)",
        "tax paid",
    } <= _flatten_labels(cash_flow_tables)


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk00001_2025_remaining_main_statement_labels_are_classified() -> None:
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(_hk_annual_anchor("00001", "2025_annual_en.pdf")),
        pdf_url=None,
        market="HK",
    )

    income_table = next(
        (
            table
            for table in tables
            if table.table_kind == "income_statement"
            and table.page_range == (134, 134)
            and table.title_text == "Consolidated Income Statement"
            and table.statement_scope_guess == "consolidated"
            and table.semantic_ambiguity_reason == "dual_currency_statement_block"
        ),
        None,
    )
    balance_table = next(
        (
            table
            for table in tables
            if table.table_kind == "balance_sheet"
            and table.page_range == (136, 136)
            and table.title_text == "Consolidated Statement of Financial Position"
            and table.statement_scope_guess == "consolidated"
            and table.semantic_ambiguity_reason == "dual_currency_statement_block"
        ),
        None,
    )
    cash_flow_table = next(
        (
            table
            for table in tables
            if table.table_kind == "cash_flow_statement"
            and table.page_range == (141, 141)
            and table.semantic_ambiguity_reason == "dual_currency_statement_block"
        ),
        None,
    )

    assert income_table is not None
    assert balance_table is not None
    assert cash_flow_table is not None

    income_labels = _labels_for_table(income_table)
    balance_labels = _labels_for_table(balance_table)
    cash_flow_labels = _labels_for_table(cash_flow_table)

    assert "cost of inventories sold" in income_labels
    assert "total assets less current liabilities" in balance_labels
    assert "total assets" not in balance_labels
    assert "tax paid" in cash_flow_labels
    assert (
        "cash generated from operating activities before interest expenses, other finance costs, tax paid, and changes in working capital"
        in cash_flow_labels
    )


@pytest.mark.real_pdf
@pytest.mark.slow
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
    assert income_table.statement_scope_guess == "consolidated"

    semantics = normalize_table_semantics(income_table)
    assert semantics.columns
    assert any(column.comparison_axis == "prior" for column in semantics.columns)
    revenue_like_row = next(row for row in semantics.rows if row.label_raw == "Company sales $")
    assert any(value.period_id is not None for value in revenue_like_row.values)
    assert any(value.comparison_axis == "prior" for value in revenue_like_row.values)


class _StubTableSource:
    def extract_raw_table_blocks(
        self,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
    ) -> list[RawTableBlock]:
        del pdf_path, pdf_url
        return [
            RawTableBlock(
                block_id="doc:page:1:table:1",
                page_index=1,
                page_range=(1, 1),
                rows=[
                    ["Condensed Consolidated Statements of Income"],
                    [
                        "",
                        "Three months ended 30 September 2025",
                        "Three months ended 30 September 2024",
                    ],
                    ["Company sales $", "1,234", "1,111"],
                ],
                page_text="Condensed Consolidated Statements of Income",
            ),
            RawTableBlock(
                block_id="doc:page:2:table:1",
                page_index=2,
                page_range=(2, 2),
                rows=[
                    ["Condensed Consolidated Statements of Income (continued)"],
                    [
                        "",
                        "Three months ended 30 September 2025",
                        "Three months ended 30 September 2024",
                    ],
                    ["Franchise fees and income", "222", "210"],
                ],
                page_text="Condensed Consolidated Statements of Income (continued)",
            ),
        ]


def test_table_structure_and_semantics_preserve_continuation_metadata_end_to_end() -> None:
    adapter = PdfTableStructureAdapter(table_source=_StubTableSource())

    tables = adapter.extract_tables(
        pdf_path="/tmp/fake.pdf",
        pdf_url=None,
        market="HK",
    )

    assert len(tables) == 1
    income_table = tables[0]
    assert income_table.statement_scope_guess == "consolidated"
    assert income_table.continued_from_table_id == f"{Path('/tmp/fake.pdf')}:parsed-table:2"
    assert income_table.continuation_confidence == 1.0

    semantics = normalize_table_semantics(income_table)
    assert [column.period_id for column in semantics.columns] == ["2025Q3", "2024Q3"]
    assert [column.comparison_axis for column in semantics.columns] == ["current", "prior"]
    merged_row = next(
        row for row in semantics.rows if row.label_raw == "Franchise fees and income"
    )
    assert [value.period_id for value in merged_row.values] == ["2025Q3", "2024Q3"]
    assert [value.comparison_axis for value in merged_row.values] == ["current", "prior"]
