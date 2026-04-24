from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, ForeignKey, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utc_iso_timestamp() -> str:
    return datetime.now(UTC).isoformat()


class IssuerRecord(Base):
    __tablename__ = "issuers"

    issuer_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    market: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    stock_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255))


class ReportRecord(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("issuer_id", "fiscal_year", "report_type", name="uq_reports_identity"),
    )

    report_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issuer_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("issuers.issuer_id"),
        nullable=False,
        index=True,
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    report_language: Mapped[str | None] = mapped_column(String(16))
    pdf_path: Mapped[str] = mapped_column(Text, nullable=False)


class ManifestRecord(Base):
    __tablename__ = "manifests"

    manifest_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    manifest_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class ManifestEntryRecord(Base):
    __tablename__ = "manifest_entries"
    __table_args__ = (
        UniqueConstraint(
            "manifest_id",
            "issuer_id",
            "fiscal_year",
            "report_type",
            name="uq_manifest_entries_identity",
        ),
    )

    manifest_entry_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    manifest_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("manifests.manifest_id"),
        nullable=False,
        index=True,
    )
    issuer_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("issuers.issuer_id"),
        nullable=False,
        index=True,
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class ExtractedArtifactRecord(Base):
    __tablename__ = "extracted_artifacts"

    artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reports.report_id"),
        nullable=False,
        index=True,
    )
    issuer_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("issuers.issuer_id"),
        nullable=False,
        index=True,
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    artifact_version: Mapped[str] = mapped_column(String(32), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class DatasetArtifactRecord(Base):
    __tablename__ = "dataset_artifacts"

    dataset_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    dataset_version: Mapped[str] = mapped_column(String(32), nullable=False)
    issuer_count: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class TurtleExportArtifactRecord(Base):
    __tablename__ = "turtle_export_artifacts"

    dataset_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("dataset_artifacts.dataset_id"),
        primary_key=True,
    )
    dataset_version: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class ExtractedReviewSurfaceRecord(Base):
    __tablename__ = "extracted_review_surfaces"

    artifact_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("extracted_artifacts.artifact_id"),
        primary_key=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class DatasetReviewSurfaceRecord(Base):
    __tablename__ = "dataset_review_surfaces"

    dataset_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("dataset_artifacts.dataset_id"),
        primary_key=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class TurtleExportReviewSurfaceRecord(Base):
    __tablename__ = "turtle_export_review_surfaces"

    dataset_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("turtle_export_artifacts.dataset_id"),
        primary_key=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class DatasetLineageRecord(Base):
    __tablename__ = "dataset_lineage_records"

    lineage_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("dataset_artifacts.dataset_id"),
        nullable=False,
        index=True,
    )
    source_artifact_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class RecomputeRunRecord(Base):
    __tablename__ = "recompute_runs"

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    manifest_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("manifests.manifest_id"),
        nullable=False,
        index=True,
    )
    dataset_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("dataset_artifacts.dataset_id"),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    target_artifact_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    diff_summary_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class ReportFileRecord(Base):
    __tablename__ = "report_files"
    __table_args__ = (
        UniqueConstraint("report_id", "file_path", name="uq_report_files_identity"),
    )

    report_file_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    report_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reports.report_id"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class DocumentRecord(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("report_file_id", name="uq_documents_report_file"),
    )

    document_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    report_file_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("report_files.report_file_id"),
        nullable=False,
        index=True,
    )
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class DocumentVersionRecord(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_label", name="uq_document_versions_identity"),
    )

    document_version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("documents.document_id"),
        nullable=False,
        index=True,
    )
    version_label: Mapped[str | None] = mapped_column(String(64))
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class ExtractionRunRecord(Base):
    __tablename__ = "extraction_runs"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id",
            "pipeline_version",
            name="uq_extraction_runs_identity",
        ),
    )

    extraction_run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("document_versions.document_version_id"),
        nullable=False,
        index=True,
    )
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class StatementTableRecord(Base):
    __tablename__ = "statement_tables"

    statement_table_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    extraction_run_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("extraction_runs.extraction_run_id"),
        nullable=False,
        index=True,
    )
    document_version_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("document_versions.document_version_id"),
        nullable=False,
        index=True,
    )
    table_family: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    statement_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class StatementTableRowRecord(Base):
    __tablename__ = "statement_table_rows"
    __table_args__ = (
        UniqueConstraint("statement_table_id", "row_index", name="uq_statement_table_rows_identity"),
    )

    statement_table_row_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    statement_table_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("statement_tables.statement_table_id"),
        nullable=False,
        index=True,
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class StatementTableColumnRecord(Base):
    __tablename__ = "statement_table_columns"
    __table_args__ = (
        UniqueConstraint(
            "statement_table_id",
            "column_index",
            name="uq_statement_table_columns_identity",
        ),
    )

    statement_table_column_id: Mapped[str] = mapped_column(
        String(128), primary_key=True
    )
    statement_table_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("statement_tables.statement_table_id"),
        nullable=False,
        index=True,
    )
    column_index: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class StatementTablePayloadRecord(Base):
    __tablename__ = "statement_table_payloads"
    __table_args__ = (
        UniqueConstraint(
            "statement_table_id",
            "payload_kind",
            name="uq_statement_table_payloads_identity",
        ),
    )

    statement_table_payload_id: Mapped[str] = mapped_column(
        String(128), primary_key=True
    )
    statement_table_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("statement_tables.statement_table_id"),
        nullable=False,
        index=True,
    )
    payload_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class FactSetRecord(Base):
    __tablename__ = "fact_sets"

    fact_set_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    extraction_run_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("extraction_runs.extraction_run_id"),
        nullable=False,
        index=True,
    )
    fact_set_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class CandidateFactRecord(Base):
    __tablename__ = "candidate_facts"

    fact_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    fact_set_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("fact_sets.fact_set_id"),
        nullable=False,
        index=True,
    )
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class CanonicalFactRecord(Base):
    __tablename__ = "canonical_facts"

    fact_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    fact_set_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("fact_sets.fact_set_id"),
        nullable=False,
        index=True,
    )
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class DerivedFactRecord(Base):
    __tablename__ = "derived_facts"

    fact_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    fact_set_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("fact_sets.fact_set_id"),
        nullable=False,
        index=True,
    )
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class FactLineageRecord(Base):
    __tablename__ = "fact_lineage_records"

    fact_lineage_record_id: Mapped[str] = mapped_column(
        String(128), primary_key=True
    )
    fact_set_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("fact_sets.fact_set_id"),
        nullable=False,
        index=True,
    )
    source_fact_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_fact_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lineage_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class EvidenceBundleTableRecord(Base):
    __tablename__ = "evidence_bundles"

    evidence_bundle_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("documents.document_id"),
        nullable=False,
        index=True,
    )
    bundle_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    primary_evidence_item_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("evidence_items.evidence_item_id"),
        index=True,
    )
    summary: Mapped[str | None] = mapped_column(Text)
    bundle_confidence: Mapped[float | None] = mapped_column(Float)
    schema_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class EvidenceItemRecord(Base):
    __tablename__ = "evidence_items"

    evidence_item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    evidence_bundle_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_bundles.evidence_bundle_id"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("documents.document_id"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class EvidenceBundleItemLinkRecord(Base):
    __tablename__ = "evidence_bundle_item_links"

    evidence_bundle_item_link_id: Mapped[str] = mapped_column(
        String(128), primary_key=True
    )
    evidence_bundle_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_bundles.evidence_bundle_id"),
        nullable=False,
        index=True,
    )
    evidence_item_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("evidence_items.evidence_item_id"),
        nullable=False,
        index=True,
    )
    item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class ValidationReportRecord(Base):
    __tablename__ = "validation_reports"

    validation_report_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    extraction_run_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("extraction_runs.extraction_run_id"),
        nullable=False,
        index=True,
    )
    fact_set_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("fact_sets.fact_set_id"),
        nullable=False,
        index=True,
    )
    overall_status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class ValidationIssueRecord(Base):
    __tablename__ = "validation_issues"

    validation_issue_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    validation_report_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("validation_reports.validation_report_id"),
        nullable=False,
        index=True,
    )
    issue_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    issue_level: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class QualityGateResultRecord(Base):
    __tablename__ = "quality_gate_results"

    quality_gate_result_id: Mapped[str] = mapped_column(
        String(128), primary_key=True
    )
    validation_report_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("validation_reports.validation_report_id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)


class MetricRegistryEntryRecord(Base):
    __tablename__ = "metric_registry_entries"

    metric_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    raw_label: Mapped[str] = mapped_column(String(255), nullable=False)
    statement_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    accounting_standard: Mapped[str] = mapped_column(String(32), nullable=False)
    industry_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_metric_id: Mapped[str | None] = mapped_column(String(128), index=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    registry_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)
