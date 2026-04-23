from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from financial_report_analysis.p5.models import P5Manifest, P5ManifestEntry
from financial_report_analysis.storage.models import (
    ExtractedArtifactRecord,
    IssuerRecord,
    ManifestEntryRecord,
    ManifestRecord,
    ReportRecord,
)

ArtifactStatus = Literal["missing", "available"]


@dataclass(frozen=True, slots=True)
class HistoricalReportRegistration:
    report_id: int
    issuer_id: str
    fiscal_year: int
    report_type: str
    pdf_path: str
    artifact_status: ArtifactStatus


class HistoricalIngestionService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def register_report(
        self,
        entry: P5ManifestEntry,
        *,
        manifest_id: str | None = None,
        manifest_version: str = "1.0",
    ) -> HistoricalReportRegistration:
        with Session(self.engine) as session:
            self._upsert_issuer(session, entry)
            report = self._upsert_report(session, entry)
            if manifest_id is not None:
                self._upsert_manifest_entry(
                    session,
                    manifest_id=manifest_id,
                    manifest_version=manifest_version,
                    entry=entry,
                )
            session.commit()

            artifact_status: ArtifactStatus = "missing"
            if session.get(ExtractedArtifactRecord, entry.artifact_id) is not None:
                artifact_status = "available"

            return HistoricalReportRegistration(
                report_id=report.report_id,
                issuer_id=entry.issuer_id,
                fiscal_year=entry.fiscal_year,
                report_type=entry.report_type,
                pdf_path=str(entry.pdf_path),
                artifact_status=artifact_status,
            )

    def register_manifest(
        self,
        manifest: P5Manifest,
    ) -> tuple[HistoricalReportRegistration, ...]:
        return tuple(
            self.register_report(
                entry,
                manifest_id=manifest.manifest_id,
                manifest_version=manifest.manifest_version,
            )
            for entry in manifest.entries
        )

    @staticmethod
    def _upsert_issuer(session: Session, entry: P5ManifestEntry) -> None:
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
    def _upsert_report(session: Session, entry: P5ManifestEntry) -> ReportRecord:
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
        entry: P5ManifestEntry,
    ) -> None:
        manifest = session.get(ManifestRecord, manifest_id)
        if manifest is None:
            manifest = ManifestRecord(
                manifest_id=manifest_id,
                manifest_version=manifest_version,
            )
            session.add(manifest)

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
                artifact_id=entry.artifact_id,
            )
            session.add(manifest_entry)
            return
        manifest_entry.artifact_id = entry.artifact_id
