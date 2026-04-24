from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass, field

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from financial_report_analysis.models.table import ParsedTable
from financial_report_analysis.models.facts import CandidateFact, CanonicalFact, DerivedFact
from financial_report_analysis.models.evidence import EvidenceBundle, EvidenceItem
from financial_report_analysis.p5.artifact_repository import (
    P5ArtifactRepositoryError,
    dataset_artifact_from_payload,
    dataset_artifact_to_payload,
    extracted_artifact_from_payload,
    extracted_artifact_to_payload,
    turtle_export_from_payload,
    turtle_export_to_payload,
)
from financial_report_analysis.p5.lineage import (
    artifact_lineage_from_payload,
    artifact_lineage_to_payload,
)
from financial_report_analysis.p5.models import (
    P5ArtifactLineage,
    P5DatasetArtifact,
    P5DatasetReviewSurface,
    P5ExtractedArtifact,
    P5ExtractedReviewSurface,
    P5RecomputePlan,
    P5RecomputeResult,
    P5TurtleExport,
    P5TurtleExportReviewSurface,
)
from financial_report_analysis.p5.recompute import (
    recompute_diff_summary_to_payload,
    recompute_result_from_payload,
    recompute_result_to_payload,
)
from financial_report_analysis.p5.review import (
    dataset_review_surface_from_payload,
    dataset_review_surface_to_payload,
    extracted_review_surface_from_payload,
    extracted_review_surface_to_payload,
    turtle_export_review_surface_from_payload,
    turtle_export_review_surface_to_payload,
)

from .artifacts import EvidenceBundleRecord
from .artifacts import (
    build_document_id,
    build_document_version_id,
    build_extraction_run_id,
    build_fact_lineage_record_id,
    build_quality_gate_result_id,
    build_report_file_id,
    build_statement_table_column_id,
    build_statement_table_id,
    build_statement_table_payload_id,
    build_statement_table_row_id,
    build_validation_issue_id,
)
from .models import (
    CandidateFactRecord,
    CanonicalFactRecord,
    DatasetLineageRecord,
    DatasetArtifactRecord,
    DocumentRecord,
    DocumentVersionRecord,
    DerivedFactRecord,
    DatasetReviewSurfaceRecord,
    ExtractedArtifactRecord,
    ExtractedReviewSurfaceRecord,
    ExtractionRunRecord,
    FactLineageRecord,
    FactSetRecord,
    IssuerRecord,
    ManifestEntryRecord,
    ManifestRecord,
    QualityGateResultRecord,
    RecomputeRunRecord,
    ReportFileRecord,
    ReportRecord,
    StatementTableColumnRecord,
    StatementTablePayloadRecord,
    StatementTableRecord,
    StatementTableRowRecord,
    TurtleExportArtifactRecord,
    TurtleExportReviewSurfaceRecord,
    ValidationIssueRecord,
    ValidationReportRecord,
)


@dataclass(frozen=True, slots=True)
class EvidenceBundleItemLink:
    evidence_bundle_id: str
    evidence_item_id: str
    sort_order: int


@dataclass(frozen=True, slots=True)
class ReportCoverage:
    issuer_id: str
    fiscal_year: int
    report_type: str
    report_registered: bool
    report_id: int | None = None
    pdf_path: str | None = None
    extracted_artifact_ids: tuple[str, ...] = ()
    extracted_artifact_available: bool = False


@dataclass(frozen=True, slots=True)
class SourceArtifactAuditRecord:
    source_artifact_id: str
    report_id: int | None
    source_pdf_path: str | None
    manifest_entry_key: tuple[str, int, str] | None
    extracted_review_surface: P5ExtractedReviewSurface | None


@dataclass(frozen=True, slots=True)
class DatasetAuditView:
    dataset_id: str
    source_artifact_ids: tuple[str, ...]
    source_artifacts: tuple[SourceArtifactAuditRecord, ...]
    dataset_review_surface: P5DatasetReviewSurface | None
    turtle_export_review_surface: P5TurtleExportReviewSurface | None
    latest_recompute_run_id: str | None
    latest_recompute_reason: str | None


@dataclass(frozen=True, slots=True)
class DocumentVersionIdentity:
    report_file_id: str
    document_id: str
    document_version_id: str


@dataclass(frozen=True, slots=True)
class ExtractionRunIdentity:
    extraction_run_id: str
    document_version_id: str
    pipeline_version: str
    status: str


@dataclass(frozen=True, slots=True)
class PersistedExtractBundleIdentity:
    report_id: int
    document_id: str
    document_version_id: str
    extraction_run_id: str


@dataclass(frozen=True, slots=True)
class StatementTableLedgerEntry:
    statement_table_id: str
    extraction_run_id: str
    document_version_id: str
    source_table_id: str
    table_family: str
    statement_type: str
    row_ids: tuple[str, ...]
    column_ids: tuple[str, ...]
    payload_kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FactSetLedgerEntry:
    fact_set_id: str
    extraction_run_id: str
    fact_set_kind: str
    status: str
    fact_ids: tuple[str, ...]
    lineage_record_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ValidationLedgerEntry:
    validation_report_id: str
    extraction_run_id: str
    fact_set_id: str
    overall_status: str
    issue_ids: tuple[str, ...]
    issue_codes: tuple[str, ...]
    quality_gate_result_id: str
    quality_gate_status: str


@dataclass(slots=True)
class InMemoryEvidenceRepository:
    _bundle_records: dict[str, EvidenceBundleRecord] = field(default_factory=dict)
    _evidence_items: dict[str, EvidenceItem] = field(default_factory=dict)
    _bundle_item_links: dict[str, list[EvidenceBundleItemLink]] = field(
        default_factory=dict
    )

    def save_evidence_bundle(self, bundle: EvidenceBundle) -> None:
        self._bundle_records[bundle.evidence_bundle_id] = EvidenceBundleRecord(
            evidence_bundle_id=bundle.evidence_bundle_id,
            document_id=bundle.document_id,
            bundle_type=bundle.bundle_type,
            primary_evidence_item_id=bundle.primary_evidence_item_id,
            summary=bundle.summary,
            bundle_confidence=bundle.bundle_confidence,
            created_at=bundle.created_at,
            schema_version=bundle.schema_version,
        )
        self._bundle_item_links[bundle.evidence_bundle_id] = [
            EvidenceBundleItemLink(
                evidence_bundle_id=bundle.evidence_bundle_id,
                evidence_item_id=item.evidence_item_id,
                sort_order=index,
            )
            for index, item in enumerate(bundle.evidence_items)
        ]
        for item in bundle.evidence_items:
            self._evidence_items[item.evidence_item_id] = item

    def save_evidence_item(self, item: EvidenceItem) -> None:
        self._evidence_items[item.evidence_item_id] = item

    def link_evidence_bundle_item(
        self,
        *,
        evidence_bundle_id: str,
        evidence_item_id: str,
        sort_order: int,
    ) -> None:
        if evidence_bundle_id not in self._bundle_records:
            raise ValueError(
                f"cannot link item to missing evidence bundle: {evidence_bundle_id}"
            )
        if evidence_item_id not in self._evidence_items:
            raise ValueError(
                f"cannot link missing evidence item: {evidence_item_id}"
            )
        self._bundle_item_links.setdefault(evidence_bundle_id, []).append(
            EvidenceBundleItemLink(
                evidence_bundle_id=evidence_bundle_id,
                evidence_item_id=evidence_item_id,
                sort_order=sort_order,
            )
        )

    def get_evidence_bundle(self, evidence_bundle_id: str) -> EvidenceBundle | None:
        record = self._bundle_records.get(evidence_bundle_id)
        if record is None:
            return None

        links = sorted(
            self._bundle_item_links.get(evidence_bundle_id, []),
            key=lambda link: (link.sort_order, link.evidence_item_id),
        )
        missing_item_ids = [
            link.evidence_item_id
            for link in links
            if link.evidence_item_id not in self._evidence_items
        ]
        if missing_item_ids:
            raise ValueError(
                "missing linked evidence item(s): " + ", ".join(sorted(missing_item_ids))
            )
        evidence_items = [
            self._evidence_items[link.evidence_item_id]
            for link in links
        ]
        return EvidenceBundle(
            evidence_bundle_id=record.evidence_bundle_id,
            document_id=record.document_id,
            bundle_type=record.bundle_type,
            evidence_items=evidence_items,
            primary_evidence_item_id=record.primary_evidence_item_id,
            summary=record.summary,
            bundle_confidence=record.bundle_confidence,
            created_at=record.created_at,
            schema_version=record.schema_version,
        )

    def list_evidence_bundle_item_links(
        self,
        evidence_bundle_id: str,
    ) -> tuple[EvidenceBundleItemLink, ...]:
        return tuple(
            sorted(
                self._bundle_item_links.get(evidence_bundle_id, []),
                key=lambda link: (link.sort_order, link.evidence_item_id),
            )
        )


@dataclass(slots=True)
class SqlAlchemyP5ArtifactRepository:
    engine: Engine

    def ensure_document_version(
        self,
        *,
        report_id: int,
        file_path: str,
        version_label: str | None = None,
        report_file_payload: dict[str, object] | None = None,
        document_payload: dict[str, object] | None = None,
        document_version_payload: dict[str, object] | None = None,
    ) -> DocumentVersionIdentity:
        report_file_id = build_report_file_id(report_id, file_path)
        document_id = build_document_id(report_file_id)
        document_version_id = build_document_version_id(
            document_id,
            version_label=version_label,
        )
        with Session(self.engine) as session:
            report_file = session.get(ReportFileRecord, report_file_id)
            if report_file is None:
                report_file = ReportFileRecord(
                    report_file_id=report_file_id,
                    report_id=report_id,
                    file_path=file_path,
                    payload_json=(
                        json.dumps(report_file_payload, ensure_ascii=False, sort_keys=True)
                        if report_file_payload is not None
                        else None
                    ),
                )
                session.add(report_file)
            else:
                report_file.report_id = report_id
                report_file.file_path = file_path
                report_file.payload_json = (
                    json.dumps(report_file_payload, ensure_ascii=False, sort_keys=True)
                    if report_file_payload is not None
                    else report_file.payload_json
                )

            document = session.get(DocumentRecord, document_id)
            if document is None:
                document = DocumentRecord(
                    document_id=document_id,
                    report_file_id=report_file_id,
                    payload_json=(
                        json.dumps(document_payload, ensure_ascii=False, sort_keys=True)
                        if document_payload is not None
                        else None
                    ),
                )
                session.add(document)
            else:
                document.report_file_id = report_file_id
                document.payload_json = (
                    json.dumps(document_payload, ensure_ascii=False, sort_keys=True)
                    if document_payload is not None
                    else document.payload_json
                )

            document_version = session.get(DocumentVersionRecord, document_version_id)
            if document_version is None:
                document_version = DocumentVersionRecord(
                    document_version_id=document_version_id,
                    document_id=document_id,
                    version_label=version_label,
                    payload_json=(
                        json.dumps(
                            document_version_payload,
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        if document_version_payload is not None
                        else None
                    ),
                )
                session.add(document_version)
            else:
                document_version.document_id = document_id
                document_version.version_label = version_label
                document_version.payload_json = (
                    json.dumps(
                        document_version_payload,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    if document_version_payload is not None
                    else document_version.payload_json
                )
            session.commit()
        return DocumentVersionIdentity(
            report_file_id=report_file_id,
            document_id=document_id,
            document_version_id=document_version_id,
        )

    def save_extraction_run(
        self,
        *,
        document_version_id: str,
        pipeline_version: str,
        status: str,
        payload: dict[str, object] | None = None,
    ) -> ExtractionRunIdentity:
        extraction_run_id = build_extraction_run_id(
            document_version_id,
            pipeline_version=pipeline_version,
        )
        with Session(self.engine) as session:
            record = session.get(ExtractionRunRecord, extraction_run_id)
            if record is None:
                record = ExtractionRunRecord(
                    extraction_run_id=extraction_run_id,
                    document_version_id=document_version_id,
                    pipeline_version=pipeline_version,
                    status=status,
                    payload_json=(
                        json.dumps(payload, ensure_ascii=False, sort_keys=True)
                        if payload is not None
                        else None
                    ),
                )
                session.add(record)
            else:
                record.document_version_id = document_version_id
                record.pipeline_version = pipeline_version
                record.status = status
                record.payload_json = (
                    json.dumps(payload, ensure_ascii=False, sort_keys=True)
                    if payload is not None
                    else record.payload_json
                )
            session.commit()
        return ExtractionRunIdentity(
            extraction_run_id=extraction_run_id,
            document_version_id=document_version_id,
            pipeline_version=pipeline_version,
            status=status,
        )

    def save_api_extract_bundle(
        self,
        *,
        artifact: P5ExtractedArtifact,
        review_surface: P5ExtractedReviewSurface,
        document_payload: dict[str, object],
        manifest_id: str,
        document_version_label: str,
        report_file_payload: dict[str, object] | None = None,
        document_version_payload: dict[str, object] | None = None,
        extraction_run_payload: dict[str, object] | None = None,
    ) -> PersistedExtractBundleIdentity:
        entry = artifact.manifest_entry
        artifact_payload_json = json.dumps(
            extracted_artifact_to_payload(artifact),
            ensure_ascii=False,
            sort_keys=True,
        )
        report_file_payload_json = (
            json.dumps(report_file_payload, ensure_ascii=False, sort_keys=True)
            if report_file_payload is not None
            else None
        )
        document_payload_json = json.dumps(
            document_payload,
            ensure_ascii=False,
            sort_keys=True,
        )
        document_version_payload_json = (
            json.dumps(document_version_payload, ensure_ascii=False, sort_keys=True)
            if document_version_payload is not None
            else None
        )
        extraction_run_payload_json = (
            json.dumps(extraction_run_payload, ensure_ascii=False, sort_keys=True)
            if extraction_run_payload is not None
            else None
        )

        report_id: int
        document_id: str
        document_version_id: str
        extraction_run_id: str
        with Session(self.engine) as session:
            with session.begin():
                self._upsert_issuer(session, artifact)
                report = self._upsert_report(session, artifact)
                report_id = report.report_id
                self._upsert_manifest_entry(
                    session,
                    manifest_id=manifest_id,
                    manifest_version="1.0",
                    artifact=artifact,
                )

                report_file_id = build_report_file_id(
                    report_id,
                    str(entry.pdf_path),
                )
                document_id = build_document_id(report_file_id)
                document_version_id = build_document_version_id(
                    document_id,
                    version_label=document_version_label,
                )
                extraction_run_id = build_extraction_run_id(
                    document_version_id,
                    pipeline_version=artifact.pipeline_version,
                )

                report_file = session.get(ReportFileRecord, report_file_id)
                if report_file is None:
                    report_file = ReportFileRecord(
                        report_file_id=report_file_id,
                        report_id=report_id,
                        file_path=str(entry.pdf_path),
                        payload_json=report_file_payload_json,
                    )
                    session.add(report_file)
                else:
                    report_file.report_id = report_id
                    report_file.file_path = str(entry.pdf_path)
                    report_file.payload_json = report_file_payload_json

                document = session.get(DocumentRecord, document_id)
                if document is None:
                    document = DocumentRecord(
                        document_id=document_id,
                        report_file_id=report_file_id,
                        payload_json=document_payload_json,
                    )
                    session.add(document)
                else:
                    document.report_file_id = report_file_id
                    document.payload_json = document_payload_json

                document_version = session.get(
                    DocumentVersionRecord,
                    document_version_id,
                )
                if document_version is None:
                    document_version = DocumentVersionRecord(
                        document_version_id=document_version_id,
                        document_id=document_id,
                        version_label=document_version_label,
                        payload_json=document_version_payload_json,
                    )
                    session.add(document_version)
                else:
                    document_version.document_id = document_id
                    document_version.version_label = document_version_label
                    document_version.payload_json = document_version_payload_json

                extraction_run = session.get(ExtractionRunRecord, extraction_run_id)
                if extraction_run is None:
                    extraction_run = ExtractionRunRecord(
                        extraction_run_id=extraction_run_id,
                        document_version_id=document_version_id,
                        pipeline_version=artifact.pipeline_version,
                        status=artifact.quality_gate,
                        payload_json=extraction_run_payload_json,
                    )
                    session.add(extraction_run)
                else:
                    extraction_run.document_version_id = document_version_id
                    extraction_run.pipeline_version = artifact.pipeline_version
                    extraction_run.status = artifact.quality_gate
                    extraction_run.payload_json = extraction_run_payload_json

                artifact_record = session.get(
                    ExtractedArtifactRecord,
                    artifact.artifact_id,
                )
                if artifact_record is None:
                    artifact_record = ExtractedArtifactRecord(
                        artifact_id=artifact.artifact_id,
                        report_id=report_id,
                        issuer_id=entry.issuer_id,
                        fiscal_year=entry.fiscal_year,
                        report_type=entry.report_type,
                        artifact_version=artifact.artifact_version,
                        pipeline_version=artifact.pipeline_version,
                        payload_json=artifact_payload_json,
                        created_at=artifact.created_at,
                    )
                    session.add(artifact_record)
                else:
                    artifact_record.report_id = report_id
                    artifact_record.issuer_id = entry.issuer_id
                    artifact_record.fiscal_year = entry.fiscal_year
                    artifact_record.report_type = entry.report_type
                    artifact_record.artifact_version = artifact.artifact_version
                    artifact_record.pipeline_version = artifact.pipeline_version
                    artifact_record.payload_json = artifact_payload_json
                    artifact_record.created_at = artifact.created_at

                review_surface_payload_json = json.dumps(
                    extracted_review_surface_to_payload(review_surface),
                    ensure_ascii=False,
                    sort_keys=True,
                )
                review_surface_record = session.get(
                    ExtractedReviewSurfaceRecord,
                    review_surface.artifact_id,
                )
                if review_surface_record is None:
                    review_surface_record = ExtractedReviewSurfaceRecord(
                        artifact_id=review_surface.artifact_id,
                        payload_json=review_surface_payload_json,
                    )
                    session.add(review_surface_record)
                else:
                    review_surface_record.payload_json = review_surface_payload_json

        return PersistedExtractBundleIdentity(
            report_id=report_id,
            document_id=document_id,
            document_version_id=document_version_id,
            extraction_run_id=extraction_run_id,
        )

    def list_available_fiscal_years(self, issuer_id: str) -> tuple[int, ...]:
        statement = (
            select(ReportRecord.fiscal_year)
            .where(ReportRecord.issuer_id == issuer_id)
            .distinct()
            .order_by(ReportRecord.fiscal_year)
        )
        with Session(self.engine) as session:
            fiscal_years = session.scalars(statement).all()
        return tuple(fiscal_years)

    def get_report_coverage(
        self,
        issuer_id: str,
        fiscal_year: int,
        report_type: str,
    ) -> ReportCoverage:
        report_statement = select(ReportRecord).where(
            ReportRecord.issuer_id == issuer_id,
            ReportRecord.fiscal_year == fiscal_year,
            ReportRecord.report_type == report_type,
        )
        with Session(self.engine) as session:
            report = session.scalar(report_statement)
            if report is None:
                return ReportCoverage(
                    issuer_id=issuer_id,
                    fiscal_year=fiscal_year,
                    report_type=report_type,
                    report_registered=False,
                )

            artifact_ids = tuple(
                session.scalars(
                    select(ExtractedArtifactRecord.artifact_id)
                    .where(ExtractedArtifactRecord.report_id == report.report_id)
                    .order_by(ExtractedArtifactRecord.artifact_id)
                ).all()
            )
        return ReportCoverage(
            issuer_id=issuer_id,
            fiscal_year=fiscal_year,
            report_type=report_type,
            report_registered=True,
            report_id=report.report_id,
            pdf_path=report.pdf_path,
            extracted_artifact_ids=artifact_ids,
            extracted_artifact_available=bool(artifact_ids),
        )

    def extracted_artifact_exists(self, artifact_id: str) -> bool:
        with Session(self.engine) as session:
            return session.get(ExtractedArtifactRecord, artifact_id) is not None

    def save_extracted_artifact(self, artifact: P5ExtractedArtifact) -> str:
        payload_json = json.dumps(
            extracted_artifact_to_payload(artifact),
            ensure_ascii=False,
            sort_keys=True,
        )
        with Session(self.engine) as session:
            self._upsert_issuer(session, artifact)
            report = self._upsert_report(session, artifact)
            record = session.get(ExtractedArtifactRecord, artifact.artifact_id)
            if record is None:
                record = ExtractedArtifactRecord(
                    artifact_id=artifact.artifact_id,
                    report_id=report.report_id,
                    issuer_id=artifact.manifest_entry.issuer_id,
                    fiscal_year=artifact.manifest_entry.fiscal_year,
                    report_type=artifact.manifest_entry.report_type,
                    artifact_version=artifact.artifact_version,
                    pipeline_version=artifact.pipeline_version,
                    payload_json=payload_json,
                    created_at=artifact.created_at,
                )
                session.add(record)
            else:
                record.report_id = report.report_id
                record.issuer_id = artifact.manifest_entry.issuer_id
                record.fiscal_year = artifact.manifest_entry.fiscal_year
                record.report_type = artifact.manifest_entry.report_type
                record.artifact_version = artifact.artifact_version
                record.pipeline_version = artifact.pipeline_version
                record.payload_json = payload_json
                record.created_at = artifact.created_at
            session.commit()
        return artifact.artifact_id

    def load_extracted_artifact(self, artifact_id: str) -> P5ExtractedArtifact:
        with Session(self.engine) as session:
            record = session.get(ExtractedArtifactRecord, artifact_id)
            if record is None:
                raise P5ArtifactRepositoryError(
                    f"missing extracted artifact in DB repository: {artifact_id}"
                )
            payload = json.loads(record.payload_json)
        return extracted_artifact_from_payload(payload)

    def save_dataset_artifact(self, dataset: P5DatasetArtifact) -> str:
        payload_json = json.dumps(
            dataset_artifact_to_payload(dataset),
            ensure_ascii=False,
            sort_keys=True,
        )
        with Session(self.engine) as session:
            record = session.get(DatasetArtifactRecord, dataset.dataset_id)
            if record is None:
                record = DatasetArtifactRecord(
                    dataset_id=dataset.dataset_id,
                    dataset_version=dataset.dataset_version,
                    issuer_count=dataset.issuer_count,
                    payload_json=payload_json,
                    created_at=dataset.created_at,
                )
                session.add(record)
            else:
                record.dataset_version = dataset.dataset_version
                record.issuer_count = dataset.issuer_count
                record.payload_json = payload_json
                record.created_at = dataset.created_at
            session.commit()
        return dataset.dataset_id

    def load_dataset_artifact(self, dataset_id: str) -> P5DatasetArtifact:
        with Session(self.engine) as session:
            record = session.get(DatasetArtifactRecord, dataset_id)
            if record is None:
                raise P5ArtifactRepositoryError(
                    f"missing dataset artifact in DB repository: {dataset_id}"
                )
            payload = json.loads(record.payload_json)
        return dataset_artifact_from_payload(payload)

    def save_turtle_export(self, turtle_export: P5TurtleExport) -> str:
        payload_json = json.dumps(
            turtle_export_to_payload(turtle_export),
            ensure_ascii=False,
            sort_keys=True,
        )
        with Session(self.engine) as session:
            record = session.get(TurtleExportArtifactRecord, turtle_export.dataset_id)
            if record is None:
                record = TurtleExportArtifactRecord(
                    dataset_id=turtle_export.dataset_id,
                    dataset_version=turtle_export.dataset_version,
                    payload_json=payload_json,
                    created_at=turtle_export.created_at,
                )
                session.add(record)
            else:
                record.dataset_version = turtle_export.dataset_version
                record.payload_json = payload_json
                record.created_at = turtle_export.created_at
            session.commit()
        return turtle_export.dataset_id

    def load_turtle_export(self, dataset_id: str) -> P5TurtleExport:
        with Session(self.engine) as session:
            record = session.get(TurtleExportArtifactRecord, dataset_id)
            if record is None:
                raise P5ArtifactRepositoryError(
                    f"missing turtle export in DB repository: {dataset_id}"
                )
            payload = json.loads(record.payload_json)
        return turtle_export_from_payload(payload)

    def list_extracted_artifact_ids(
        self,
        *,
        issuer_id: str | None = None,
        fiscal_year: int | None = None,
    ) -> tuple[str, ...]:
        statement = select(ExtractedArtifactRecord.artifact_id).order_by(
            ExtractedArtifactRecord.artifact_id
        )
        if issuer_id is not None:
            statement = statement.where(ExtractedArtifactRecord.issuer_id == issuer_id)
        if fiscal_year is not None:
            statement = statement.where(ExtractedArtifactRecord.fiscal_year == fiscal_year)
        with Session(self.engine) as session:
            artifact_ids = session.scalars(statement).all()
        return tuple(artifact_ids)

    def save_extracted_review_surface(
        self,
        surface: P5ExtractedReviewSurface,
    ) -> str:
        payload_json = json.dumps(
            extracted_review_surface_to_payload(surface),
            ensure_ascii=False,
            sort_keys=True,
        )
        with Session(self.engine) as session:
            record = session.get(ExtractedReviewSurfaceRecord, surface.artifact_id)
            if record is None:
                record = ExtractedReviewSurfaceRecord(
                    artifact_id=surface.artifact_id,
                    payload_json=payload_json,
                )
                session.add(record)
            else:
                record.payload_json = payload_json
            session.commit()
        return surface.artifact_id

    def load_extracted_review_surface(
        self,
        artifact_id: str,
    ) -> P5ExtractedReviewSurface:
        with Session(self.engine) as session:
            record = session.get(ExtractedReviewSurfaceRecord, artifact_id)
            if record is None:
                raise P5ArtifactRepositoryError(
                    f"missing extracted review surface in DB repository: {artifact_id}"
                )
            payload = json.loads(record.payload_json)
        return extracted_review_surface_from_payload(payload)

    def save_dataset_review_surface(
        self,
        surface: P5DatasetReviewSurface,
    ) -> str:
        payload_json = json.dumps(
            dataset_review_surface_to_payload(surface),
            ensure_ascii=False,
            sort_keys=True,
        )
        with Session(self.engine) as session:
            record = session.get(DatasetReviewSurfaceRecord, surface.dataset_id)
            if record is None:
                record = DatasetReviewSurfaceRecord(
                    dataset_id=surface.dataset_id,
                    payload_json=payload_json,
                )
                session.add(record)
            else:
                record.payload_json = payload_json
            session.commit()
        return surface.dataset_id

    def load_dataset_review_surface(self, dataset_id: str) -> P5DatasetReviewSurface:
        with Session(self.engine) as session:
            record = session.get(DatasetReviewSurfaceRecord, dataset_id)
            if record is None:
                raise P5ArtifactRepositoryError(
                    f"missing dataset review surface in DB repository: {dataset_id}"
                )
            payload = json.loads(record.payload_json)
        return dataset_review_surface_from_payload(payload)

    def save_turtle_export_review_surface(
        self,
        surface: P5TurtleExportReviewSurface,
    ) -> str:
        payload_json = json.dumps(
            turtle_export_review_surface_to_payload(surface),
            ensure_ascii=False,
            sort_keys=True,
        )
        with Session(self.engine) as session:
            record = session.get(TurtleExportReviewSurfaceRecord, surface.dataset_id)
            if record is None:
                record = TurtleExportReviewSurfaceRecord(
                    dataset_id=surface.dataset_id,
                    payload_json=payload_json,
                )
                session.add(record)
            else:
                record.payload_json = payload_json
            session.commit()
        return surface.dataset_id

    def load_turtle_export_review_surface(
        self,
        dataset_id: str,
    ) -> P5TurtleExportReviewSurface:
        with Session(self.engine) as session:
            record = session.get(TurtleExportReviewSurfaceRecord, dataset_id)
            if record is None:
                raise P5ArtifactRepositoryError(
                    f"missing turtle export review surface in DB repository: {dataset_id}"
                )
            payload = json.loads(record.payload_json)
        return turtle_export_review_surface_from_payload(payload)

    def save_lineage_records(
        self,
        lineage_records: tuple[P5ArtifactLineage, ...],
    ) -> int:
        if not lineage_records:
            return 0
        dataset_ids = {lineage.dataset_id for lineage in lineage_records}
        if len(dataset_ids) != 1:
            raise ValueError("lineage records must belong to exactly one dataset")
        dataset_id = lineage_records[0].dataset_id
        with Session(self.engine) as session:
            session.query(DatasetLineageRecord).filter(
                DatasetLineageRecord.dataset_id == dataset_id
            ).delete()
            for lineage in lineage_records:
                session.add(
                    DatasetLineageRecord(
                        dataset_id=lineage.dataset_id,
                        source_artifact_id=lineage.source_artifact_id,
                        payload_json=json.dumps(
                            artifact_lineage_to_payload(lineage),
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    )
                )
            session.commit()
        return len(lineage_records)

    def list_lineage_records(
        self,
        *,
        dataset_id: str | None = None,
        source_artifact_id: str | None = None,
    ) -> tuple[P5ArtifactLineage, ...]:
        statement = select(DatasetLineageRecord).order_by(DatasetLineageRecord.lineage_id)
        if dataset_id is not None:
            statement = statement.where(DatasetLineageRecord.dataset_id == dataset_id)
        if source_artifact_id is not None:
            statement = statement.where(
                DatasetLineageRecord.source_artifact_id == source_artifact_id
            )
        with Session(self.engine) as session:
            records = session.scalars(statement).all()
        return tuple(
            artifact_lineage_from_payload(json.loads(record.payload_json))
            for record in records
        )

    def save_recompute_result(
        self,
        *,
        run_id: str,
        plan: P5RecomputePlan,
        result: P5RecomputeResult,
    ) -> str:
        target_artifact_ids_json = json.dumps(
            list(plan.target_artifact_ids),
            ensure_ascii=False,
            sort_keys=True,
        )
        diff_summary_json = json.dumps(
            recompute_diff_summary_to_payload(result.diff_summary),
            ensure_ascii=False,
            sort_keys=True,
        )
        result_json = json.dumps(
            recompute_result_to_payload(result),
            ensure_ascii=False,
            sort_keys=True,
        )
        with Session(self.engine) as session:
            record = session.get(RecomputeRunRecord, run_id)
            if record is None:
                record = RecomputeRunRecord(
                    run_id=run_id,
                    manifest_id=plan.manifest_id,
                    dataset_id=plan.dataset_id,
                    reason=plan.reason,
                    target_artifact_ids_json=target_artifact_ids_json,
                    diff_summary_json=diff_summary_json,
                    result_json=result_json,
                )
                session.add(record)
            else:
                record.manifest_id = plan.manifest_id
                record.dataset_id = plan.dataset_id
                record.reason = plan.reason
                record.target_artifact_ids_json = target_artifact_ids_json
                record.diff_summary_json = diff_summary_json
                record.result_json = result_json
            session.commit()
        return run_id

    def load_recompute_result(self, run_id: str) -> P5RecomputeResult:
        with Session(self.engine) as session:
            record = session.get(RecomputeRunRecord, run_id)
            if record is None or record.result_json is None:
                raise P5ArtifactRepositoryError(
                    f"missing recompute result in DB repository: {run_id}"
                )
            payload = json.loads(record.result_json)
        return recompute_result_from_payload(payload)

    def load_dataset_audit_view(self, dataset_id: str) -> DatasetAuditView:
        dataset = self.load_dataset_artifact(dataset_id)
        with Session(self.engine) as session:
            dataset_review_record = session.get(DatasetReviewSurfaceRecord, dataset_id)
            turtle_review_record = session.get(TurtleExportReviewSurfaceRecord, dataset_id)
            recompute_record = session.scalar(
                select(RecomputeRunRecord)
                .where(RecomputeRunRecord.dataset_id == dataset_id)
                .order_by(RecomputeRunRecord.created_at.desc(), RecomputeRunRecord.run_id.desc())
                .limit(1)
            )

            source_artifacts: list[SourceArtifactAuditRecord] = []
            for artifact_id in dataset.source_artifacts:
                artifact_record = session.get(ExtractedArtifactRecord, artifact_id)
                if artifact_record is None:
                    raise P5ArtifactRepositoryError(
                        "dataset audit view references missing source artifact in DB "
                        f"repository: {artifact_id}"
                    )
                report = session.get(ReportRecord, artifact_record.report_id)
                extracted_artifact = extracted_artifact_from_payload(
                    json.loads(artifact_record.payload_json)
                )
                extracted_review_record = session.get(
                    ExtractedReviewSurfaceRecord,
                    artifact_id,
                )
                extracted_review_surface = (
                    extracted_review_surface_from_payload(
                        json.loads(extracted_review_record.payload_json)
                    )
                    if extracted_review_record is not None
                    else None
                )
                source_artifacts.append(
                    SourceArtifactAuditRecord(
                        source_artifact_id=artifact_id,
                        report_id=report.report_id if report is not None else None,
                        source_pdf_path=str(extracted_artifact.source_pdf_path),
                        manifest_entry_key=(
                            extracted_review_surface.manifest_entry_key
                            if extracted_review_surface is not None
                            else None
                        ),
                        extracted_review_surface=extracted_review_surface,
                    )
                )

        return DatasetAuditView(
            dataset_id=dataset_id,
            source_artifact_ids=dataset.source_artifacts,
            source_artifacts=tuple(source_artifacts),
            dataset_review_surface=(
                dataset_review_surface_from_payload(
                    json.loads(dataset_review_record.payload_json)
                )
                if dataset_review_record is not None
                else None
            ),
            turtle_export_review_surface=(
                turtle_export_review_surface_from_payload(
                    json.loads(turtle_review_record.payload_json)
                )
                if turtle_review_record is not None
                else None
            ),
            latest_recompute_run_id=(
                recompute_record.run_id if recompute_record is not None else None
            ),
            latest_recompute_reason=(
                recompute_record.reason if recompute_record is not None else None
            ),
        )

    def save_statement_tables(
        self,
        *,
        extraction_run_id: str,
        document_version_id: str,
        tables: tuple[ParsedTable, ...],
    ) -> tuple[StatementTableLedgerEntry, ...]:
        entries: list[StatementTableLedgerEntry] = []
        with Session(self.engine) as session:
            for table in tables:
                statement_table_id = build_statement_table_id(
                    extraction_run_id,
                    table.table_id,
                )
                row_ids = tuple(
                    build_statement_table_row_id(statement_table_id, row.row_index)
                    for row in table.body_rows
                )
                column_candidates = (*table.period_columns, *table.comparison_columns)
                column_ids = tuple(
                    build_statement_table_column_id(
                        statement_table_id,
                        column.column_index,
                    )
                    for column in column_candidates
                )
                record = session.get(StatementTableRecord, statement_table_id)
                if record is None:
                    record = StatementTableRecord(
                        statement_table_id=statement_table_id,
                        extraction_run_id=extraction_run_id,
                        document_version_id=document_version_id,
                        table_family=table.table_kind,
                        statement_type=table.table_kind,
                        payload_json=None,
                    )
                    session.add(record)
                else:
                    record.extraction_run_id = extraction_run_id
                    record.document_version_id = document_version_id
                    record.table_family = table.table_kind
                    record.statement_type = table.table_kind

                for row in table.body_rows:
                    row_id = build_statement_table_row_id(
                        statement_table_id,
                        row.row_index,
                    )
                    row_record = session.get(StatementTableRowRecord, row_id)
                    row_payload = json.dumps(asdict(row), ensure_ascii=False, sort_keys=True)
                    if row_record is None:
                        row_record = StatementTableRowRecord(
                            statement_table_row_id=row_id,
                            statement_table_id=statement_table_id,
                            row_index=row.row_index,
                            payload_json=row_payload,
                        )
                        session.add(row_record)
                    else:
                        row_record.statement_table_id = statement_table_id
                        row_record.row_index = row.row_index
                        row_record.payload_json = row_payload

                for column in column_candidates:
                    column_id = build_statement_table_column_id(
                        statement_table_id,
                        column.column_index,
                    )
                    column_record = session.get(StatementTableColumnRecord, column_id)
                    column_payload = json.dumps(asdict(column), ensure_ascii=False, sort_keys=True)
                    if column_record is None:
                        column_record = StatementTableColumnRecord(
                            statement_table_column_id=column_id,
                            statement_table_id=statement_table_id,
                            column_index=column.column_index,
                            payload_json=column_payload,
                        )
                        session.add(column_record)
                    else:
                        column_record.statement_table_id = statement_table_id
                        column_record.column_index = column.column_index
                        column_record.payload_json = column_payload

                table_payloads = {
                    "table": {
                        "table_id": table.table_id,
                        "document_id": table.document_id,
                        "page_range": list(table.page_range),
                        "table_kind": table.table_kind,
                        "title_text": table.title_text,
                        "statement_scope_guess": table.statement_scope_guess,
                    },
                    "source_blocks": [asdict(block) for block in table.source_blocks],
                }
                payload_kinds = tuple(sorted(table_payloads))
                for payload_kind, payload in table_payloads.items():
                    payload_id = build_statement_table_payload_id(
                        statement_table_id,
                        payload_kind,
                    )
                    payload_record = session.get(
                        StatementTablePayloadRecord,
                        payload_id,
                    )
                    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                    if payload_record is None:
                        payload_record = StatementTablePayloadRecord(
                            statement_table_payload_id=payload_id,
                            statement_table_id=statement_table_id,
                            payload_kind=payload_kind,
                            payload_json=payload_json,
                        )
                        session.add(payload_record)
                    else:
                        payload_record.statement_table_id = statement_table_id
                        payload_record.payload_kind = payload_kind
                        payload_record.payload_json = payload_json

                entries.append(
                    StatementTableLedgerEntry(
                        statement_table_id=statement_table_id,
                        extraction_run_id=extraction_run_id,
                        document_version_id=document_version_id,
                        source_table_id=table.table_id,
                        table_family=table.table_kind,
                        statement_type=table.table_kind,
                        row_ids=row_ids,
                        column_ids=column_ids,
                        payload_kinds=payload_kinds,
                    )
                )
            session.commit()
        return tuple(entries)

    def list_statement_tables(
        self,
        *,
        extraction_run_id: str,
    ) -> tuple[StatementTableLedgerEntry, ...]:
        statement = (
            select(StatementTableRecord)
            .where(StatementTableRecord.extraction_run_id == extraction_run_id)
            .order_by(StatementTableRecord.statement_table_id)
        )
        with Session(self.engine) as session:
            records = session.scalars(statement).all()
            entries: list[StatementTableLedgerEntry] = []
            for record in records:
                row_ids = tuple(
                    session.scalars(
                        select(StatementTableRowRecord.statement_table_row_id)
                        .where(
                            StatementTableRowRecord.statement_table_id
                            == record.statement_table_id
                        )
                        .order_by(StatementTableRowRecord.row_index)
                    ).all()
                )
                column_ids = tuple(
                    session.scalars(
                        select(StatementTableColumnRecord.statement_table_column_id)
                        .where(
                            StatementTableColumnRecord.statement_table_id
                            == record.statement_table_id
                        )
                        .order_by(StatementTableColumnRecord.column_index)
                    ).all()
                )
                payload_kinds = tuple(
                    session.scalars(
                        select(StatementTablePayloadRecord.payload_kind)
                        .where(
                            StatementTablePayloadRecord.statement_table_id
                            == record.statement_table_id
                        )
                        .order_by(StatementTablePayloadRecord.payload_kind)
                    ).all()
                )
                table_payload_record = session.scalar(
                    select(StatementTablePayloadRecord)
                    .where(
                        StatementTablePayloadRecord.statement_table_id
                        == record.statement_table_id,
                        StatementTablePayloadRecord.payload_kind == "table",
                    )
                )
                source_table_id = record.statement_table_id
                if table_payload_record is not None and table_payload_record.payload_json:
                    payload = json.loads(table_payload_record.payload_json)
                    if isinstance(payload, dict):
                        source_table_id = str(payload.get("table_id", record.statement_table_id))
                entries.append(
                    StatementTableLedgerEntry(
                        statement_table_id=record.statement_table_id,
                        extraction_run_id=record.extraction_run_id,
                        document_version_id=record.document_version_id,
                        source_table_id=source_table_id,
                        table_family=record.table_family,
                        statement_type=record.statement_type,
                        row_ids=row_ids,
                        column_ids=column_ids,
                        payload_kinds=payload_kinds,
                    )
                )
        return tuple(entries)

    def save_fact_set(
        self,
        *,
        fact_set_id: str,
        extraction_run_id: str,
        fact_set_kind: str,
        status: str,
        facts: tuple[CandidateFact | CanonicalFact | DerivedFact, ...],
    ) -> FactSetLedgerEntry:
        lineage_record_ids: list[str] = []
        with Session(self.engine) as session:
            fact_set_record = session.get(FactSetRecord, fact_set_id)
            if fact_set_record is None:
                fact_set_record = FactSetRecord(
                    fact_set_id=fact_set_id,
                    extraction_run_id=extraction_run_id,
                    fact_set_kind=fact_set_kind,
                    status=status,
                )
                session.add(fact_set_record)
            else:
                fact_set_record.extraction_run_id = extraction_run_id
                fact_set_record.fact_set_kind = fact_set_kind
                fact_set_record.status = status

            if fact_set_kind == "candidate":
                session.query(CandidateFactRecord).filter(
                    CandidateFactRecord.fact_set_id == fact_set_id
                ).delete()
            elif fact_set_kind == "canonical":
                session.query(CanonicalFactRecord).filter(
                    CanonicalFactRecord.fact_set_id == fact_set_id
                ).delete()
            elif fact_set_kind == "derived":
                session.query(DerivedFactRecord).filter(
                    DerivedFactRecord.fact_set_id == fact_set_id
                ).delete()
            else:
                raise ValueError(f"unsupported fact_set_kind: {fact_set_kind}")

            session.query(FactLineageRecord).filter(
                FactLineageRecord.fact_set_id == fact_set_id
            ).delete()

            for fact in facts:
                payload_json = json.dumps(asdict(fact), ensure_ascii=False, sort_keys=True)
                if fact_set_kind == "candidate":
                    session.add(
                        CandidateFactRecord(
                            fact_id=fact.fact_id,
                            fact_set_id=fact_set_id,
                            payload_json=payload_json,
                        )
                    )
                elif fact_set_kind == "canonical":
                    session.add(
                        CanonicalFactRecord(
                            fact_id=fact.fact_id,
                            fact_set_id=fact_set_id,
                            payload_json=payload_json,
                        )
                    )
                    assert isinstance(fact, CanonicalFact)
                    for source_fact_id in fact.source_candidate_fact_ids:
                        lineage_record_id = build_fact_lineage_record_id(
                            fact_set_id,
                            source_fact_id,
                            fact.fact_id,
                            "candidate_to_canonical",
                        )
                        lineage_record_ids.append(lineage_record_id)
                        session.add(
                            FactLineageRecord(
                                fact_lineage_record_id=lineage_record_id,
                                fact_set_id=fact_set_id,
                                source_fact_id=source_fact_id,
                                target_fact_id=fact.fact_id,
                                lineage_kind="candidate_to_canonical",
                                payload_json=None,
                            )
                        )
                elif fact_set_kind == "derived":
                    session.add(
                        DerivedFactRecord(
                            fact_id=fact.fact_id,
                            fact_set_id=fact_set_id,
                            payload_json=payload_json,
                        )
                    )
                    assert isinstance(fact, DerivedFact)
                    for source_fact_id in fact.source_canonical_fact_ids:
                        lineage_record_id = build_fact_lineage_record_id(
                            fact_set_id,
                            source_fact_id,
                            fact.fact_id,
                            "canonical_to_derived",
                        )
                        lineage_record_ids.append(lineage_record_id)
                        session.add(
                            FactLineageRecord(
                                fact_lineage_record_id=lineage_record_id,
                                fact_set_id=fact_set_id,
                                source_fact_id=source_fact_id,
                                target_fact_id=fact.fact_id,
                                lineage_kind="canonical_to_derived",
                                payload_json=None,
                            )
                        )
            session.commit()
        return FactSetLedgerEntry(
            fact_set_id=fact_set_id,
            extraction_run_id=extraction_run_id,
            fact_set_kind=fact_set_kind,
            status=status,
            fact_ids=tuple(fact.fact_id for fact in facts),
            lineage_record_ids=tuple(lineage_record_ids),
        )

    def list_fact_sets(
        self,
        *,
        extraction_run_id: str,
    ) -> tuple[FactSetLedgerEntry, ...]:
        statement = (
            select(FactSetRecord)
            .where(FactSetRecord.extraction_run_id == extraction_run_id)
            .order_by(FactSetRecord.fact_set_kind, FactSetRecord.fact_set_id)
        )
        with Session(self.engine) as session:
            fact_set_records = session.scalars(statement).all()
            entries: list[FactSetLedgerEntry] = []
            for record in fact_set_records:
                if record.fact_set_kind == "candidate":
                    fact_ids = tuple(
                        session.scalars(
                            select(CandidateFactRecord.fact_id)
                            .where(CandidateFactRecord.fact_set_id == record.fact_set_id)
                            .order_by(CandidateFactRecord.fact_id)
                        ).all()
                    )
                elif record.fact_set_kind == "canonical":
                    fact_ids = tuple(
                        session.scalars(
                            select(CanonicalFactRecord.fact_id)
                            .where(CanonicalFactRecord.fact_set_id == record.fact_set_id)
                            .order_by(CanonicalFactRecord.fact_id)
                        ).all()
                    )
                else:
                    fact_ids = tuple(
                        session.scalars(
                            select(DerivedFactRecord.fact_id)
                            .where(DerivedFactRecord.fact_set_id == record.fact_set_id)
                            .order_by(DerivedFactRecord.fact_id)
                        ).all()
                    )
                lineage_record_ids = tuple(
                    session.scalars(
                        select(FactLineageRecord.fact_lineage_record_id)
                        .where(FactLineageRecord.fact_set_id == record.fact_set_id)
                        .order_by(FactLineageRecord.fact_lineage_record_id)
                    ).all()
                )
                entries.append(
                    FactSetLedgerEntry(
                        fact_set_id=record.fact_set_id,
                        extraction_run_id=record.extraction_run_id,
                        fact_set_kind=record.fact_set_kind,
                        status=record.status,
                        fact_ids=fact_ids,
                        lineage_record_ids=lineage_record_ids,
                    )
                )
        return tuple(entries)

    def save_validation_result(
        self,
        *,
        validation_report_id: str,
        extraction_run_id: str,
        fact_set_id: str,
        overall_status: str,
        issue_codes: tuple[str, ...],
        quality_gate_status: str,
        summary: dict[str, object] | None = None,
    ) -> ValidationLedgerEntry:
        quality_gate_result_id = build_quality_gate_result_id(validation_report_id)
        issue_ids: list[str] = []
        with Session(self.engine) as session:
            report_record = session.get(ValidationReportRecord, validation_report_id)
            summary_json = (
                json.dumps(summary, ensure_ascii=False, sort_keys=True)
                if summary is not None
                else None
            )
            if report_record is None:
                report_record = ValidationReportRecord(
                    validation_report_id=validation_report_id,
                    extraction_run_id=extraction_run_id,
                    fact_set_id=fact_set_id,
                    overall_status=overall_status,
                    summary_json=summary_json,
                )
                session.add(report_record)
            else:
                report_record.extraction_run_id = extraction_run_id
                report_record.fact_set_id = fact_set_id
                report_record.overall_status = overall_status
                report_record.summary_json = summary_json

            session.query(ValidationIssueRecord).filter(
                ValidationIssueRecord.validation_report_id == validation_report_id
            ).delete()
            for index, issue_code in enumerate(issue_codes):
                issue_id = build_validation_issue_id(
                    validation_report_id,
                    issue_code,
                    index,
                )
                issue_ids.append(issue_id)
                session.add(
                    ValidationIssueRecord(
                        validation_issue_id=issue_id,
                        validation_report_id=validation_report_id,
                        issue_code=issue_code,
                        issue_level="error",
                        payload_json=None,
                    )
                )

            quality_record = session.get(QualityGateResultRecord, quality_gate_result_id)
            if quality_record is None:
                quality_record = QualityGateResultRecord(
                    quality_gate_result_id=quality_gate_result_id,
                    validation_report_id=validation_report_id,
                    status=quality_gate_status,
                    summary_json=summary_json,
                )
                session.add(quality_record)
            else:
                quality_record.validation_report_id = validation_report_id
                quality_record.status = quality_gate_status
                quality_record.summary_json = summary_json
            session.commit()
        return ValidationLedgerEntry(
            validation_report_id=validation_report_id,
            extraction_run_id=extraction_run_id,
            fact_set_id=fact_set_id,
            overall_status=overall_status,
            issue_ids=tuple(issue_ids),
            issue_codes=issue_codes,
            quality_gate_result_id=quality_gate_result_id,
            quality_gate_status=quality_gate_status,
        )

    def load_validation_result(self, validation_report_id: str) -> ValidationLedgerEntry:
        with Session(self.engine) as session:
            report_record = session.get(ValidationReportRecord, validation_report_id)
            if report_record is None:
                raise P5ArtifactRepositoryError(
                    f"missing validation result in DB repository: {validation_report_id}"
                )
            issue_rows = session.scalars(
                select(ValidationIssueRecord)
                .where(ValidationIssueRecord.validation_report_id == validation_report_id)
                .order_by(ValidationIssueRecord.validation_issue_id)
            ).all()
            quality_record = session.scalar(
                select(QualityGateResultRecord).where(
                    QualityGateResultRecord.validation_report_id == validation_report_id
                )
            )
            if quality_record is None:
                raise P5ArtifactRepositoryError(
                    "missing quality gate result for validation report in DB repository: "
                    f"{validation_report_id}"
                )
        return ValidationLedgerEntry(
            validation_report_id=validation_report_id,
            extraction_run_id=report_record.extraction_run_id,
            fact_set_id=report_record.fact_set_id,
            overall_status=report_record.overall_status,
            issue_ids=tuple(issue.validation_issue_id for issue in issue_rows),
            issue_codes=tuple(issue.issue_code for issue in issue_rows),
            quality_gate_result_id=quality_record.quality_gate_result_id,
            quality_gate_status=quality_record.status,
        )

    @staticmethod
    def _upsert_issuer(session: Session, artifact: P5ExtractedArtifact) -> None:
        entry = artifact.manifest_entry
        issuer = session.get(IssuerRecord, entry.issuer_id)
        if issuer is None:
            issuer = IssuerRecord(
                issuer_id=entry.issuer_id,
                market=entry.market,
                stock_code=entry.stock_code,
                company_name=entry.company_name,
            )
            session.add(issuer)
            return
        issuer.market = entry.market
        issuer.stock_code = entry.stock_code
        issuer.company_name = entry.company_name

    @staticmethod
    def _upsert_report(session: Session, artifact: P5ExtractedArtifact) -> ReportRecord:
        entry = artifact.manifest_entry
        statement = select(ReportRecord).where(
            ReportRecord.issuer_id == entry.issuer_id,
            ReportRecord.fiscal_year == entry.fiscal_year,
            ReportRecord.report_type == entry.report_type,
        )
        report = session.scalar(statement)
        if report is None:
            report = ReportRecord(
                issuer_id=entry.issuer_id,
                fiscal_year=entry.fiscal_year,
                report_type=entry.report_type,
                source=entry.source,
                report_language=entry.report_language,
                pdf_path=str(entry.pdf_path),
            )
            session.add(report)
            session.flush()
            return report
        report.source = entry.source
        report.report_language = entry.report_language
        report.pdf_path = str(entry.pdf_path)
        session.flush()
        return report

    @staticmethod
    def _upsert_manifest_entry(
        session: Session,
        *,
        manifest_id: str,
        manifest_version: str,
        artifact: P5ExtractedArtifact,
    ) -> None:
        entry = artifact.manifest_entry
        manifest = session.get(ManifestRecord, manifest_id)
        if manifest is None:
            manifest = ManifestRecord(
                manifest_id=manifest_id,
                manifest_version=manifest_version,
            )
            session.add(manifest)
        else:
            manifest.manifest_version = manifest_version

        statement = select(ManifestEntryRecord).where(
            ManifestEntryRecord.manifest_id == manifest_id,
            ManifestEntryRecord.issuer_id == entry.issuer_id,
            ManifestEntryRecord.fiscal_year == entry.fiscal_year,
            ManifestEntryRecord.report_type == entry.report_type,
        )
        manifest_entry = session.scalar(statement)
        if manifest_entry is None:
            manifest_entry = ManifestEntryRecord(
                manifest_id=manifest_id,
                issuer_id=entry.issuer_id,
                fiscal_year=entry.fiscal_year,
                report_type=entry.report_type,
                artifact_id=artifact.artifact_id,
            )
            session.add(manifest_entry)
            return
        manifest_entry.artifact_id = artifact.artifact_id
