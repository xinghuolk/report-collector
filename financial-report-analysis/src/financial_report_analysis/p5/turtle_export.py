from __future__ import annotations

from dataclasses import asdict

from financial_report_analysis.p5.models import P5DatasetArtifact, P5TurtleExport

TURTLE_ALIAS_MAP = {
    "operating_cost": "oper_cost",
    "operating_profit": "operate_profit",
    "net_profit": "n_income",
    "total_liabilities": "total_liab",
    "equity_attributable_to_owners": "total_hldr_eqy_exc_min_int",
    "operating_cash_flow": "n_cashflow_act",
    "investing_cash_flow": "n_cashflow_inv_act",
    "financing_cash_flow": "n_cash_flows_fnc_act",
    "cash": "money_cap",
}


def build_turtle_export(dataset: P5DatasetArtifact) -> P5TurtleExport:
    rows: list[dict[str, object]] = []
    for row in dataset.rows:
        payload = asdict(row)
        payload["canonical_metric_id"] = row.metric_id
        payload["turtle_field"] = TURTLE_ALIAS_MAP.get(row.metric_id, row.metric_id)
        rows.append(payload)

    return P5TurtleExport(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        created_at=dataset.created_at,
        rows=tuple(rows),
        alias_map=dict(TURTLE_ALIAS_MAP),
    )
