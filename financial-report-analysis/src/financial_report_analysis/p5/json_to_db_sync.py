from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from financial_report_analysis.models import MetricLifecycleRecomputeAudit
from financial_report_analysis.p5.artifact_repository import P5ArtifactRepositoryError
from financial_report_analysis.p5.models import (
    P5ArtifactLineage,
    P5DatasetArtifact,
    P5DatasetReviewSurface,
    P5RecomputePlan,
    P5RecomputeResult,
    P5TurtleExport,
    P5TurtleExportReviewSurface,
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
    requested_by: str
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
            "input_hashes": dict(request.input_hashes),
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


def _validate_input_hashes(request: JsonToDbSyncRequest) -> None:
    if set(request.input_hashes) != set(request.dataset.source_artifacts):
        raise P5ArtifactRepositoryError(
            "input hash source artifacts must match dataset source artifacts"
        )


def _validate_source_artifact_match(request: JsonToDbSyncRequest) -> None:
    dataset_artifacts = request.dataset.source_artifacts
    if dataset_artifacts != request.recompute_result.extracted_artifact_ids:
        raise P5ArtifactRepositoryError(
            "source artifact mismatch between dataset and recompute result"
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
