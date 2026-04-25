from __future__ import annotations

import importlib
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from financial_report_analysis.api.app import create_app
from financial_report_analysis.ingestion import (
    PdfIngestionAdapter,
    PdfTableStructureAdapter,
    normalize_table_semantics,
)
from financial_report_analysis.models import (
    ParsedCell,
    ParsedColumn,
    ParsedRow,
    ParsedTable,
)
from financial_report_analysis.p5.metric_availability_report import (
    build_metric_availability_report,
)
from financial_report_analysis.p5.ollama_fallback_e2e import (
    selected_ollama_fallback_e2e_case,
)
from financial_report_analysis.pipeline import analyze_report
from financial_report_analysis.semantic_fallback import (
    SemanticFallbackSettings,
    build_semantic_fallback_service,
    load_semantic_fallback_settings,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
MAIN_REPO_ROOT = REPO_ROOT.parent.parent
_P4C_METRIC_IDS = {
    "revenue",
    "operating_cost",
    "operating_profit",
    "net_profit",
    "total_assets",
    "total_liabilities",
    "equity_attributable_to_owners",
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "c_pay_to_staff",
    "c_paid_for_taxes",
}

_P4D_PARENT_METRIC_IDS = {
    "cash",
    "lt_eqt_invest",
    "st_borr",
    "lt_borr",
    "bond_payable",
    "non_cur_liab_due_1y",
    "total_assets",
    "total_liabilities",
    "equity",
    "equity_attributable_to_owners",
}

_P4E_METRIC_IDS = {
    "fix_assets",
    "cip",
    "rd_exp",
    "invest_income",
    "asset_disp_income",
    "n_recp_disp_fiolta",
    "c_recp_return_invest",
}


def _resolve_sample(*relative_parts: str) -> Path:
    for root in (REPO_ROOT, MAIN_REPO_ROOT):
        candidate = root / "report" / "downloads" / Path(*relative_parts)
        if candidate.exists():
            return candidate
    raise AssertionError(f"Sample PDF not found for {relative_parts}")


def _candidate_labels_for_metric(
    payload: dict[str, object],
    metric_id: str,
) -> set[str]:
    return {
        str(candidate.get("metric_label_raw", "")).casefold()
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict) and str(candidate.get("metric_id")) == metric_id
    }


def _extract_payload_for_pdf(pdf_path: Path, *, market: str) -> dict[str, object]:
    return PdfIngestionAdapter().extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market=market,
        min_confidence=None,
    )


def _metric_ids_from_candidates(payload: dict[str, object]) -> set[str]:
    return {
        str(candidate.get("metric_id"))
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict) and candidate.get("metric_id") is not None
    }


def _candidate_facts_for_metric(
    payload: dict[str, object],
    metric_id: str,
) -> list[dict[str, object]]:
    return [
        candidate
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict) and str(candidate.get("metric_id")) == metric_id
    ]


def _deterministic_statement_row_candidates_for_metric(
    payload: dict[str, object],
    *,
    metric_id: str,
    statement_type: str,
    table_kind: str,
    entity_scope: str = "consolidated",
) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for candidate in _candidate_facts_for_metric(payload, metric_id):
        extensions = candidate.get("extensions")
        if not isinstance(extensions, dict):
            continue
        if candidate.get("extraction_method") != "table_semantics":
            continue
        if candidate.get("statement_type") != statement_type:
            continue
        if candidate.get("entity_scope") != entity_scope:
            continue
        if extensions.get("table_kind") != table_kind:
            continue
        if extensions.get("semantic_source") != "deterministic":
            continue
        matches.append(candidate)
    return matches


def _assert_deterministic_balance_sheet_candidates(
    payload: dict[str, object],
    *,
    metric_id: str,
    label_prefix: str,
    period_ids: set[str],
    statement_scope_guess: str,
) -> None:
    candidates_by_period: dict[str, dict[str, object]] = {}
    for candidate in _candidate_facts_for_metric(payload, metric_id):
        extensions = candidate.get("extensions")
        if not isinstance(extensions, dict):
            continue
        if candidate.get("extraction_method") != "table_semantics":
            continue
        if candidate.get("statement_type") != "balance_sheet":
            continue
        if extensions.get("table_kind") != "balance_sheet":
            continue
        if extensions.get("semantic_source") != "deterministic":
            continue
        if extensions.get("statement_scope_guess") != statement_scope_guess:
            continue
        label = str(candidate.get("metric_label_raw", "")).casefold()
        if not label.startswith(label_prefix.casefold()):
            continue
        period_id = str(candidate.get("period_id"))
        assert period_id not in candidates_by_period, metric_id
        candidates_by_period[period_id] = candidate

    assert set(candidates_by_period) == period_ids


def _ollama_model_available(*, base_url: str, model: str) -> bool:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=3.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return False
    payload = response.json()
    models = payload.get("models", [])
    return any(
        entry.get("name") == model for entry in models if isinstance(entry, dict)
    )


def _real_ollama_fallback_service():
    loaded = load_semantic_fallback_settings()
    if not _ollama_model_available(base_url=loaded.base_url, model=loaded.model):
        pytest.skip(f"local Ollama model is unavailable: {loaded.model}")
    return build_semantic_fallback_service(
        SemanticFallbackSettings(
            enabled=True,
            provider="ollama",
            base_url=loaded.base_url,
            model=loaded.model,
            timeout_seconds=loaded.timeout_seconds,
        )
    )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_09987_2025_annual_en_recovers_statement_and_note_facts() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")

    payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    metadata = payload["document_metadata"]
    candidates = [
        candidate
        for candidate in payload["candidate_facts"]
        if isinstance(candidate, dict)
    ]
    accounts_receiv_candidates = [
        candidate
        for candidate in candidates
        if candidate.get("metric_id") == "accounts_receiv"
    ]

    assert metadata["language"] == "en"
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="revenue",
        statement_type="income_statement",
        table_kind="income_statement",
    )
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="cash",
        statement_type="balance_sheet",
        table_kind="balance_sheet",
    )
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="total_assets",
        statement_type="balance_sheet",
        table_kind="balance_sheet",
    )
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="total_liabilities",
        statement_type="balance_sheet",
        table_kind="balance_sheet",
    )
    assert accounts_receiv_candidates
    assert any(
        candidate["numeric_value"] == 95.0
        and candidate["currency"] == "USD"
        and candidate["raw_unit"] == "US$ millions"
        for candidate in accounts_receiv_candidates
    )
    assert all(
        candidate["numeric_value"] != 2025.0
        for candidate in accounts_receiv_candidates
    )
    assert len({candidate["fact_id"] for candidate in candidates}) == len(candidates)


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_annual_semantics_preserve_statement_scope_and_ambiguity() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="HK",
    )

    balance_sheet = next(
        table for table in tables if table.table_kind == "balance_sheet"
    )
    semantics = normalize_table_semantics(balance_sheet)

    assert semantics.statement_scope_guess == "consolidated"
    assert semantics.semantic_source == "deterministic"
    assert semantics.semantic_ambiguity_reason in {None, "numeric_only_statement_block"}


@pytest.mark.real_pdf
@pytest.mark.slow
def test_cn_annual_semantics_expose_normalized_row_labels() -> None:
    pdf_path = _resolve_sample("cn_stocks", "601919", "annual", "2024_年度报告.pdf")
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="CN",
    )

    income_statement = next(
        table for table in tables if table.table_kind == "income_statement"
    )
    semantics = normalize_table_semantics(income_statement)

    assert any(row.normalized_row_label for row in semantics.rows)


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
def test_cn_annual_reference_semantics_preserve_deterministic_provenance(
    stock_code: str,
    filename: str,
) -> None:
    pdf_path = _resolve_sample("cn_stocks", stock_code, "annual", filename)
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="CN",
    )

    income_statement = next(
        table for table in tables if table.table_kind == "income_statement"
    )
    semantics = normalize_table_semantics(income_statement)

    assert semantics.semantic_source == "deterministic"
    assert any(row.normalized_row_label for row in semantics.rows)
    assert semantics.unit_semantic_source == "deterministic"
    assert semantics.currency_semantic_source == "deterministic"


@pytest.mark.real_pdf
@pytest.mark.slow
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


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_q3_anchor_preserves_semantic_provenance_in_parsed_tables() -> None:
    pdf_path = _resolve_sample(
        "hk_stocks", "09987", "quarterly", "2025_quarterly_q3_en.pdf"
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


@pytest.mark.real_pdf
@pytest.mark.ollama
@pytest.mark.external
@pytest.mark.slow
def test_hk_09987_q3_real_pdf_keeps_row_label_fallback_bounded() -> None:
    pdf_path = _resolve_sample(
        "hk_stocks",
        "09987",
        "quarterly",
        "2025_quarterly_q3_en.pdf",
    )
    fallback_service = _real_ollama_fallback_service()

    ingestion_payload = PdfIngestionAdapter(
        semantic_fallback_service=fallback_service,
    ).extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    counts = ingestion_payload["document_metadata"]["semantic_fallback_call_counts"]
    assert counts["row_label"] <= 20
    assert (
        ingestion_payload["document_metadata"]["semantic_fallback_budget_exhausted"]
        is False
    )
    assert len(ingestion_payload["candidate_facts"]) >= 1


@pytest.mark.real_pdf
@pytest.mark.ollama
@pytest.mark.external
@pytest.mark.slow
def test_ollama_fallback_e2e_supports_replaceable_real_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = selected_ollama_fallback_e2e_case()
    pdf_path = _resolve_sample(*case.relative_pdf_parts)
    monkeypatch.setenv("FRA_SEMANTIC_FALLBACK_ENABLED", "true")

    fallback_service = _real_ollama_fallback_service()
    ingestion_payload = PdfIngestionAdapter(
        semantic_fallback_service=fallback_service,
    ).extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market=case.market,
        min_confidence=0.8,
    )

    metadata = ingestion_payload["document_metadata"]
    counts = metadata["semantic_fallback_call_counts"]
    assert metadata["semantic_fallback_enabled"] is True
    assert sum(counts.values()) > 0
    assert len(ingestion_payload["candidate_facts"]) >= 1

    expected_metric_ids = (
        case.expected_metric_ids or case.expected_fallback_metric_ids
    )
    if expected_metric_ids:
        availability = build_metric_availability_report(
            payload=ingestion_payload,
            expected_metric_ids=expected_metric_ids,
            metric_profile="ollama_fallback_e2e",
            pdf_path=str(pdf_path),
            market=case.market,
        )
        metrics = {metric.metric_id: metric for metric in availability.metrics}
        missing = [
            metric_id
            for metric_id in expected_metric_ids
            if metrics[metric_id].status != "present"
        ]
        assert not missing, f"missing expected metrics: {missing}"

        fallback_missing = [
            metric_id
            for metric_id in case.expected_fallback_metric_ids
            if not metrics[metric_id].recovered_by_fallback
        ]
        assert not fallback_missing, (
            "expected fallback-recovered metrics were not recovered by fallback: "
            f"{fallback_missing}"
        )


@pytest.mark.real_pdf
@pytest.mark.slow
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


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_annual_2025_anchor_preserves_deterministic_unit_currency_provenance() -> (
    None
):
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")
    ingestion_payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    parsed_tables = ingestion_payload["document_metadata"]["parsed_tables"]
    assert parsed_tables
    assert any(
        table.get("unit_semantic_source") == "deterministic"
        and table.get("currency_semantic_source") == "deterministic"
        for table in parsed_tables
    )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_annual_2025_anchor_preserves_deterministic_semantic_coverage() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="HK",
    )

    assert {table.table_kind for table in tables} >= {
        "income_statement",
        "balance_sheet",
        "cash_flow_statement",
    }

    semantics_tables = [normalize_table_semantics(table) for table in tables]
    assert semantics_tables
    assert all(table.semantic_source == "deterministic" for table in semantics_tables)
    assert all(
        table.unit_semantic_source == "deterministic" for table in semantics_tables
    )
    assert all(
        table.currency_semantic_source == "deterministic" for table in semantics_tables
    )
    assert all(
        table.table_currency in {"HKD", "USD", "unknown"} for table in semantics_tables
    )


def test_pipeline_prefers_main_statement_provenance_when_source_ranks_tie(
    monkeypatch,
    tmp_path,
) -> None:
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )

    table_fact_builder = importlib.import_module(
        "financial_report_analysis.services.table_fact_builder"
    )
    monkeypatch.setattr(table_fact_builder, "_source_rank_hint", lambda table_kind: 10)

    income_statement = ParsedTable(
        table_id="doc:parsed-table:income",
        document_id="doc",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        statement_scope_guess="consolidated",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-income-revenue",
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
                column_id="column-income",
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
    metrics_table = ParsedTable(
        table_id="doc:parsed-table:metrics",
        document_id="doc",
        page_range=(2, 2),
        table_kind="metrics",
        title_text="Key Financial Metrics",
        statement_scope_guess="consolidated",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-metrics-revenue",
                row_index=1,
                label_raw="Revenue",
                normalized_label_hint="revenue",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="9,999",
                        numeric_value=9999.0,
                        page_index=2,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-metrics-growth",
                row_index=2,
                label_raw="Revenue growth",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=2,
                        column_index=1,
                        text_raw="18.5",
                        numeric_value=18.5,
                        page_index=2,
                    )
                ],
            ),
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-metrics",
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
    secondary_table = ParsedTable(
        table_id="doc:parsed-table:secondary",
        document_id="doc",
        page_range=(3, 3),
        table_kind="key_metrics",
        title_text="Key Financial Summary",
        statement_scope_guess="consolidated",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-secondary-summary",
                row_index=1,
                label_raw="Operating profit margin",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="12.0",
                        numeric_value=12.0,
                        page_index=3,
                    )
                ],
            )
        ],
        table_unit="thousand",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-secondary",
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
        lambda self, **kwargs: [metrics_table, secondary_table, income_statement],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text_pages",
        lambda self, **kwargs: [],
    )
    pdf_path = tmp_path / "ignored.pdf"
    pdf_path.touch()

    payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )
    result = analyze_report(
        {
            "document_id": str(pdf_path),
            "pdf_path": str(pdf_path),
            "pdf_url": None,
            "market": "HK",
            "language": payload["document_metadata"]["language"],
            "metadata": payload["document_metadata"],
        },
        payload,
    )

    revenue_candidates = [
        fact for fact in payload["candidate_facts"] if fact["metric_id"] == "revenue"
    ]
    assert len(revenue_candidates) == 2
    assert all(
        fact["extensions"]["table_kind"] in {"income_statement", "metrics"}
        for fact in revenue_candidates
    )
    assert all(
        "growth" not in fact["metric_label_raw"].lower()
        for fact in payload["candidate_facts"]
    )

    assert len(result.canonical_facts) == 1
    canonical = result.canonical_facts[0]
    assert canonical.metric_id == "revenue"
    assert canonical.numeric_value == 1_234_000.0
    assert canonical.extensions["table_kind"] == "income_statement"
    assert canonical.extensions["semantic_source"] == "deterministic"


def test_phase1_investor_inputs_survive_mocked_statement_pipeline_without_noise(
    monkeypatch,
    tmp_path,
) -> None:
    from financial_report_analysis.models import (
        ParsedCell,
        ParsedColumn,
        ParsedRow,
        ParsedTable,
    )

    income_statement = ParsedTable(
        table_id="doc:parsed-table:income",
        document_id="doc",
        page_range=(1, 1),
        table_kind="income_statement",
        title_text="Consolidated Income Statement",
        statement_scope_guess="consolidated",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-net-income-attr",
                row_index=1,
                label_raw="Profit attributable to owners of the parent",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="123",
                        numeric_value=123.0,
                        page_index=1,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-basic-eps",
                row_index=2,
                label_raw="Basic EPS",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=2,
                        column_index=1,
                        text_raw="1.23",
                        numeric_value=1.23,
                        page_index=1,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-diluted-eps",
                row_index=3,
                label_raw="Diluted EPS",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=3,
                        column_index=1,
                        text_raw="1.11",
                        numeric_value=1.11,
                        page_index=1,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-non-gaap-eps",
                row_index=4,
                label_raw="Non-GAAP earnings per share",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=4,
                        column_index=1,
                        text_raw="1.88",
                        numeric_value=1.88,
                        page_index=1,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-finance-exp",
                row_index=5,
                label_raw="Finance costs",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=5,
                        column_index=1,
                        text_raw="45",
                        numeric_value=45.0,
                        page_index=1,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-total-profit",
                row_index=6,
                label_raw="Profit before tax",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=6,
                        column_index=1,
                        text_raw="200",
                        numeric_value=200.0,
                        page_index=1,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-income-tax",
                row_index=7,
                label_raw="Income tax expense",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=7,
                        column_index=1,
                        text_raw="30",
                        numeric_value=30.0,
                        page_index=1,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-minority-gain",
                row_index=8,
                label_raw="Profit attributable to non-controlling interests",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=8,
                        column_index=1,
                        text_raw="5",
                        numeric_value=5.0,
                        page_index=1,
                    )
                ],
            ),
        ],
        table_unit="million",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-income",
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
    cash_flow_statement = ParsedTable(
        table_id="doc:parsed-table:cashflow",
        document_id="doc",
        page_range=(2, 2),
        table_kind="cash_flow_statement",
        title_text="Consolidated Cash Flow Statement",
        statement_scope_guess="consolidated",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-capex",
                row_index=1,
                label_raw="Payments for acquisition and construction of long-term assets",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="80",
                        numeric_value=80.0,
                        page_index=2,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-depr",
                row_index=2,
                label_raw=(
                    "Depreciation of fixed assets oil and gas assets and "
                    "productive biological assets"
                ),
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=2,
                        column_index=1,
                        text_raw="20",
                        numeric_value=20.0,
                        page_index=2,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-amort-intang",
                row_index=3,
                label_raw="Amortization of intangible assets",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=3,
                        column_index=1,
                        text_raw="5",
                        numeric_value=5.0,
                        page_index=2,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-amort-lt-deferred",
                row_index=4,
                label_raw="Amortization of long-term deferred expenses",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=4,
                        column_index=1,
                        text_raw="2",
                        numeric_value=2.0,
                        page_index=2,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-dividends-paid",
                row_index=5,
                label_raw="Cash paid for distribution of dividends or profits and interest expenses",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=5,
                        column_index=1,
                        text_raw="12",
                        numeric_value=12.0,
                        page_index=2,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-narrative-cfo",
                row_index=6,
                label_raw="Cash flows before changes in working capital",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=6,
                        column_index=1,
                        text_raw="999",
                        numeric_value=999.0,
                        page_index=2,
                    )
                ],
            ),
        ],
        table_unit="million",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-cashflow",
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
    key_metrics = ParsedTable(
        table_id="doc:parsed-table:key-metrics",
        document_id="doc",
        page_range=(3, 3),
        table_kind="key_metrics",
        title_text="Financial Highlights",
        statement_scope_guess="unknown",
        header_rows=[["Item", "2024"]],
        body_rows=[
            ParsedRow(
                row_id="row-revenue-growth",
                row_index=1,
                label_raw="Revenue growth",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="12.3%",
                        numeric_value=12.3,
                        page_index=3,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-operating-profit-margin",
                row_index=2,
                label_raw="Operating profit margin",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=2,
                        column_index=1,
                        text_raw="8.8%",
                        numeric_value=8.8,
                        page_index=3,
                    )
                ],
            ),
            ParsedRow(
                row_id="row-adjusted-eps",
                row_index=3,
                label_raw="Adjusted EPS",
                normalized_label_hint=None,
                value_cells=[
                    ParsedCell(
                        row_index=3,
                        column_index=1,
                        text_raw="2.22",
                        numeric_value=2.22,
                        page_index=3,
                    )
                ],
            ),
        ],
        table_unit="million",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-key-metrics",
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
        lambda self, **kwargs: [income_statement, cash_flow_statement, key_metrics],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text_pages",
        lambda self, **kwargs: [],
    )
    pdf_path = tmp_path / "ignored.pdf"
    pdf_path.touch()

    payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )
    candidate_metric_ids = {
        fact["metric_id"]
        for fact in payload["candidate_facts"]
        if fact.get("extraction_method") == "table_semantics"
    }
    assert {
        "n_income_attr_p",
        "basic_eps",
        "finance_exp",
        "total_profit",
        "income_tax",
        "minority_gain",
        "c_pay_acq_const_fiolta",
        "depr_fa_coga_dpba",
        "amort_intang_assets",
        "lt_amort_deferred_exp",
        "c_pay_dist_dpcp_int_exp",
    } <= candidate_metric_ids
    assert all(
        fact["metric_label_raw"]
        not in {
            "Diluted EPS",
            "Non-GAAP earnings per share",
            "Revenue growth",
            "Operating profit margin",
            "Adjusted EPS",
            "Cash flows before changes in working capital",
        }
        for fact in payload["candidate_facts"]
    )

    result = analyze_report(
        {
            "document_id": str(pdf_path),
            "pdf_path": str(pdf_path),
            "pdf_url": None,
            "market": "HK",
            "language": payload["document_metadata"]["language"],
            "metadata": payload["document_metadata"],
        },
        payload,
    )

    canonical_metric_ids = {fact.metric_id for fact in result.canonical_facts}
    assert {
        "n_income_attr_p",
        "basic_eps",
        "finance_exp",
        "total_profit",
        "income_tax",
        "minority_gain",
    } <= canonical_metric_ids
    basic_eps = next(
        fact for fact in result.canonical_facts if fact.metric_id == "basic_eps"
    )
    assert basic_eps.normalized_unit == "per_share_amount"
    assert basic_eps.extensions["value_type"] == "per_share"
    assert all(
        fact.metric_label_raw
        not in {
            "Diluted EPS",
            "Non-GAAP earnings per share",
            "Revenue growth",
            "Operating profit margin",
            "Adjusted EPS",
            "Cash flows before changes in working capital",
        }
        for fact in result.canonical_facts
    )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_cn_annual_601919_2025_surfaces_phase1_real_pdf_floor() -> None:
    pdf_path = _resolve_sample("cn_stocks", "601919", "annual", "2025_年度报告.pdf")

    payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="CN",
        min_confidence=0.8,
    )

    candidate_metric_ids = {
        fact["metric_id"]
        for fact in payload["candidate_facts"]
        if fact.get("extraction_method") == "table_semantics"
    }
    assert {"basic_eps", "finance_exp"} <= candidate_metric_ids

    result = analyze_report(
        {
            "document_id": str(pdf_path),
            "pdf_path": str(pdf_path),
            "pdf_url": None,
            "market": "CN",
            "language": payload["document_metadata"]["language"],
            "metadata": payload["document_metadata"],
        },
        payload,
    )

    canonical_metric_ids = {fact.metric_id for fact in result.canonical_facts}
    assert {"basic_eps", "finance_exp"} <= canonical_metric_ids
    basic_eps = next(
        fact for fact in result.canonical_facts if fact.metric_id == "basic_eps"
    )
    assert basic_eps.normalized_unit == "per_share_amount"
    assert basic_eps.extensions["value_type"] == "per_share"


@pytest.mark.real_pdf
@pytest.mark.slow
def test_cn_601919_2025_surfaces_p2a_working_capital_candidates() -> None:
    pdf_path = _resolve_sample("cn_stocks", "601919", "annual", "2025_年度报告.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="CN")

    for metric_id, label_prefix in (
        ("accounts_receiv", "应收账款"),
        ("notes_receiv", "应收票据"),
        ("oth_receiv", "其他应收款"),
        ("acct_payable", "应付账款"),
        ("notes_payable", "应付票据"),
    ):
        _assert_deterministic_balance_sheet_candidates(
            payload,
            metric_id=metric_id,
            label_prefix=label_prefix,
            period_ids={"2024FY", "2025FY"},
            statement_scope_guess="consolidated",
        )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_02498_2022_surfaces_p2a_statement_row_candidates() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")

    for metric_id, label_prefix, period_ids in (
        ("accounts_receiv", "accounts receivable", {"2021FY", "2022FY"}),
        ("notes_receiv", "notes receivable", {"2021FY", "2022FY"}),
        ("oth_receiv", "other receivables", {"2021FY", "2022FY"}),
        ("contract_liab", "contract liabilities", {"2021FY", "2022FY"}),
        ("adv_receipts", "payments received in advance", {"2022FY"}),
        ("acct_payable", "accounts payable", {"2021FY", "2022FY"}),
        ("notes_payable", "notes payable", {"2021FY", "2022FY"}),
    ):
        _assert_deterministic_balance_sheet_candidates(
            payload,
            metric_id=metric_id,
            label_prefix=label_prefix,
            period_ids=period_ids,
            statement_scope_guess="consolidated",
        )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_cn_601919_2025_surfaces_p2b_debt_candidates() -> None:
    pdf_path = _resolve_sample("cn_stocks", "601919", "annual", "2025_年度报告.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="CN")

    for metric_id, label_prefix, period_ids in (
        ("st_borr", "\u77ed\u671f\u501f\u6b3e", {"2024FY", "2025FY"}),
        ("lt_borr", "\u957f\u671f\u501f\u6b3e", {"2024FY", "2025FY"}),
        (
            "non_cur_liab_due_1y",
            "\u4e00\u5e74\u5185\u5230\u671f\u7684\u975e\u6d41\u52a8\u8d1f\u503a",
            {"2024FY", "2025FY"},
        ),
    ):
        _assert_deterministic_balance_sheet_candidates(
            payload,
            metric_id=metric_id,
            label_prefix=label_prefix,
            period_ids=period_ids,
            statement_scope_guess="consolidated",
        )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_02498_2022_surfaces_p2b_statement_row_debt_candidates() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")

    for metric_id, label_prefix, period_ids in (
        ("st_borr", "short-term borrowings", {"2021FY", "2022FY"}),
        ("lt_borr", "long-term borrowings", {"2021FY", "2022FY"}),
    ):
        _assert_deterministic_balance_sheet_candidates(
            payload,
            metric_id=metric_id,
            label_prefix=label_prefix,
            period_ids=period_ids,
            statement_scope_guess="consolidated",
        )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_02498_2022_does_not_promote_p2b_negative_control_rows() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")

    for metric_id in ("st_borr", "lt_borr"):
        candidate_labels = _candidate_labels_for_metric(payload, metric_id)
        assert candidate_labels, metric_id
        assert "lease liabilities" not in candidate_labels
        assert "accounts payable" not in candidate_labels
        assert "contract liabilities" not in candidate_labels


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_02498_2022_does_not_promote_p2a_negative_control_rows() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")

    for metric_id, forbidden_label in (
        ("accounts_receiv", "accounts receivable financing"),
        ("oth_receiv", "long-term receivables"),
        ("notes_payable", "bonds payable"),
    ):
        candidate_labels = _candidate_labels_for_metric(payload, metric_id)
        assert candidate_labels, metric_id
        assert forbidden_label not in candidate_labels


@pytest.mark.real_pdf
@pytest.mark.slow
def test_cn_601919_2025_surfaces_p3_asset_quality_candidates() -> None:
    pdf_path = _resolve_sample("cn_stocks", "601919", "annual", "2025_年度报告.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="CN")

    for metric_id, label_prefix in (
        ("cash", "货币资金"),
        ("trad_asset", "交易性金融资产"),
        ("inventories", "存货"),
        ("goodwill", "商誉"),
        ("intang_assets", "无形资产"),
    ):
        _assert_deterministic_balance_sheet_candidates(
            payload,
            metric_id=metric_id,
            label_prefix=label_prefix,
            period_ids={"2024FY", "2025FY"},
            statement_scope_guess="consolidated",
        )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_02498_2022_surfaces_p3_statement_row_asset_candidates() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")

    for metric_id, label_prefix, period_ids in (
        ("inventories", "inventories", {"2021FY", "2022FY"}),
        ("goodwill", "goodwill", {"2022FY"}),
        ("intang_assets", "intangible assets", {"2021FY", "2022FY"}),
    ):
        _assert_deterministic_balance_sheet_candidates(
            payload,
            metric_id=metric_id,
            label_prefix=label_prefix,
            period_ids=period_ids,
            statement_scope_guess="consolidated",
        )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_02498_2022_does_not_promote_p3_asset_negative_control_rows() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    all_candidate_labels = {
        str(candidate.get("metric_label_raw", "")).casefold()
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict)
    }

    for metric_id in ("inventories", "goodwill", "intang_assets"):
        assert _candidate_labels_for_metric(payload, metric_id), metric_id

    assert all_candidate_labels.isdisjoint(
        {
            "restricted cash",
            "assets held for sale",
            "investment properties",
            "prepayments",
            "right-of-use assets",
            "deferred tax assets",
            "capitalized development costs",
            "total non-current assets",
            "contract assets",
            "other non-current assets",
        }
    )

    assert not _candidate_labels_for_metric(payload, "cash")
    assert not _candidate_labels_for_metric(payload, "trad_asset")


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_09987_2025_surfaces_p2a_note_disclosure_candidates_without_hallucination() -> (
    None
):
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    metric_ids = _metric_ids_from_candidates(payload)

    assert {"accounts_receiv", "acct_payable", "contract_liab"}.issubset(metric_ids)
    assert "notes_receiv" not in metric_ids
    assert "notes_payable" not in metric_ids
    missing_status = payload.get("document_metadata", {}).get(
        "working_capital_missing_status",
        {},
    )
    assert missing_status["notes_receiv"] == "absent"
    assert missing_status["notes_payable"] == "absent"
    assert missing_status["adv_receipts"] == "not_surfaced"


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_09987_2025_note_disclosure_candidates_keep_note_provenance() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    p2a_candidates = [
        candidate
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict)
        and candidate.get("metric_id")
        in {"accounts_receiv", "acct_payable", "contract_liab"}
    ]

    assert p2a_candidates
    assert any(
        candidate.get("extraction_method") == "note_disclosure"
        for candidate in p2a_candidates
    )
    assert all(
        candidate.get("extensions", {}).get("semantic_source")
        in {"deterministic", "llm_fallback"}
        for candidate in p2a_candidates
    )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_09987_2025_surfaces_only_missing_p2b_note_disclosure_candidates() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    debt_metric_ids = {
        "st_borr",
        "lt_borr",
        "bond_payable",
        "non_cur_liab_due_1y",
    }
    debt_candidates = [
        candidate
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict)
        and candidate.get("metric_id") in debt_metric_ids
    ]

    assert debt_candidates
    assert {candidate["metric_id"] for candidate in debt_candidates} == {"st_borr"}
    assert len(debt_candidates) == 1
    candidate = debt_candidates[0]
    assert candidate["metric_label_raw"].casefold().startswith("short-term borrowings")
    assert candidate["extraction_method"] == "note_disclosure"
    assert candidate["extensions"]["table_kind"] == "note_disclosure"
    assert candidate["extensions"]["semantic_source"] in {
        "deterministic",
        "llm_fallback",
    }
    missing_status = payload.get("document_metadata", {}).get("debt_missing_status", {})
    assert missing_status == {
        "st_borr": "present",
        "lt_borr": "absent",
        "bond_payable": "absent",
        "non_cur_liab_due_1y": "absent",
    }


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_09987_2025_surfaces_only_missing_p3_note_only_asset_candidates() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    asset_metric_ids = {"contract_assets", "other_non_current_assets"}
    asset_candidates = [
        candidate
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict)
        and candidate.get("metric_id") in asset_metric_ids
    ]

    assert asset_candidates == []
    assert payload.get("document_metadata", {}).get("asset_missing_status") == {
        "contract_assets": "not_surfaced",
        "other_non_current_assets": "not_surfaced",
    }


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_02498_2022_keeps_p4b_cash_health_absent() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    assert not _candidate_facts_for_metric(payload, "restricted_cash")
    assert not _candidate_facts_for_metric(payload, "interest_paid_cash")
    assert not _candidate_facts_for_metric(payload, "time_deposits_or_wealth_products")
    assert payload.get("document_metadata", {}).get("cash_health_missing_status") == {
        "restricted_cash": "absent",
        "interest_paid_cash": "absent",
        "time_deposits_or_wealth_products": "absent",
    }


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_09987_2025_surfaces_p4b_cash_health_candidates() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    metric_ids = _metric_ids_from_candidates(payload)

    assert {
        "restricted_cash",
        "interest_paid_cash",
        "time_deposits_or_wealth_products",
    }.issubset(metric_ids)
    assert payload.get("document_metadata", {}).get("cash_health_missing_status") == {
        "restricted_cash": "present",
        "interest_paid_cash": "present",
        "time_deposits_or_wealth_products": "present",
    }


@pytest.mark.real_pdf
@pytest.mark.slow
def test_cn_601919_2025_keeps_p4b_cash_health_as_not_surfaced() -> None:
    pdf_path = _resolve_sample("cn_stocks", "601919", "annual", "2025_年度报告.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="CN")

    assert not _candidate_facts_for_metric(payload, "restricted_cash")
    assert not _candidate_facts_for_metric(payload, "interest_paid_cash")
    assert not _candidate_facts_for_metric(payload, "time_deposits_or_wealth_products")
    assert payload.get("document_metadata", {}).get("cash_health_missing_status") == {
        "restricted_cash": "not_surfaced",
        "interest_paid_cash": "not_surfaced",
        "time_deposits_or_wealth_products": "not_surfaced",
    }


@pytest.mark.real_pdf
@pytest.mark.slow
def test_cn_601919_2025_surfaces_p4c_core_statement_subset() -> None:
    pdf_path = _resolve_sample("cn_stocks", "601919", "annual", "2025_年度报告.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="CN")
    metric_ids = _metric_ids_from_candidates(payload)

    assert {
        "revenue",
        "total_assets",
        "total_liabilities",
        "operating_cash_flow",
        "c_paid_for_taxes",
    }.issubset(metric_ids)
    assert metric_ids.intersection(_P4C_METRIC_IDS) == {
        "revenue",
        "total_assets",
        "total_liabilities",
        "operating_cash_flow",
        "c_paid_for_taxes",
        "investing_cash_flow",
        "financing_cash_flow",
    }
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="revenue",
        statement_type="income_statement",
        table_kind="income_statement",
    )
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="total_assets",
        statement_type="balance_sheet",
        table_kind="balance_sheet",
    )
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="total_liabilities",
        statement_type="balance_sheet",
        table_kind="balance_sheet",
    )
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="operating_cash_flow",
        statement_type="cash_flow_statement",
        table_kind="cash_flow_statement",
    )
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="c_paid_for_taxes",
        statement_type="cash_flow_statement",
        table_kind="cash_flow_statement",
    )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_02498_2022_surfaces_only_p4c_balance_sheet_totals() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    metric_ids = _metric_ids_from_candidates(payload)

    assert metric_ids.intersection(_P4C_METRIC_IDS) == {
        "total_assets",
        "total_liabilities",
    }
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="total_assets",
        statement_type="balance_sheet",
        table_kind="balance_sheet",
    )
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="total_liabilities",
        statement_type="balance_sheet",
        table_kind="balance_sheet",
    )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_09987_2025_keeps_p4c_statement_metrics_not_surfaced() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")

    surfaced_metric_ids = {
        str(candidate.get("metric_id"))
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict)
        and candidate.get("extraction_method") == "table_semantics"
        and candidate.get("entity_scope") == "consolidated"
        and isinstance(candidate.get("extensions"), dict)
        and candidate["extensions"].get("table_kind")
        in {"income_statement", "balance_sheet", "cash_flow_statement"}
        and candidate["extensions"].get("semantic_source") == "deterministic"
    }

    assert not surfaced_metric_ids.intersection(_P4C_METRIC_IDS)


@pytest.mark.real_pdf
@pytest.mark.slow
def test_cn_601919_2025_surfaces_p4d_parent_statement_subset() -> None:
    pdf_path = _resolve_sample("cn_stocks", "601919", "annual", "2025_年度报告.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="CN")
    parent_metric_ids = {
        str(candidate.get("metric_id"))
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict) and candidate.get("entity_scope") == "parent_company"
    }

    assert {"cash", "lt_eqt_invest", "total_assets"}.issubset(parent_metric_ids)
    assert parent_metric_ids.intersection(_P4D_PARENT_METRIC_IDS) == {
        "cash",
        "lt_eqt_invest",
        "total_assets",
    }
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="cash",
        statement_type="balance_sheet",
        table_kind="balance_sheet",
        entity_scope="parent_company",
    )
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="lt_eqt_invest",
        statement_type="balance_sheet",
        table_kind="balance_sheet",
        entity_scope="parent_company",
    )
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="total_assets",
        statement_type="balance_sheet",
        table_kind="balance_sheet",
        entity_scope="parent_company",
    )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_02498_2022_keeps_p4d_parent_metrics_out_of_scope() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    parent_metric_ids = {
        str(candidate.get("metric_id"))
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict) and candidate.get("entity_scope") == "parent_company"
    }

    assert not parent_metric_ids.intersection(_P4D_PARENT_METRIC_IDS)
    assert payload.get("document_metadata", {}).get("cash_health_missing_status") == {
        "restricted_cash": "absent",
        "interest_paid_cash": "absent",
        "time_deposits_or_wealth_products": "absent",
    }


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_09987_2025_keeps_p4d_parent_metrics_not_surfaced() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    parent_metric_ids = {
        str(candidate.get("metric_id"))
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict) and candidate.get("entity_scope") == "parent_company"
    }

    assert not parent_metric_ids.intersection(_P4D_PARENT_METRIC_IDS)
    assert {
        "restricted_cash",
        "interest_paid_cash",
        "time_deposits_or_wealth_products",
    }.issubset(_metric_ids_from_candidates(payload))


@pytest.mark.real_pdf
@pytest.mark.slow
def test_cn_601919_2025_surfaces_p4e_core_subset() -> None:
    pdf_path = _resolve_sample("cn_stocks", "601919", "annual", "2025_年度报告.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="CN")
    metric_ids = _metric_ids_from_candidates(payload)

    assert {"fix_assets", "cip", "rd_exp", "c_recp_return_invest"}.issubset(metric_ids)
    assert metric_ids.intersection(_P4E_METRIC_IDS) == {
        "fix_assets",
        "cip",
        "rd_exp",
        "c_recp_return_invest",
    }
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="fix_assets",
        statement_type="balance_sheet",
        table_kind="balance_sheet",
    )
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="cip",
        statement_type="balance_sheet",
        table_kind="balance_sheet",
    )
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="rd_exp",
        statement_type="income_statement",
        table_kind="income_statement",
    )
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="c_recp_return_invest",
        statement_type="cash_flow_statement",
        table_kind="cash_flow_statement",
    )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_02498_2022_surfaces_p4e_balance_sheet_subset() -> None:
    pdf_path = _resolve_sample("hk_stocks", "02498", "annual", "2022_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    metric_ids = _metric_ids_from_candidates(payload)

    assert metric_ids.intersection(_P4E_METRIC_IDS) == {"fix_assets", "cip"}
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="fix_assets",
        statement_type="balance_sheet",
        table_kind="balance_sheet",
    )
    assert _deterministic_statement_row_candidates_for_metric(
        payload,
        metric_id="cip",
        statement_type="balance_sheet",
        table_kind="balance_sheet",
    )


@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_09987_2025_keeps_p4e_metrics_not_surfaced() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    surfaced_metric_ids = {
        str(candidate.get("metric_id"))
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict)
        and candidate.get("extraction_method") == "table_semantics"
        and candidate.get("entity_scope") == "consolidated"
        and isinstance(candidate.get("extensions"), dict)
        and candidate["extensions"].get("table_kind")
        in {"income_statement", "balance_sheet", "cash_flow_statement"}
        and candidate["extensions"].get("semantic_source") == "deterministic"
    }

    assert not surfaced_metric_ids.intersection(_P4E_METRIC_IDS)


def test_hk_09987_debt_note_disclosure_supplement_preserves_statement_row_precedence(
    monkeypatch,
    tmp_path,
) -> None:
    debt_statement = ParsedTable(
        table_id="doc:parsed-table:balance-sheet",
        document_id="doc",
        page_range=(42, 42),
        table_kind="balance_sheet",
        title_text="Consolidated Statement of Financial Position",
        statement_scope_guess="consolidated",
        header_rows=[["Item", "2025"]],
        body_rows=[
            ParsedRow(
                row_id="row-st-borr",
                row_index=1,
                label_raw="Short-term borrowings",
                normalized_label_hint="short-term borrowings",
                value_cells=[
                    ParsedCell(
                        row_index=1,
                        column_index=1,
                        text_raw="500",
                        numeric_value=500.0,
                        page_index=42,
                    )
                ],
            )
        ],
        table_unit="million",
        table_currency="HKD",
        period_columns=[
            ParsedColumn(
                column_id="column-current",
                column_index=1,
                header_text="2025",
                period_id="2025FY",
                value_time_shape="point_in_time",
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
        lambda self, **kwargs: [debt_statement],
    )
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "_extract_text_pages",
        lambda self, **kwargs: [
            (153, "Note 9 - Credit Facilities and Short-term Borrowings"),
            (
                154,
                "\n".join(
                    [
                        (
                            "As of December 31, 2025 and 2024, we had outstanding "
                            "short-term bank borrowings of $127 million and $168 "
                            "million, respectively."
                        ),
                        "Long-term borrowings 560 600",
                    ]
                ),
            ),
        ],
    )

    pdf_path = tmp_path / "09987-annual.pdf"
    pdf_path.touch()

    payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="HK",
        min_confidence=None,
    )

    st_borr_candidates = _candidate_facts_for_metric(payload, "st_borr")
    lt_borr_candidates = _candidate_facts_for_metric(payload, "lt_borr")

    assert len(st_borr_candidates) == 1
    assert st_borr_candidates[0]["extraction_method"] == "table_semantics"
    assert st_borr_candidates[0]["numeric_value"] == 500.0
    assert all(
        candidate["extraction_method"] != "note_disclosure"
        for candidate in st_borr_candidates
    )
    assert len(lt_borr_candidates) == 1
    assert lt_borr_candidates[0]["extraction_method"] == "note_disclosure"
    assert lt_borr_candidates[0]["numeric_value"] == 560.0


@pytest.mark.parametrize(
    ("stock_code", "filename"),
    [
        ("02498", "2022_annual_en.pdf"),
        ("09987", "2025_annual_en.pdf"),
    ],
)
@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_anchor_candidate_facts_do_not_map_growth_margin_ratio_rows(
    stock_code: str,
    filename: str,
) -> None:
    pdf_path = _resolve_sample("hk_stocks", stock_code, "annual", filename)

    ingestion_payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path=str(pdf_path),
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    suppressed_tokens = ("growth", "margin", "ratio")
    assert all(
        not any(
            token in fact["metric_label_raw"].lower() for token in suppressed_tokens
        )
        for fact in ingestion_payload["candidate_facts"]
        if fact["metric_id"]
        in {"revenue", "operating_cost", "operating_profit", "net_profit"}
    )


def test_balance_sheet_equity_semantics_preserve_scope_and_filter_false_positives() -> (
    None
):
    semantics = normalize_table_semantics(
        ParsedTable(
            table_id="doc:table:equity-regression",
            document_id="doc",
            page_range=(4, 4),
            table_kind="balance_sheet",
            title_text="Consolidated Statement of Financial Position",
            statement_scope_guess="consolidated",
            table_unit="thousand",
            table_currency="HKD",
            body_rows=[
                ParsedRow(
                    row_id="row-equity",
                    row_index=1,
                    label_raw="总权益",
                    normalized_label_hint="equity",
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-attributable-equity",
                    row_index=2,
                    label_raw="归属于母公司股东权益",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
                ParsedRow(
                    row_id="row-book-value",
                    row_index=3,
                    label_raw="book value per share",
                    normalized_label_hint=None,
                    value_cells=[],
                ),
            ],
        )
    )

    assert semantics.statement_scope_guess == "consolidated"
    assert semantics.semantic_source == "deterministic"
    assert semantics.unit_semantic_source == "deterministic"
    assert semantics.currency_semantic_source == "deterministic"
    assert semantics.rows[0].normalized_row_label == "equity"
    assert (
        semantics.rows[1].normalized_row_label
        == "equity attributable to owners of the parent"
    )
    assert semantics.rows[2].normalized_row_label is None
