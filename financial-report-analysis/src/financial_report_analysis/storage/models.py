from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
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
