from __future__ import annotations

from pathlib import Path

from financial_report_analysis.p5.dataset import assemble_dataset
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry


def _artifact(
    *,
    tmp_path: Path,
    fiscal_year: int,
    canonical_facts: tuple[dict[str, object], ...],
    missing_status: dict[str, dict[str, str]] | None = None,
    quality_gate: str = "pass",
) -> P5ExtractedArtifact:
    pdf_path = tmp_path / f"report_{fiscal_year}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=fiscal_year,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
    )
    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={"document_id": str(pdf_path)},
        document_metadata={},
        candidate_facts=(),
        canonical_facts=canonical_facts,
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate=quality_gate,
        missing_status=missing_status or {},
        created_at="2026-04-23T00:00:00",
    )


def test_assemble_dataset_emits_present_rows_and_missing_status_rows(
    tmp_path: Path,
) -> None:
    artifact_2025 = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(
            {
                "fact_id": "fact-2025-revenue",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 100.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-1",
                "extensions": {"period_scope": "duration"},
            },
        ),
        missing_status={
            "asset_missing_status": {"goodwill": "not_surfaced"},
        },
    )
    artifact_2024 = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2024,
        canonical_facts=(
            {
                "fact_id": "fact-2024-cash",
                "metric_id": "cash",
                "statement_type": "balance_sheet",
                "entity_scope": "consolidated",
                "period_id": "2024FY",
                "numeric_value": 80.0,
                "currency": "CNY",
                "raw_unit": "CNY",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-2",
                "extensions": {"period_scope": "point_in_time"},
            },
        ),
        missing_status={
            "working_capital_missing_status": {"inventory": "out_of_scope"},
        },
    )

    dataset = assemble_dataset(
        dataset_id="p5_seed",
        artifacts=(artifact_2025, artifact_2024),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert dataset.dataset_id == "p5_seed"
    assert dataset.dataset_version == "1.0"
    assert dataset.created_at == "2026-04-23T00:00:00"
    assert dataset.issuer_count == 1
    assert dataset.periods == (2024, 2025)
    assert dataset.metrics == ("cash", "goodwill", "inventory", "revenue")
    assert dataset.source_artifacts == ("CN_601919_2024", "CN_601919_2025")

    rows_by_key = {
        (row.fiscal_year, row.metric_id, row.entity_scope, row.period_scope): row
        for row in dataset.rows
    }
    assert rows_by_key[(2025, "revenue", "consolidated", "duration")].value == 100.0
    assert rows_by_key[(2025, "revenue", "consolidated", "duration")].missing_status == "present"
    assert rows_by_key[(2025, "goodwill", "consolidated", "unknown")].missing_status == "not_surfaced"
    assert rows_by_key[(2024, "inventory", "consolidated", "unknown")].missing_status == "out_of_scope"
    assert dataset.quality_summary["unknown_count"] == 0
    assert dataset.quality_summary["duplicate_fact_conflicts"] == []


def test_assemble_dataset_dedupes_duplicate_canonical_facts_with_conflict_summary(
    tmp_path: Path,
) -> None:
    artifact = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(
            {
                "fact_id": "fact-revenue-a",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 100.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-a",
                "extensions": {"period_scope": "duration"},
            },
            {
                "fact_id": "fact-revenue-b",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 120.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-b",
                "extensions": {"period_scope": "duration"},
            },
        ),
    )

    dataset = assemble_dataset(
        dataset_id="p5_seed",
        artifacts=(artifact,),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert len(dataset.rows) == 2
    assert {
        (row.statement_type, row.source_fact_id, row.value) for row in dataset.rows
    } == {
        ("income_statement", "fact-revenue-a", 100.0),
        ("income_statement", "fact-revenue-b", 120.0),
    }
    assert dataset.quality_summary["duplicate_fact_conflicts"] == [
        {
            "issuer_id": "CN_601919",
            "fiscal_year": 2025,
            "metric_id": "revenue",
            "entity_scope": "consolidated",
            "period_scope": "duration",
            "statement_type": "income_statement",
            "values": [100.0, 120.0],
            "source_fact_ids": ["fact-revenue-a", "fact-revenue-b"],
        }
    ]


def test_assemble_dataset_adds_unknown_rows_for_required_metrics_without_present_facts(
    tmp_path: Path,
) -> None:
    artifact = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(),
        missing_status={},
        quality_gate="review",
    )

    dataset = assemble_dataset(
        dataset_id="p5_seed",
        artifacts=(artifact,),
        required_metric_ids=("cash", "revenue"),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    rows_by_metric = {row.metric_id: row for row in dataset.rows}
    assert rows_by_metric["cash"].missing_status == "unknown"
    assert rows_by_metric["revenue"].missing_status == "unknown"
    assert dataset.quality_summary["unknown_count"] == 2
    assert dataset.quality_summary["review_required_artifacts"] == ["CN_601919_2025"]


def test_assemble_dataset_keeps_missing_row_when_only_different_scope_is_present(
    tmp_path: Path,
) -> None:
    artifact = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(
            {
                "fact_id": "fact-cash-parent",
                "metric_id": "cash",
                "statement_type": "balance_sheet",
                "entity_scope": "parent_company",
                "period_id": "2025FY",
                "numeric_value": 80.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-parent",
                "extensions": {"period_scope": "point_in_time"},
            },
        ),
        missing_status={
            "asset_missing_status": {"cash": "absent"},
        },
    )

    dataset = assemble_dataset(
        dataset_id="p5_seed",
        artifacts=(artifact,),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    cash_rows = [row for row in dataset.rows if row.metric_id == "cash"]
    assert {row.entity_scope for row in cash_rows} == {"parent_company", "consolidated"}
    assert {row.missing_status for row in cash_rows} == {"present", "absent"}


def test_assemble_dataset_separates_duplicate_conflicts_by_statement_type(
    tmp_path: Path,
) -> None:
    artifact = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(
            {
                "fact_id": "fact-revenue-income",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 100.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-income",
                "extensions": {"period_scope": "duration"},
            },
            {
                "fact_id": "fact-revenue-cashflow",
                "metric_id": "revenue",
                "statement_type": "cash_flow_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 120.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-cashflow",
                "extensions": {"period_scope": "duration"},
            },
        ),
    )

    dataset = assemble_dataset(
        dataset_id="p5_seed",
        artifacts=(artifact,),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert len(dataset.rows) == 2
    assert {
        (row.statement_type, row.source_fact_id, row.value) for row in dataset.rows
    } == {
        ("income_statement", "fact-revenue-income", 100.0),
        ("cash_flow_statement", "fact-revenue-cashflow", 120.0),
    }
    assert dataset.quality_summary["duplicate_fact_conflicts"] == []


def test_assemble_dataset_preserves_statement_type_and_source_fact_lineage(
    tmp_path: Path,
) -> None:
    artifact = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(
            {
                "fact_id": "fact-revenue-income-a",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 100.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-income-a",
                "extensions": {"period_scope": "duration"},
            },
            {
                "fact_id": "fact-revenue-income-b",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 120.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-income-b",
                "extensions": {"period_scope": "duration"},
            },
            {
                "fact_id": "fact-revenue-cashflow",
                "metric_id": "revenue",
                "statement_type": "cash_flow_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 130.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-cashflow",
                "extensions": {"period_scope": "duration"},
            },
        ),
    )

    dataset = assemble_dataset(
        dataset_id="p5_seed",
        artifacts=(artifact,),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    revenue_rows = [row for row in dataset.rows if row.metric_id == "revenue"]
    assert len(revenue_rows) == 3
    assert {
        (row.statement_type, row.source_fact_id) for row in revenue_rows
    } == {
        ("income_statement", "fact-revenue-income-a"),
        ("income_statement", "fact-revenue-income-b"),
        ("cash_flow_statement", "fact-revenue-cashflow"),
    }
    assert dataset.quality_summary["duplicate_fact_conflicts"] == [
        {
            "issuer_id": "CN_601919",
            "fiscal_year": 2025,
            "metric_id": "revenue",
            "entity_scope": "consolidated",
            "period_scope": "duration",
            "statement_type": "income_statement",
            "values": [100.0, 120.0],
            "source_fact_ids": [
                "fact-revenue-income-a",
                "fact-revenue-income-b",
            ],
        }
    ]
