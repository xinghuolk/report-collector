from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from financial_report_analysis.models import (
    MetricLifecycleRecomputeAudit,
    MetricLifecycleRecomputeAuditItem,
    MetricLifecycleRecomputeAuditSummary,
)
from financial_report_analysis.p5.artifact_repository import P5JsonArtifactRepository
from financial_report_analysis.p5.models import (
    P5ExtractedArtifact,
    P5RecomputeDiffSummary,
    P5RecomputePlan,
    P5RecomputeResult,
)
from financial_report_analysis.p5.runner import (
    P5RunResult,
    _save_turtle_export,
    run_p5_dataset_build,
)
from financial_report_analysis.p5.turtle_export import build_turtle_export
from financial_report_analysis.services.metric_lifecycle_consumption import (
    apply_metric_lifecycle_consumption,
)

_LIFECYCLE_RECOMPUTE_REASON = "metric_lifecycle_decision_changed"


def build_recompute_plan(
    *,
    manifest_id: str,
    dataset_id: str,
    extracted_artifact_ids: tuple[str, ...],
    reason: str,
) -> P5RecomputePlan:
    rebuild_dataset, rebuild_turtle_export = _rebuild_flags_for_reason(reason)
    return P5RecomputePlan(
        manifest_id=manifest_id,
        dataset_id=dataset_id,
        target_artifact_ids=tuple(sorted(set(extracted_artifact_ids))),
        rebuild_dataset=rebuild_dataset,
        rebuild_turtle_export=rebuild_turtle_export,
        reason=reason,
    )


def execute_recompute_plan(
    *,
    plan: P5RecomputePlan,
    manifest_path: str | Path,
    artifact_root: str | Path,
    pdf_root: str | Path | None,
    lifecycle_consumption_audit: MetricLifecycleRecomputeAudit | None = None,
    run_p5_dataset_build_func: Callable[..., P5RunResult] = run_p5_dataset_build,
) -> P5RecomputeResult:
    repository = P5JsonArtifactRepository(artifact_root)
    before_dataset = _safe_read_json_payload(repository.dataset_artifact_path(plan.dataset_id))
    before_turtle = _safe_read_json_payload(
        repository.turtle_export_artifact_path(plan.dataset_id)
    )
    if plan.rebuild_dataset:
        build_kwargs: dict[str, object] = {}
        if _is_lifecycle_recompute_reason(plan.reason):
            if lifecycle_consumption_audit is None:
                raise ValueError(
                    "lifecycle_consumption_audit is required for lifecycle recompute"
                )

            def transform_artifact(
                artifact: P5ExtractedArtifact,
            ) -> P5ExtractedArtifact:
                return apply_metric_lifecycle_consumption(
                    artifact=artifact,
                    audit=lifecycle_consumption_audit,
                )

            build_kwargs["artifact_transform_func"] = transform_artifact
        run_result = run_p5_dataset_build_func(
            manifest_path=manifest_path,
            artifact_root=artifact_root,
            dataset_id=plan.dataset_id,
            pdf_root=pdf_root,
            force_rebuild_artifact_ids=_force_rebuild_artifact_ids_for_reason(plan),
            write_turtle_export=plan.rebuild_turtle_export,
            **build_kwargs,
        )
        after_dataset = _safe_read_json_payload(run_result.dataset_path)
        after_turtle = _safe_read_json_payload(run_result.turtle_export_path)
        return P5RecomputeResult(
            manifest_id=run_result.manifest_id,
            extracted_artifact_ids=run_result.extracted_artifact_ids,
            dataset_path=run_result.dataset_path,
            turtle_export_path=run_result.turtle_export_path,
            diff_summary=P5RecomputeDiffSummary(
                reason=plan.reason,
                target_artifact_ids=plan.target_artifact_ids,
                dataset_changed=before_dataset != after_dataset,
                turtle_export_changed=before_turtle != after_turtle,
                rebuilt_dataset=True,
                rebuilt_turtle_export=plan.rebuild_turtle_export,
            ),
        )

    dataset_path = repository.dataset_artifact_path(plan.dataset_id)
    turtle_export_path = repository.turtle_export_artifact_path(plan.dataset_id)
    if plan.rebuild_turtle_export:
        dataset = repository.load_dataset_artifact(plan.dataset_id)
        turtle_export = build_turtle_export(dataset)
        turtle_export_path = _save_turtle_export(repository, turtle_export)
    after_dataset = _safe_read_json_payload(dataset_path)
    after_turtle = _safe_read_json_payload(turtle_export_path)

    return P5RecomputeResult(
        manifest_id=plan.manifest_id,
        extracted_artifact_ids=plan.target_artifact_ids,
        dataset_path=dataset_path,
        turtle_export_path=turtle_export_path,
        diff_summary=P5RecomputeDiffSummary(
            reason=plan.reason,
            target_artifact_ids=plan.target_artifact_ids,
            dataset_changed=before_dataset != after_dataset,
            turtle_export_changed=before_turtle != after_turtle,
            rebuilt_dataset=False,
            rebuilt_turtle_export=plan.rebuild_turtle_export,
        ),
    )


def _rebuild_flags_for_reason(reason: str) -> tuple[bool, bool]:
    normalized = reason.strip().lower()
    reason_map = {
        "manifest_changed": (True, True),
        "source_pdf_changed": (True, True),
        "extracted_artifact_contract_changed": (True, True),
        "pipeline_version_changed": (True, True),
        "manual_review_check": (True, True),
        "dataset_assembly_contract_changed": (True, True),
        _LIFECYCLE_RECOMPUTE_REASON: (True, True),
        "export_alias_changed": (False, True),
        "export_shape_changed": (False, True),
    }
    return reason_map.get(normalized, (True, True))


def _force_rebuild_artifact_ids_for_reason(plan: P5RecomputePlan) -> tuple[str, ...]:
    normalized = plan.reason.strip().lower()
    if normalized in {
        "source_pdf_changed",
        "extracted_artifact_contract_changed",
        "pipeline_version_changed",
    }:
        return plan.target_artifact_ids
    return ()


def _is_lifecycle_recompute_reason(reason: str) -> bool:
    return reason.strip().lower() == _LIFECYCLE_RECOMPUTE_REASON


def _safe_read_json_payload(path: Path) -> object | None:
    if not path.exists():
        return None
    return _strip_volatile_fields(json.loads(path.read_text(encoding="utf-8")))


def _strip_volatile_fields(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _strip_volatile_fields(item)
            for key, item in value.items()
            if key != "created_at"
        }
    if isinstance(value, list):
        return [_strip_volatile_fields(item) for item in value]
    return value


def metric_lifecycle_recompute_audit_to_payload(
    audit: MetricLifecycleRecomputeAudit,
) -> dict[str, object]:
    return {
        "items": [
            {
                "review_item_id": item.review_item_id,
                "artifact_id": item.artifact_id,
                "issuer_id": item.issuer_id,
                "fiscal_year": item.fiscal_year,
                "report_type": item.report_type,
                "candidate_metric_id": item.candidate_metric_id,
                "raw_label": item.raw_label,
                "lifecycle_entry_id": item.lifecycle_entry_id,
                "current_status": item.current_status,
                "latest_decision_id": item.latest_decision_id,
                "latest_decision_action": item.latest_decision_action,
                "target_metric_id": item.target_metric_id,
                "recompute_needed": item.recompute_needed,
                "consumption_action": item.consumption_action,
                "conflict_state": item.conflict_state,
                "reason": item.reason,
            }
            for item in audit.items
        ],
        "summary": {
            "review_item_count": audit.summary.review_item_count,
            "artifact_count": audit.summary.artifact_count,
            "recompute_needed_count": audit.summary.recompute_needed_count,
            "dry_run_conflict_count": audit.summary.dry_run_conflict_count,
        },
    }


def metric_lifecycle_recompute_audit_from_payload(
    payload: dict[str, object],
) -> MetricLifecycleRecomputeAudit:
    summary_payload = payload["summary"]
    if not isinstance(summary_payload, dict):
        raise ValueError("lifecycle recompute audit summary must be an object")
    if "items" not in payload:
        raise ValueError("lifecycle recompute audit items are required")
    item_payloads = payload["items"]
    if not isinstance(item_payloads, list):
        raise ValueError("lifecycle recompute audit items must be a list")
    for index, item in enumerate(item_payloads):
        if not isinstance(item, dict):
            raise ValueError(
                f"lifecycle recompute audit item at index {index} must be an object"
            )

    return MetricLifecycleRecomputeAudit(
        items=tuple(
            _metric_lifecycle_recompute_audit_item_from_payload(item)
            for item in item_payloads
        ),
        summary=MetricLifecycleRecomputeAuditSummary(
            review_item_count=int(summary_payload["review_item_count"]),
            artifact_count=int(summary_payload["artifact_count"]),
            recompute_needed_count=int(summary_payload["recompute_needed_count"]),
            dry_run_conflict_count=int(summary_payload["dry_run_conflict_count"]),
        ),
    )


def _metric_lifecycle_recompute_audit_item_from_payload(
    payload: dict[str, object],
) -> MetricLifecycleRecomputeAuditItem:
    recompute_needed = payload["recompute_needed"]
    if not isinstance(recompute_needed, bool):
        raise ValueError("lifecycle recompute audit item recompute_needed must be a bool")

    return MetricLifecycleRecomputeAuditItem(
        review_item_id=str(payload["review_item_id"]),
        artifact_id=str(payload["artifact_id"]),
        issuer_id=str(payload["issuer_id"]),
        fiscal_year=int(payload["fiscal_year"]),
        report_type=str(payload["report_type"]),
        candidate_metric_id=str(payload["candidate_metric_id"]),
        raw_label=str(payload["raw_label"]),
        lifecycle_entry_id=(
            str(payload["lifecycle_entry_id"])
            if payload.get("lifecycle_entry_id") is not None
            else None
        ),
        current_status=payload.get("current_status"),  # type: ignore[arg-type]
        latest_decision_id=(
            str(payload["latest_decision_id"])
            if payload.get("latest_decision_id") is not None
            else None
        ),
        latest_decision_action=payload.get("latest_decision_action"),  # type: ignore[arg-type]
        target_metric_id=(
            str(payload["target_metric_id"])
            if payload.get("target_metric_id") is not None
            else None
        ),
        recompute_needed=recompute_needed,
        consumption_action=str(payload["consumption_action"]),  # type: ignore[arg-type]
        conflict_state=str(payload["conflict_state"]),  # type: ignore[arg-type]
        reason=str(payload["reason"]),
    )


def recompute_diff_summary_to_payload(
    diff_summary: P5RecomputeDiffSummary,
) -> dict[str, object]:
    return {
        "reason": diff_summary.reason,
        "target_artifact_ids": list(diff_summary.target_artifact_ids),
        "dataset_changed": diff_summary.dataset_changed,
        "turtle_export_changed": diff_summary.turtle_export_changed,
        "rebuilt_dataset": diff_summary.rebuilt_dataset,
        "rebuilt_turtle_export": diff_summary.rebuilt_turtle_export,
    }


def recompute_diff_summary_from_payload(
    payload: dict[str, object],
) -> P5RecomputeDiffSummary:
    return P5RecomputeDiffSummary(
        reason=str(payload["reason"]),
        target_artifact_ids=tuple(payload.get("target_artifact_ids", ())),  # type: ignore[arg-type]
        dataset_changed=bool(payload["dataset_changed"]),
        turtle_export_changed=bool(payload["turtle_export_changed"]),
        rebuilt_dataset=bool(payload["rebuilt_dataset"]),
        rebuilt_turtle_export=bool(payload["rebuilt_turtle_export"]),
    )


def recompute_result_to_payload(
    result: P5RecomputeResult,
) -> dict[str, object]:
    return {
        "manifest_id": result.manifest_id,
        "extracted_artifact_ids": list(result.extracted_artifact_ids),
        "dataset_path": str(result.dataset_path),
        "turtle_export_path": str(result.turtle_export_path),
        "diff_summary": recompute_diff_summary_to_payload(result.diff_summary),
    }


def recompute_result_from_payload(
    payload: dict[str, object],
) -> P5RecomputeResult:
    return P5RecomputeResult(
        manifest_id=str(payload["manifest_id"]),
        extracted_artifact_ids=tuple(payload.get("extracted_artifact_ids", ())),  # type: ignore[arg-type]
        dataset_path=Path(str(payload["dataset_path"])),
        turtle_export_path=Path(str(payload["turtle_export_path"])),
        diff_summary=recompute_diff_summary_from_payload(payload["diff_summary"]),  # type: ignore[arg-type]
    )
