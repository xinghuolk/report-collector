from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from financial_report_analysis.models.facts import CandidateFact, CanonicalFact, DerivedFact
from financial_report_analysis.services.conflict_resolver import ConflictResolver
from financial_report_analysis.services.derivation_service import DerivationService
from financial_report_analysis.services.fact_normalizer import FactNormalizer
from financial_report_analysis.services.validation_service import (
    ValidationReport,
    ValidationService,
)
from financial_report_analysis.storage.artifacts import (
    build_fact_set_id,
    build_validation_report_id,
)


@dataclass(slots=True)
class PipelineResult:
    canonical_fact_set_id: str
    derived_fact_set_id: str
    validation_report_id: str
    quality_gate: str
    canonical_facts: list[CanonicalFact]
    derived_facts: list[DerivedFact]
    validation_report: ValidationReport


def analyze_report(document_ref: dict[str, Any], extracted_payload: dict[str, Any]) -> PipelineResult:
    document_id = str(document_ref["document_id"])
    unsupported_language_result = _unsupported_language_result(document_ref, document_id)
    if unsupported_language_result is not None:
        return unsupported_language_result

    candidates = [
        _candidate_fact_from_payload(document_id=document_id, payload=payload)
        for payload in extracted_payload.get("candidate_facts", [])
    ]
    normalized_candidates = FactNormalizer().normalize_candidates(candidates)
    canonical_facts = ConflictResolver().resolve(normalized_candidates)
    derived_facts = DerivationService().derive_ttm(canonical_facts)
    validation_report = ValidationService().validate(canonical_facts, derived_facts)

    return PipelineResult(
        canonical_fact_set_id=build_fact_set_id(document_id, "canonical"),
        derived_fact_set_id=build_fact_set_id(document_id, "derived"),
        validation_report_id=build_validation_report_id(document_id),
        quality_gate=_quality_gate(validation_report),
        canonical_facts=canonical_facts,
        derived_facts=derived_facts,
        validation_report=validation_report,
    )


def _candidate_fact_from_payload(
    *,
    document_id: str,
    payload: dict[str, Any],
) -> CandidateFact:
    fact_payload = dict(payload)
    payload_document_id = fact_payload.get("document_id")
    if payload_document_id is None:
        fact_payload["document_id"] = document_id
    elif str(payload_document_id) != document_id:
        raise ValueError("candidate document_id must match document_ref document_id")
    fact_payload["fact_kind"] = "candidate"
    fact_payload["table_coord"] = _stringify_table_coord(
        fact_payload.get("table_coord"),
    )
    return CandidateFact(**fact_payload)


def _stringify_table_coord(value: object) -> str | None:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return ",".join(str(part) for part in value)
    return str(value)


def _quality_gate(validation_report: ValidationReport) -> str:
    if validation_report.overall_status == "ok":
        return "pass"
    if validation_report.overall_status in {"review_required", "unsupported_in_phase1"}:
        return "review"
    return "fail"


def _unsupported_language_result(
    document_ref: dict[str, Any],
    document_id: str,
) -> PipelineResult | None:
    if document_ref.get("market") != "HK":
        return None

    language = document_ref.get("language")
    if language in {None, "en"}:
        return None

    validation_report = ValidationReport(
        overall_status="unsupported_in_phase1",
        canonical_fact_count=0,
        derived_fact_count=0,
        issues=("unsupported_in_phase1",),
    )
    return PipelineResult(
        canonical_fact_set_id=build_fact_set_id(document_id, "canonical"),
        derived_fact_set_id=build_fact_set_id(document_id, "derived"),
        validation_report_id=build_validation_report_id(document_id),
        quality_gate="review",
        canonical_facts=[],
        derived_facts=[],
        validation_report=validation_report,
    )
