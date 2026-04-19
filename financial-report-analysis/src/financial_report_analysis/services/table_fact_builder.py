from __future__ import annotations

from typing import Any

from financial_report_analysis.models import NormalizedTableSemantics
from financial_report_analysis.registries import MetricMappingRegistry


def build_table_candidate_facts(
    semantics_tables: list[NormalizedTableSemantics],
    *,
    registry: MetricMappingRegistry,
    document_id: str,
    market: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    candidate_index = 0
    for table in semantics_tables:
        for row in table.rows:
            for value in row.values:
                definition = registry.match(
                    table_kind=table.table_kind,
                    normalized_row_label=row.normalized_row_label,
                    value_time_shape=value.value_time_shape,
                    market=market,
                )
                if definition is None or value.numeric_value is None or value.period_id is None:
                    continue
                candidate_index += 1
                candidates.append(
                    _build_candidate_payload(
                        candidate_index=candidate_index,
                        definition=definition,
                        document_id=document_id,
                        table=table,
                        row=row,
                        value=value,
                        market=market,
                    )
                )
    return candidates


def _build_candidate_payload(
    *,
    candidate_index: int,
    definition: Any,
    document_id: str,
    table: NormalizedTableSemantics,
    row: Any,
    value: Any,
    market: str,
) -> dict[str, Any]:
    return {
        "fact_id": f"{document_id}:candidate:{candidate_index}",
        "fact_kind": "candidate",
        "metric_id": definition.metric_id,
        "metric_label_raw": row.label_raw,
        "statement_type": definition.statement_type,
        "entity_scope": _entity_scope(table.statement_scope_guess),
        "comparison_axis": value.comparison_axis or "current",
        "adjustment_basis": "reported",
        "period_id": value.period_id,
        "currency": table.table_currency or _default_currency(market),
        "raw_value": value.raw_text,
        "numeric_value": value.numeric_value,
        "raw_unit": table.table_unit,
        "normalized_unit": None,
        "precision": _precision(value.raw_text),
        "confidence": 0.9,
        "extensions": {
            "market": market,
            "accounting_standard": "OTHER",
            "statement_scope_guess": table.statement_scope_guess,
        },
        "document_id": document_id,
        "block_id": f"{table.table_id}:row:{row.row_id}",
        "page_index": 0,
        "table_id": table.table_id,
        "table_coord": (value.row_index, value.column_index),
        "evidence_bundle_id": f"{document_id}:bundle:table",
        "extraction_method": "table_semantics",
        "extraction_version": "v1",
        "source_rank_hint": _source_rank_hint(table.table_kind),
    }


def _entity_scope(statement_scope_guess: str) -> str:
    if statement_scope_guess == "parent_only":
        return "parent"
    if statement_scope_guess == "consolidated":
        return "consolidated"
    return "other"


def _default_currency(market: str) -> str:
    if market == "HK":
        return "HKD"
    if market == "US":
        return "USD"
    return "CNY"


def _source_rank_hint(table_kind: str) -> int:
    if table_kind == "income_statement":
        return 30
    if table_kind == "cash_flow_statement":
        return 25
    if table_kind == "balance_sheet":
        return 20
    if table_kind == "metrics":
        return 10
    return 5


def _precision(raw_text: str) -> int:
    if "." not in raw_text:
        return 0
    return len(raw_text.split(".", maxsplit=1)[1].rstrip("0"))
