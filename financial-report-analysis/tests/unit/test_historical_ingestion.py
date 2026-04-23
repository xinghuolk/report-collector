from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from financial_report_analysis.p5.models import P5ExtractedArtifact, P5Manifest, P5ManifestEntry
from financial_report_analysis.storage.database import create_sqlite_engine, initialize_database
from financial_report_analysis.storage.historical_ingestion import HistoricalIngestionService
from financial_report_analysis.storage.models import (
    ManifestEntryRecord,
    ManifestRecord,
    ReportRecord,
)
from financial_report_analysis.storage.repositories import SqlAlchemyP5ArtifactRepository


def _entry(tmp_path: Path, *, fiscal_year: int = 2025) -> P5ManifestEntry:
    pdf_path = tmp_path / f"CN_601919_{fiscal_year}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    return P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=fiscal_year,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
        company_name="中远海控",
        report_language="zh",
    )


def _artifact(entry: P5ManifestEntry) -> P5ExtractedArtifact:
    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={"document_id": str(entry.pdf_path), "pdf_path": str(entry.pdf_path)},
        document_metadata={},
        candidate_facts=(),
        canonical_facts=(),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={},
        created_at="2026-04-23T00:00:00+00:00",
    )


def test_register_report_deduplicates_same_issuer_year_and_report_type(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    service = HistoricalIngestionService(engine)
    entry = _entry(tmp_path)

    first = service.register_report(entry)
    second = service.register_report(entry)

    assert first.report_id == second.report_id

    with Session(engine) as session:
        report_count = session.scalar(select(func.count()).select_from(ReportRecord))

    assert report_count == 1


def test_register_report_binds_local_pdf_path(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    service = HistoricalIngestionService(engine)
    entry = _entry(tmp_path)

    registration = service.register_report(entry)

    with Session(engine) as session:
        report = session.get(ReportRecord, registration.report_id)

    assert report is not None
    assert report.pdf_path == str(entry.pdf_path)


def test_register_report_marks_missing_artifact_when_no_extracted_artifact_exists(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    service = HistoricalIngestionService(engine)

    registration = service.register_report(_entry(tmp_path))

    assert registration.artifact_status == "missing"


def test_register_report_marks_available_artifact_when_extracted_artifact_exists(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    service = HistoricalIngestionService(engine)
    entry = _entry(tmp_path)

    repository = SqlAlchemyP5ArtifactRepository(engine)
    repository.save_extracted_artifact(_artifact(entry))

    registration = service.register_report(entry)

    assert registration.artifact_status == "available"


def test_register_manifest_creates_manifest_and_manifest_entries(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    service = HistoricalIngestionService(engine)
    manifest = P5Manifest(
        manifest_id="p5_seed",
        manifest_version="1.0",
        entries=(_entry(tmp_path, fiscal_year=2024), _entry(tmp_path, fiscal_year=2025)),
    )

    registrations = service.register_manifest(manifest)

    assert len(registrations) == 2

    with Session(engine) as session:
        manifest_record = session.get(ManifestRecord, "p5_seed")
        manifest_entry_count = session.scalar(select(func.count()).select_from(ManifestEntryRecord))

    assert manifest_record is not None
    assert manifest_entry_count == 2


def test_register_manifest_is_atomic_when_a_later_entry_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    service = HistoricalIngestionService(engine)
    manifest = P5Manifest(
        manifest_id="p5_seed",
        manifest_version="1.0",
        entries=(_entry(tmp_path, fiscal_year=2024), _entry(tmp_path, fiscal_year=2025)),
    )

    original = service._upsert_manifest_entry
    call_count = 0

    def failing_upsert(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("boom")
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_upsert_manifest_entry", failing_upsert)

    with pytest.raises(RuntimeError, match="boom"):
        service.register_manifest(manifest)

    with Session(engine) as session:
        report_count = session.scalar(select(func.count()).select_from(ReportRecord))
        manifest_count = session.scalar(select(func.count()).select_from(ManifestRecord))
        manifest_entry_count = session.scalar(select(func.count()).select_from(ManifestEntryRecord))

    assert report_count == 0
    assert manifest_count == 0
    assert manifest_entry_count == 0
