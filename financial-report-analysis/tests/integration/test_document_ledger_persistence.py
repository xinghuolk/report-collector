from __future__ import annotations

from pathlib import Path

from financial_report_analysis.models.facts import CanonicalFact, DerivedFact
from financial_report_analysis.models.table import ParsedColumn, ParsedRow, ParsedTable
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.services.validation_service import ValidationReport
from financial_report_analysis.storage.artifacts import (
    build_fact_set_id,
    build_validation_report_id,
)
from financial_report_analysis.storage.database import create_sqlite_engine, initialize_database
from financial_report_analysis.storage.historical_ingestion import HistoricalIngestionService
from financial_report_analysis.storage.repositories import SqlAlchemyP5ArtifactRepository


def _entry(tmp_path: Path) -> P5ManifestEntry:
    pdf_path = tmp_path / "CN_601919_2025.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    return P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
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
        canonical_facts=({"fact_id": "canonical-revenue-2025", "metric_id": "revenue"},),
        derived_facts=({"fact_id": "derived-revenue-ttm", "metric_id": "revenue_ttm"},),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={},
        created_at="2026-04-24T00:00:00+00:00",
    )


def _table(document_id: str) -> ParsedTable:
    return ParsedTable(
        table_id="table-income-1",
        document_id=document_id,
        page_range=(3, 4),
        table_kind="income_statement",
        title_text="合并利润表",
        body_rows=[
            ParsedRow(
                row_id="row-1",
                row_index=0,
                label_raw="营业收入",
                normalized_label_hint="revenue",
            )
        ],
        period_columns=[
            ParsedColumn(
                column_id="col-1",
                column_index=0,
                header_text="2025年",
                period_id="2025",
                value_time_shape="duration",
                comparison_axis=None,
                is_current=True,
            )
        ],
    )


def _canonical_fact(document_id: str) -> CanonicalFact:
    return CanonicalFact(
        fact_id="canonical-revenue-2025",
        metric_id="revenue",
        metric_label_raw="营业收入",
        statement_type="income_statement",
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        period_id="2025",
        currency="CNY",
        raw_value="100",
        numeric_value=100.0,
        raw_unit="元",
        normalized_unit="currency_amount",
        precision=0,
        confidence=0.99,
        source_candidate_fact_ids=["candidate-revenue-2025"],
        resolution_reason="deterministic",
        resolution_score=1.0,
        validation_flags=[],
        quality_status="ok",
        is_primary=True,
        evidence_bundle_id=f"bundle:{document_id}",
    )


def _derived_fact(document_id: str) -> DerivedFact:
    return DerivedFact(
        fact_id="derived-revenue-ttm",
        metric_id="revenue_ttm",
        metric_label_raw="营业收入TTM",
        statement_type="income_statement",
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        period_id="2025",
        currency="CNY",
        raw_value="100",
        numeric_value=100.0,
        raw_unit="元",
        normalized_unit="currency_amount",
        precision=0,
        confidence=0.95,
        source_canonical_fact_ids=["canonical-revenue-2025"],
        derivation_type="ttm",
        derivation_formula="sum(last_4_quarters)",
        derivation_version="v1",
        validation_status="ok",
        consistency_check_against_fact_id=None,
        evidence_bundle_id=f"bundle:{document_id}",
    )


def test_document_ledger_objects_coexist_with_artifact_snapshot(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)
    service = HistoricalIngestionService(engine)

    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    registration = service.register_report(entry)
    repository.save_extracted_artifact(artifact)

    identity = repository.ensure_document_version(
        report_id=registration.report_id,
        file_path=str(entry.pdf_path),
        document_payload=artifact.document,
        document_version_payload={"artifact_id": artifact.artifact_id},
    )
    extraction_run = repository.save_extraction_run(
        document_version_id=identity.document_version_id,
        pipeline_version=artifact.pipeline_version,
        status="completed",
        payload={"artifact_id": artifact.artifact_id, "quality_gate": artifact.quality_gate},
    )
    tables = repository.save_statement_tables(
        extraction_run_id=extraction_run.extraction_run_id,
        document_version_id=identity.document_version_id,
        tables=(_table(identity.document_id),),
    )
    canonical_set = repository.save_fact_set(
        fact_set_id=build_fact_set_id(identity.document_id, "canonical"),
        extraction_run_id=extraction_run.extraction_run_id,
        fact_set_kind="canonical",
        status="completed",
        facts=(_canonical_fact(identity.document_id),),
    )
    derived_set = repository.save_fact_set(
        fact_set_id=build_fact_set_id(identity.document_id, "derived"),
        extraction_run_id=extraction_run.extraction_run_id,
        fact_set_kind="derived",
        status="completed",
        facts=(_derived_fact(identity.document_id),),
    )
    validation = ValidationReport(
        overall_status="ok",
        canonical_fact_count=1,
        derived_fact_count=1,
        issues=(),
    )
    validation_entry = repository.save_validation_result(
        validation_report_id=build_validation_report_id(identity.document_id),
        extraction_run_id=extraction_run.extraction_run_id,
        fact_set_id=canonical_set.fact_set_id,
        overall_status=validation.overall_status,
        issue_codes=validation.issues,
        quality_gate_status=artifact.quality_gate,
        summary={
            "canonical_fact_count": validation.canonical_fact_count,
            "derived_fact_count": validation.derived_fact_count,
        },
    )

    loaded_artifact = repository.load_extracted_artifact(artifact.artifact_id)
    listed_tables = repository.list_statement_tables(
        extraction_run_id=extraction_run.extraction_run_id,
    )
    listed_fact_sets = repository.list_fact_sets(
        extraction_run_id=extraction_run.extraction_run_id,
    )
    loaded_validation = repository.load_validation_result(
        validation_entry.validation_report_id
    )

    assert loaded_artifact == artifact
    assert listed_tables == tables
    assert listed_fact_sets == (canonical_set, derived_set)
    assert loaded_validation == validation_entry
