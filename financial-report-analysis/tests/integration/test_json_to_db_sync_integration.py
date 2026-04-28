from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from financial_report_analysis.p5.artifact_repository import (
    P5ArtifactRepositoryError,
    extracted_artifact_to_payload,
)
from financial_report_analysis.p5.json_to_db_sync import (
    JsonToDbSyncAuditView,
    JsonToDbSyncRequest,
    JsonToDbSyncStatus,
    compute_payload_hash,
    sync_json_recompute_to_db,
)
from financial_report_analysis.p5.recompute import recompute_result_to_payload
from financial_report_analysis.p5.review import dataset_review_surface_to_payload
from financial_report_analysis.p5.models import (
    P5DatasetArtifact,
    P5DatasetReviewSurface,
    P5DatasetRow,
    P5ExtractedArtifact,
    P5ManifestEntry,
    P5RecomputeDiffSummary,
    P5RecomputePlan,
    P5RecomputeResult,
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


def _entry(tmp_path: Path) -> P5ManifestEntry:
    pdf_path = tmp_path / "CN_601919_2025.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    return P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
        company_name="测试公司",
        report_language="zh",
    )


def _artifact(entry: P5ManifestEntry) -> P5ExtractedArtifact:
    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={"document_id": str(entry.pdf_path), "pdf_path": str(entry.pdf_path)},
        document_metadata={},
        candidate_facts=(),
        canonical_facts=({"fact_id": f"canonical-{entry.artifact_id}"},),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={},
        created_at="2026-04-28T00:00:00+00:00",
    )


def _dataset(
    artifact: P5ExtractedArtifact,
    *,
    dataset_version: str = "1.0",
    value: float = 100.0,
) -> P5DatasetArtifact:
    return P5DatasetArtifact(
        dataset_id="dataset-1",
        dataset_version=dataset_version,
        created_at="2026-04-28T00:00:00+00:00",
        issuer_count=1,
        periods=(2025,),
        metrics=("revenue",),
        rows=(
            P5DatasetRow(
                issuer_id=artifact.manifest_entry.issuer_id,
                market=artifact.manifest_entry.market,
                stock_code=artifact.manifest_entry.stock_code,
                fiscal_year=artifact.manifest_entry.fiscal_year,
                metric_id="revenue",
                entity_scope="consolidated",
                period_scope="duration",
                statement_type="income_statement",
                value=value,
                currency="CNY",
                unit="currency_amount",
                quality_status="ok",
                missing_status="present",
                source_fact_id=f"canonical-{artifact.artifact_id}",
                source_artifact_id=artifact.artifact_id,
                evidence_bundle_id=f"bundle-{artifact.artifact_id}",
            ),
        ),
        quality_summary={"present_row_count": 1, "missing_row_count": 0},
        source_artifacts=(artifact.artifact_id,),
    )


def _dataset_review_surface(dataset: P5DatasetArtifact) -> P5DatasetReviewSurface:
    return P5DatasetReviewSurface(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        issuer_count=dataset.issuer_count,
        period_count=len(dataset.periods),
        pipeline_versions=("p5-v1",),
        source_artifact_ids=dataset.source_artifacts,
        present_row_count=1,
        missing_row_count=0,
        review_required_artifact_ids=(),
    )


def _seed_sync_request(
    tmp_path: Path,
) -> tuple[SqlAlchemyP5ArtifactRepository, JsonToDbSyncRequest]:
    repository = _repository(tmp_path)
    artifact = _artifact(_entry(tmp_path))
    repository.save_extracted_artifact(artifact)
    before_dataset = _dataset(artifact, dataset_version="1.0", value=100.0)
    repository.save_dataset_artifact(before_dataset)
    after_dataset = replace(before_dataset, dataset_version="2.0", rows=())
    plan = P5RecomputePlan(
        manifest_id="manifest-1",
        dataset_id=after_dataset.dataset_id,
        target_artifact_ids=after_dataset.source_artifacts,
        rebuild_dataset=True,
        rebuild_turtle_export=False,
        reason="pipeline_version_changed",
    )
    recompute_result = P5RecomputeResult(
        manifest_id="manifest-1",
        extracted_artifact_ids=after_dataset.source_artifacts,
        dataset_path=tmp_path / "dataset.json",
        turtle_export_path=tmp_path / "turtle.json",
        diff_summary=P5RecomputeDiffSummary(
            reason="pipeline_version_changed",
            target_artifact_ids=after_dataset.source_artifacts,
            dataset_changed=True,
            turtle_export_changed=False,
            rebuilt_dataset=True,
            rebuilt_turtle_export=False,
        ),
    )
    request = JsonToDbSyncRequest(
        recompute_run_id="sync-service-recompute-run-1",
        plan=plan,
        recompute_result=recompute_result,
        dataset=after_dataset,
        dataset_review_surface=_dataset_review_surface(after_dataset),
        turtle_export=None,
        turtle_export_review_surface=None,
        lineage_records=(),
        lifecycle_recompute_audit=None,
        input_hashes={
            artifact.artifact_id: compute_payload_hash(
                extracted_artifact_to_payload(artifact)
            )
        },
        before_refs=repository.load_current_json_to_db_before_refs(
            before_dataset.dataset_id
        ),
        requested_by="integration-test",
        sync_reason="integration success",
    )
    return repository, request


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


def test_sync_service_writes_dataset_bundle_recompute_and_sync_metadata(
    tmp_path: Path,
) -> None:
    repository, request = _seed_sync_request(tmp_path)

    result = sync_json_recompute_to_db(repository=repository, request=request)

    assert result.status is JsonToDbSyncStatus.COMPLETED
    assert repository.load_dataset_artifact(request.dataset.dataset_id) == request.dataset
    assert repository.load_dataset_review_surface(request.dataset.dataset_id) == (
        request.dataset_review_surface
    )
    assert repository.load_recompute_result(request.recompute_run_id) == (
        request.recompute_result
    )
    latest = repository.load_latest_json_to_db_sync_for_dataset(
        request.dataset.dataset_id
    )
    assert latest is not None
    assert latest.sync_id == result.sync_id
    assert latest.status is JsonToDbSyncStatus.COMPLETED
    assert latest.before_refs == request.before_refs
    expected_after_refs = {
        "dataset_id": request.dataset.dataset_id,
        "dataset_payload_hash": repository.compute_dataset_artifact_hash(
            request.dataset.dataset_id
        ),
        "dataset_review_surface_hash": compute_payload_hash(
            dataset_review_surface_to_payload(request.dataset_review_surface)
        ),
        "lineage_payload_hash": compute_payload_hash(()),
        "recompute_result_hash": compute_payload_hash(
            recompute_result_to_payload(request.recompute_result)
        ),
    }
    assert latest.after_refs == expected_after_refs
    assert latest.written_refs == {
        **expected_after_refs,
        "recompute_run_id": request.recompute_run_id,
    }


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
