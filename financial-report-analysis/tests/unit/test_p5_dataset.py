from __future__ import annotations

from pathlib import Path

from financial_report_analysis.p5.dataset import assemble_dataset
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry


def _standard_extensions(period_scope: str) -> dict[str, object]:
    return {
        "period_scope": period_scope,
        "metric_governance": {
            "registry_status": "standard",
            "metric_namespace": "standard",
            "review_required": False,
            "auto_analysis_allowed": True,
            "governance_reason": "standard_metric",
        },
    }


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
                "extensions": _standard_extensions("duration"),
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
                "extensions": _standard_extensions("point_in_time"),
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


def test_assemble_dataset_includes_post_p5_profit_metric_rows(
    tmp_path: Path,
) -> None:
    artifact = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(
            {
                "fact_id": "fact-selling-general-administrative",
                "metric_id": "selling_general_administrative",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": -120.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-sga",
                "extensions": _standard_extensions("duration"),
            },
            {
                "fact_id": "fact-fv-value-chg-gain",
                "metric_id": "fv_value_chg_gain",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 18.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-fv-gain",
                "extensions": _standard_extensions("duration"),
            },
            {
                "fact_id": "fact-non-oper-income",
                "metric_id": "non_oper_income",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 6.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-non-oper-income",
                "extensions": _standard_extensions("duration"),
            },
            {
                "fact_id": "fact-non-oper-exp",
                "metric_id": "non_oper_exp",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": -3.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-non-oper-exp",
                "extensions": _standard_extensions("duration"),
            },
        ),
    )

    dataset = assemble_dataset(
        dataset_id="p5_seed",
        artifacts=(artifact,),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    rows_by_metric = {row.metric_id: row for row in dataset.rows}
    assert {
        "selling_general_administrative",
        "fv_value_chg_gain",
        "non_oper_income",
        "non_oper_exp",
    }.issubset(rows_by_metric)
    for metric_id in (
        "selling_general_administrative",
        "fv_value_chg_gain",
        "non_oper_income",
        "non_oper_exp",
    ):
        assert rows_by_metric[metric_id].missing_status == "present"
    assert rows_by_metric["selling_general_administrative"].value == -120.0
    assert rows_by_metric["fv_value_chg_gain"].statement_type == "income_statement"


def test_assemble_dataset_preserves_lifecycle_consumption_provenance(
    tmp_path: Path,
) -> None:
    provenance = {
        "source_review_item_id": "CN_601919_2025:candidate-1",
        "lifecycle_entry_id": "metric-lifecycle:1",
        "decision_id": "metric-lifecycle-decision:1",
        "decision_action": "map_to_standard",
        "source_candidate_metric_id": "custom::receivables",
        "target_metric_id": "accounts_receiv",
        "consumption_action": "map_to_standard",
    }
    artifact = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(
            {
                "fact_id": "fact-governed-receivables",
                "metric_id": "accounts_receiv",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 100.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-1",
                "extensions": {
                    "period_scope": "duration",
                    "metric_governance": {
                        "registry_status": "standard",
                        "metric_namespace": "standard",
                        "review_required": False,
                        "auto_analysis_allowed": True,
                        "governance_reason": "standard_metric",
                        "lifecycle_consumption": provenance,
                    },
                },
            },
            {
                "fact_id": "fact-revenue",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 200.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-2",
                "extensions": _standard_extensions("duration"),
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

    rows_by_metric = {row.metric_id: row for row in dataset.rows}
    assert rows_by_metric["accounts_receiv"].lifecycle_consumption == provenance
    assert rows_by_metric["revenue"].lifecycle_consumption is None
    assert rows_by_metric["cash"].lifecycle_consumption is None


def test_assemble_dataset_does_not_emit_present_missing_status_without_fact(
    tmp_path: Path,
) -> None:
    artifact = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(),
        missing_status={
            "cash_health_missing_status": {"restricted_cash": "present"},
        },
    )

    dataset = assemble_dataset(
        dataset_id="p5_seed",
        artifacts=(artifact,),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert len(dataset.rows) == 1
    row = dataset.rows[0]
    assert row.metric_id == "restricted_cash"
    assert row.missing_status == "not_surfaced"
    assert row.source_fact_id is None
    assert dataset.quality_summary["present_row_count"] == 0


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
                "extensions": _standard_extensions("duration"),
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
                "extensions": _standard_extensions("duration"),
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
                "extensions": _standard_extensions("point_in_time"),
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
                "extensions": _standard_extensions("duration"),
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
                "extensions": _standard_extensions("duration"),
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
                "extensions": _standard_extensions("duration"),
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
                "extensions": _standard_extensions("duration"),
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
                "extensions": _standard_extensions("duration"),
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


def test_assemble_dataset_blocks_non_consumable_governed_canonical_facts(
    tmp_path: Path,
) -> None:
    artifact = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(
            {
                "fact_id": "fact-custom-revenue",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 100.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-custom",
                "extensions": {
                    "period_scope": "duration",
                    "metric_governance": {
                        "registry_status": "provisional",
                        "metric_namespace": "custom",
                        "review_required": True,
                        "auto_analysis_allowed": False,
                        "governance_reason": "provisional_custom_metric",
                    },
                },
            },
        ),
        missing_status={
            "working_capital_missing_status": {"revenue": "present"},
        },
    )

    dataset = assemble_dataset(
        dataset_id="p5_seed",
        artifacts=(artifact,),
        required_metric_ids=("revenue",),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert len(dataset.rows) == 1
    row = dataset.rows[0]
    assert row.metric_id == "revenue"
    assert row.missing_status == "not_surfaced"
    assert row.source_fact_id is None
    assert dataset.quality_summary["present_row_count"] == 0
    assert dataset.quality_summary["governance_blocked_fact_count"] == 1
    assert dataset.quality_summary["governance_blocked_by_metric"] == {"revenue": 1}
    assert dataset.quality_summary["governance_blocked_by_reason"] == {
        "auto_analysis_not_allowed": 1
    }
    assert dataset.quality_summary["governance_blocked_source_fact_ids"] == [
        "fact-custom-revenue"
    ]


def test_assemble_dataset_blocks_missing_governance_metadata_by_default(
    tmp_path: Path,
) -> None:
    artifact = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(
            {
                "fact_id": "fact-legacy-revenue",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 100.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-legacy",
                "extensions": {"period_scope": "duration"},
            },
        ),
    )

    dataset = assemble_dataset(
        dataset_id="p5_seed",
        artifacts=(artifact,),
        required_metric_ids=("revenue",),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert dataset.rows[0].missing_status == "unknown"
    assert dataset.quality_summary["governance_blocked_fact_count"] == 1
    assert dataset.quality_summary["governance_blocked_by_reason"] == {
        "missing_metric_governance": 1
    }
