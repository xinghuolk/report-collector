from __future__ import annotations

from financial_report_analysis.semantic_fallback import (
    OllamaSemanticFallbackClient,
    SemanticFallbackService,
)
from financial_report_analysis.semantic_fallback.config import (
    SemanticFallbackSettings,
    build_semantic_fallback_service,
)


def test_build_semantic_fallback_service_returns_none_when_disabled() -> None:
    settings = SemanticFallbackSettings(enabled=False)

    service = build_semantic_fallback_service(settings)

    assert service is None


def test_build_semantic_fallback_service_builds_ollama_client() -> None:
    settings = SemanticFallbackSettings(
        enabled=True,
        provider="ollama",
        base_url="http://127.0.0.1:11434",
        model="qwen3.5:9b",
        timeout_seconds=12.5,
    )

    service = build_semantic_fallback_service(settings)

    assert isinstance(service, SemanticFallbackService)
    assert isinstance(service._client, OllamaSemanticFallbackClient)
    assert service._client._base_url == "http://127.0.0.1:11434"
    assert service._client._model == "qwen3.5:9b"
    assert service._client._timeout_seconds == 12.5
