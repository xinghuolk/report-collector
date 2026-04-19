from __future__ import annotations

from pathlib import Path

from financial_report_analysis.ingestion import (
    PdfTableStructureAdapter,
    normalize_table_semantics,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
MAIN_REPO_ROOT = REPO_ROOT.parent.parent


def _resolve_sample(*relative_parts: str) -> Path:
    for root in (REPO_ROOT, MAIN_REPO_ROOT):
        candidate = root / "report" / "downloads" / Path(*relative_parts)
        if candidate.exists():
            return candidate
    raise AssertionError(f"Sample PDF not found for {relative_parts}")


def test_hk_annual_semantics_preserve_statement_scope_and_ambiguity() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="HK",
    )

    balance_sheet = next(table for table in tables if table.table_kind == "balance_sheet")
    semantics = normalize_table_semantics(balance_sheet)

    assert semantics.statement_scope_guess == "consolidated"
    assert semantics.semantic_source == "deterministic"
    assert semantics.semantic_ambiguity_reason in {None, "numeric_only_statement_block"}


def test_cn_annual_semantics_expose_normalized_row_labels() -> None:
    pdf_path = _resolve_sample("cn_stocks", "601919", "annual", "2024_年度报告.pdf")
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="CN",
    )

    income_statement = next(table for table in tables if table.table_kind == "income_statement")
    semantics = normalize_table_semantics(income_statement)

    assert any(row.normalized_row_label for row in semantics.rows)
