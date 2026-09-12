from __future__ import annotations

from typing import cast

import pytest

from financial_report_analysis.models import MetricLifecycleRecomputeAudit
from financial_report_analysis.p5.artifact_repository import P5ArtifactRepositoryError
from financial_report_analysis.p5.db_recompute_boundary import (
    RecomputeExecutionMode,
    build_db_recompute_boundary_view,
)
from financial_report_analysis.p5.json_to_db_sync import (
    JsonToDbSyncAuditView,
    JsonToDbSyncStatus,
)
from financial_report_analysis.storage.repositories import (
    DatasetAuditView,
    SourceArtifactAuditRecord,
)


class _FakeRepository:
    def __init__(self, audit_view: DatasetAuditView) -> None:
        self.audit_view = audit_view

    def load_dataset_audit_view(self, dataset_id: str) -> DatasetAuditView:
        if dataset_id != self.audit_view.dataset_id:
            raise AssertionError(f"unexpected dataset id: {dataset_id}")
        return self.audit_view


def _audit_view(
    *,
    source_artifact_ids: tuple[str, ...] = ("artifact-1",),
    source_audit_artifact_ids: tuple[str, ...] | None = None,
    source_artifact_count: int | None = None,
    latest_recompute_reason: str | None = None,
    lifecycle_audit_present: bool = False,
) -> DatasetAuditView:
    audit_artifact_ids = (
        source_artifact_ids
        if source_audit_artifact_ids is None
        else source_audit_artifact_ids
    )
    artifact_count = (
        len(audit_artifact_ids)
        if source_artifact_count is None
        else source_artifact_count
    )
    source_artifacts = tuple(
        SourceArtifactAuditRecord(
            source_artifact_id=(
                audit_artifact_ids[index]
                if index < len(audit_artifact_ids)
                else f"extra-artifact-{index}"
            ),
            report_id=None,
            source_pdf_path=None,
            manifest_entry_key=None,
            extracted_review_surface=None,
        )
        for index in range(artifact_count)
    )
    return DatasetAuditView(
        dataset_id="dataset-1",
        source_artifact_ids=source_artifact_ids,
        source_artifacts=source_artifacts,
        dataset_review_surface=None,
        turtle_export_review_surface=None,
        latest_recompute_run_id=(
            "recompute-run-1" if latest_recompute_reason is not None else None
        ),
        latest_recompute_reason=latest_recompute_reason,
        latest_lifecycle_recompute_audit=(
            cast(MetricLifecycleRecomputeAudit, object())
            if lifecycle_audit_present
            else None
        ),
    )


def _sync_view(
    status: JsonToDbSyncStatus,
    *,
    recompute_run_id: str = "recompute-run-1",
) -> JsonToDbSyncAuditView:
    return JsonToDbSyncAuditView(
        sync_id="sync-1",
        recompute_run_id=recompute_run_id,
        dataset_id="dataset-1",
        status=status,
        input_hashes={"artifact-1": "hash-1"},
        before_refs={"dataset": "before"},
        after_refs={"dataset": "after"},
        written_refs={"dataset": "dataset-1"},
        skipped_refs={},
        blocking_reasons=(),
        requested_by="test",
        sync_reason="pipeline_version_changed",
        created_at="2026-04-28T00:00:00+00:00",
        completed_at="2026-04-28T00:00:01+00:00",
    )


def test_boundary_exposes_latest_json_to_db_sync_status() -> None:
    audit_view = _audit_view(latest_recompute_reason="pipeline_version_changed")
    audit_view = DatasetAuditView(
        dataset_id=audit_view.dataset_id,
        source_artifact_ids=audit_view.source_artifact_ids,
        source_artifacts=audit_view.source_artifacts,
        dataset_review_surface=audit_view.dataset_review_surface,
        turtle_export_review_surface=audit_view.turtle_export_review_surface,
        latest_recompute_run_id=audit_view.latest_recompute_run_id,
        latest_recompute_reason=audit_view.latest_recompute_reason,
        latest_lifecycle_recompute_audit=audit_view.latest_lifecycle_recompute_audit,
        latest_json_to_db_sync=_sync_view(JsonToDbSyncStatus.COMPLETED),
    )

    view = build_db_recompute_boundary_view(
        repository=_FakeRepository(audit_view),
        dataset_id="dataset-1",
    )

    assert view.latest_json_to_db_sync_status is JsonToDbSyncStatus.COMPLETED
    assert view.latest_json_to_db_sync_id == "sync-1"
    assert view.json_to_db_sync_effective_status is JsonToDbSyncStatus.COMPLETED
    assert view.json_to_db_sync_blocking_reasons == ()


def test_boundary_does_not_treat_old_sync_as_current_recompute_state() -> None:
    audit_view = _audit_view(latest_recompute_reason="pipeline_version_changed")
    audit_view = DatasetAuditView(
        dataset_id=audit_view.dataset_id,
        source_artifact_ids=audit_view.source_artifact_ids,
        source_artifacts=audit_view.source_artifacts,
        dataset_review_surface=audit_view.dataset_review_surface,
        turtle_export_review_surface=audit_view.turtle_export_review_surface,
        latest_recompute_run_id="recompute-run-2",
        latest_recompute_reason=audit_view.latest_recompute_reason,
        latest_lifecycle_recompute_audit=audit_view.latest_lifecycle_recompute_audit,
        latest_json_to_db_sync=_sync_view(
            JsonToDbSyncStatus.COMPLETED,
            recompute_run_id="recompute-run-1",
        ),
    )

    view = build_db_recompute_boundary_view(
        repository=_FakeRepository(audit_view),
        dataset_id="dataset-1",
    )

    assert view.latest_json_to_db_sync_status is JsonToDbSyncStatus.COMPLETED
    assert view.json_to_db_sync_effective_status is JsonToDbSyncStatus.OUT_OF_SYNC
    assert "sync_recompute_run_mismatch" in view.json_to_db_sync_blocking_reasons


def test_lifecycle_reason_requires_json_first_and_reports_lifecycle_audit() -> None:
    view = build_db_recompute_boundary_view(
        repository=_FakeRepository(
            _audit_view(
                latest_recompute_reason="metric_lifecycle_decision_changed",
                lifecycle_audit_present=True,
            )
        ),
        dataset_id="dataset-1",
        requested_reason="metric_lifecycle_decision_changed",
    )

    assert view.dataset_id == "dataset-1"
    assert view.latest_recompute_run_id == "recompute-run-1"
    assert view.latest_recompute_reason == "metric_lifecycle_decision_changed"
    assert view.latest_lifecycle_audit_present is True
    assert view.source_artifact_ids == ("artifact-1",)
    assert view.required_mode is RecomputeExecutionMode.JSON_FIRST_REQUIRED
    assert view.supported_modes == (
        RecomputeExecutionMode.JSON_FIRST_REQUIRED,
        RecomputeExecutionMode.DB_ASSEMBLY_AVAILABLE,
    )
    assert view.blocking_reasons == (
        "reason metric_lifecycle_decision_changed requires the JSON-first "
        "recompute executor",
        "DB assembly is available for persisted single-artifact inputs but is "
        "not a recompute executor",
    )


def test_db_native_request_is_reported_as_unsupported() -> None:
    view = build_db_recompute_boundary_view(
        repository=_FakeRepository(_audit_view(source_artifact_ids=("artifact-1",))),
        dataset_id="dataset-1",
        requested_reason="db_native_recompute",
    )

    assert view.required_mode is RecomputeExecutionMode.DB_NATIVE_UNSUPPORTED
    assert view.supported_modes == (
        RecomputeExecutionMode.JSON_FIRST_REQUIRED,
        RecomputeExecutionMode.DB_ASSEMBLY_AVAILABLE,
    )
    assert view.blocking_reasons == (
        "DB-native recompute is not supported in this phase",
        "DB assembly is available for persisted single-artifact inputs but is "
        "not a recompute executor",
    )


def test_multi_artifact_dataset_does_not_claim_db_assembly_available() -> None:
    view = build_db_recompute_boundary_view(
        repository=_FakeRepository(
            _audit_view(source_artifact_ids=("artifact-1", "artifact-2"))
        ),
        dataset_id="dataset-1",
        requested_reason="manual_review_check",
    )

    assert view.required_mode is RecomputeExecutionMode.JSON_FIRST_REQUIRED
    assert view.supported_modes == (RecomputeExecutionMode.JSON_FIRST_REQUIRED,)
    assert view.blocking_reasons == (
        "reason manual_review_check requires the JSON-first recompute executor",
        "DB assembly is currently limited to persisted single-artifact assembly "
        "and is not a recompute executor",
    )


def test_empty_source_artifacts_fail_fast_with_repository_error() -> None:
    with pytest.raises(
        P5ArtifactRepositoryError,
        match="missing source artifacts for dataset in DB repository",
    ):
        build_db_recompute_boundary_view(
            repository=_FakeRepository(_audit_view(source_artifact_ids=())),
            dataset_id="dataset-1",
        )


def test_source_artifact_id_count_must_match_loaded_audit_records() -> None:
    with pytest.raises(
        P5ArtifactRepositoryError,
        match="source artifact audit records do not match source artifact ids",
    ):
        build_db_recompute_boundary_view(
            repository=_FakeRepository(
                _audit_view(
                    source_artifact_ids=("artifact-1",),
                    source_artifact_count=0,
                )
            ),
            dataset_id="dataset-1",
        )


def test_source_artifact_ids_must_match_loaded_audit_record_ids() -> None:
    with pytest.raises(
        P5ArtifactRepositoryError,
        match="source artifact audit record ids do not match source artifact ids",
    ):
        build_db_recompute_boundary_view(
            repository=_FakeRepository(
                _audit_view(
                    source_artifact_ids=("artifact-1",),
                    source_audit_artifact_ids=("artifact-2",),
                )
            ),
            dataset_id="dataset-1",
        )
