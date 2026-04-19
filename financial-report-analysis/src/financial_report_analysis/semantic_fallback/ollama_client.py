from __future__ import annotations

import json

import httpx

from financial_report_analysis.semantic_fallback.models import (
    RowLabelFallbackRequest,
    SemanticFallbackResult,
    TableKindFallbackRequest,
    supported_row_label_outputs,
    supported_table_kind_outputs,
)


class OllamaSemanticFallbackClient:
    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3:8b",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def classify_table_kind(
        self,
        request: TableKindFallbackRequest,
    ) -> SemanticFallbackResult:
        prompt = (
            "Choose exactly one table kind label from this set: "
            f"{', '.join(supported_table_kind_outputs())}.\n"
            f"Title: {request.title_text}\n"
            f"Context: {request.local_context}\n"
            f"Deterministic candidates: {', '.join(request.deterministic_candidates) or 'none'}\n"
            "Return JSON with keys value and confidence."
        )
        payload = self._invoke(prompt)
        value = _normalize_choice(
            payload.get("value", ""),
            allowed=supported_table_kind_outputs(),
            default="unknown",
        )
        confidence = _parse_confidence(payload.get("confidence"))
        return SemanticFallbackResult(
            value=value,
            semantic_source="llm_fallback",
            semantic_confidence=confidence,
            fallback_reason=request.ambiguity_reason,
        )

    def normalize_row_label(
        self,
        request: RowLabelFallbackRequest,
    ) -> SemanticFallbackResult:
        prompt = (
            "Choose exactly one normalized row label from this set: "
            f"{', '.join(supported_row_label_outputs())}.\n"
            f"Table kind: {request.table_kind}\n"
            f"Raw label: {request.raw_label}\n"
            f"Context: {request.local_context}\n"
            f"Deterministic candidates: {', '.join(request.deterministic_candidates) or 'none'}\n"
            "Return JSON with keys value and confidence."
        )
        payload = self._invoke(prompt)
        value = _normalize_choice(
            payload.get("value", ""),
            allowed=supported_row_label_outputs(),
            default="none",
        )
        confidence = _parse_confidence(payload.get("confidence"))
        return SemanticFallbackResult(
            value=value,
            semantic_source="llm_fallback",
            semantic_confidence=confidence,
            fallback_reason=request.ambiguity_reason,
        )

    def _invoke(self, prompt: str) -> dict[str, object]:
        response = httpx.post(
            f"{self._base_url}/api/generate",
            json={
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        raw_response = payload.get("response", "{}")
        if isinstance(raw_response, str):
            try:
                parsed = json.loads(raw_response)
            except json.JSONDecodeError:
                parsed = {"value": raw_response}
            if isinstance(parsed, dict):
                return parsed
        return {}


def _normalize_choice(value: object, *, allowed: tuple[str, ...], default: str) -> str:
    normalized = str(value).strip().casefold()
    return normalized if normalized in allowed else default


def _parse_confidence(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
