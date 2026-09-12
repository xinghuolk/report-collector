from __future__ import annotations

from hashlib import sha1
from dataclasses import dataclass
from typing import Literal

FactSetKind = Literal["candidate", "canonical", "derived"]


def _stable_suffix(*parts: str) -> str:
    digest = sha1("::".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def build_fact_set_id(document_id: str, fact_set_kind: FactSetKind) -> str:
    return f"{document_id}:{fact_set_kind}:v1"


def build_validation_report_id(document_id: str) -> str:
    return f"{document_id}:validation:v1"


def build_report_file_id(report_id: int, file_path: str) -> str:
    return f"report-file:{report_id}:{_stable_suffix(str(report_id), file_path)}"


def build_document_id(report_file_id: str) -> str:
    return f"document:{_stable_suffix(report_file_id)}"


def build_document_version_id(
    document_id: str,
    *,
    version_label: str | None = None,
) -> str:
    label = version_label or "source"
    return f"document-version:{_stable_suffix(document_id, label)}"


def build_extraction_run_id(
    document_version_id: str,
    *,
    pipeline_version: str,
) -> str:
    return f"extraction-run:{_stable_suffix(document_version_id, pipeline_version)}"


def build_statement_table_id(extraction_run_id: str, source_table_id: str) -> str:
    return f"statement-table:{_stable_suffix(extraction_run_id, source_table_id)}"


def build_statement_table_row_id(statement_table_id: str, row_index: int) -> str:
    return f"statement-table-row:{_stable_suffix(statement_table_id, str(row_index))}"


def build_statement_table_column_id(statement_table_id: str, column_index: int) -> str:
    return f"statement-table-column:{_stable_suffix(statement_table_id, str(column_index))}"


def build_statement_table_payload_id(statement_table_id: str, payload_kind: str) -> str:
    return f"statement-table-payload:{_stable_suffix(statement_table_id, payload_kind)}"


def build_fact_lineage_record_id(
    fact_set_id: str,
    source_fact_id: str,
    target_fact_id: str,
    lineage_kind: str,
) -> str:
    return (
        "fact-lineage:"
        f"{_stable_suffix(fact_set_id, source_fact_id, target_fact_id, lineage_kind)}"
    )


def build_validation_issue_id(
    validation_report_id: str,
    issue_code: str,
    issue_index: int,
) -> str:
    return (
        "validation-issue:"
        f"{_stable_suffix(validation_report_id, issue_code, str(issue_index))}"
    )


def build_quality_gate_result_id(validation_report_id: str) -> str:
    return f"quality-gate:{_stable_suffix(validation_report_id)}"


def build_report_id(issuer_id: str, fiscal_year: int, report_type: str) -> str:
    return f"{issuer_id}:{fiscal_year}:{report_type}"


def build_manifest_entry_id(manifest_id: str, issuer_id: str, fiscal_year: int, report_type: str) -> str:
    return f"{manifest_id}:{issuer_id}:{fiscal_year}:{report_type}"


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
