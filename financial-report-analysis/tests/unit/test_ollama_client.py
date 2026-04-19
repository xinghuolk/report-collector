from __future__ import annotations

import json

import httpx

from financial_report_analysis.semantic_fallback.ollama_client import (
    OllamaSemanticFallbackClient,
)
from financial_report_analysis.semantic_fallback.models import (
    RowLabelFallbackRequest,
    TableKindFallbackRequest,
)


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def test_ollama_client_parses_table_kind_response(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, *, json: dict[str, object], timeout: float) -> _FakeResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse({"response": '{"value": "balance_sheet", "confidence": 0.72}'})

    monkeypatch.setattr(httpx, "post", fake_post)

    client = OllamaSemanticFallbackClient(base_url="http://ollama.local", model="qwen3:8b")
    result = client.classify_table_kind(
        TableKindFallbackRequest(
            title_text="Statement of Financial Position",
            local_context="balance sheet context",
            deterministic_candidates=("unknown",),
            ambiguity_reason="weak_title_match",
        )
    )

    assert captured["url"] == "http://ollama.local/api/generate"
    assert result.value == "balance_sheet"
    assert result.semantic_source == "llm_fallback"
    assert result.semantic_confidence == 0.72


def test_ollama_client_bounds_invalid_row_label_output_to_none(monkeypatch) -> None:
    def fake_post(url: str, *, json: dict[str, object], timeout: float) -> _FakeResponse:
        del url, json, timeout
        return _FakeResponse({"response": json_module.dumps({"value": "gross_margin"})})

    json_module = json
    monkeypatch.setattr(httpx, "post", fake_post)

    client = OllamaSemanticFallbackClient()
    result = client.normalize_row_label(
        RowLabelFallbackRequest(
            raw_label="Gross margin",
            table_kind="key_metrics",
            local_context="summary table",
            deterministic_candidates=(),
            ambiguity_reason="unknown_row_label",
        )
    )

    assert result.value == "none"
