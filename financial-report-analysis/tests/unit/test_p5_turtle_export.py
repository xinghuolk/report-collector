from __future__ import annotations

from financial_report_analysis.p5.models import P5DatasetArtifact, P5DatasetRow
from financial_report_analysis.p5.turtle_export import build_turtle_export


def test_build_turtle_export_maps_canonical_ids_to_turtle_aliases() -> None:
    dataset = P5DatasetArtifact(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00",
        issuer_count=1,
        periods=(2025,),
        metrics=("cash", "operating_cash_flow", "revenue"),
        rows=(
            P5DatasetRow(
                issuer_id="CN_601919",
                market="CN",
                stock_code="601919",
                fiscal_year=2025,
                metric_id="cash",
                entity_scope="consolidated",
                period_scope="point_in_time",
                statement_type="balance_sheet",
                value=100.0,
                currency="CNY",
                unit="currency_amount",
                quality_status="ok",
                missing_status="present",
                source_fact_id="fact-cash",
                source_artifact_id="CN_601919_2025",
                evidence_bundle_id="bundle-cash",
            ),
            P5DatasetRow(
                issuer_id="CN_601919",
                market="CN",
                stock_code="601919",
                fiscal_year=2025,
                metric_id="operating_cash_flow",
                entity_scope="consolidated",
                period_scope="duration",
                statement_type="cash_flow_statement",
                value=80.0,
                currency="CNY",
                unit="currency_amount",
                quality_status="ok",
                missing_status="present",
                source_fact_id="fact-ocf",
                source_artifact_id="CN_601919_2025",
                evidence_bundle_id="bundle-ocf",
            ),
        ),
        quality_summary={},
        source_artifacts=("CN_601919_2025",),
    )

    export = build_turtle_export(dataset)

    assert export.dataset_id == "p5_seed"
    assert export.dataset_version == "1.0"
    assert export.created_at == "2026-04-23T00:00:00"
    assert export.alias_map["cash"] == "money_cap"
    assert export.rows[0]["turtle_field"] == "money_cap"
    assert export.rows[1]["turtle_field"] == "n_cashflow_act"
    assert export.rows[0]["canonical_metric_id"] == "cash"
    assert export.rows[1]["canonical_metric_id"] == "operating_cash_flow"
