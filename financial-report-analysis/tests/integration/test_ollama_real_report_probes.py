from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

import httpx
import pytest

from financial_report_analysis.semantic_fallback import (
    RowLabelFallbackRequest,
    SemanticFallbackSettings,
    build_semantic_fallback_service,
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
REAL_REPORT_ROW_LABEL_PROBE_CASES = PROBE_MODULE.REAL_REPORT_ROW_LABEL_PROBE_CASES


def test_real_report_row_label_probe_dataset_covers_target_outputs() -> None:
    positive_expected_values = {
        case.expected_value
        for case in REAL_REPORT_ROW_LABEL_PROBE_CASES
        if case.expectation_type == "positive"
    }
    negative_cases = [
        case
        for case in REAL_REPORT_ROW_LABEL_PROBE_CASES
        if case.expectation_type == "negative"
    ]
    negative_raw_labels = {case.raw_label.casefold() for case in negative_cases}

    assert positive_expected_values == set(supported_row_label_outputs()) - {"none"}
    assert negative_cases
    assert any(
        "margin" in raw_label or "ratio" in raw_label
        for raw_label in negative_raw_labels
    )


def test_local_ollama_real_report_row_label_probe_dataset() -> None:
    if os.getenv("FRA_RUN_OLLAMA_REAL_REPORT_PROBES", "").strip().casefold() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        pytest.skip("set FRA_RUN_OLLAMA_REAL_REPORT_PROBES=1 to run real probe evaluation")

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

    positive_hits = 0
    negative_hits = 0
    positive_total = 0
    negative_total = 0
    failures: list[str] = []

    for case in REAL_REPORT_ROW_LABEL_PROBE_CASES:
        result = service.resolve_row_label(
            RowLabelFallbackRequest(
                raw_label=case.raw_label,
                table_kind=case.table_kind,
                local_context=case.local_context,
                deterministic_candidates=(),
                ambiguity_reason="real_report_probe",
            )
        )

        assert result.semantic_source == "llm_fallback"
        assert result.value in supported_row_label_outputs()

        matched = result.value == case.expected_value
        if case.expectation_type == "positive":
            positive_total += 1
            positive_hits += int(matched)
        else:
            negative_total += 1
            negative_hits += int(matched)

        if not matched:
            failures.append(
                f"{case.market}/{case.report_family}/{case.raw_label} => {result.value} "
                f"(expected {case.expected_value})"
            )

    assert positive_total > 0
    assert negative_total > 0
    assert positive_hits / positive_total >= 0.66, failures
    assert negative_hits / negative_total >= 0.66, failures


def _ollama_available(base_url: str, model: str) -> bool:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=3.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return False

    payload = response.json()
    models = payload.get("models", [])
    return any(entry.get("name") == model for entry in models if isinstance(entry, dict))
