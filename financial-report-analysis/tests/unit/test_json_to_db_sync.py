from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from financial_report_analysis.models import MetricLifecycleRecomputeAudit
from financial_report_analysis.p5.artifact_repository import P5ArtifactRepositoryError
from financial_report_analysis.p5.json_to_db_sync import (
    JsonToDbSyncAuditView,
    JsonToDbSyncRequest,
    JsonToDbSyncStatus,
    build_json_to_db_sync_id,
    compute_payload_hash,
    validate_json_to_db_sync_request,
)
from financial_report_analysis.p5.models import (
    P5DatasetArtifact,
    P5DatasetReviewSurface,
    P5RecomputeDiffSummary,
    P5RecomputePlan,
    P5RecomputeResult,
    P5TurtleExport,
    P5TurtleExportReviewSurface,
)


def _dataset() -> P5DatasetArtifact:
    return P5DatasetArtifact(
        dataset_id="dataset-1",
        dataset_version="1.0",
        created_at="2026-04-28T00:00:00+00:00",
        issuer_count=1,
        periods=(2025,),
        metrics=("revenue",),
        rows=(),
        quality_summary={},
        source_artifacts=("artifact-1",),
    )


def _dataset_review_surface() -> P5DatasetReviewSurface:
    return P5DatasetReviewSurface(
        dataset_id="dataset-1",
        dataset_version="1.0",
        issuer_count=1,
        period_count=1,
        pipeline_versions=("p5-v1",),
        source_artifact_ids=("artifact-1",),
        present_row_count=0,
        missing_row_count=0,
        review_required_artifact_ids=(),
    )


def _plan() -> P5RecomputePlan:
    return P5RecomputePlan(
        manifest_id="manifest-1",
        dataset_id="dataset-1",
        target_artifact_ids=("artifact-1",),
        rebuild_dataset=True,
        rebuild_turtle_export=True,
        reason="pipeline_version_changed",
    )


def _result() -> P5RecomputeResult:
    return P5RecomputeResult(
        manifest_id="manifest-1",
        extracted_artifact_ids=("artifact-1",),
        dataset_path=Path("dataset.json"),
        turtle_export_path=Path("turtle.json"),
        diff_summary=P5RecomputeDiffSummary(
            reason="pipeline_version_changed",
            target_artifact_ids=("artifact-1",),
            dataset_changed=True,
            turtle_export_changed=True,
            rebuilt_dataset=True,
            rebuilt_turtle_export=True,
        ),
    )


def _request() -> JsonToDbSyncRequest:
    return JsonToDbSyncRequest(
        recompute_run_id="recompute-run-1",
        plan=_plan(),
        recompute_result=_result(),
        dataset=_dataset(),
        dataset_review_surface=_dataset_review_surface(),
        turtle_export=None,
        turtle_export_review_surface=None,
        lineage_records=(),
        lifecycle_recompute_audit=None,
        input_hashes={"artifact-1": "hash-1"},
        before_refs={"dataset": "dataset-hash-1", "recompute_run": "none"},
        requested_by="test",
        sync_reason="test-sync",
    )


def test_status_values_are_stable() -> None:
    assert [status.value for status in JsonToDbSyncStatus] == [
        "pending",
        "completed",
        "failed",
        "partial",
        "skipped_idempotent",
        "not_attempted",
        "out_of_sync",
    ]


def test_sync_id_is_deterministic_for_run_dataset_and_hashes() -> None:
    request = _request()

    assert build_json_to_db_sync_id(request) == build_json_to_db_sync_id(request)
    assert build_json_to_db_sync_id(request).startswith(
        "json-to-db-sync:dataset-1:recompute-run-1:"
    )


def test_sync_id_changes_when_input_hashes_change() -> None:
    request = _request()
    changed_request = replace(request, input_hashes={"artifact-1": "hash-2"})

    assert build_json_to_db_sync_id(request) != build_json_to_db_sync_id(
        changed_request
    )


def test_sync_id_changes_when_before_refs_change() -> None:
    request = _request()
    changed_request = replace(
        request,
        before_refs={"dataset": "dataset-hash-2", "recompute_run": "none"},
    )

    assert build_json_to_db_sync_id(request) != build_json_to_db_sync_id(
        changed_request
    )


def test_sync_id_changes_when_after_identity_changes() -> None:
    request = _request()
    changed_request = replace(
        request,
        dataset=replace(_dataset(), dataset_version="2.0"),
    )

    assert build_json_to_db_sync_id(request) != build_json_to_db_sync_id(
        changed_request
    )


def test_sync_id_changes_when_after_payload_changes_without_identity_change() -> None:
    request = _request()
    changed_request = replace(
        request,
        dataset=replace(_dataset(), quality_summary={"quality": "changed"}),
    )

    assert build_json_to_db_sync_id(request) != build_json_to_db_sync_id(
        changed_request
    )


def test_request_accepts_null_requested_by() -> None:
    request = replace(_request(), requested_by=None)

    assert request.requested_by is None


def test_payload_hash_is_order_insensitive_for_dict_keys() -> None:
    assert compute_payload_hash({"b": 2, "a": 1}) == compute_payload_hash(
        {"a": 1, "b": 2}
    )


def test_audit_view_carries_complete_sync_metadata() -> None:
    view = JsonToDbSyncAuditView(
        sync_id="json-to-db-sync:dataset-1:recompute-run-1:hash",
        recompute_run_id="recompute-run-1",
        dataset_id="dataset-1",
        status=JsonToDbSyncStatus.COMPLETED,
        input_hashes={"artifact-1": "hash-1"},
        before_refs={"dataset": "dataset-hash-1"},
        after_refs={"dataset": "dataset-hash-2"},
        written_refs={"dataset": "dataset-hash-2"},
        skipped_refs={},
        blocking_reasons=(),
        requested_by="test",
        sync_reason="test-sync",
        created_at="2026-04-28T00:00:00+00:00",
        completed_at="2026-04-28T00:00:01+00:00",
    )

    assert view.dataset_id == "dataset-1"
    assert view.input_hashes == {"artifact-1": "hash-1"}
    assert view.after_refs == {"dataset": "dataset-hash-2"}
    assert view.requested_by == "test"


def test_validate_rejects_empty_source_artifacts() -> None:
    invalid_request = replace(
        _request(),
        dataset=replace(_dataset(), source_artifacts=()),
    )

    with pytest.raises(P5ArtifactRepositoryError, match="source artifacts are required"):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_rejects_dataset_id_mismatch() -> None:
    invalid_request = replace(
        _request(),
        plan=replace(_plan(), dataset_id="other-dataset"),
    )

    with pytest.raises(P5ArtifactRepositoryError, match="dataset id mismatch"):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_rejects_manifest_id_mismatch() -> None:
    invalid_request = replace(
        _request(),
        recompute_result=replace(_result(), manifest_id="other-manifest"),
    )

    with pytest.raises(P5ArtifactRepositoryError, match="manifest id mismatch"):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_rejects_source_artifact_mismatch_between_dataset_and_result() -> None:
    invalid_request = replace(
        _request(),
        recompute_result=replace(_result(), extracted_artifact_ids=("artifact-2",)),
    )

    with pytest.raises(P5ArtifactRepositoryError, match="source artifact mismatch"):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_rejects_plan_target_artifact_mismatch() -> None:
    invalid_request = replace(
        _request(),
        plan=replace(_plan(), target_artifact_ids=("artifact-2",)),
    )

    with pytest.raises(P5ArtifactRepositoryError, match="plan target artifacts"):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_rejects_diff_summary_target_artifact_mismatch() -> None:
    invalid_request = replace(
        _request(),
        recompute_result=replace(
            _result(),
            diff_summary=replace(
                _result().diff_summary,
                target_artifact_ids=("artifact-2",),
            ),
        ),
    )

    with pytest.raises(P5ArtifactRepositoryError, match="diff summary target artifacts"):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_allows_plan_target_subset_of_dataset_source_artifacts() -> None:
    dataset = replace(_dataset(), source_artifacts=("artifact-1", "artifact-2"))
    review_surface = replace(
        _dataset_review_surface(),
        source_artifact_ids=("artifact-1", "artifact-2"),
    )
    result = replace(_result(), extracted_artifact_ids=("artifact-1", "artifact-2"))
    request = replace(
        _request(),
        dataset=dataset,
        dataset_review_surface=review_surface,
        recompute_result=result,
        input_hashes={"artifact-1": "hash-1", "artifact-2": "hash-2"},
    )

    validate_json_to_db_sync_request(request)


def test_validate_rejects_input_hash_source_artifact_mismatch() -> None:
    invalid_request = replace(_request(), input_hashes={"artifact-2": "hash-2"})

    with pytest.raises(P5ArtifactRepositoryError, match="input hash source artifacts"):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_rejects_turtle_review_surface_without_turtle_export() -> None:
    invalid_request = replace(
        _request(),
        turtle_export=None,
        turtle_export_review_surface=P5TurtleExportReviewSurface(
            dataset_id="dataset-1",
            dataset_version="1.0",
            source_artifact_ids=("artifact-1",),
            row_count=0,
            present_row_count=0,
            missing_row_count=0,
            alias_count=0,
        ),
    )

    with pytest.raises(
        P5ArtifactRepositoryError,
        match="turtle export is required when turtle export review surface is present",
    ):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_accepts_matching_turtle_export_and_review_surface() -> None:
    request = replace(
        _request(),
        turtle_export=P5TurtleExport(
            dataset_id="dataset-1",
            dataset_version="1.0",
            created_at="2026-04-28T00:00:00+00:00",
            rows=(),
        ),
        turtle_export_review_surface=P5TurtleExportReviewSurface(
            dataset_id="dataset-1",
            dataset_version="1.0",
            source_artifact_ids=("artifact-1",),
            row_count=0,
            present_row_count=0,
            missing_row_count=0,
            alias_count=0,
        ),
    )

    validate_json_to_db_sync_request(request)


def test_validate_rejects_missing_dataset_before_ref() -> None:
    invalid_request = replace(_request(), before_refs={"recompute_run": "none"})

    with pytest.raises(P5ArtifactRepositoryError, match="before dataset ref is required"):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_rejects_missing_after_dataset_review_surface() -> None:
    invalid_request = replace(_request(), dataset_review_surface=None)

    with pytest.raises(
        P5ArtifactRepositoryError,
        match="after dataset review surface is required",
    ):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_rejects_malformed_lifecycle_audit() -> None:
    invalid_request = replace(
        _request(),
        lifecycle_recompute_audit=cast(MetricLifecycleRecomputeAudit, object()),
    )

    with pytest.raises(
        P5ArtifactRepositoryError,
        match="malformed lifecycle recompute audit",
    ):
        validate_json_to_db_sync_request(invalid_request)
