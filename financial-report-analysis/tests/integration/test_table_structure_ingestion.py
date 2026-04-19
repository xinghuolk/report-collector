from __future__ import annotations

from pathlib import Path

from financial_report_analysis.ingestion import (
    PdfTableStructureAdapter,
    normalize_table_semantics,
)
from financial_report_analysis.ingestion.table_source import RawTableBlock


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
    assert income_table.continued_from_table_id == "/tmp/fake.pdf:parsed-table:2"
    assert income_table.continuation_confidence == 1.0

    semantics = normalize_table_semantics(income_table)
    assert [column.period_id for column in semantics.columns] == ["2025Q3", "2024Q3"]
    assert [column.comparison_axis for column in semantics.columns] == ["current", "prior"]
    merged_row = next(
        row for row in semantics.rows if row.label_raw == "Franchise fees and income"
    )
    assert [value.period_id for value in merged_row.values] == ["2025Q3", "2024Q3"]
    assert [value.comparison_axis for value in merged_row.values] == ["current", "prior"]
