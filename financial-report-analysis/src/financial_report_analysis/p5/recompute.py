from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from financial_report_analysis.p5.artifact_repository import P5JsonArtifactRepository
from financial_report_analysis.p5.models import (
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
    run_p5_dataset_build_func: Callable[..., P5RunResult] = run_p5_dataset_build,
) -> P5RecomputeResult:
    repository = P5JsonArtifactRepository(artifact_root)
    before_dataset = _safe_read_json_payload(repository._dataset_path(plan.dataset_id))  # noqa: SLF001
    before_turtle = _safe_read_json_payload(
        repository.datasets_dir
        / f"{repository._dataset_path(plan.dataset_id).stem}_turtle_export.json"  # noqa: SLF001
    )
    if plan.rebuild_dataset:
        run_result = run_p5_dataset_build_func(
            manifest_path=manifest_path,
            artifact_root=artifact_root,
            dataset_id=plan.dataset_id,
            pdf_root=pdf_root,
            force_rebuild_artifact_ids=plan.target_artifact_ids,
            write_turtle_export=plan.rebuild_turtle_export,
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

    dataset_path = repository._dataset_path(plan.dataset_id)  # noqa: SLF001
    turtle_export_path = repository.datasets_dir / f"{dataset_path.stem}_turtle_export.json"
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
        "export_alias_changed": (False, True),
        "export_shape_changed": (False, True),
    }
    return reason_map.get(normalized, (True, True))


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
