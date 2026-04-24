from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnalysisExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pdf_path: str | None = None
    pdf_url: str | None = None
    market: str | None = None
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class AnalysisExtractResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: dict[str, Any]
    canonical_fact_set_id: str
    derived_fact_set_id: str
    validation_report_id: str
    quality_gate: str
    key_facts: list[dict[str, Any]]
    ttm_facts: list[dict[str, Any]]
    analysis_snapshot: dict[str, Any]
    blocked_items: list[dict[str, Any]]


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class ManifestEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issuer_id: str
    market: str
    stock_code: str
    fiscal_year: int
    report_type: str
    pdf_path: str
    source: str
    company_name: str | None
    report_language: str | None


class ReportCoverageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issuer_id: str
    fiscal_year: int
    report_type: str
    report_registered: bool
    report_id: int | None = None
    pdf_path: str | None = None
    extracted_artifact_ids: tuple[str, ...] = ()
    extracted_artifact_available: bool = False


class IssuerReportsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issuer_id: str
    reports: list[ReportCoverageResponse]


class ExtractedArtifactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    artifact_version: str
    pipeline_version: str
    manifest_entry: ManifestEntryResponse
    source_pdf_path: str
    document: dict[str, Any]
    document_metadata: dict[str, Any]
    candidate_facts: list[dict[str, Any]]
    canonical_facts: list[dict[str, Any]]
    derived_facts: list[dict[str, Any]]
    validation_report: dict[str, Any]
    review_packets: list[dict[str, Any]]
    quality_gate: str
    missing_status: dict[str, dict[str, str]]
    created_at: str


class DatasetRowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    missing_status: str
    source_fact_id: str | None
    source_artifact_id: str
    evidence_bundle_id: str | None


class DatasetArtifactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    dataset_version: str
    created_at: str
    issuer_count: int
    periods: list[int]
    metrics: list[str]
    rows: list[DatasetRowResponse]
    quality_summary: dict[str, Any]
    source_artifacts: list[str]


class ExtractedReviewSurfaceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    artifact_version: str
    pipeline_version: str
    source_pdf_path: str
    manifest_entry_key: tuple[str, int, str]
    quality_gate: str
    review_issue_count: int
    missing_status_groups: tuple[str, ...]
    review_required_signals: tuple[str, ...] = ()
    duplicate_conflict_count: int = 0
    scope_mismatch_count: int = 0


class DatasetReviewSurfaceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    dataset_version: str
    issuer_count: int
    period_count: int
    pipeline_versions: tuple[str, ...]
    source_artifact_ids: tuple[str, ...]
    present_row_count: int
    missing_row_count: int
    review_required_artifact_ids: tuple[str, ...]
    duplicate_conflict_count: int = 0
    scope_mismatch_count: int = 0
    unknown_count: int = 0


class TurtleExportReviewSurfaceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    dataset_version: str
    source_artifact_ids: tuple[str, ...]
    row_count: int
    present_row_count: int
    missing_row_count: int
    alias_count: int
    review_required_artifact_ids: tuple[str, ...] = ()
    duplicate_conflict_count: int = 0
    scope_mismatch_count: int = 0


class SourceArtifactAuditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_artifact_id: str
    report_id: int | None
    source_pdf_path: str | None
    manifest_entry_key: tuple[str, int, str] | None
    extracted_review_surface: ExtractedReviewSurfaceResponse | None


class DatasetAuditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    source_artifact_ids: tuple[str, ...]
    source_artifacts: list[SourceArtifactAuditResponse]
    dataset_review_surface: DatasetReviewSurfaceResponse | None
    turtle_export_review_surface: TurtleExportReviewSurfaceResponse | None
    latest_recompute_run_id: str | None
    latest_recompute_reason: str | None


class RecomputeDiffSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str
    target_artifact_ids: tuple[str, ...]
    dataset_changed: bool
    turtle_export_changed: bool
    rebuilt_dataset: bool
    rebuilt_turtle_export: bool


class RecomputeResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    manifest_id: str
    extracted_artifact_ids: tuple[str, ...]
    dataset_path: str
    turtle_export_path: str
    diff_summary: RecomputeDiffSummaryResponse
