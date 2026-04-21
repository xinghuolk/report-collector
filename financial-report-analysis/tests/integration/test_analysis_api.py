from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
import httpx
from fastapi.testclient import TestClient

from financial_report_analysis.api.app import create_app
from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
from financial_report_analysis.semantic_fallback import load_semantic_fallback_settings

REPO_ROOT = Path(__file__).resolve().parents[3]
MAIN_REPO_ROOT = REPO_ROOT.parent.parent


def _resolve_sample_path(*relative_parts: str) -> Path | None:
    for root in (REPO_ROOT, MAIN_REPO_ROOT):
        candidate = root.joinpath(*relative_parts)
        if candidate.exists():
            return candidate
    return None


def _resolve_cn_annual_sample() -> Path | None:
    annual_dir = _resolve_sample_path(
        "report",
        "downloads",
        "cn_stocks",
        "601919",
        "annual",
    )
    if annual_dir is None:
        return None
    target = annual_dir / "2024_年度报告.pdf"
    return target if target.exists() else None


def _resolve_hk_annual_sample(stock_code: str, filename: str) -> Path | None:
    return _resolve_sample_path(
        "report",
        "downloads",
        "hk_stocks",
        stock_code,
        "annual",
        filename,
    )


def _resolve_cn_quarterly_sample() -> Path | None:
    return _resolve_sample_path(
        "report",
        "downloads",
        "cn_stocks",
        "688008",
        "quarterly",
        "2024_第三季度报告.pdf",
    )


def _resolve_hk_non_english_sample() -> Path:
    resolved = _resolve_sample_path(
        "report",
        "downloads",
        "hk_stocks",
        "01810",
        "annual",
        "2020_annual_zh.pdf",
    )
    assert resolved is not None
    return resolved


def _ollama_model_available(*, base_url: str, model: str) -> bool:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=3.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return False
    payload = response.json()
    models = payload.get("models", [])
    return any(entry.get("name") == model for entry in models if isinstance(entry, dict))


def _real_ollama_endpoint() -> tuple[str, str]:
    settings = load_semantic_fallback_settings()
    return settings.base_url, settings.model


def test_health_endpoint_reports_ready() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_extract_endpoint_requires_pdf_source() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "pdf_path or pdf_url is required"


def test_extract_endpoint_rejects_whitespace_only_sources() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": "   ",
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "pdf_path or pdf_url is required"


def test_extract_endpoint_rejects_both_sources() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": "/tmp/report.pdf",
            "pdf_url": "https://example.com/report.pdf",
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "provide only one of pdf_path or pdf_url"


def test_extract_endpoint_rejects_missing_pdf_path() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": "/tmp/report.pdf",
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "pdf_path does not exist"


def test_extract_endpoint_runs_ingestion_path_for_pdf_input(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )

    pdf_path = tmp_path / "mock.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [],
    )

    def fake_extract_text(
        self: PdfIngestionAdapter,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
    ) -> str:
        assert pdf_path == str(pdf_file)
        assert pdf_url is None
        return "2024 Annual Report\nRevenue 1,234 RMB'000\n"

    pdf_file = pdf_path
    monkeypatch.setattr(PdfIngestionAdapter, "_extract_text", fake_extract_text)

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(pdf_path),
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["quality_gate"] == "pass"
    assert payload["document"]["metadata"]["parsed_tables"] == []
    assert payload["key_facts"]
    assert payload["key_facts"][0]["metric_id"] == "revenue"
    assert payload["key_facts"][0]["numeric_value"] == 1_234_000.0


def _phase1_candidate_payload(
    *,
    fact_id: str,
    metric_id: str,
    metric_label_raw: str,
    numeric_value: float,
    raw_unit: str,
    document_id: str,
    statement_type: str = "income_statement",
    extensions: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "fact_id": fact_id,
        "metric_id": metric_id,
        "metric_label_raw": metric_label_raw,
        "statement_type": statement_type,
        "entity_scope": "consolidated",
        "comparison_axis": "current",
        "adjustment_basis": "reported",
        "period_id": "2024FY",
        "currency": "CNY",
        "raw_value": str(numeric_value),
        "numeric_value": numeric_value,
        "raw_unit": raw_unit,
        "normalized_unit": None,
        "precision": 2 if raw_unit == "元/股" else 0,
        "confidence": 0.9,
        "extensions": extensions or {},
        "document_id": document_id,
        "block_id": f"block::{fact_id}",
        "page_index": 0,
        "evidence_bundle_id": f"bundle::{fact_id}",
        "source_rank_hint": 30,
    }


def test_extract_endpoint_surfaces_phase1_api_visible_metrics(
    monkeypatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "mock.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

    def fake_extract_candidate_facts(*args, **kwargs):
        del args, kwargs
        filler_candidates = [
            _phase1_candidate_payload(
                fact_id=f"custom-{index}",
                metric_id=f"custom_metric_{index}",
                metric_label_raw=f"Alpha metric {index}",
                numeric_value=float(index),
                raw_unit="CNY",
                document_id=str(pdf_path),
            )
            for index in range(1, 11)
        ]
        return {
            "document_metadata": {
                "language": "zh",
                "parsed_tables": [],
            },
            "candidate_facts": [
                *filler_candidates,
                _phase1_candidate_payload(
                    fact_id="phase1-net-income",
                    metric_id="n_income_attr_p",
                    metric_label_raw="Net profit attributable to owners of the parent",
                    numeric_value=123.0,
                    raw_unit="CNY",
                    document_id=str(pdf_path),
                    extensions={
                        "semantic_source": "llm_fallback",
                        "semantic_confidence": 0.77,
                        "fallback_reason": "owner_scope_disambiguation",
                    },
                ),
                _phase1_candidate_payload(
                    fact_id="phase1-basic-eps",
                    metric_id="basic_eps",
                    metric_label_raw="Basic EPS",
                    numeric_value=1.23,
                    raw_unit="元/股",
                    document_id=str(pdf_path),
                    extensions={
                        "value_type": "per_share",
                        "unit_expectation": "per_share_amount",
                    },
                ),
            ],
        }

    monkeypatch.setattr(
        PdfIngestionAdapter,
        "extract_candidate_facts",
        fake_extract_candidate_facts,
    )

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(pdf_path),
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    key_fact_ids = [fact["metric_id"] for fact in payload["key_facts"]]
    assert "n_income_attr_p" in key_fact_ids
    assert "basic_eps" in key_fact_ids
    basic_eps = next(fact for fact in payload["key_facts"] if fact["metric_id"] == "basic_eps")
    assert basic_eps["numeric_value"] == 1.23
    assert basic_eps["normalized_unit"] == "per_share_amount"


def test_pdf_ingestion_prefers_parsed_tables_over_text_regex(
    monkeypatch,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )

    table = ParsedTable(
        table_id="doc:parsed-table:1",
        document_id="doc",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=1,
                label_raw="Revenue",
                normalized_label_hint="revenue",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=1,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [table],
    )

    def fake_extract_text(
        self: PdfIngestionAdapter,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
    ) -> str:
        return "2023 Annual Report Revenue 9,999 RMB'000"

    monkeypatch.setattr(PdfIngestionAdapter, "_extract_text", fake_extract_text)

    payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    assert payload["document_metadata"]["parsed_tables"][0]["table_currency"] == "HKD"
    assert payload["document_metadata"]["parsed_tables"][0]["table_unit"] == "thousand"
    assert payload["candidate_facts"][0]["period_id"] == "2024FY"
    assert payload["candidate_facts"][0]["currency"] == "HKD"
    assert payload["candidate_facts"][0]["raw_unit"] == "thousand"
    assert payload["candidate_facts"][0]["numeric_value"] == 1234.0


def test_pdf_ingestion_applies_gated_row_label_fallback_for_ambiguous_table(
    monkeypatch,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )
    from financial_report_analysis.semantic_fallback import (
        RowLabelFallbackRequest,
        SemanticFallbackResult,
        SemanticFallbackService,
    )

    table = ParsedTable(
        table_id="doc:parsed-table:ambiguous",
        document_id="doc",
        page_range=(1, 1),
        table_kind="balance_sheet",
        title_text="Consolidated Statement of Financial Position",
        statement_scope_guess="consolidated",
        semantic_ambiguity_reason="numeric_only_statement_block",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=1,
                label_raw="Assets total",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=1,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="point",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [table],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "",
    )

    class _StubFallbackService(SemanticFallbackService):
        def __init__(self) -> None:
            super().__init__(client=None)
            self.requests: list[RowLabelFallbackRequest] = []

        def resolve_row_label(
            self,
            request: RowLabelFallbackRequest,
        ) -> SemanticFallbackResult:
            self.requests.append(request)
            return SemanticFallbackResult(
                value="total_assets",
                semantic_source="llm_fallback",
                semantic_confidence=0.83,
                fallback_reason=request.ambiguity_reason,
            )

    fallback_service = _StubFallbackService()

    payload = PdfIngestionAdapter(
        semantic_fallback_service=fallback_service,
    ).extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    assert fallback_service.requests
    assert payload["candidate_facts"][0]["metric_id"] == "total_assets"
    assert payload["candidate_facts"][0]["extraction_method"] == "table_semantics"
    assert payload["candidate_facts"][0]["extensions"]["semantic_source"] == "llm_fallback"
    assert payload["candidate_facts"][0]["extensions"]["fallback_reason"] == "numeric_only_statement_block"
    assert payload["document_metadata"]["parsed_tables"][0]["semantic_source"] == "llm_fallback"


def test_pdf_ingestion_applies_gated_currency_fallback_for_ambiguous_unknown_currency(
    monkeypatch,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )
    from financial_report_analysis.semantic_fallback import (
        CurrencyFallbackRequest,
        SemanticFallbackResult,
        SemanticFallbackService,
    )

    table = ParsedTable(
        table_id="doc:parsed-table:currency",
        document_id="doc",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        statement_scope_guess="consolidated",
        semantic_ambiguity_reason="numeric_only_statement_block",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=1,
                label_raw="Revenue",
                normalized_label_hint="revenue",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=1,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency=None,
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [table],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "",
    )

    class _StubFallbackService(SemanticFallbackService):
        def __init__(self) -> None:
            super().__init__(client=None)
            self.currency_requests: list[CurrencyFallbackRequest] = []

        def resolve_currency(
            self,
            request: CurrencyFallbackRequest,
        ) -> SemanticFallbackResult:
            self.currency_requests.append(request)
            return SemanticFallbackResult(
                value="HKD",
                semantic_source="llm_fallback",
                semantic_confidence=0.74,
                fallback_reason=request.ambiguity_reason,
            )

    fallback_service = _StubFallbackService()

    payload = PdfIngestionAdapter(
        semantic_fallback_service=fallback_service,
    ).extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    assert fallback_service.currency_requests
    assert payload["candidate_facts"][0]["currency"] == "HKD"
    assert payload["candidate_facts"][0]["extensions"]["semantic_source"] == "llm_fallback"
    assert (
        payload["candidate_facts"][0]["extensions"]["currency_semantic_source"]
        == "llm_fallback"
    )
    assert (
        payload["document_metadata"]["parsed_tables"][0]["currency_semantic_source"]
        == "llm_fallback"
    )


def test_pdf_ingestion_applies_row_label_fallback_for_unmapped_normalized_label(
    monkeypatch,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )
    from financial_report_analysis.semantic_fallback import (
        RowLabelFallbackRequest,
        SemanticFallbackResult,
        SemanticFallbackService,
    )

    table = ParsedTable(
        table_id="doc:parsed-table:unmapped-label",
        document_id="doc",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        statement_scope_guess="consolidated",
        semantic_ambiguity_reason=None,
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=1,
                label_raw="Business revenue",
                normalized_label_hint="business revenue",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=1,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [table],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "",
    )

    class _StubFallbackService(SemanticFallbackService):
        def __init__(self) -> None:
            super().__init__(client=None)
            self.requests: list[RowLabelFallbackRequest] = []

        def resolve_row_label(
            self,
            request: RowLabelFallbackRequest,
        ) -> SemanticFallbackResult:
            self.requests.append(request)
            return SemanticFallbackResult(
                value="revenue",
                semantic_source="llm_fallback",
                semantic_confidence=0.82,
                fallback_reason=request.ambiguity_reason,
            )

    fallback_service = _StubFallbackService()

    payload = PdfIngestionAdapter(
        semantic_fallback_service=fallback_service,
    ).extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    assert fallback_service.requests
    assert fallback_service.requests[0].ambiguity_reason == "unmapped_normalized_row_label"
    assert payload["candidate_facts"][0]["metric_id"] == "revenue"
    assert payload["candidate_facts"][0]["extensions"]["semantic_source"] == "llm_fallback"


@pytest.mark.ollama
@pytest.mark.external
def test_extract_endpoint_uses_real_ollama_fallback_for_ambiguous_table_smoke(
    monkeypatch,
) -> None:
    """Smoke test only.

    This verifies that a real local Ollama fallback call can reach the API main
    path, mark parsed-table provenance as llm_fallback, and surface a non-empty
    analysis result. It is intentionally not a gold-standard semantic quality
    test for difficult labels.
    """
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )

    base_url, model = _real_ollama_endpoint()
    if not _ollama_model_available(base_url=base_url, model=model):
        pytest.skip("local Ollama qwen3.5:9b is unavailable")

    table = ParsedTable(
        table_id="doc:parsed-table:ollama",
        document_id="doc",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Consolidated Statement of Profit or Loss",
        statement_scope_guess="consolidated",
        semantic_ambiguity_reason="numeric_only_statement_block",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=1,
                label_raw="Business revenue",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=1,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [table],
    )
    monkeypatch.setenv("FRA_SEMANTIC_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("FRA_SEMANTIC_FALLBACK_PROVIDER", "ollama")
    monkeypatch.setenv("FRA_SEMANTIC_FALLBACK_BASE_URL", base_url)
    monkeypatch.setenv("FRA_SEMANTIC_FALLBACK_MODEL", model)
    monkeypatch.setenv("FRA_SEMANTIC_FALLBACK_TIMEOUT_SECONDS", "30")

    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter

    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "",
    )

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": "ignored.pdf",
            "market": "HK",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["key_facts"]
    assert any(fact["statement_type"] == "income_statement" for fact in payload["key_facts"])
    assert payload["document"]["metadata"]["parsed_tables"][0]["semantic_source"] == "llm_fallback"


def test_pdf_ingestion_uses_revenue_table_period_over_earlier_table_period(
    monkeypatch,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )

    key_metrics_table = ParsedTable(
        table_id="doc:parsed-table:0",
        document_id="doc",
        page_range=(1, 1),
        table_kind="key_metrics",
        title_text="Key Financial Metrics",
        header_rows=[["Item", "2023"]],
        body_rows=[],
        table_unit=None,
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-0",
                column_index=1,
                header_text="2023",
                period_id="2023FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )
    revenue_table = ParsedTable(
        table_id="doc:parsed-table:1",
        document_id="doc",
        page_range=(2, 2),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=1,
                label_raw="Revenue",
                normalized_label_hint="revenue",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=2,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [key_metrics_table, revenue_table],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "2022 Annual Report Revenue 9,999 RMB'000",
    )

    payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    assert payload["candidate_facts"][0]["period_id"] == "2024FY"


def test_pdf_ingestion_matches_operating_revenue_table_labels(
    monkeypatch,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )

    table = ParsedTable(
        table_id="doc:parsed-table:1",
        document_id="doc",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=1,
                label_raw="Operating Revenue",
                normalized_label_hint="revenue",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=1,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [table],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "2023 Annual Report Revenue 9,999 RMB'000",
    )

    payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    assert payload["candidate_facts"][0]["metric_label_raw"] == "Operating Revenue"


def test_pdf_ingestion_ignores_balance_sheet_deferred_revenue_rows(
    monkeypatch,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )

    balance_sheet_table = ParsedTable(
        table_id="doc:parsed-table:0",
        document_id="doc",
        page_range=(1, 1),
        table_kind="balance_sheet",
        title_text="Consolidated Balance Sheet",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-0",
                row_index=1,
                label_raw="Deferred revenue",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="9,999",
                        numeric_value=9999.0,
                        page_index=1,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-0",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="point",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )
    income_statement_table = ParsedTable(
        table_id="doc:parsed-table:1",
        document_id="doc",
        page_range=(2, 2),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=1,
                label_raw="Operating Revenue",
                normalized_label_hint="revenue",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=2,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [balance_sheet_table, income_statement_table],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "2024 Annual Report Revenue 9,999 RMB'000",
    )

    payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    assert payload["candidate_facts"][0]["statement_type"] == "income_statement"
    assert payload["candidate_facts"][0]["metric_label_raw"] == "Operating Revenue"
    assert payload["candidate_facts"][0]["numeric_value"] == 1234.0


def test_pdf_ingestion_prefers_income_statement_over_key_metrics_growth_rows(
    monkeypatch,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )

    key_metrics_table = ParsedTable(
        table_id="doc:parsed-table:0",
        document_id="doc",
        page_range=(1, 1),
        table_kind="key_metrics",
        title_text="Key Financial Metrics",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-0",
                row_index=1,
                label_raw="Revenue growth",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="18.5",
                        numeric_value=18.5,
                        page_index=1,
                    )
                ],
            )
        ],
        table_unit="%",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-0",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )
    income_statement_table = ParsedTable(
        table_id="doc:parsed-table:1",
        document_id="doc",
        page_range=(2, 2),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=1,
                label_raw="Operating Revenue",
                normalized_label_hint="revenue",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=2,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [key_metrics_table, income_statement_table],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "2024 Annual Report Revenue 9,999 RMB'000",
    )

    payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    assert payload["candidate_facts"][0]["statement_type"] == "income_statement"
    assert payload["candidate_facts"][0]["metric_label_raw"] == "Operating Revenue"
    assert payload["candidate_facts"][0]["numeric_value"] == 1234.0
    assert payload["candidate_facts"][0]["extensions"]["table_kind"] == "income_statement"
    assert payload["candidate_facts"][0]["raw_unit"] == "thousand"


def test_extract_endpoint_prefers_income_statement_over_key_metrics_summary_rows(
    monkeypatch,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )

    key_metrics_table = ParsedTable(
        table_id="doc:parsed-table:summary",
        document_id="doc",
        page_range=(1, 1),
        table_kind="key_metrics",
        title_text="Key Financial Metrics",
        statement_scope_guess="consolidated",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=1,
                label_raw="Revenue",
                normalized_label_hint="revenue",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="9,999",
                        numeric_value=9999.0,
                        page_index=1,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-2",
                row_index=2,
                label_raw="Operating profit margin",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=2,
                        column_index=1,
                        text_raw="18.5",
                        numeric_value=18.5,
                        page_index=1,
                    )
                ],
            ),
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-0",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )
    income_statement_table = ParsedTable(
        table_id="doc:parsed-table:income",
        document_id="doc",
        page_range=(2, 2),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        statement_scope_guess="consolidated",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=1,
                label_raw="Operating Revenue",
                normalized_label_hint="revenue",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=2,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [key_metrics_table, income_statement_table],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "2024 Annual Report Revenue 9,999 RMB'000",
    )

    payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    revenue_candidates = [
        fact for fact in payload["candidate_facts"] if fact["metric_id"] == "revenue"
    ]

    assert len(revenue_candidates) == 1
    assert revenue_candidates[0]["metric_label_raw"] == "Operating Revenue"
    assert all(
        "margin" not in fact["metric_label_raw"].lower()
        for fact in payload["candidate_facts"]
    )


def test_pdf_ingestion_does_not_silence_unexpected_table_parser_errors(
    monkeypatch,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("parser exploded")),
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "2024 Annual Report Revenue 9,999 RMB'000",
    )

    with pytest.raises(RuntimeError, match="parser exploded"):
        PdfIngestionAdapter().extract_candidate_facts(
            pdf_path="ignored.pdf",
            pdf_url=None,
            market="CN",
            min_confidence=0.8,
        )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_extract_endpoint_accepts_cn_annual_sample_pdf() -> None:
    sample_pdf = _resolve_cn_annual_sample()
    if sample_pdf is None or not sample_pdf.exists():
        pytest.skip("CN annual sample PDF not found")

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(sample_pdf),
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["pdf_path"] == str(sample_pdf)
    assert payload["quality_gate"] in {"pass", "review"}
    assert payload["key_facts"]


@pytest.mark.parametrize(
    ("stock_code", "filename"),
    [
        ("600519", "2024_年度报告.pdf"),
        ("600519", "2025_年度报告.pdf"),
        ("601919", "2025_年度报告.pdf"),
        ("688008", "2024_年度报告.pdf"),
        ("688008", "2025_年度报告.pdf"),
    ],
)
@pytest.mark.real_pdf
@pytest.mark.slow
def test_extract_endpoint_accepts_cn_annual_reference_pdfs(
    stock_code: str,
    filename: str,
) -> None:
    sample_pdf = _resolve_sample_path(
        "report",
        "downloads",
        "cn_stocks",
        stock_code,
        "annual",
        filename,
    )
    if sample_pdf is None or not sample_pdf.exists():
        pytest.skip("CN annual reference sample PDF not found")

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(sample_pdf),
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["pdf_path"] == str(sample_pdf)
    assert payload["document"]["metadata"]["parsed_tables"]
    assert payload["quality_gate"] in {"pass", "review"}
    assert payload["key_facts"]


@pytest.mark.real_pdf
@pytest.mark.slow
def test_extract_endpoint_includes_parsed_tables_for_cn_sample() -> None:
    sample_pdf = _resolve_cn_annual_sample()
    if sample_pdf is None or not sample_pdf.exists():
        pytest.skip("CN annual sample PDF not found")

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(sample_pdf),
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["metadata"]["parsed_tables"]
    first_table = payload["document"]["metadata"]["parsed_tables"][0]
    assert first_table["table_kind"] in {
        "income_statement",
        "balance_sheet",
        "cash_flow_statement",
        "key_metrics",
    }
    assert first_table["table_id"]
    assert first_table["page_range"]


@pytest.mark.parametrize(
    ("stock_code", "filename"),
    [
        ("02498", "2022_annual_en.pdf"),
        ("06862", "2024_annual_en.pdf"),
        ("09987", "2024_annual_en.pdf"),
        ("09987", "2025_annual_en.pdf"),
    ],
)
@pytest.mark.real_pdf
@pytest.mark.slow
def test_extract_endpoint_accepts_hk_annual_anchor_pdfs(
    stock_code: str,
    filename: str,
) -> None:
    sample_pdf = _resolve_hk_annual_sample(stock_code, filename)
    if sample_pdf is None or not sample_pdf.exists():
        pytest.skip("HK annual sample PDF not found")

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(sample_pdf),
            "market": "HK",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["pdf_path"] == str(sample_pdf)
    assert payload["document"]["metadata"]["parsed_tables"]
    assert payload["quality_gate"] in {"pass", "review"}
    assert payload["document"]["metadata"]["parsed_tables"][0]["semantic_source"] in {
        "deterministic",
        "llm_fallback",
    }


def test_extract_endpoint_promotes_table_semantic_candidates_to_canonical_facts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )

    table = ParsedTable(
        table_id="doc:parsed-table:1",
        document_id="doc",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        statement_scope_guess="consolidated",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=1,
                label_raw="Revenue",
                normalized_label_hint="revenue",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=1,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [table],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "2023 Annual Report Revenue 9,999 RMB'000",
    )

    pdf_path = tmp_path / "table-mock.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

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
    assert payload["quality_gate"] == "pass"
    assert any(fact["metric_id"] == "revenue" for fact in payload["key_facts"])


def test_extract_endpoint_promotes_income_statement_core_metrics_to_key_facts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )

    table = ParsedTable(
        table_id="doc:parsed-table:income-core",
        document_id="doc",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        statement_scope_guess="consolidated",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-revenue",
                row_index=1,
                label_raw="Revenue",
                normalized_label_hint="revenue",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="1,234",
                        numeric_value=1234.0,
                        page_index=1,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-cost",
                row_index=2,
                label_raw="Cost of sales",
                normalized_label_hint="cost of sales",
                value_cells=[
                    ParsedCell(
                        row_index=2,
                        column_index=1,
                        text_raw="800",
                        numeric_value=800.0,
                        page_index=1,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-net-profit",
                row_index=3,
                label_raw="Profit attributable to equity holders",
                normalized_label_hint="profit attributable to equity holders",
                value_cells=[
                    ParsedCell(
                        row_index=3,
                        column_index=1,
                        text_raw="120",
                        numeric_value=120.0,
                        page_index=1,
                    )
                ],
            ),
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [table],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "2024 Annual Report Revenue 9,999 RMB'000",
    )

    pdf_path = tmp_path / "income-core.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

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
    assert payload["quality_gate"] == "pass"
    assert {fact["metric_id"] for fact in payload["key_facts"]} >= {
        "revenue",
        "operating_cost",
        "net_profit",
    }


def test_extract_endpoint_promotes_cash_flow_primary_sections_to_key_facts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )

    table = ParsedTable(
        table_id="doc:parsed-table:cash-flow-core",
        document_id="doc",
        page_range=(1, 1),
        table_kind="cash_flow_statement",
        title_text="Consolidated Statement of Cash Flows",
        statement_scope_guess="consolidated",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-operating",
                row_index=1,
                label_raw="Net cash generated from operating activities",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="500",
                        numeric_value=500.0,
                        page_index=1,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-investing",
                row_index=2,
                label_raw="Net cash from investing activities",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=2,
                        column_index=1,
                        text_raw="-200",
                        numeric_value=-200.0,
                        page_index=1,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-financing",
                row_index=3,
                label_raw="Net cash from financing activities",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=3,
                        column_index=1,
                        text_raw="-100",
                        numeric_value=-100.0,
                        page_index=1,
                    )
                ],
            ),
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [table],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "2024 Annual Report Cash flows 9,999 RMB'000",
    )

    pdf_path = tmp_path / "cash-flow-core.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

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
    assert payload["quality_gate"] == "pass"
    assert {fact["metric_id"] for fact in payload["key_facts"]} >= {
        "operating_cash_flow",
        "investing_cash_flow",
        "financing_cash_flow",
    }


def test_extract_endpoint_promotes_gross_profit_to_key_facts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )

    table = ParsedTable(
        table_id="doc:parsed-table:gross-profit",
        document_id="doc",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        statement_scope_guess="consolidated",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-gross-profit",
                row_index=1,
                label_raw="Gross profit for the period",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="456",
                        numeric_value=456.0,
                        page_index=1,
                    )
                ],
            ),
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="duration",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [table],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "2024 Annual Report Gross profit 456 HKD'000",
    )

    pdf_path = tmp_path / "gross-profit.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

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
    assert payload["quality_gate"] == "pass"
    assert {fact["metric_id"] for fact in payload["key_facts"]} == {"gross_profit"}


def test_extract_endpoint_promotes_equity_metrics_to_key_facts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
    from financial_report_analysis.ingestion.table_structure import (
        PdfTableStructureAdapter,
    )
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )

    table = ParsedTable(
        table_id="doc:parsed-table:equity",
        document_id="doc",
        page_range=(1, 1),
        table_kind="balance_sheet",
        title_text="Consolidated Statement of Financial Position",
        statement_scope_guess="consolidated",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-equity",
                row_index=1,
                label_raw="所有者权益合计",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="3,500",
                        numeric_value=3500.0,
                        page_index=1,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-attributable-equity",
                row_index=2,
                label_raw="归属于母公司所有者权益",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=2,
                        column_index=1,
                        text_raw="3,100",
                        numeric_value=3100.0,
                        page_index=1,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-equity-ratio",
                row_index=3,
                label_raw="权益比率",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=3,
                        column_index=1,
                        text_raw="43%",
                        numeric_value=43.0,
                        page_index=1,
                    )
                ],
            ),
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-1",
                column_index=1,
                header_text="2024",
                period_id="2024FY",
                value_time_shape="point",
                comparison_axis="current",
                is_current=True,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    monkeypatch.setattr(
        PdfTableStructureAdapter,
        "extract_tables",
        lambda self, **kwargs: [table],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text",
        lambda self, **kwargs: "2024 Annual Report HK$3,500 HK$'000",
    )

    pdf_path = tmp_path / "equity.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

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
    assert payload["quality_gate"] == "pass"
    assert {fact["metric_id"] for fact in payload["key_facts"]} == {
        "equity",
        "equity_attributable_to_owners",
    }
    assert all(fact["statement_type"] == "balance_sheet" for fact in payload["key_facts"])
    assert all(fact["entity_scope"] == "consolidated" for fact in payload["key_facts"])


@pytest.mark.real_pdf
@pytest.mark.slow
def test_extract_endpoint_accepts_cn_quarterly_sample_pdf() -> None:
    sample_pdf = _resolve_cn_quarterly_sample()
    if sample_pdf is None or not sample_pdf.exists():
        pytest.skip("CN quarterly sample PDF not found")

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(sample_pdf),
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["pdf_path"] == str(sample_pdf)
    assert payload["quality_gate"] in {"pass", "review"}
    assert payload["key_facts"]


@pytest.mark.real_pdf
@pytest.mark.slow
def test_extract_endpoint_marks_hk_non_english_input_as_unsupported_review() -> None:
    sample_pdf = _resolve_hk_non_english_sample()
    if not sample_pdf.exists():
        pytest.skip("HK non-English sample PDF not found")

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(sample_pdf),
            "market": "HK",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["quality_gate"] == "review"
    assert payload["blocked_items"] == [
        {
            "code": "unsupported_in_phase1",
            "status": "unsupported_in_phase1",
        }
    ]


def test_package_root_does_not_import_api_app_transitively() -> None:
    sys.modules.pop("financial_report_analysis", None)
    sys.modules.pop("financial_report_analysis.api", None)
    sys.modules.pop("financial_report_analysis.api.app", None)

    module = importlib.import_module("financial_report_analysis")

    assert "financial_report_analysis.api.app" not in sys.modules
    assert not hasattr(module, "create_app")
