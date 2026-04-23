from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

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
from .models import (
    DatasetLineageRecord,
    DatasetArtifactRecord,
    DatasetReviewSurfaceRecord,
    ExtractedArtifactRecord,
    ExtractedReviewSurfaceRecord,
    IssuerRecord,
    RecomputeRunRecord,
    ReportRecord,
    TurtleExportArtifactRecord,
    TurtleExportReviewSurfaceRecord,
)


@dataclass(frozen=True, slots=True)
class EvidenceBundleItemLink:
    evidence_bundle_id: str
    evidence_item_id: str
    sort_order: int


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
            self._upsert_report(session, artifact)
            record = session.get(ExtractedArtifactRecord, artifact.artifact_id)
            if record is None:
                record = ExtractedArtifactRecord(
                    artifact_id=artifact.artifact_id,
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
    def _upsert_report(session: Session, artifact: P5ExtractedArtifact) -> None:
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
            return
        report.source = entry.source
        report.report_language = entry.report_language
        report.pdf_path = str(entry.pdf_path)
