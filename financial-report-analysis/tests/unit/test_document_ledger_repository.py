from __future__ import annotations

from pathlib import Path

from financial_report_analysis.models.facts import CanonicalFact, DerivedFact
from financial_report_analysis.models.table import ParsedColumn, ParsedRow, ParsedTable
from financial_report_analysis.services.validation_service import ValidationReport
from financial_report_analysis.storage.artifacts import (
    build_fact_set_id,
    build_validation_report_id,
)
from financial_report_analysis.storage.database import create_sqlite_engine, initialize_database
from financial_report_analysis.storage.historical_ingestion import HistoricalIngestionService
from financial_report_analysis.storage.repositories import SqlAlchemyP5ArtifactRepository


def _report_entry(tmp_path: Path):
    pdf_path = tmp_path / "CN_601919_2025.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    from financial_report_analysis.p5.models import P5ManifestEntry

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


def _statement_table(document_id: str) -> ParsedTable:
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
            ),
            ParsedRow(
                row_id="row-2",
                row_index=1,
                label_raw="营业成本",
                normalized_label_hint="operating_cost",
            ),
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
            ),
            ParsedColumn(
                column_id="col-2",
                column_index=1,
                header_text="2024年",
                period_id="2024",
                value_time_shape="duration",
                comparison_axis="prior_year",
                is_comparison=True,
            ),
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


def test_repository_persists_document_version_identity_chain(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)
    service = HistoricalIngestionService(engine)
    entry = _report_entry(tmp_path)
    registration = service.register_report(entry)

    first = repository.ensure_document_version(
        report_id=registration.report_id,
        file_path=str(entry.pdf_path),
    )
    second = repository.ensure_document_version(
        report_id=registration.report_id,
        file_path=str(entry.pdf_path),
    )
    normalized = repository.ensure_document_version(
        report_id=registration.report_id,
        file_path=str(entry.pdf_path),
        version_label="normalized",
    )

    assert first == second
    assert first.report_file_id != ""
    assert first.document_id != ""
    assert first.document_version_id != ""
    assert normalized.document_version_id != first.document_version_id


def test_repository_persists_extraction_runs_and_statement_tables(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)
    service = HistoricalIngestionService(engine)
    entry = _report_entry(tmp_path)
    registration = service.register_report(entry)

    identity = repository.ensure_document_version(
        report_id=registration.report_id,
        file_path=str(entry.pdf_path),
    )
    extraction_run = repository.save_extraction_run(
        document_version_id=identity.document_version_id,
        pipeline_version="p5-v1",
        status="completed",
        payload={"quality_gate": "pass"},
    )

    saved_tables = repository.save_statement_tables(
        extraction_run_id=extraction_run.extraction_run_id,
        document_version_id=identity.document_version_id,
        tables=(_statement_table(identity.document_id),),
    )
    listed_tables = repository.list_statement_tables(
        extraction_run_id=extraction_run.extraction_run_id,
    )

    assert len(saved_tables) == 1
    assert listed_tables == saved_tables
    assert saved_tables[0].source_table_id == "table-income-1"
    assert len(saved_tables[0].row_ids) == 2
    assert len(saved_tables[0].column_ids) == 2
    assert saved_tables[0].payload_kinds == ("source_blocks", "table")


def test_repository_persists_fact_sets_and_validation_results(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)
    service = HistoricalIngestionService(engine)
    entry = _report_entry(tmp_path)
    registration = service.register_report(entry)

    identity = repository.ensure_document_version(
        report_id=registration.report_id,
        file_path=str(entry.pdf_path),
    )
    extraction_run = repository.save_extraction_run(
        document_version_id=identity.document_version_id,
        pipeline_version="p5-v1",
        status="completed",
    )

    canonical_fact_set = repository.save_fact_set(
        fact_set_id=build_fact_set_id(identity.document_id, "canonical"),
        extraction_run_id=extraction_run.extraction_run_id,
        fact_set_kind="canonical",
        status="completed",
        facts=(_canonical_fact(identity.document_id),),
    )
    derived_fact_set = repository.save_fact_set(
        fact_set_id=build_fact_set_id(identity.document_id, "derived"),
        extraction_run_id=extraction_run.extraction_run_id,
        fact_set_kind="derived",
        status="completed",
        facts=(_derived_fact(identity.document_id),),
    )
    listed_fact_sets = repository.list_fact_sets(
        extraction_run_id=extraction_run.extraction_run_id,
    )

    assert listed_fact_sets == (canonical_fact_set, derived_fact_set)
    assert canonical_fact_set.lineage_record_ids != ()
    assert derived_fact_set.lineage_record_ids != ()

    validation = ValidationReport(
        overall_status="ok",
        canonical_fact_count=1,
        derived_fact_count=1,
        issues=("derived_fact_references_missing_canonical_fact",),
    )
    validation_entry = repository.save_validation_result(
        validation_report_id=build_validation_report_id(identity.document_id),
        extraction_run_id=extraction_run.extraction_run_id,
        fact_set_id=canonical_fact_set.fact_set_id,
        overall_status=validation.overall_status,
        issue_codes=validation.issues,
        quality_gate_status="pass",
        summary={
            "canonical_fact_count": validation.canonical_fact_count,
            "derived_fact_count": validation.derived_fact_count,
        },
    )
    loaded_validation = repository.load_validation_result(
        validation_entry.validation_report_id
    )

    assert loaded_validation == validation_entry
