from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnalysisExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pdf_path: str | None = None
    pdf_url: str | None = None
    market: str | None = None
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    persist_to_storage: bool = False
    build_dataset: bool = False
    build_turtle: bool = False
    dataset_id: str | None = None
    dataset_version: str | None = None
    issuer_id: str | None = None
    stock_code: str | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    report_type: str | None = None
    company_name: str | None = None
    report_language: str | None = None
    source: str = "api"

    @model_validator(mode="after")
    def validate_persistence_identity(self) -> "AnalysisExtractRequest":
        if (self.build_dataset or self.build_turtle) and not self.persist_to_storage:
            field_name = "build_turtle" if self.build_turtle else "build_dataset"
            raise ValueError(f"{field_name} requires persist_to_storage=true")

        if not self.persist_to_storage:
            return self

        missing_fields = [
            field_name
            for field_name in ("issuer_id", "stock_code", "fiscal_year", "report_type")
            if _is_missing_identity_value(getattr(self, field_name))
        ]
        if missing_fields:
            raise ValueError(
                "persist_to_storage requires explicit report identity fields: "
                + ", ".join(missing_fields)
            )
        if self.report_type != "annual":
            raise ValueError(
                "persist_to_storage currently supports report_type='annual' only"
            )
        return self


def _is_missing_identity_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


class AnalysisBuildResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str | None = None
    dataset_version: str | None = None
    turtle_export_id: str | None = None
    dataset_lookup_path: str | None = None
    turtle_export_lookup_path: str | None = None
    source_artifact_ids: tuple[str, ...] = ()
    lineage_record_count: int = 0
    build_warnings: tuple[str, ...] = ()


class AnalysisStorageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: bool
    artifact_id: str | None = None
    report_id: int | None = None
    document_id: str | None = None
    document_version_id: str | None = None
    extraction_run_id: str | None = None
    artifact_lookup_path: str | None = None
    report_lookup_path: str | None = None
    build: AnalysisBuildResult | None = None


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
    storage: AnalysisStorageResult | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class MetricGovernanceDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_item_id: str
    decision_type: Literal["keep_provisional", "map_to_standard"]
    target_metric_id: str | None = None
    reason: str
    actor: str

    @model_validator(mode="after")
    def validate_decision_shape(self) -> "MetricGovernanceDecisionRequest":
        if self.decision_type == "map_to_standard" and not self.target_metric_id:
            raise ValueError(
                "target_metric_id is required for decision_type='map_to_standard'"
            )
        if self.decision_type == "keep_provisional" and self.target_metric_id is not None:
            raise ValueError(
                "target_metric_id is not allowed for decision_type='keep_provisional'"
            )
        return self


class MetricGovernanceDecisionAnnotationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_type: str
    target_metric_id: str | None = None
    reason: str
    actor: str
    created_at: str


class MetricGovernanceReviewItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_item_id: str
    artifact_id: str
    issuer_id: str
    fiscal_year: int
    report_type: str
    metric_id: str
    raw_label: str
    normalized_label: str | None = None
    statement_type: str
    candidate_value: int | float | None = None
    period_label: str | None = None
    source_page: int | None = None
    source_table_id: str | None = None
    evidence_bundle_id: str | None = None
    metric_governance: dict[str, Any]
    latest_decision: MetricGovernanceDecisionAnnotationResponse | None = None


class MetricGovernanceReviewListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MetricGovernanceReviewItemResponse]


class MetricGovernanceDecisionWriteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: MetricGovernanceDecisionAnnotationResponse
    review_item: MetricGovernanceReviewItemResponse


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


class AvailabilityMetricResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    status: str
    value: int | float | None = None
    currency: str | None = None
    unit: str | None = None
    quality_status: str | None = None
    source_artifact_id: str | None = None
    source_fact_id: str | None = None
    evidence_bundle_id: str | None = None


class AvailabilityYearResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fiscal_year: int
    report_status: str
    artifact_status: str
    report_id: int | None = None
    pdf_path: str | None = None
    source_artifact_ids: list[str] = Field(default_factory=list)
    metrics: list[AvailabilityMetricResponse] = Field(default_factory=list)


class MultiYearAvailabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issuer_id: str
    report_type: str
    start_year: int
    end_year: int
    metric_profile: str
    years: list[AvailabilityYearResponse] = Field(default_factory=list)
    coverage_summary: dict[str, int]
    recommended_next_actions: list[str] = Field(default_factory=list)


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
