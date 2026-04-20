from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

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
    dotenv_values = _load_dotenv_values(_project_root() / ".env")
    return SemanticFallbackSettings(
        enabled=_env_bool(
            "FRA_SEMANTIC_FALLBACK_ENABLED",
            default=False,
            dotenv_values=dotenv_values,
        ),
        provider=_env_text(
            "FRA_SEMANTIC_FALLBACK_PROVIDER",
            default="ollama",
            dotenv_values=dotenv_values,
        ).casefold(),
        base_url=_env_text(
            "FRA_SEMANTIC_FALLBACK_BASE_URL",
            default="http://127.0.0.1:11434",
            dotenv_values=dotenv_values,
        ),
        model=_env_text(
            "FRA_SEMANTIC_FALLBACK_MODEL",
            default="qwen3.5:9b",
            dotenv_values=dotenv_values,
        ),
        timeout_seconds=_env_float(
            "FRA_SEMANTIC_FALLBACK_TIMEOUT_SECONDS",
            default=30.0,
            dotenv_values=dotenv_values,
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


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_dotenv_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _env_text(
    name: str,
    *,
    default: str,
    dotenv_values: dict[str, str],
) -> str:
    raw_value = os.getenv(name)
    if raw_value is None:
        raw_value = dotenv_values.get(name)
    if raw_value is None:
        return default
    return raw_value.strip()


def _env_bool(
    name: str,
    *,
    default: bool,
    dotenv_values: dict[str, str],
) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        raw_value = dotenv_values.get(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _env_float(
    name: str,
    *,
    default: float,
    dotenv_values: dict[str, str],
) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        raw_value = dotenv_values.get(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default
