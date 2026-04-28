from __future__ import annotations

from pathlib import Path

from financial_report_analysis.p5.json_to_db_sync import (
    JsonToDbSyncAuditView,
    JsonToDbSyncStatus,
)
from financial_report_analysis.storage.database import create_sqlite_engine, initialize_database
from financial_report_analysis.storage.repositories import SqlAlchemyP5ArtifactRepository


def _repository(tmp_path: Path) -> SqlAlchemyP5ArtifactRepository:
    engine = create_sqlite_engine(tmp_path / "sync-metadata.db")
    initialize_database(engine)
    return SqlAlchemyP5ArtifactRepository(engine)


def _sync_view(
    sync_id: str,
    *,
    dataset_id: str = "dataset-1",
    recompute_run_id: str | None = "recompute-run-1",
    status: JsonToDbSyncStatus = JsonToDbSyncStatus.COMPLETED,
    created_at: str = "2026-04-24T00:00:00+00:00",
) -> JsonToDbSyncAuditView:
    return JsonToDbSyncAuditView(
        sync_id=sync_id,
        recompute_run_id=recompute_run_id,
        dataset_id=dataset_id,
        status=status,
        input_hashes={"artifact-1": f"input-{sync_id}"},
        before_refs={"dataset": f"before-{sync_id}"},
        after_refs={"dataset": f"after-{sync_id}"},
        written_refs={"dataset": f"written-{sync_id}"},
        skipped_refs={"turtle_export": f"skipped-{sync_id}"},
        blocking_reasons=(f"blocking-{sync_id}",),
        requested_by="integration-test",
        sync_reason="metadata persistence test",
        created_at=created_at,
        completed_at="2026-04-24T00:01:00+00:00",
    )


def test_json_to_db_sync_result_persists_and_loads_by_sync_id(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    view = _sync_view(
        "sync-roundtrip",
        status=JsonToDbSyncStatus.SKIPPED_IDEMPOTENT,
    )

    assert repository.save_json_to_db_sync_result(view) == "sync-roundtrip"

    loaded = repository.load_json_to_db_sync_result("sync-roundtrip")
    assert loaded == view
    assert loaded.status is JsonToDbSyncStatus.SKIPPED_IDEMPOTENT


def test_json_to_db_sync_latest_loaders_order_by_created_at_then_sync_id(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    older = _sync_view(
        "sync-older",
        dataset_id="dataset-1",
        recompute_run_id="recompute-run-1",
        created_at="2026-04-24T00:00:00+00:00",
    )
    same_timestamp_lower_sync_id = _sync_view(
        "sync-a",
        dataset_id="dataset-1",
        recompute_run_id="recompute-run-1",
        status=JsonToDbSyncStatus.PARTIAL,
        created_at="2026-04-24T01:00:00+00:00",
    )
    expected_latest = _sync_view(
        "sync-z",
        dataset_id="dataset-1",
        recompute_run_id="recompute-run-1",
        status=JsonToDbSyncStatus.FAILED,
        created_at="2026-04-24T01:00:00+00:00",
    )
    other_dataset = _sync_view(
        "sync-other-dataset",
        dataset_id="dataset-2",
        recompute_run_id="recompute-run-1",
        created_at="2026-04-24T02:00:00+00:00",
    )
    other_recompute_run = _sync_view(
        "sync-other-recompute",
        dataset_id="dataset-1",
        recompute_run_id="recompute-run-2",
        created_at="2026-04-24T03:00:00+00:00",
    )

    for view in (
        older,
        same_timestamp_lower_sync_id,
        expected_latest,
        other_dataset,
        other_recompute_run,
    ):
        repository.save_json_to_db_sync_result(view)

    assert (
        repository.load_latest_json_to_db_sync_for_dataset("dataset-1")
        == other_recompute_run
    )
    assert (
        repository.load_latest_json_to_db_sync_for_recompute_run("recompute-run-1")
        == other_dataset
    )
    assert repository.load_latest_json_to_db_sync_for_dataset("missing") is None
    assert (
        repository.load_latest_json_to_db_sync_for_recompute_run("missing")
        is None
    )
