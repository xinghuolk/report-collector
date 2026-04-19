from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FactSetKind = Literal["candidate", "canonical", "derived"]


def build_fact_set_id(document_id: str, fact_set_kind: FactSetKind) -> str:
    return f"{document_id}:{fact_set_kind}:v1"


def build_validation_report_id(document_id: str) -> str:
    return f"{document_id}:validation:v1"


@dataclass(frozen=True, slots=True)
class EvidenceBundleRecord:
    evidence_bundle_id: str
    document_id: str
    bundle_type: Literal[
        "fact_support",
        "derivation_support",
        "validation_support",
        "analysis_support",
    ]
    primary_evidence_item_id: str | None = None
    summary: str | None = None
    bundle_confidence: float | None = None
    created_at: str | None = None
    schema_version: str | None = None


@dataclass(frozen=True, slots=True)
class FactSetArtifact:
    fact_set_id: str
    document_id: str
    fact_set_kind: FactSetKind
    fact_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ValidationReportArtifact:
    validation_report_id: str
    document_id: str
    canonical_fact_set_id: str
    derived_fact_set_id: str
    overall_status: str
    issue_count: int
