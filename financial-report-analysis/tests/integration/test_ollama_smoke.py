from __future__ import annotations

import httpx
import pytest

from financial_report_analysis.semantic_fallback import (
    RowLabelFallbackRequest,
    SemanticFallbackSettings,
    build_semantic_fallback_service,
    supported_row_label_outputs,
)


def test_local_ollama_row_label_fallback_smoke() -> None:
    settings = SemanticFallbackSettings(
        enabled=True,
        provider="ollama",
        base_url="http://127.0.0.1:11434",
        model="qwen3.5:9b",
        timeout_seconds=30.0,
    )

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
def test_local_ollama_row_label_capability_probe_cases(
    raw_label: str,
    table_kind: str,
    local_context: str,
    expected_value: str,
) -> None:
    settings = SemanticFallbackSettings(
        enabled=True,
        provider="ollama",
        base_url="http://127.0.0.1:11434",
        model="qwen3.5:9b",
        timeout_seconds=30.0,
    )

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


def _ollama_available(base_url: str, model: str) -> bool:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=3.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return False

    payload = response.json()
    models = payload.get("models", [])
    return any(entry.get("name") == model for entry in models if isinstance(entry, dict))
