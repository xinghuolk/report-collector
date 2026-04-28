from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from financial_report_analysis.p5.artifact_repository import P5ArtifactRepositoryError
from financial_report_analysis.p5.json_to_db_sync import (
    JsonToDbSyncAuditView,
    JsonToDbSyncStatus,
)
from financial_report_analysis.storage.database import create_sqlite_engine, initialize_database
from financial_report_analysis.storage.models import JsonToDbSyncRecord
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
    created_at: str | None = "2026-04-24T00:00:00+00:00",
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
        created_at="2026-04-23T02:00:00+00:00",
    )
    other_recompute_run = _sync_view(
        "sync-other-recompute",
        dataset_id="dataset-1",
        recompute_run_id="recompute-run-2",
        created_at="2026-04-23T03:00:00+00:00",
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
        repository.load_latest_json_to_db_sync_for_dataset("dataset-1") == expected_latest
    )
    assert (
        repository.load_latest_json_to_db_sync_for_recompute_run("recompute-run-1")
        == expected_latest
    )
    assert repository.load_latest_json_to_db_sync_for_dataset("dataset-2") == other_dataset
    assert (
        repository.load_latest_json_to_db_sync_for_recompute_run("recompute-run-2")
        == other_recompute_run
    )
    assert repository.load_latest_json_to_db_sync_for_dataset("missing") is None
    assert (
        repository.load_latest_json_to_db_sync_for_recompute_run("missing")
        is None
    )


def test_json_to_db_sync_save_fills_missing_created_at_for_stable_latest_ordering(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    older = _sync_view(
        "sync-old-explicit-created-at",
        dataset_id="dataset-default-created-at",
        created_at="2000-01-01T00:00:00+00:00",
    )
    missing_created_at = _sync_view(
        "sync-missing-created-at",
        dataset_id="dataset-default-created-at",
        created_at=None,
    )

    repository.save_json_to_db_sync_result(older)
    repository.save_json_to_db_sync_result(missing_created_at)

    loaded = repository.load_json_to_db_sync_result("sync-missing-created-at")
    assert loaded.created_at is not None
    assert loaded.created_at != ""
    assert (
        repository.load_latest_json_to_db_sync_for_dataset("dataset-default-created-at")
        == loaded
    )


def test_json_to_db_sync_load_wraps_invalid_status_with_sync_id_and_field(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    with Session(repository.engine) as session:
        session.add(
            JsonToDbSyncRecord(
                sync_id="sync-invalid-status",
                recompute_run_id="recompute-run-1",
                dataset_id="dataset-1",
                status="not-a-status",
                input_hashes_json='{"artifact-1": "hash-1"}',
                before_refs_json='{"dataset": "before"}',
                after_refs_json='{"dataset": "after"}',
                written_refs_json='{}',
                skipped_refs_json='{}',
                blocking_reasons_json="[]",
                requested_by=None,
                sync_reason=None,
                created_at="2026-04-24T00:00:00+00:00",
                completed_at=None,
            )
        )
        session.commit()

    with pytest.raises(P5ArtifactRepositoryError, match="sync-invalid-status.*status"):
        repository.load_json_to_db_sync_result("sync-invalid-status")


@pytest.mark.parametrize(
    ("field_name", "column_values"),
    (
        (
            "input_hashes",
            {"input_hashes_json": '["not", "a", "mapping"]'},
        ),
        (
            "before_refs",
            {"before_refs_json": '{"dataset": 123}'},
        ),
        (
            "blocking_reasons",
            {"blocking_reasons_json": '["ok", 123]'},
        ),
    ),
)
def test_json_to_db_sync_load_wraps_invalid_json_shapes_with_sync_id_and_field(
    tmp_path: Path,
    field_name: str,
    column_values: dict[str, str],
) -> None:
    repository = _repository(tmp_path)
    values = {
        "input_hashes_json": '{"artifact-1": "hash-1"}',
        "before_refs_json": '{"dataset": "before"}',
        "after_refs_json": '{"dataset": "after"}',
        "written_refs_json": "{}",
        "skipped_refs_json": "{}",
        "blocking_reasons_json": "[]",
    }
    values.update(column_values)
    with Session(repository.engine) as session:
        session.add(
            JsonToDbSyncRecord(
                sync_id=f"sync-invalid-{field_name}",
                recompute_run_id="recompute-run-1",
                dataset_id="dataset-1",
                status=JsonToDbSyncStatus.COMPLETED.value,
                requested_by=None,
                sync_reason=None,
                created_at="2026-04-24T00:00:00+00:00",
                completed_at=None,
                **values,
            )
        )
        session.commit()

    with pytest.raises(
        P5ArtifactRepositoryError,
        match=rf"sync-invalid-{field_name}.*{field_name}",
    ):
        repository.load_json_to_db_sync_result(f"sync-invalid-{field_name}")
