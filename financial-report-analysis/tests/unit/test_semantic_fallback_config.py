from __future__ import annotations

from pathlib import Path
import textwrap

from financial_report_analysis.semantic_fallback import (
    OllamaSemanticFallbackClient,
    SemanticFallbackService,
)
from financial_report_analysis.semantic_fallback.config import (
    SemanticFallbackSettings,
    build_semantic_fallback_service,
    load_semantic_fallback_settings,
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
        max_concurrency=3,
    )

    service = build_semantic_fallback_service(settings)

    assert isinstance(service, SemanticFallbackService)
    assert isinstance(service._client, OllamaSemanticFallbackClient)
    assert service._client._base_url == "http://127.0.0.1:11434"
    assert service._client._model == "qwen3.5:9b"
    assert service._client._timeout_seconds == 12.5
    assert service._max_concurrency == 3


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


def test_load_semantic_fallback_settings_reads_base_url_from_dotenv(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        textwrap.dedent(
            """
            FRA_SEMANTIC_FALLBACK_ENABLED=true
            FRA_SEMANTIC_FALLBACK_BASE_URL=http://192.168.10.103:11434
            FRA_SEMANTIC_FALLBACK_MODEL=qwen3.5:9b
            FRA_SEMANTIC_FALLBACK_MAX_CONCURRENCY=2
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("FRA_SEMANTIC_FALLBACK_ENABLED", raising=False)
    monkeypatch.delenv("FRA_SEMANTIC_FALLBACK_BASE_URL", raising=False)
    monkeypatch.delenv("FRA_SEMANTIC_FALLBACK_MODEL", raising=False)
    monkeypatch.delenv("FRA_SEMANTIC_FALLBACK_MAX_CONCURRENCY", raising=False)
    monkeypatch.setattr(
        "financial_report_analysis.semantic_fallback.config._project_root",
        lambda: tmp_path,
    )

    settings = load_semantic_fallback_settings()

    assert settings.enabled is True
    assert settings.base_url == "http://192.168.10.103:11434"
    assert settings.model == "qwen3.5:9b"
    assert settings.max_concurrency == 2


def test_load_semantic_fallback_settings_prefers_environment_over_dotenv(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "FRA_SEMANTIC_FALLBACK_BASE_URL=http://192.168.10.103:11434\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("FRA_SEMANTIC_FALLBACK_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setattr(
        "financial_report_analysis.semantic_fallback.config._project_root",
        lambda: tmp_path,
    )

    settings = load_semantic_fallback_settings()

    assert settings.base_url == "http://127.0.0.1:11434"
