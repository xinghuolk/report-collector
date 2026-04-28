from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from financial_report_analysis.p5.artifact_repository import P5ArtifactRepositoryError
from financial_report_analysis.storage.repositories import DatasetAuditView


class RecomputeExecutionMode(StrEnum):
    JSON_FIRST_REQUIRED = "json_first_required"
    DB_ASSEMBLY_AVAILABLE = "db_assembly_available"
    DB_NATIVE_UNSUPPORTED = "db_native_unsupported"


@dataclass(frozen=True, slots=True)
class DbRecomputeBoundaryView:
    dataset_id: str
    latest_recompute_run_id: str | None
    latest_recompute_reason: str | None
    latest_lifecycle_audit_present: bool
    source_artifact_ids: tuple[str, ...]
    supported_modes: tuple[RecomputeExecutionMode, ...]
    required_mode: RecomputeExecutionMode
    blocking_reasons: tuple[str, ...]


class _DatasetAuditRepository(Protocol):
    def load_dataset_audit_view(self, dataset_id: str) -> DatasetAuditView:
        raise NotImplementedError


_DB_NATIVE_REQUEST_REASONS = frozenset(
    {
        "db_native",
        "db_native_recompute",
        "db-backed-native-recompute",
    }
)


def build_db_recompute_boundary_view(
    *,
    repository: _DatasetAuditRepository,
    dataset_id: str,
    requested_reason: str | None = None,
) -> DbRecomputeBoundaryView:
    audit_view = repository.load_dataset_audit_view(dataset_id)
    source_artifact_ids = tuple(audit_view.source_artifact_ids)
    if not source_artifact_ids:
        raise P5ArtifactRepositoryError(
            "missing source artifacts for dataset in DB repository: "
            f"{dataset_id}"
        )
    if len(audit_view.source_artifacts) != len(source_artifact_ids):
        raise P5ArtifactRepositoryError(
            "source artifact audit records do not match source artifact ids "
            f"for dataset in DB repository: {dataset_id}"
        )

    normalized_reason = _normalize_reason(requested_reason)
    required_mode = _required_mode_for_reason(normalized_reason)
    supported_modes = _supported_modes_for_source_artifacts(source_artifact_ids)
    blocking_reasons = _blocking_reasons(
        normalized_reason=normalized_reason,
        required_mode=required_mode,
        source_artifact_ids=source_artifact_ids,
    )
    return DbRecomputeBoundaryView(
        dataset_id=audit_view.dataset_id,
        latest_recompute_run_id=audit_view.latest_recompute_run_id,
        latest_recompute_reason=audit_view.latest_recompute_reason,
        latest_lifecycle_audit_present=(
            audit_view.latest_lifecycle_recompute_audit is not None
        ),
        source_artifact_ids=source_artifact_ids,
        supported_modes=supported_modes,
        required_mode=required_mode,
        blocking_reasons=blocking_reasons,
    )


def _normalize_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    normalized = reason.strip().lower()
    return normalized or None


def _required_mode_for_reason(
    normalized_reason: str | None,
) -> RecomputeExecutionMode:
    if normalized_reason in _DB_NATIVE_REQUEST_REASONS:
        return RecomputeExecutionMode.DB_NATIVE_UNSUPPORTED
    return RecomputeExecutionMode.JSON_FIRST_REQUIRED


def _supported_modes_for_source_artifacts(
    source_artifact_ids: tuple[str, ...],
) -> tuple[RecomputeExecutionMode, ...]:
    if len(source_artifact_ids) == 1:
        return (
            RecomputeExecutionMode.JSON_FIRST_REQUIRED,
            RecomputeExecutionMode.DB_ASSEMBLY_AVAILABLE,
        )
    return (RecomputeExecutionMode.JSON_FIRST_REQUIRED,)


def _blocking_reasons(
    *,
    normalized_reason: str | None,
    required_mode: RecomputeExecutionMode,
    source_artifact_ids: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if required_mode is RecomputeExecutionMode.DB_NATIVE_UNSUPPORTED:
        reasons.append("DB-native recompute is not supported in this phase")
    elif normalized_reason is not None:
        reasons.append(
            f"reason {normalized_reason} requires the JSON-first recompute executor"
        )
    else:
        reasons.append("recompute execution remains JSON-first in this phase")

    if len(source_artifact_ids) == 1:
        reasons.append(
            "DB assembly is available for persisted single-artifact inputs but is "
            "not a recompute executor"
        )
    else:
        reasons.append(
            "DB assembly is currently limited to persisted single-artifact assembly "
            "and is not a recompute executor"
        )
    return tuple(reasons)
