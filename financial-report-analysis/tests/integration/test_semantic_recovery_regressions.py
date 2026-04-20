from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from financial_report_analysis.api.app import create_app
from financial_report_analysis.ingestion import (
    PdfIngestionAdapter,
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


def test_hk_annual_anchor_surfaces_non_empty_key_fact_path() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")
    ingestion_payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )
    assert any(
        fact.get("extraction_method") == "table_semantics"
        for fact in ingestion_payload["candidate_facts"]
    )

    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(pdf_path),
            "market": "HK",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["key_facts"]
    assert any(
        fact.get("statement_type") == "balance_sheet"
        and fact.get("period_id") in {"2021FY", "2022FY"}
        for fact in payload["key_facts"]
    )


def test_hk_q3_anchor_preserves_semantic_provenance_in_parsed_tables() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "quarterly", "2025_quarterly_q3_en.pdf")
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(pdf_path),
            "market": "HK",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["metadata"]["parsed_tables"]
    assert any(
        table.get("semantic_source") in {"deterministic", "llm_fallback"}
        for table in payload["document"]["metadata"]["parsed_tables"]
    )
    assert any(
        table.get("unit_semantic_source") == "deterministic"
        and table.get("currency_semantic_source") == "deterministic"
        for table in payload["document"]["metadata"]["parsed_tables"]
        if table.get("table_unit") or table.get("table_currency")
    )


def test_hk_annual_anchor_preserves_deterministic_unit_currency_provenance() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")
    ingestion_payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    table_semantic_candidates = [
        fact
        for fact in ingestion_payload["candidate_facts"]
        if fact.get("extraction_method") == "table_semantics"
    ]

    assert table_semantic_candidates
    assert any(
        fact["extensions"].get("unit_semantic_source") == "deterministic"
        and fact["extensions"].get("currency_semantic_source") == "deterministic"
        for fact in table_semantic_candidates
    )
