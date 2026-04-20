from __future__ import annotations

from dataclasses import dataclass
import os

from financial_report_analysis.semantic_fallback.ollama_client import (
    OllamaSemanticFallbackClient,
)
from financial_report_analysis.semantic_fallback.service import SemanticFallbackService


@dataclass(frozen=True, slots=True)
class SemanticFallbackSettings:
    enabled: bool = False
    provider: str = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3.5:9b"
    timeout_seconds: float = 30.0


def load_semantic_fallback_settings() -> SemanticFallbackSettings:
    return SemanticFallbackSettings(
        enabled=_env_bool("FRA_SEMANTIC_FALLBACK_ENABLED", default=False),
        provider=os.getenv("FRA_SEMANTIC_FALLBACK_PROVIDER", "ollama").strip().casefold(),
        base_url=os.getenv(
            "FRA_SEMANTIC_FALLBACK_BASE_URL",
            "http://127.0.0.1:11434",
        ).strip(),
        model=os.getenv("FRA_SEMANTIC_FALLBACK_MODEL", "qwen3.5:9b").strip(),
        timeout_seconds=_env_float(
            "FRA_SEMANTIC_FALLBACK_TIMEOUT_SECONDS",
            default=30.0,
        ),
    )


def build_semantic_fallback_service(
    settings: SemanticFallbackSettings | None = None,
) -> SemanticFallbackService | None:
    resolved = settings or load_semantic_fallback_settings()
    if not resolved.enabled:
        return None
    if resolved.provider != "ollama":
        raise ValueError(
            f"unsupported semantic fallback provider: {resolved.provider}",
        )
    return SemanticFallbackService(
        client=OllamaSemanticFallbackClient(
            base_url=resolved.base_url,
            model=resolved.model,
            timeout_seconds=resolved.timeout_seconds,
        )
    )


def _env_bool(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _env_float(name: str, *, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default
