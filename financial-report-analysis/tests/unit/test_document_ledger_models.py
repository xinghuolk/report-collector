from __future__ import annotations

from sqlalchemy import inspect

from financial_report_analysis.storage.artifacts import (
    build_document_id,
    build_document_version_id,
    build_extraction_run_id,
    build_report_file_id,
)
from financial_report_analysis.storage.database import create_sqlite_engine, initialize_database


def test_document_ledger_identity_builders_are_stable_and_layered() -> None:
    report_file_id = build_report_file_id(
        42,
        "report/downloads/cn_stocks/601919/annual/2025_年度报告.pdf",
    )
    document_id = build_document_id(report_file_id)
    source_document_version_id = build_document_version_id(document_id)
    normalized_document_version_id = build_document_version_id(
        document_id,
        version_label="normalized",
    )
    extraction_run_id = build_extraction_run_id(
        source_document_version_id,
        pipeline_version="p5-v1",
    )

    assert report_file_id == build_report_file_id(
        42,
        "report/downloads/cn_stocks/601919/annual/2025_年度报告.pdf",
    )
    assert report_file_id != build_report_file_id(
        42,
        "report/downloads/cn_stocks/601919/annual/2024_年度报告.pdf",
    )
    assert document_id == build_document_id(report_file_id)
    assert source_document_version_id != normalized_document_version_id
    assert extraction_run_id == build_extraction_run_id(
        source_document_version_id,
        pipeline_version="p5-v1",
    )
    assert extraction_run_id != build_extraction_run_id(
        source_document_version_id,
        pipeline_version="p5-v2",
    )


def test_document_ledger_tables_expose_minimum_unique_identity_constraints(
    tmp_path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    inspector = inspect(engine)

    def unique_column_sets(table_name: str) -> set[tuple[str, ...]]:
        return {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table_name)
        }

    assert ("report_id", "file_path") in unique_column_sets("report_files")
    assert ("report_file_id",) in unique_column_sets("documents")
    assert ("document_id", "version_label") in unique_column_sets("document_versions")
    assert ("document_version_id", "pipeline_version") in unique_column_sets(
        "extraction_runs"
    )


def test_document_ledger_tables_keep_expected_foreign_key_chain(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    inspector = inspect(engine)

    def fk_targets(table_name: str) -> set[tuple[str, str]]:
        return {
            (fk["constrained_columns"][0], fk["referred_table"])
            for fk in inspector.get_foreign_keys(table_name)
        }

    assert ("report_id", "reports") in fk_targets("report_files")
    assert ("report_file_id", "report_files") in fk_targets("documents")
    assert ("document_id", "documents") in fk_targets("document_versions")
    assert ("document_version_id", "document_versions") in fk_targets("extraction_runs")
