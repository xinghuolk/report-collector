from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Market = Literal["CN", "HK", "US"]
ReportType = Literal["annual"]
MissingStatus = Literal["present", "absent", "not_surfaced", "out_of_scope", "unknown"]


class P5ManifestValidationError(ValueError):
    """Raised when a P5 manifest cannot be used safely."""


@dataclass(frozen=True, slots=True)
class P5ManifestEntry:
    issuer_id: str
    market: Market
    stock_code: str
    fiscal_year: int
    report_type: ReportType
    pdf_path: Path
    source: str
    company_name: str | None = None
    report_language: str | None = None

    @property
    def artifact_id(self) -> str:
        return f"{self.market}_{self.stock_code}_{self.fiscal_year}"

    @property
    def entry_key(self) -> tuple[str, int, str]:
        return (self.issuer_id, self.fiscal_year, self.report_type)


@dataclass(frozen=True, slots=True)
class P5Manifest:
    manifest_id: str
    manifest_version: str
    entries: tuple[P5ManifestEntry, ...]


@dataclass(frozen=True, slots=True)
class P5ExtractedArtifact:
    artifact_id: str
    artifact_version: str
    pipeline_version: str
    manifest_entry: P5ManifestEntry
    source_pdf_path: Path
    document: dict[str, Any]
    document_metadata: dict[str, Any]
    candidate_facts: tuple[dict[str, Any], ...]
    canonical_facts: tuple[dict[str, Any], ...]
    derived_facts: tuple[dict[str, Any], ...]
    validation_report: dict[str, Any]
    review_packets: tuple[dict[str, Any], ...]
    quality_gate: str
    missing_status: dict[str, dict[str, str]]
    created_at: str


@dataclass(frozen=True, slots=True)
class P5DatasetRow:
    issuer_id: str
    market: str
    stock_code: str
    fiscal_year: int
    metric_id: str
    entity_scope: str
    period_scope: str
    statement_type: str
    value: int | float | None
    currency: str | None
    unit: str | None
    quality_status: str | None
    missing_status: MissingStatus
    source_fact_id: str | None
    source_artifact_id: str
    evidence_bundle_id: str | None


@dataclass(frozen=True, slots=True)
class P5DatasetArtifact:
    dataset_id: str
    dataset_version: str
    created_at: str
    issuer_count: int
    periods: tuple[int, ...]
    metrics: tuple[str, ...]
    rows: tuple[P5DatasetRow, ...]
    quality_summary: dict[str, Any]
    source_artifacts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class P5ExtractedReviewSurface:
    artifact_id: str
    artifact_version: str
    pipeline_version: str
    source_pdf_path: str
    manifest_entry_key: tuple[str, int, str]
    quality_gate: str
    review_issue_count: int
    missing_status_groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class P5DatasetReviewSurface:
    dataset_id: str
    dataset_version: str
    issuer_count: int
    period_count: int
    source_artifact_ids: tuple[str, ...]
    present_row_count: int
    missing_row_count: int
    review_required_artifact_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class P5ArtifactLineage:
    dataset_id: str
    source_artifact_id: str
    source_pdf_path: str
    pipeline_version: str
    source_fact_id: str | None
    evidence_bundle_id: str | None


@dataclass(frozen=True, slots=True)
class P5RecomputePlan:
    manifest_id: str
    dataset_id: str
    target_artifact_ids: tuple[str, ...]
    rebuild_dataset: bool
    rebuild_turtle_export: bool
    reason: str


@dataclass(frozen=True, slots=True)
class P5TurtleExport:
    dataset_id: str
    dataset_version: str
    created_at: str
    rows: tuple[dict[str, Any], ...]
    alias_map: dict[str, str] = field(default_factory=dict)
