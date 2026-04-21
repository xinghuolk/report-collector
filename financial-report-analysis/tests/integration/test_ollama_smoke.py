from __future__ import annotations

import importlib.util
import httpx
import pytest
from pathlib import Path
import sys

from financial_report_analysis.semantic_fallback import (
    RowLabelFallbackRequest,
    SemanticFallbackSettings,
    build_semantic_fallback_service,
    load_semantic_fallback_settings,
    supported_row_label_outputs,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
PROBE_MODULE_PATH = FIXTURES_DIR / "ollama_real_report_probes.py"
PROBE_SPEC = importlib.util.spec_from_file_location(
    "ollama_real_report_probes",
    PROBE_MODULE_PATH,
)
assert PROBE_SPEC is not None and PROBE_SPEC.loader is not None
PROBE_MODULE = importlib.util.module_from_spec(PROBE_SPEC)
sys.modules.setdefault("ollama_real_report_probes", PROBE_MODULE)
PROBE_SPEC.loader.exec_module(PROBE_MODULE)
PROMOTED_REAL_REPORT_PROBE_CASES = PROBE_MODULE.PROMOTED_REAL_REPORT_PROBE_CASES
PROMOTED_REAL_REPORT_SEMANTIC_PROBE_CASES = (
    PROBE_MODULE.PROMOTED_REAL_REPORT_SEMANTIC_PROBE_CASES
)


def _real_ollama_settings() -> SemanticFallbackSettings:
    loaded = load_semantic_fallback_settings()
    return SemanticFallbackSettings(
        enabled=True,
        provider="ollama",
        base_url=loaded.base_url,
        model=loaded.model,
        timeout_seconds=loaded.timeout_seconds,
    )


@pytest.mark.ollama
@pytest.mark.external
def test_local_ollama_row_label_fallback_smoke() -> None:
    settings = _real_ollama_settings()

    if not _ollama_available(settings.base_url, settings.model):
        pytest.skip("local Ollama endpoint or model is unavailable")

    service = build_semantic_fallback_service(settings)
    assert service is not None

    result = service.resolve_row_label(
        RowLabelFallbackRequest(
            raw_label="Cash and cash equivalents",
            table_kind="balance_sheet",
            local_context="Consolidated Statement of Financial Position\nCash and cash equivalents",
            deterministic_candidates=(),
            ambiguity_reason="unknown_row_label",
        )
    )

    assert result.semantic_source == "llm_fallback"
    assert result.value in supported_row_label_outputs()
    assert result.fallback_reason == "unknown_row_label"


@pytest.mark.parametrize(
    ("raw_label", "table_kind", "local_context", "expected_value"),
    [
        (
            "Business revenue",
            "income_statement",
            "Consolidated Statement of Profit or Loss\nBusiness revenue",
            "revenue",
        ),
        (
            "Operating income",
            "income_statement",
            "Consolidated Statement of Profit or Loss\nOperating income",
            "operating_profit",
        ),
        (
            "Profit attributable to owners",
            "income_statement",
            "Consolidated Statement of Profit or Loss\nProfit attributable to owners",
            "net_profit",
        ),
    ],
)
@pytest.mark.ollama
@pytest.mark.external
def test_local_ollama_row_label_capability_probe_cases(
    raw_label: str,
    table_kind: str,
    local_context: str,
    expected_value: str,
) -> None:
    settings = _real_ollama_settings()

    if not _ollama_available(settings.base_url, settings.model):
        pytest.skip("local Ollama endpoint or model is unavailable")

    service = build_semantic_fallback_service(settings)
    assert service is not None

    result = service.resolve_row_label(
        RowLabelFallbackRequest(
            raw_label=raw_label,
            table_kind=table_kind,
            local_context=local_context,
            deterministic_candidates=(),
            ambiguity_reason="numeric_only_statement_block",
        )
    )

    assert result.semantic_source == "llm_fallback"
    assert result.value == expected_value
    assert result.fallback_reason == "numeric_only_statement_block"


@pytest.mark.ollama
@pytest.mark.external
def test_local_ollama_promoted_real_report_cases() -> None:
    promoted = PROMOTED_REAL_REPORT_PROBE_CASES
    assert promoted

    for case in promoted:
        result = resolve_row_label_with_real_ollama(case.raw_label, case.table_kind, case.local_context)
        assert result.value == case.expected_value


@pytest.mark.ollama
@pytest.mark.external
def test_local_ollama_promoted_unit_currency_cases() -> None:
    promoted = PROMOTED_REAL_REPORT_SEMANTIC_PROBE_CASES
    assert promoted

    for case in promoted:
        result = resolve_unit_or_currency_with_real_ollama(case)
        assert result.value == case.expected_value


def test_promoted_real_report_cases_are_selected_by_identity() -> None:
    promoted = PROBE_MODULE.promoted_real_report_probe_cases()
    assert [
        (case.raw_label, case.expected_value) for case in promoted
    ] == [
        (raw_label, expected_value)
        for _, _, _, raw_label, expected_value in PROBE_MODULE.PROMOTED_REAL_REPORT_PROBE_IDENTITIES
    ]


def test_promoted_real_report_semantic_cases_are_selected_by_identity() -> None:
    promoted = PROBE_MODULE.promoted_real_report_semantic_probe_cases()
    assert [
        (case.semantic_kind, case.raw_text, case.expected_value) for case in promoted
    ] == [
        ("currency", "HK$ million", "HKD"),
        ("unit", "HK$'000", "thousand"),
    ]


def resolve_row_label_with_real_ollama(
    raw_label: str,
    table_kind: str,
    local_context: str,
):
    settings = _real_ollama_settings()

    if not _ollama_available(settings.base_url, settings.model):
        pytest.skip("local Ollama endpoint or model is unavailable")

    service = build_semantic_fallback_service(settings)
    assert service is not None

    return service.resolve_row_label(
        RowLabelFallbackRequest(
            raw_label=raw_label,
            table_kind=table_kind,
            local_context=local_context,
            deterministic_candidates=(),
            ambiguity_reason="real_report_promoted_probe",
        )
    )


def resolve_unit_or_currency_with_real_ollama(case):
    settings = _real_ollama_settings()

    if not _ollama_available(settings.base_url, settings.model):
        pytest.skip("local Ollama endpoint or model is unavailable")

    service = build_semantic_fallback_service(settings)
    assert service is not None

    if case.semantic_kind == "currency":
        from financial_report_analysis.semantic_fallback import CurrencyFallbackRequest

        return service.resolve_currency(
            CurrencyFallbackRequest(
                raw_text=case.raw_text,
                local_context=case.local_context,
                deterministic_candidates=(),
                ambiguity_reason="real_report_promoted_probe",
            )
        )

    from financial_report_analysis.semantic_fallback import UnitFallbackRequest

    return service.resolve_unit(
        UnitFallbackRequest(
            raw_text=case.raw_text,
            local_context=case.local_context,
            deterministic_candidates=(),
            ambiguity_reason="real_report_promoted_probe",
        )
    )


def _ollama_available(base_url: str, model: str) -> bool:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=3.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return False

    payload = response.json()
    models = payload.get("models", [])
    return any(entry.get("name") == model for entry in models if isinstance(entry, dict))
