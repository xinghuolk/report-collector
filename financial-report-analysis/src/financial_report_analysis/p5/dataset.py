from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Callable, Mapping, cast

from financial_report_analysis.p5.models import (
    MissingStatus,
    P5DatasetArtifact,
    P5DatasetRow,
    P5ExtractedArtifact,
)

P5_DATASET_VERSION = "1.0"
_MISSING_STATUS_VALUES: tuple[MissingStatus, ...] = (
    "present",
    "absent",
    "not_surfaced",
    "out_of_scope",
    "unknown",
)
_MISSING_STATUS_GROUPS = (
    "working_capital_missing_status",
    "debt_missing_status",
    "asset_missing_status",
    "cash_health_missing_status",
)


def assemble_dataset(
    *,
    dataset_id: str,
    artifacts: tuple[P5ExtractedArtifact, ...],
    required_metric_ids: tuple[str, ...] = (),
    now_func: Callable[[], str] | None = None,
) -> P5DatasetArtifact:
    created_at = now_func() if now_func is not None else _utc_now_iso()
    present_rows = [
        _present_row_from_fact(artifact, fact)
        for artifact in artifacts
        for fact in artifact.canonical_facts
    ]
    deduped_present_rows = _dedupe_present_rows(present_rows)
    missing_rows = _missing_rows(
        artifacts=artifacts,
        present_rows=deduped_present_rows,
        required_metric_ids=required_metric_ids,
    )
    rows = tuple(
        sorted(
            [*deduped_present_rows, *missing_rows],
            key=_row_sort_key,
        )
    )
    source_artifacts = tuple(sorted({artifact.artifact_id for artifact in artifacts}))

    return P5DatasetArtifact(
        dataset_id=dataset_id,
        dataset_version=P5_DATASET_VERSION,
        created_at=created_at,
        issuer_count=len({artifact.manifest_entry.issuer_id for artifact in artifacts}),
        periods=tuple(sorted({row.fiscal_year for row in rows})),
        metrics=tuple(sorted({row.metric_id for row in rows})),
        rows=rows,
        quality_summary=_quality_summary(
            artifacts=artifacts,
            present_rows=tuple(present_rows),
            rows=rows,
        ),
        source_artifacts=source_artifacts,
    )


def _present_row_from_fact(
    artifact: P5ExtractedArtifact,
    fact: Mapping[str, Any],
) -> P5DatasetRow:
    entry = artifact.manifest_entry
    extensions = _mapping_value(fact.get("extensions"))
    return P5DatasetRow(
        issuer_id=entry.issuer_id,
        market=entry.market,
        stock_code=entry.stock_code,
        fiscal_year=entry.fiscal_year,
        metric_id=_text_value(fact.get("metric_id"), "metric_id"),
        entity_scope=_text_value(fact.get("entity_scope"), "entity_scope", default="unknown"),
        period_scope=_text_value(extensions.get("period_scope"), "period_scope", default="unknown"),
        statement_type=_text_value(
            fact.get("statement_type"),
            "statement_type",
            default="metrics",
        ),
        value=_numeric_value(fact.get("numeric_value")),
        currency=_optional_text_value(fact.get("currency")),
        unit=_optional_text_value(
            fact.get("normalized_unit") if fact.get("normalized_unit") is not None else fact.get("raw_unit")
        ),
        quality_status=_optional_text_value(fact.get("quality_status")),
        missing_status="present",
        source_fact_id=_optional_text_value(fact.get("fact_id")),
        source_artifact_id=artifact.artifact_id,
        evidence_bundle_id=_optional_text_value(fact.get("evidence_bundle_id")),
    )


def _dedupe_present_rows(rows: list[P5DatasetRow]) -> list[P5DatasetRow]:
    grouped: dict[
        tuple[str, int, str, str, str, str, str],
        list[P5DatasetRow],
    ] = defaultdict(list)
    for row in rows:
        grouped[_row_key(row)].append(row)

    deduped_rows: list[P5DatasetRow] = []
    for key in sorted(grouped):
        deduped_rows.append(grouped[key][0])
    return deduped_rows


def _missing_rows(
    *,
    artifacts: tuple[P5ExtractedArtifact, ...],
    present_rows: list[P5DatasetRow],
    required_metric_ids: tuple[str, ...],
) -> list[P5DatasetRow]:
    present_row_keys = {
        _missing_row_key(row)
        for row in present_rows
    }
    rows: list[P5DatasetRow] = []
    for artifact in artifacts:
        artifact_missing_status = _flatten_missing_status(artifact.missing_status)
        metric_ids = sorted(
            set(required_metric_ids)
            | set(artifact_missing_status.keys())
        )
        for metric_id in metric_ids:
            missing_row = P5DatasetRow(
                issuer_id=artifact.manifest_entry.issuer_id,
                market=artifact.manifest_entry.market,
                stock_code=artifact.manifest_entry.stock_code,
                fiscal_year=artifact.manifest_entry.fiscal_year,
                metric_id=metric_id,
                entity_scope="consolidated",
                period_scope="unknown",
                statement_type="metrics",
                value=None,
                currency=None,
                unit=None,
                quality_status=None,
                missing_status=artifact_missing_status.get(metric_id, "unknown"),
                source_fact_id=None,
                source_artifact_id=artifact.artifact_id,
                evidence_bundle_id=None,
            )
            if _missing_row_key(missing_row) not in present_row_keys:
                rows.append(missing_row)
    return rows


def _flatten_missing_status(
    missing_status: Mapping[str, Mapping[str, str]],
) -> dict[str, MissingStatus]:
    flattened: dict[str, MissingStatus] = {}
    for group_name in _MISSING_STATUS_GROUPS:
        group = _mapping_value(missing_status.get(group_name))
        for metric_id, status in group.items():
            normalized_status = _missing_status_value(status)
            if metric_id not in flattened:
                flattened[metric_id] = normalized_status
    return flattened


def _quality_summary(
    *,
    artifacts: tuple[P5ExtractedArtifact, ...],
    present_rows: tuple[P5DatasetRow, ...],
    rows: tuple[P5DatasetRow, ...],
) -> dict[str, Any]:
    missing_by_metric: dict[str, int] = defaultdict(int)
    missing_by_issuer: dict[str, int] = defaultdict(int)
    unknown_count = 0
    for row in rows:
        if row.missing_status == "present":
            continue
        missing_by_metric[row.metric_id] += 1
        missing_by_issuer[row.issuer_id] += 1
        if row.missing_status == "unknown":
            unknown_count += 1

    return {
        "present_row_count": sum(1 for row in rows if row.missing_status == "present"),
        "missing_row_count": sum(1 for row in rows if row.missing_status != "present"),
        "missing_by_metric": dict(sorted(missing_by_metric.items())),
        "missing_by_issuer": dict(sorted(missing_by_issuer.items())),
        "unknown_count": unknown_count,
        "review_required_artifacts": sorted(
            artifact.artifact_id
            for artifact in artifacts
            if artifact.quality_gate != "pass"
        ),
        "duplicate_fact_conflicts": _duplicate_fact_conflicts(present_rows),
        "scope_mismatch_warnings": _scope_mismatch_warnings(present_rows),
    }


def _duplicate_fact_conflicts(rows: tuple[P5DatasetRow, ...]) -> list[dict[str, Any]]:
    grouped: dict[
        tuple[str, int, str, str, str, str],
        list[P5DatasetRow],
    ] = defaultdict(list)
    for row in rows:
        if row.missing_status != "present":
            continue
        grouped[_duplicate_conflict_key(row)].append(row)

    conflicts: list[dict[str, Any]] = []
    for key in sorted(grouped):
        key_rows = grouped[key]
        unique_values = sorted(
            {
                row.value
                for row in key_rows
                if row.value is not None
            }
        )
        if len(unique_values) <= 1:
            continue
        issuer_id, fiscal_year, metric_id, entity_scope, period_scope, statement_type = key
        conflicts.append(
            {
                "issuer_id": issuer_id,
                "fiscal_year": fiscal_year,
                "metric_id": metric_id,
                "entity_scope": entity_scope,
                "period_scope": period_scope,
                "statement_type": statement_type,
                "values": unique_values,
                "source_fact_ids": sorted(
                    row.source_fact_id
                    for row in key_rows
                    if row.source_fact_id is not None
                ),
            }
        )
    return conflicts


def _scope_mismatch_warnings(rows: tuple[P5DatasetRow, ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, str], set[str]] = defaultdict(set)
    for row in rows:
        if row.missing_status != "present":
            continue
        grouped[(row.issuer_id, row.fiscal_year, row.metric_id)].add(row.entity_scope)

    warnings: list[dict[str, Any]] = []
    for (issuer_id, fiscal_year, metric_id), scopes in sorted(grouped.items()):
        if len(scopes) <= 1:
            continue
        if not ({"consolidated", "parent_company"} <= scopes or "unknown" in scopes):
            continue
        warnings.append(
            {
                "issuer_id": issuer_id,
                "fiscal_year": fiscal_year,
                "metric_id": metric_id,
                "scopes": sorted(scopes),
            }
        )
    return warnings


def _row_sort_key(row: P5DatasetRow) -> tuple[object, ...]:
    return (
        row.issuer_id,
        row.fiscal_year,
        row.metric_id,
        row.entity_scope,
        row.period_scope,
        row.statement_type,
        row.source_artifact_id,
        row.source_fact_id or "",
    )


def _row_key(row: P5DatasetRow) -> tuple[str, int, str, str, str, str, str]:
    return (
        row.issuer_id,
        row.fiscal_year,
        row.metric_id,
        row.entity_scope,
        row.period_scope,
        row.statement_type,
        row.source_fact_id or "",
    )


def _duplicate_conflict_key(row: P5DatasetRow) -> tuple[str, int, str, str, str, str]:
    return (
        row.issuer_id,
        row.fiscal_year,
        row.metric_id,
        row.entity_scope,
        row.period_scope,
        row.statement_type,
    )


def _missing_row_key(row: P5DatasetRow) -> tuple[str, int, str, str, str, str]:
    return (
        row.issuer_id,
        row.fiscal_year,
        row.metric_id,
        row.entity_scope,
        row.period_scope,
        row.statement_type,
    )


def _numeric_value(value: object) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _optional_text_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_value(value: object, field_name: str, *, default: str | None = None) -> str:
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{field_name} is required")
    text = str(value).strip()
    if not text:
        if default is not None:
            return default
        raise ValueError(f"{field_name} is required")
    return text


def _mapping_value(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("expected mapping value")
    return dict(value)


def _missing_status_value(value: object) -> MissingStatus:
    text = _text_value(value, "missing_status")
    if text not in _MISSING_STATUS_VALUES:
        raise ValueError(f"unsupported missing_status: {text}")
    return cast(MissingStatus, text)


def _utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()
