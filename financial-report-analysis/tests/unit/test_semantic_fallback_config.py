from __future__ import annotations

from pathlib import Path

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


def test_integration_ollama_tests_do_not_hardcode_localhost_endpoint() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    integration_dir = repo_root / "tests" / "integration"

    target_files = (
        integration_dir / "test_analysis_api.py",
        integration_dir / "test_ollama_smoke.py",
        integration_dir / "test_ollama_real_report_probes.py",
    )

    for path in target_files:
        assert "http://127.0.0.1:11434" not in path.read_text(encoding="utf-8")
