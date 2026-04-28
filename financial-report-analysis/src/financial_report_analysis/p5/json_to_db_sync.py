from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Protocol

from financial_report_analysis.models import MetricLifecycleRecomputeAudit
from financial_report_analysis.p5.artifact_repository import (
    P5ArtifactRepositoryError,
    dataset_artifact_to_payload,
    turtle_export_to_payload,
)
from financial_report_analysis.p5.lineage import artifact_lineage_to_payload
from financial_report_analysis.p5.models import (
    P5ArtifactLineage,
    P5DatasetArtifact,
    P5DatasetReviewSurface,
    P5RecomputePlan,
    P5RecomputeResult,
    P5TurtleExport,
    P5TurtleExportReviewSurface,
)
from financial_report_analysis.p5.recompute import (
    metric_lifecycle_recompute_audit_to_payload,
    recompute_result_to_payload,
)
from financial_report_analysis.p5.review import (
    dataset_review_surface_to_payload,
    turtle_export_review_surface_to_payload,
)


class JsonToDbSyncStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED_IDEMPOTENT = "skipped_idempotent"
    NOT_ATTEMPTED = "not_attempted"
    OUT_OF_SYNC = "out_of_sync"


@dataclass(frozen=True, slots=True)
class JsonToDbSyncRequest:
    recompute_run_id: str
    plan: P5RecomputePlan
    recompute_result: P5RecomputeResult
    dataset: P5DatasetArtifact
    dataset_review_surface: P5DatasetReviewSurface | None
    turtle_export: P5TurtleExport | None
    turtle_export_review_surface: P5TurtleExportReviewSurface | None
    lineage_records: tuple[P5ArtifactLineage, ...]
    lifecycle_recompute_audit: MetricLifecycleRecomputeAudit | None
    input_hashes: Mapping[str, str]
    before_refs: Mapping[str, str]
    requested_by: str | None
    sync_reason: str


@dataclass(frozen=True, slots=True)
class JsonToDbSyncResult:
    sync_id: str
    recompute_run_id: str
    dataset_id: str
    status: JsonToDbSyncStatus
    written_refs: Mapping[str, str]
    skipped_refs: Mapping[str, str]
    blocking_reasons: tuple[str, ...]
    input_hashes: Mapping[str, str]
    before_refs: Mapping[str, str]
    after_refs: Mapping[str, str]
    created_at: str
    completed_at: str | None = None


@dataclass(frozen=True, slots=True)
class JsonToDbSyncAuditView:
    sync_id: str | None
    recompute_run_id: str | None
    dataset_id: str
    status: JsonToDbSyncStatus
    input_hashes: Mapping[str, str]
    before_refs: Mapping[str, str]
    after_refs: Mapping[str, str]
    written_refs: Mapping[str, str]
    skipped_refs: Mapping[str, str]
    blocking_reasons: tuple[str, ...]
    requested_by: str | None
    sync_reason: str | None
    created_at: str | None
    completed_at: str | None


class JsonToDbSyncRepository(Protocol):
    def load_dataset_audit_view(self, dataset_id: str) -> Any: ...

    def load_current_json_to_db_before_refs(self, dataset_id: str) -> dict[str, str]: ...

    def load_json_to_db_sync_result(self, sync_id: str) -> JsonToDbSyncAuditView: ...

    def load_latest_json_to_db_sync_for_recompute_run(
        self,
        recompute_run_id: str,
    ) -> JsonToDbSyncAuditView | None: ...

    def compute_extracted_artifact_hash(self, artifact_id: str) -> str: ...

    def save_p5_assembly_bundle(
        self,
        *,
        dataset: P5DatasetArtifact,
        dataset_review_surface: P5DatasetReviewSurface,
        lineage_records: tuple[P5ArtifactLineage, ...],
        turtle_export: P5TurtleExport | None = None,
        turtle_export_review_surface: P5TurtleExportReviewSurface | None = None,
    ) -> int: ...

    def save_recompute_result(
        self,
        *,
        run_id: str,
        plan: P5RecomputePlan,
        result: P5RecomputeResult,
        lifecycle_recompute_audit: MetricLifecycleRecomputeAudit | None = None,
    ) -> str: ...

    def save_json_to_db_sync_result(self, view: JsonToDbSyncAuditView) -> str: ...


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_payload_hash(payload: Any) -> str:
    canonical_payload = _to_jsonable(payload)
    encoded = json.dumps(
        canonical_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_json_to_db_sync_id(request: JsonToDbSyncRequest) -> str:
    payload_hash = compute_payload_hash(
        {
            "before_refs": dict(request.before_refs),
            "after_refs": _derived_after_refs(request),
            "input_hashes": dict(request.input_hashes),
            "lifecycle_recompute_audit": (
                None
                if request.lifecycle_recompute_audit is None
                else metric_lifecycle_recompute_audit_to_payload(
                    request.lifecycle_recompute_audit
                )
            ),
            "source_artifact_ids": request.dataset.source_artifacts,
        }
    )
    return (
        "json-to-db-sync:"
        f"{request.dataset.dataset_id}:"
        f"{request.recompute_run_id}:"
        f"{payload_hash}"
    )


def validate_json_to_db_sync_request(request: JsonToDbSyncRequest) -> None:
    if not request.dataset.source_artifacts:
        raise P5ArtifactRepositoryError("source artifacts are required for JSON-to-DB sync")

    if request.dataset.dataset_id != request.plan.dataset_id:
        raise P5ArtifactRepositoryError("dataset id mismatch for JSON-to-DB sync request")

    if request.plan.manifest_id != request.recompute_result.manifest_id:
        raise P5ArtifactRepositoryError("manifest id mismatch for JSON-to-DB sync request")

    if request.dataset_review_surface is None:
        raise P5ArtifactRepositoryError(
            "after dataset review surface is required for JSON-to-DB sync"
        )

    if request.dataset_review_surface.dataset_id != request.dataset.dataset_id:
        raise P5ArtifactRepositoryError(
            "dataset id mismatch between dataset and review surface"
        )

    if request.turtle_export is not None and (
        request.turtle_export.dataset_id != request.dataset.dataset_id
    ):
        raise P5ArtifactRepositoryError(
            "dataset id mismatch between dataset and turtle export"
        )

    if request.turtle_export is None and request.turtle_export_review_surface is not None:
        raise P5ArtifactRepositoryError(
            "turtle export is required when turtle export review surface is present"
        )

    if request.turtle_export_review_surface is not None and (
        request.turtle_export_review_surface.dataset_id != request.dataset.dataset_id
    ):
        raise P5ArtifactRepositoryError(
            "dataset id mismatch between dataset and turtle review surface"
        )

    _validate_input_hashes(request)
    _validate_source_artifact_match(request)
    _validate_before_refs(request.before_refs)
    _validate_lifecycle_recompute_audit(request.lifecycle_recompute_audit)


def sync_json_recompute_to_db(
    *,
    repository: JsonToDbSyncRepository,
    request: JsonToDbSyncRequest,
) -> JsonToDbSyncResult:
    validate_json_to_db_sync_request(request)
    dataset_review_surface = request.dataset_review_surface
    if dataset_review_surface is None:
        raise P5ArtifactRepositoryError(
            "after dataset review surface is required for JSON-to-DB sync"
        )

    sync_id = build_json_to_db_sync_id(request)
    existing = _load_existing_sync_by_id(repository, sync_id)
    if _is_same_completed_sync(existing, sync_id, request):
        return _result_from_view(
            existing,
            status=JsonToDbSyncStatus.SKIPPED_IDEMPOTENT,
            skipped_refs={"sync_id": existing.sync_id or sync_id},
        )

    try:
        stale_reasons = _stale_input_hash_reasons(repository, request)
        stale_reasons.extend(_db_source_artifact_reasons(repository, request))
        stale_reasons.extend(_stale_before_ref_reasons(repository, request))
    except Exception as exc:
        stale_reasons = [f"preflight_failed: {exc}"]

    if stale_reasons:
        view = _build_sync_view(
            request=request,
            sync_id=sync_id,
            status=JsonToDbSyncStatus.FAILED,
            after_refs={},
            written_refs={},
            skipped_refs={},
            blocking_reasons=tuple(stale_reasons),
            completed_at=utc_now_iso(),
        )
        repository.save_json_to_db_sync_result(view)
        return _result_from_view(view)

    after_refs = _after_refs_for_request(request)
    pending_view = _build_sync_view(
        request=request,
        sync_id=sync_id,
        status=JsonToDbSyncStatus.PENDING,
        after_refs=after_refs,
        written_refs={},
        skipped_refs={},
        blocking_reasons=(),
        completed_at=None,
    )
    repository.save_json_to_db_sync_result(pending_view)

    written_refs: dict[str, str] = {}
    try:
        repository.save_p5_assembly_bundle(
            dataset=request.dataset,
            dataset_review_surface=dataset_review_surface,
            lineage_records=request.lineage_records,
            turtle_export=request.turtle_export,
            turtle_export_review_surface=request.turtle_export_review_surface,
        )
        written_refs.update(_assembly_written_refs(after_refs))
        repository.save_recompute_result(
            run_id=request.recompute_run_id,
            plan=request.plan,
            result=request.recompute_result,
            lifecycle_recompute_audit=request.lifecycle_recompute_audit,
        )
        written_refs.update(_recompute_written_refs(after_refs, request))
    except Exception as exc:
        status = JsonToDbSyncStatus.PARTIAL if written_refs else JsonToDbSyncStatus.FAILED
        view = _build_sync_view(
            request=request,
            sync_id=sync_id,
            status=status,
            after_refs=after_refs,
            written_refs=written_refs,
            skipped_refs={},
            blocking_reasons=(str(exc),),
            completed_at=utc_now_iso(),
        )
        repository.save_json_to_db_sync_result(view)
        return _result_from_view(view)

    view = _build_sync_view(
        request=request,
        sync_id=sync_id,
        status=JsonToDbSyncStatus.COMPLETED,
        after_refs=after_refs,
        written_refs=written_refs,
        skipped_refs={},
        blocking_reasons=(),
        completed_at=utc_now_iso(),
    )
    try:
        repository.save_json_to_db_sync_result(view)
    except Exception as exc:
        raise P5ArtifactRepositoryError(
            "completed JSON-to-DB sync metadata write failed; unknown sync state "
            f"after payload writes: {exc}"
        ) from exc
    return _result_from_view(view)


def _validate_input_hashes(request: JsonToDbSyncRequest) -> None:
    if set(request.input_hashes) != set(request.dataset.source_artifacts):
        raise P5ArtifactRepositoryError(
            "input hash source artifacts must match dataset source artifacts"
        )


def _derived_after_refs(request: JsonToDbSyncRequest) -> dict[str, Any]:
    return {
        "dataset": {
            "dataset_id": request.dataset.dataset_id,
            "dataset_version": request.dataset.dataset_version,
            "payload_hash": compute_payload_hash(request.dataset),
        },
        "dataset_review_surface": (
            None
            if request.dataset_review_surface is None
            else {
                "dataset_id": request.dataset_review_surface.dataset_id,
                "dataset_version": request.dataset_review_surface.dataset_version,
                "payload_hash": compute_payload_hash(request.dataset_review_surface),
            }
        ),
        "lineage_records": {
            "count": len(request.lineage_records),
            "payload_hash": compute_payload_hash(request.lineage_records),
        },
        "recompute_result": {
            "payload_hash": compute_payload_hash(request.recompute_result),
        },
        "lifecycle_recompute_audit": (
            None
            if request.lifecycle_recompute_audit is None
            else {
                "payload_hash": compute_payload_hash(
                    metric_lifecycle_recompute_audit_to_payload(
                        request.lifecycle_recompute_audit
                    )
                ),
            }
        ),
        "turtle_export": (
            None
            if request.turtle_export is None
            else {
                "dataset_id": request.turtle_export.dataset_id,
                "dataset_version": request.turtle_export.dataset_version,
                "payload_hash": compute_payload_hash(request.turtle_export),
            }
        ),
        "turtle_export_review_surface": (
            None
            if request.turtle_export_review_surface is None
            else {
                "dataset_id": request.turtle_export_review_surface.dataset_id,
                "dataset_version": request.turtle_export_review_surface.dataset_version,
                "payload_hash": compute_payload_hash(
                    request.turtle_export_review_surface
                ),
            }
        ),
    }


def _validate_source_artifact_match(request: JsonToDbSyncRequest) -> None:
    dataset_artifacts = request.dataset.source_artifacts
    if dataset_artifacts != request.recompute_result.extracted_artifact_ids:
        raise P5ArtifactRepositoryError(
            "source artifact mismatch between dataset and recompute result"
        )

    sorted_plan_targets = tuple(sorted(request.plan.target_artifact_ids))
    sorted_diff_targets = tuple(
        sorted(request.recompute_result.diff_summary.target_artifact_ids)
    )
    if sorted_plan_targets != sorted_diff_targets:
        raise P5ArtifactRepositoryError(
            "diff summary target artifacts must match plan target artifacts"
        )

    if not set(request.plan.target_artifact_ids).issubset(set(dataset_artifacts)):
        raise P5ArtifactRepositoryError(
            "plan target artifacts must be a subset of dataset source artifacts"
        )

    if dataset_artifacts != request.dataset_review_surface.source_artifact_ids:
        raise P5ArtifactRepositoryError(
            "source artifact mismatch between dataset and review surface"
        )

    if request.turtle_export_review_surface is not None and (
        dataset_artifacts != request.turtle_export_review_surface.source_artifact_ids
    ):
        raise P5ArtifactRepositoryError(
            "source artifact mismatch between dataset and turtle review surface"
        )


def _validate_before_refs(before_refs: Mapping[str, str]) -> None:
    if not before_refs.get("dataset"):
        raise P5ArtifactRepositoryError("before dataset ref is required for JSON-to-DB sync")


def _validate_lifecycle_recompute_audit(
    audit: MetricLifecycleRecomputeAudit | None,
) -> None:
    if audit is not None and not isinstance(audit, MetricLifecycleRecomputeAudit):
        raise P5ArtifactRepositoryError(
            "malformed lifecycle recompute audit for JSON-to-DB sync"
        )


def _is_same_completed_sync(
    existing: JsonToDbSyncAuditView | None,
    sync_id: str,
    request: JsonToDbSyncRequest,
) -> bool:
    return (
        existing is not None
        and existing.sync_id == sync_id
        and existing.status is JsonToDbSyncStatus.COMPLETED
        and existing.recompute_run_id == request.recompute_run_id
        and existing.dataset_id == request.dataset.dataset_id
        and existing.input_hashes == dict(request.input_hashes)
        and existing.before_refs == dict(request.before_refs)
    )


def _load_existing_sync_by_id(
    repository: JsonToDbSyncRepository,
    sync_id: str,
) -> JsonToDbSyncAuditView | None:
    try:
        return repository.load_json_to_db_sync_result(sync_id)
    except P5ArtifactRepositoryError as exc:
        if "missing" in str(exc).lower():
            return None
        raise


def _stale_input_hash_reasons(
    repository: JsonToDbSyncRepository,
    request: JsonToDbSyncRequest,
) -> list[str]:
    reasons: list[str] = []
    for artifact_id, expected_hash in sorted(request.input_hashes.items()):
        actual_hash = repository.compute_extracted_artifact_hash(artifact_id)
        if actual_hash != expected_hash:
            reasons.append(f"stale_input_hash: {artifact_id}")
    return reasons


def _db_source_artifact_reasons(
    repository: JsonToDbSyncRepository,
    request: JsonToDbSyncRequest,
) -> list[str]:
    audit_view = repository.load_dataset_audit_view(request.dataset.dataset_id)
    if tuple(audit_view.source_artifact_ids) != tuple(request.dataset.source_artifacts):
        return ["db_source_artifact_mismatch"]
    return []


def _stale_before_ref_reasons(
    repository: JsonToDbSyncRepository,
    request: JsonToDbSyncRequest,
) -> list[str]:
    current_refs = repository.load_current_json_to_db_before_refs(
        request.dataset.dataset_id
    )
    reasons: list[str] = []
    for ref_name, expected_ref in sorted(request.before_refs.items()):
        if current_refs.get(ref_name) != expected_ref:
            reasons.append(f"stale_before_ref: {ref_name}")
    return reasons


def _after_refs_for_request(request: JsonToDbSyncRequest) -> dict[str, str]:
    refs = {
        "dataset_id": request.dataset.dataset_id,
        "dataset_payload_hash": compute_payload_hash(
            dataset_artifact_to_payload(request.dataset)
        ),
        "lineage_payload_hash": compute_payload_hash(
            tuple(
                artifact_lineage_to_payload(lineage)
                for lineage in request.lineage_records
            )
        ),
        "recompute_result_hash": compute_payload_hash(
            recompute_result_to_payload(request.recompute_result)
        ),
    }
    if request.dataset_review_surface is not None:
        refs["dataset_review_surface_hash"] = compute_payload_hash(
            dataset_review_surface_to_payload(request.dataset_review_surface)
        )
    if request.turtle_export is not None:
        refs["turtle_export_id"] = request.turtle_export.dataset_id
        refs["turtle_export_hash"] = compute_payload_hash(
            turtle_export_to_payload(request.turtle_export)
        )
    if request.turtle_export_review_surface is not None:
        refs["turtle_export_review_surface_hash"] = compute_payload_hash(
            turtle_export_review_surface_to_payload(
                request.turtle_export_review_surface
            )
        )
    if request.lifecycle_recompute_audit is not None:
        refs["lifecycle_recompute_audit_hash"] = compute_payload_hash(
            metric_lifecycle_recompute_audit_to_payload(
                request.lifecycle_recompute_audit
            )
        )
    return refs


def _assembly_written_refs(after_refs: Mapping[str, str]) -> dict[str, str]:
    assembly_keys = (
        "dataset_id",
        "dataset_payload_hash",
        "dataset_review_surface_hash",
        "lineage_payload_hash",
        "turtle_export_id",
        "turtle_export_hash",
        "turtle_export_review_surface_hash",
    )
    return {key: after_refs[key] for key in assembly_keys if key in after_refs}


def _recompute_written_refs(
    after_refs: Mapping[str, str],
    request: JsonToDbSyncRequest,
) -> dict[str, str]:
    recompute_keys = (
        "recompute_result_hash",
        "lifecycle_recompute_audit_hash",
    )
    refs = {key: after_refs[key] for key in recompute_keys if key in after_refs}
    refs["recompute_run_id"] = request.recompute_run_id
    return refs


def _build_sync_view(
    *,
    request: JsonToDbSyncRequest,
    sync_id: str,
    status: JsonToDbSyncStatus,
    after_refs: Mapping[str, str],
    written_refs: Mapping[str, str],
    skipped_refs: Mapping[str, str],
    blocking_reasons: tuple[str, ...],
    completed_at: str | None,
) -> JsonToDbSyncAuditView:
    return JsonToDbSyncAuditView(
        sync_id=sync_id,
        recompute_run_id=request.recompute_run_id,
        dataset_id=request.dataset.dataset_id,
        status=status,
        input_hashes=dict(request.input_hashes),
        before_refs=dict(request.before_refs),
        after_refs=dict(after_refs),
        written_refs=dict(written_refs),
        skipped_refs=dict(skipped_refs),
        blocking_reasons=blocking_reasons,
        requested_by=request.requested_by,
        sync_reason=request.sync_reason,
        created_at=utc_now_iso(),
        completed_at=completed_at,
    )


def _result_from_view(
    view: JsonToDbSyncAuditView,
    *,
    status: JsonToDbSyncStatus | None = None,
    skipped_refs: Mapping[str, str] | None = None,
) -> JsonToDbSyncResult:
    if view.sync_id is None or view.recompute_run_id is None:
        raise P5ArtifactRepositoryError("JSON-to-DB sync view is missing identity fields")
    if view.created_at is None:
        raise P5ArtifactRepositoryError("JSON-to-DB sync view is missing created_at")
    return JsonToDbSyncResult(
        sync_id=view.sync_id,
        recompute_run_id=view.recompute_run_id,
        dataset_id=view.dataset_id,
        status=view.status if status is None else status,
        written_refs=dict(view.written_refs),
        skipped_refs=(
            dict(view.skipped_refs) if skipped_refs is None else dict(skipped_refs)
        ),
        blocking_reasons=view.blocking_reasons,
        input_hashes=dict(view.input_hashes),
        before_refs=dict(view.before_refs),
        after_refs=dict(view.after_refs),
        created_at=view.created_at,
        completed_at=view.completed_at,
    )


def _to_jsonable(payload: Any) -> Any:
    if is_dataclass(payload) and not isinstance(payload, type):
        return _to_jsonable(asdict(payload))
    if isinstance(payload, Mapping):
        return {str(key): _to_jsonable(value) for key, value in payload.items()}
    if isinstance(payload, tuple | list):
        return [_to_jsonable(value) for value in payload]
    if isinstance(payload, Path):
        return str(payload)
    return payload
