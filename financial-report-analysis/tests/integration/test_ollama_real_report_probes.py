from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
import sys

import httpx
import pytest

from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter
from financial_report_analysis.semantic_fallback import (
    CurrencyFallbackRequest,
    RowLabelFallbackRequest,
    SemanticFallbackSettings,
    UnitFallbackRequest,
    build_semantic_fallback_service,
    load_semantic_fallback_settings,
    supported_currency_outputs,
    supported_row_label_outputs,
    supported_unit_outputs,
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
REAL_REPORT_SEMANTIC_PROBE_CASES = PROBE_MODULE.REAL_REPORT_SEMANTIC_PROBE_CASES


@dataclass(frozen=True, slots=True)
class ProbeEvaluationSummary:
    positive_total: int
    positive_hits: int
    negative_total: int
    negative_hits: int
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SemanticProbeEvaluationSummary:
    positive_total: int
    positive_hits: int
    negative_total: int
    negative_hits: int
    failures: tuple[str, ...]


def _real_ollama_settings() -> SemanticFallbackSettings:
    loaded = load_semantic_fallback_settings()
    return SemanticFallbackSettings(
        enabled=True,
        provider="ollama",
        base_url=loaded.base_url,
        model=loaded.model,
        timeout_seconds=loaded.timeout_seconds,
    )


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


def test_promoted_real_report_row_label_cases_match_fallback_gating() -> None:
    promoted = PROBE_MODULE.promoted_real_report_probe_cases()
    assert promoted

    for case in promoted:
        eligible = PdfIngestionAdapter._is_row_label_fallback_eligible(
            case.raw_label,
            case.raw_label,
        )
        if case.expectation_type == "positive":
            assert eligible, case.raw_label
        else:
            assert not eligible, case.raw_label


def test_real_report_probe_dataset_covers_supported_unit_currency_outputs() -> None:
    assert any(
        case.semantic_kind == "currency" and case.expected_value == "HKD"
        for case in REAL_REPORT_SEMANTIC_PROBE_CASES
    )
    assert any(
        case.semantic_kind == "unit" and case.expected_value == "thousand"
        for case in REAL_REPORT_SEMANTIC_PROBE_CASES
    )
    assert any(case.expected_value == "unknown" for case in REAL_REPORT_SEMANTIC_PROBE_CASES)


@pytest.mark.ollama
@pytest.mark.external
@pytest.mark.slow
def test_local_ollama_real_report_row_label_probe_dataset() -> None:
    if os.getenv("FRA_RUN_OLLAMA_REAL_REPORT_PROBES", "").strip().casefold() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        pytest.skip("set FRA_RUN_OLLAMA_REAL_REPORT_PROBES=1 to run real probe evaluation")

    settings = _real_ollama_settings()
    if not _ollama_available(settings.base_url, settings.model):
        pytest.skip("local Ollama endpoint or model is unavailable")

    results = run_real_probe_evaluation()

    assert results.positive_total > 0
    assert results.negative_total > 0
    assert results.positive_hits / results.positive_total >= 0.66, results.failures
    assert results.negative_hits / results.negative_total >= 0.66, results.failures


@pytest.mark.ollama
@pytest.mark.external
@pytest.mark.slow
def test_real_report_probe_evaluation_reports_positive_and_negative_hit_rates() -> None:
    if os.getenv("FRA_RUN_OLLAMA_REAL_REPORT_PROBES", "").strip().casefold() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        pytest.skip("set FRA_RUN_OLLAMA_REAL_REPORT_PROBES=1 to run real probe evaluation")

    results = run_real_probe_evaluation()
    assert results.positive_total >= 7
    assert results.negative_total >= 4
    assert results.positive_hits >= 5
    assert results.negative_hits >= 3


@pytest.mark.ollama
@pytest.mark.external
@pytest.mark.slow
def test_local_ollama_real_report_unit_currency_probe_dataset() -> None:
    if os.getenv("FRA_RUN_OLLAMA_REAL_REPORT_PROBES", "").strip().casefold() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        pytest.skip("set FRA_RUN_OLLAMA_REAL_REPORT_PROBES=1 to run real probe evaluation")

    results = run_real_semantic_probe_evaluation()

    assert results.positive_total > 0
    assert results.negative_total > 0
    assert results.positive_hits / results.positive_total >= 1.0, results.failures
    assert results.negative_hits / results.negative_total >= 1.0, results.failures


@pytest.mark.ollama
@pytest.mark.external
@pytest.mark.slow
def test_real_report_semantic_probe_evaluation_reports_positive_and_negative_hit_rates() -> None:
    if os.getenv("FRA_RUN_OLLAMA_REAL_REPORT_PROBES", "").strip().casefold() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        pytest.skip("set FRA_RUN_OLLAMA_REAL_REPORT_PROBES=1 to run real probe evaluation")

    results = run_real_semantic_probe_evaluation()
    assert results.positive_total >= 2
    assert results.negative_total >= 2
    assert results.positive_hits >= 2
    assert results.negative_hits >= 2


def run_real_probe_evaluation() -> ProbeEvaluationSummary:
    settings = _real_ollama_settings()
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

    return ProbeEvaluationSummary(
        positive_total=positive_total,
        positive_hits=positive_hits,
        negative_total=negative_total,
        negative_hits=negative_hits,
        failures=tuple(failures),
    )


def run_real_semantic_probe_evaluation() -> SemanticProbeEvaluationSummary:
    settings = _real_ollama_settings()
    if not _ollama_available(settings.base_url, settings.model):
        pytest.skip("local Ollama endpoint or model is unavailable")

    service = build_semantic_fallback_service(settings)
    assert service is not None

    positive_hits = 0
    negative_hits = 0
    positive_total = 0
    negative_total = 0
    failures: list[str] = []

    for case in REAL_REPORT_SEMANTIC_PROBE_CASES:
        if case.semantic_kind == "currency":
            result = service.resolve_currency(
                CurrencyFallbackRequest(
                    raw_text=case.raw_text,
                    local_context=case.local_context,
                    deterministic_candidates=(),
                    ambiguity_reason="real_report_probe",
                )
            )
            assert result.value in supported_currency_outputs()
        else:
            result = service.resolve_unit(
                UnitFallbackRequest(
                    raw_text=case.raw_text,
                    local_context=case.local_context,
                    deterministic_candidates=(),
                    ambiguity_reason="real_report_probe",
                )
            )
            assert result.value in supported_unit_outputs()

        assert result.semantic_source == "llm_fallback"

        matched = result.value == case.expected_value
        if case.expectation_type == "positive":
            positive_total += 1
            positive_hits += int(matched)
        else:
            negative_total += 1
            negative_hits += int(matched)

        if not matched:
            failures.append(
                f"{case.market}/{case.report_family}/{case.semantic_kind}/{case.raw_text} => "
                f"{result.value} (expected {case.expected_value})"
            )

    return SemanticProbeEvaluationSummary(
        positive_total=positive_total,
        positive_hits=positive_hits,
        negative_total=negative_total,
        negative_hits=negative_hits,
        failures=tuple(failures),
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
