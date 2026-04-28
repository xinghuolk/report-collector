# Explicit JSON-to-DB Sync Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an explicit, auditable sync bridge that writes successful JSON-first recompute outputs into DB-backed read surfaces without introducing DB-native recompute or async workflow behavior.

**Architecture:** Add a focused `p5/json_to_db_sync.py` contract/service that validates source artifacts, input hashes, before refs, recompute run identity, and after artifacts before writing through `SqlAlchemyP5ArtifactRepository`. Persist sync metadata in a dedicated DB table with pending-first semantics so dataset audit, recompute run reads, and recompute boundary views can report sync status without inferring it from payload existence.

**Tech Stack:** Python 3.10+, dataclasses, SQLAlchemy ORM, Pydantic API schemas, FastAPI routes, pytest, Ruff.

---

## File Structure

- Create `financial-report-analysis/src/financial_report_analysis/p5/json_to_db_sync.py`.
  - Owns `JsonToDbSyncStatus`, `JsonToDbSyncRequest`, `JsonToDbSyncResult`, `JsonToDbSyncAuditView`, stable hash helpers, payload conversion helpers, and `sync_json_recompute_to_db(...)`.
  - Does not import FastAPI or concrete SQLAlchemy session internals.
- Modify `financial-report-analysis/src/financial_report_analysis/storage/models.py`.
  - Adds `JsonToDbSyncRecord` SQLAlchemy model.
- Modify `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`.
  - Adds repository methods to save/load/list latest sync records.
  - Adds sync metadata to `DatasetAuditView` and `RecomputeRunAuditView`.
- Modify `financial-report-analysis/src/financial_report_analysis/p5/db_recompute_boundary.py`.
  - Extends `DbRecomputeBoundaryView` with latest sync status fields.
- Modify `financial-report-analysis/src/financial_report_analysis/api/schemas.py`.
  - Adds `JsonToDbSyncStatusResponse` and embeds it in dataset audit, recompute run, and boundary responses.
- Modify `financial-report-analysis/src/financial_report_analysis/api/routes.py`.
  - Serializes sync metadata in existing read-only endpoints.
- Add `financial-report-analysis/tests/unit/test_json_to_db_sync.py`.
  - Unit coverage for contract validation, hash mismatch, source artifact mismatch, stale before refs, missing after payloads, pending-first writes, and idempotent detection using fakes.
- Add or extend `financial-report-analysis/tests/integration/test_json_to_db_sync_integration.py`.
  - SQLite repository coverage for success, persisted readback, stale hash rejection, and partial failure status.
- Extend `financial-report-analysis/tests/integration/test_api_storage_runtime.py`.
  - API response coverage for dataset audit, recompute run, and recompute boundary sync fields.
- Update docs:
  - `docs/superpowers/specs/active/2026-04-28-financial-report-analysis-explicit-json-to-db-sync-bridge-design.md`
  - `docs/superpowers/plans/README.md`
  - `docs/superpowers/plans/active/README.md`

## Task 1: Contract And Unit Validation

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/p5/json_to_db_sync.py`
- Test: `financial-report-analysis/tests/unit/test_json_to_db_sync.py`

- [ ] **Step 1: Write failing contract tests**

Add tests that lock the exact statuses, deterministic sync id, hash helper, and validation errors.

```python
from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from financial_report_analysis.models import MetricLifecycleRecomputeAudit
from financial_report_analysis.p5.artifact_repository import P5ArtifactRepositoryError
from financial_report_analysis.p5.json_to_db_sync import (
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


def test_payload_hash_is_order_insensitive_for_dict_keys() -> None:
    assert compute_payload_hash({"b": 2, "a": 1}) == compute_payload_hash(
        {"a": 1, "b": 2}
    )


def test_validate_rejects_empty_source_artifacts() -> None:
    request = _request()
    invalid_dataset = _dataset()
    invalid_dataset = P5DatasetArtifact(
        dataset_id=invalid_dataset.dataset_id,
        dataset_version=invalid_dataset.dataset_version,
        created_at=invalid_dataset.created_at,
        issuer_count=invalid_dataset.issuer_count,
        periods=invalid_dataset.periods,
        metrics=invalid_dataset.metrics,
        rows=invalid_dataset.rows,
        quality_summary=invalid_dataset.quality_summary,
        source_artifacts=(),
    )
    invalid_request = JsonToDbSyncRequest(
        recompute_run_id=request.recompute_run_id,
        plan=request.plan,
        recompute_result=request.recompute_result,
        dataset=invalid_dataset,
        dataset_review_surface=request.dataset_review_surface,
        turtle_export=request.turtle_export,
        turtle_export_review_surface=request.turtle_export_review_surface,
        lineage_records=request.lineage_records,
        lifecycle_recompute_audit=request.lifecycle_recompute_audit,
        input_hashes=request.input_hashes,
        before_refs=request.before_refs,
        requested_by=request.requested_by,
        sync_reason=request.sync_reason,
    )

    with pytest.raises(P5ArtifactRepositoryError, match="source artifacts are required"):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_rejects_dataset_id_mismatch() -> None:
    request = _request()
    invalid_plan = P5RecomputePlan(
        manifest_id="manifest-1",
        dataset_id="other-dataset",
        target_artifact_ids=("artifact-1",),
        rebuild_dataset=True,
        rebuild_turtle_export=True,
        reason="pipeline_version_changed",
    )
    invalid_request = JsonToDbSyncRequest(
        recompute_run_id=request.recompute_run_id,
        plan=invalid_plan,
        recompute_result=request.recompute_result,
        dataset=request.dataset,
        dataset_review_surface=request.dataset_review_surface,
        turtle_export=request.turtle_export,
        turtle_export_review_surface=request.turtle_export_review_surface,
        lineage_records=request.lineage_records,
        lifecycle_recompute_audit=request.lifecycle_recompute_audit,
        input_hashes=request.input_hashes,
        before_refs=request.before_refs,
        requested_by=request.requested_by,
        sync_reason=request.sync_reason,
    )

    with pytest.raises(P5ArtifactRepositoryError, match="dataset id mismatch"):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_rejects_source_artifact_mismatch_between_dataset_and_result() -> None:
    request = _request()
    invalid_result = P5RecomputeResult(
        manifest_id="manifest-1",
        extracted_artifact_ids=("artifact-2",),
        dataset_path=Path("dataset.json"),
        turtle_export_path=Path("turtle.json"),
        diff_summary=request.recompute_result.diff_summary,
    )
    invalid_request = JsonToDbSyncRequest(
        recompute_run_id=request.recompute_run_id,
        plan=request.plan,
        recompute_result=invalid_result,
        dataset=request.dataset,
        dataset_review_surface=request.dataset_review_surface,
        turtle_export=request.turtle_export,
        turtle_export_review_surface=request.turtle_export_review_surface,
        lineage_records=request.lineage_records,
        lifecycle_recompute_audit=request.lifecycle_recompute_audit,
        input_hashes=request.input_hashes,
        before_refs=request.before_refs,
        requested_by=request.requested_by,
        sync_reason=request.sync_reason,
    )

    with pytest.raises(P5ArtifactRepositoryError, match="source artifact mismatch"):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_rejects_missing_dataset_before_ref() -> None:
    request = _request()
    invalid_request = JsonToDbSyncRequest(
        recompute_run_id=request.recompute_run_id,
        plan=request.plan,
        recompute_result=request.recompute_result,
        dataset=request.dataset,
        dataset_review_surface=request.dataset_review_surface,
        turtle_export=request.turtle_export,
        turtle_export_review_surface=request.turtle_export_review_surface,
        lineage_records=request.lineage_records,
        lifecycle_recompute_audit=request.lifecycle_recompute_audit,
        input_hashes=request.input_hashes,
        before_refs={},
        requested_by=request.requested_by,
        sync_reason=request.sync_reason,
    )

    with pytest.raises(P5ArtifactRepositoryError, match="before dataset ref is required"):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_rejects_missing_after_dataset_review_surface() -> None:
    request = _request()
    invalid_request = JsonToDbSyncRequest(
        recompute_run_id=request.recompute_run_id,
        plan=request.plan,
        recompute_result=request.recompute_result,
        dataset=request.dataset,
        dataset_review_surface=None,
        turtle_export=request.turtle_export,
        turtle_export_review_surface=request.turtle_export_review_surface,
        lineage_records=request.lineage_records,
        lifecycle_recompute_audit=request.lifecycle_recompute_audit,
        input_hashes=request.input_hashes,
        before_refs=request.before_refs,
        requested_by=request.requested_by,
        sync_reason=request.sync_reason,
    )

    with pytest.raises(P5ArtifactRepositoryError, match="after dataset review surface"):
        validate_json_to_db_sync_request(invalid_request)


def test_validate_rejects_malformed_lifecycle_audit() -> None:
    request = _request()
    invalid_request = JsonToDbSyncRequest(
        recompute_run_id=request.recompute_run_id,
        plan=request.plan,
        recompute_result=request.recompute_result,
        dataset=request.dataset,
        dataset_review_surface=request.dataset_review_surface,
        turtle_export=request.turtle_export,
        turtle_export_review_surface=request.turtle_export_review_surface,
        lineage_records=request.lineage_records,
        lifecycle_recompute_audit=cast(MetricLifecycleRecomputeAudit, object()),
        input_hashes=request.input_hashes,
        before_refs=request.before_refs,
        requested_by=request.requested_by,
        sync_reason=request.sync_reason,
    )

    with pytest.raises(P5ArtifactRepositoryError, match="malformed lifecycle audit"):
        validate_json_to_db_sync_request(invalid_request)
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_json_to_db_sync.py -q
```

Expected: fail during import with `ModuleNotFoundError: No module named 'financial_report_analysis.p5.json_to_db_sync'`.

- [ ] **Step 3: Implement the contract and validation**

Create `financial-report-analysis/src/financial_report_analysis/p5/json_to_db_sync.py` with this initial content:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
import hashlib
import json
from typing import Mapping, Protocol

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
    requested_by: str | None
    sync_reason: str


@dataclass(frozen=True, slots=True)
class JsonToDbSyncResult:
    sync_id: str
    recompute_run_id: str
    dataset_id: str
    status: JsonToDbSyncStatus
    input_hashes: dict[str, str]
    before_refs: dict[str, str]
    after_refs: dict[str, str]
    written_refs: dict[str, str]
    skipped_refs: dict[str, str]
    blocking_reasons: tuple[str, ...]
    requested_by: str | None
    sync_reason: str
    created_at: str
    completed_at: str | None


@dataclass(frozen=True, slots=True)
class JsonToDbSyncAuditView:
    sync_id: str
    recompute_run_id: str
    dataset_id: str
    status: JsonToDbSyncStatus
    input_hashes: dict[str, str]
    before_refs: dict[str, str]
    after_refs: dict[str, str]
    written_refs: dict[str, str]
    skipped_refs: dict[str, str]
    blocking_reasons: tuple[str, ...]
    requested_by: str | None
    sync_reason: str
    created_at: str
    completed_at: str | None


class JsonToDbSyncRepository(Protocol):
    def load_extracted_artifact(self, artifact_id: str): ...


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def compute_payload_hash(payload: object) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_json_to_db_sync_id(request: JsonToDbSyncRequest) -> str:
    hash_key = compute_payload_hash(dict(sorted(request.input_hashes.items())))[:16]
    return (
        f"json-to-db-sync:{request.dataset.dataset_id}:"
        f"{request.recompute_run_id}:{hash_key}"
    )


def validate_json_to_db_sync_request(request: JsonToDbSyncRequest) -> None:
    if not request.recompute_run_id.strip():
        raise P5ArtifactRepositoryError("recompute run id is required")
    if request.plan.dataset_id != request.dataset.dataset_id:
        raise P5ArtifactRepositoryError("dataset id mismatch between plan and dataset")
    if request.recompute_result.manifest_id != request.plan.manifest_id:
        raise P5ArtifactRepositoryError("manifest id mismatch between plan and result")
    if not request.dataset.source_artifacts:
        raise P5ArtifactRepositoryError("source artifacts are required for sync")
    if not request.before_refs.get("dataset"):
        raise P5ArtifactRepositoryError("before dataset ref is required for sync")
    if set(request.dataset.source_artifacts) != set(request.input_hashes):
        raise P5ArtifactRepositoryError(
            "input hashes must exactly match dataset source artifacts"
        )
    if set(request.dataset.source_artifacts) != set(
        request.recompute_result.extracted_artifact_ids
    ):
        raise P5ArtifactRepositoryError(
            "source artifact mismatch between dataset and recompute result"
        )
    if request.dataset_review_surface is None:
        raise P5ArtifactRepositoryError("after dataset review surface is required")
    if request.lifecycle_recompute_audit is not None and not isinstance(
        request.lifecycle_recompute_audit,
        MetricLifecycleRecomputeAudit,
    ):
        raise P5ArtifactRepositoryError("malformed lifecycle audit for sync")
    if request.dataset_review_surface is not None:
        if request.dataset_review_surface.dataset_id != request.dataset.dataset_id:
            raise P5ArtifactRepositoryError("dataset review surface dataset id mismatch")
    if request.turtle_export is not None:
        if request.turtle_export.dataset_id != request.dataset.dataset_id:
            raise P5ArtifactRepositoryError("turtle export dataset id mismatch")
    if request.turtle_export_review_surface is not None:
        if request.turtle_export is None:
            raise P5ArtifactRepositoryError(
                "turtle export review surface requires turtle export"
            )
        if request.turtle_export_review_surface.dataset_id != request.dataset.dataset_id:
            raise P5ArtifactRepositoryError(
                "turtle export review surface dataset id mismatch"
            )
    lineage_dataset_ids = {lineage.dataset_id for lineage in request.lineage_records}
    if lineage_dataset_ids and lineage_dataset_ids != {request.dataset.dataset_id}:
        raise P5ArtifactRepositoryError("lineage records must belong to dataset")
```

- [ ] **Step 4: Run unit tests and verify Task 1 passes**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_json_to_db_sync.py -q
```

Expected: all tests in `test_json_to_db_sync.py` pass.

- [ ] **Step 5: Run Ruff on the new module and tests**

Run:

```bash
cd financial-report-analysis
uv run ruff check src/financial_report_analysis/p5/json_to_db_sync.py tests/unit/test_json_to_db_sync.py
```

Expected: `All checks passed!`

- [ ] **Step 6: Commit Task 1**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/json_to_db_sync.py financial-report-analysis/tests/unit/test_json_to_db_sync.py
git commit -m "feat: add json to db sync contract"
```

## Task 2: Persist Sync Metadata In Storage

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/models.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Test: `financial-report-analysis/tests/integration/test_json_to_db_sync_integration.py`

- [ ] **Step 1: Write failing repository persistence tests**

Create `financial-report-analysis/tests/integration/test_json_to_db_sync_integration.py` with repository-focused tests.

```python
from __future__ import annotations

from financial_report_analysis.p5.json_to_db_sync import (
    JsonToDbSyncAuditView,
    JsonToDbSyncStatus,
)
from financial_report_analysis.storage.database import create_sqlite_engine, initialize_database
from financial_report_analysis.storage.repositories import SqlAlchemyP5ArtifactRepository


def _sync_view(
    *,
    sync_id: str = "json-to-db-sync:dataset-1:run-1:hash",
    status: JsonToDbSyncStatus = JsonToDbSyncStatus.COMPLETED,
) -> JsonToDbSyncAuditView:
    return JsonToDbSyncAuditView(
        sync_id=sync_id,
        recompute_run_id="run-1",
        dataset_id="dataset-1",
        status=status,
        input_hashes={"artifact-1": "hash-1"},
        before_refs={"dataset": "dataset-1@before"},
        after_refs={"dataset": "dataset-1@after"},
        written_refs={"dataset": "dataset-1"},
        skipped_refs={},
        blocking_reasons=(),
        requested_by="test",
        sync_reason="pipeline_version_changed",
        created_at="2026-04-28T00:00:00+00:00",
        completed_at="2026-04-28T00:00:01+00:00",
    )


def test_repository_persists_and_loads_json_to_db_sync_record(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)

    repository.save_json_to_db_sync_result(_sync_view())

    loaded = repository.load_json_to_db_sync_result(
        "json-to-db-sync:dataset-1:run-1:hash"
    )
    assert loaded == _sync_view()


def test_repository_loads_latest_sync_by_dataset_and_run(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)
    repository.save_json_to_db_sync_result(_sync_view(sync_id="sync-old"))
    repository.save_json_to_db_sync_result(
        JsonToDbSyncAuditView(
            sync_id="sync-new",
            recompute_run_id="run-2",
            dataset_id="dataset-1",
            status=JsonToDbSyncStatus.PARTIAL,
            input_hashes={"artifact-1": "hash-2"},
            before_refs={"dataset": "dataset-1@before"},
            after_refs={"dataset": "dataset-1@after-2"},
            written_refs={"dataset": "dataset-1"},
            skipped_refs={},
            blocking_reasons=("write turtle export failed",),
            requested_by="test",
            sync_reason="pipeline_version_changed",
            created_at="2026-04-28T00:00:02+00:00",
            completed_at=None,
        )
    )

    assert repository.load_latest_json_to_db_sync_for_dataset("dataset-1").sync_id == (
        "sync-new"
    )
    assert repository.load_latest_json_to_db_sync_for_recompute_run("run-2").sync_id == (
        "sync-new"
    )
```

- [ ] **Step 2: Run the repository tests and verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_json_to_db_sync_integration.py -q
```

Expected: fail because `save_json_to_db_sync_result` is not implemented.

- [ ] **Step 3: Add the SQLAlchemy model**

Modify `financial-report-analysis/src/financial_report_analysis/storage/models.py`:

```python
class JsonToDbSyncRecord(Base):
    __tablename__ = "json_to_db_sync_records"

    sync_id: Mapped[str] = mapped_column(String(192), primary_key=True)
    recompute_run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    input_hashes_json: Mapped[str] = mapped_column(Text, nullable=False)
    before_refs_json: Mapped[str] = mapped_column(Text, nullable=False)
    after_refs_json: Mapped[str] = mapped_column(Text, nullable=False)
    written_refs_json: Mapped[str] = mapped_column(Text, nullable=False)
    skipped_refs_json: Mapped[str] = mapped_column(Text, nullable=False)
    blocking_reasons_json: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(128))
    sync_reason: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), default=_utc_iso_timestamp)
    completed_at: Mapped[str | None] = mapped_column(String(64))
```

- [ ] **Step 4: Import the model and sync dataclasses in repository**

Modify imports in `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`:

```python
from financial_report_analysis.p5.json_to_db_sync import (
    JsonToDbSyncAuditView,
    JsonToDbSyncStatus,
)
```

Add `JsonToDbSyncRecord` to the `.models` import list.

- [ ] **Step 5: Add repository methods**

Add these methods to `SqlAlchemyP5ArtifactRepository` near recompute methods:

```python
    def save_json_to_db_sync_result(self, view: JsonToDbSyncAuditView) -> str:
        with Session(self.engine) as session:
            record = session.get(JsonToDbSyncRecord, view.sync_id)
            payload = {
                "input_hashes_json": json.dumps(view.input_hashes, sort_keys=True),
                "before_refs_json": json.dumps(view.before_refs, sort_keys=True),
                "after_refs_json": json.dumps(view.after_refs, sort_keys=True),
                "written_refs_json": json.dumps(view.written_refs, sort_keys=True),
                "skipped_refs_json": json.dumps(view.skipped_refs, sort_keys=True),
                "blocking_reasons_json": json.dumps(
                    list(view.blocking_reasons),
                    sort_keys=True,
                ),
            }
            if record is None:
                record = JsonToDbSyncRecord(
                    sync_id=view.sync_id,
                    recompute_run_id=view.recompute_run_id,
                    dataset_id=view.dataset_id,
                    status=view.status.value,
                    requested_by=view.requested_by,
                    sync_reason=view.sync_reason,
                    created_at=view.created_at,
                    completed_at=view.completed_at,
                    **payload,
                )
                session.add(record)
            else:
                record.recompute_run_id = view.recompute_run_id
                record.dataset_id = view.dataset_id
                record.status = view.status.value
                record.input_hashes_json = payload["input_hashes_json"]
                record.before_refs_json = payload["before_refs_json"]
                record.after_refs_json = payload["after_refs_json"]
                record.written_refs_json = payload["written_refs_json"]
                record.skipped_refs_json = payload["skipped_refs_json"]
                record.blocking_reasons_json = payload["blocking_reasons_json"]
                record.requested_by = view.requested_by
                record.sync_reason = view.sync_reason
                record.created_at = view.created_at
                record.completed_at = view.completed_at
            session.commit()
        return view.sync_id

    def load_json_to_db_sync_result(self, sync_id: str) -> JsonToDbSyncAuditView:
        with Session(self.engine) as session:
            record = session.get(JsonToDbSyncRecord, sync_id)
            if record is None:
                raise P5ArtifactRepositoryError(
                    f"missing JSON-to-DB sync record in DB repository: {sync_id}"
                )
            return _json_to_db_sync_view_from_record(record)

    def load_latest_json_to_db_sync_for_dataset(
        self,
        dataset_id: str,
    ) -> JsonToDbSyncAuditView | None:
        with Session(self.engine) as session:
            record = session.scalar(
                select(JsonToDbSyncRecord)
                .where(JsonToDbSyncRecord.dataset_id == dataset_id)
                .order_by(
                    JsonToDbSyncRecord.created_at.desc(),
                    JsonToDbSyncRecord.sync_id.desc(),
                )
                .limit(1)
            )
            return _json_to_db_sync_view_from_record(record) if record is not None else None

    def load_latest_json_to_db_sync_for_recompute_run(
        self,
        recompute_run_id: str,
    ) -> JsonToDbSyncAuditView | None:
        with Session(self.engine) as session:
            record = session.scalar(
                select(JsonToDbSyncRecord)
                .where(JsonToDbSyncRecord.recompute_run_id == recompute_run_id)
                .order_by(
                    JsonToDbSyncRecord.created_at.desc(),
                    JsonToDbSyncRecord.sync_id.desc(),
                )
                .limit(1)
            )
            return _json_to_db_sync_view_from_record(record) if record is not None else None
```

Add helper at module bottom:

```python
def _json_to_db_sync_view_from_record(
    record: JsonToDbSyncRecord,
) -> JsonToDbSyncAuditView:
    return JsonToDbSyncAuditView(
        sync_id=record.sync_id,
        recompute_run_id=record.recompute_run_id,
        dataset_id=record.dataset_id,
        status=JsonToDbSyncStatus(record.status),
        input_hashes=json.loads(record.input_hashes_json),
        before_refs=json.loads(record.before_refs_json),
        after_refs=json.loads(record.after_refs_json),
        written_refs=json.loads(record.written_refs_json),
        skipped_refs=json.loads(record.skipped_refs_json),
        blocking_reasons=tuple(json.loads(record.blocking_reasons_json)),
        requested_by=record.requested_by,
        sync_reason=record.sync_reason,
        created_at=record.created_at,
        completed_at=record.completed_at,
    )
```

- [ ] **Step 6: Run repository tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_json_to_db_sync_integration.py -q
```

Expected: repository sync record tests pass.

- [ ] **Step 7: Run storage focused regressions**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_storage_query_audit_integration.py tests/unit/test_document_ledger_repository.py -q
```

Expected: existing storage/query/audit tests pass.

- [ ] **Step 8: Commit Task 2**

```bash
git add financial-report-analysis/src/financial_report_analysis/storage/models.py financial-report-analysis/src/financial_report_analysis/storage/repositories.py financial-report-analysis/tests/integration/test_json_to_db_sync_integration.py
git commit -m "feat: persist json to db sync records"
```

## Task 3: Sync Service Success, Idempotency, And Fail-Closed Validation

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/json_to_db_sync.py`
- Test: `financial-report-analysis/tests/unit/test_json_to_db_sync.py`
- Test: `financial-report-analysis/tests/integration/test_json_to_db_sync_integration.py`

- [ ] **Step 1: Add failing unit tests for service validation**

Append to `tests/unit/test_json_to_db_sync.py`:

```python
from financial_report_analysis.p5.json_to_db_sync import sync_json_recompute_to_db


class _FakeRepository:
    def __init__(
        self,
        *,
        existing_sync=None,
        artifact_hashes=None,
        db_source_artifact_ids=("artifact-1",),
        current_before_refs=None,
    ) -> None:
        self.existing_sync = existing_sync
        self.artifact_hashes = artifact_hashes or {"artifact-1": "hash-1"}
        self.db_source_artifact_ids = db_source_artifact_ids
        self.current_before_refs = current_before_refs or {
            "dataset": "dataset-hash-1",
            "recompute_run": "none",
        }
        self.saved_sync = None
        self.saved_syncs = []
        self.saved_bundle_count = 0
        self.saved_recompute_count = 0

    def load_dataset_audit_view(self, dataset_id):
        return type(
            "AuditView",
            (),
            {"source_artifact_ids": self.db_source_artifact_ids},
        )()

    def load_current_json_to_db_before_refs(self, dataset_id):
        return self.current_before_refs

    def load_latest_json_to_db_sync_for_recompute_run(self, recompute_run_id):
        return self.existing_sync

    def compute_extracted_artifact_hash(self, artifact_id):
        return self.artifact_hashes[artifact_id]

    def save_p5_assembly_bundle(self, **kwargs):
        self.saved_bundle_count += 1
        return len(kwargs["lineage_records"])

    def save_recompute_result(self, **kwargs):
        self.saved_recompute_count += 1
        return kwargs["run_id"]

    def save_json_to_db_sync_result(self, view):
        self.saved_sync = view
        self.saved_syncs.append(view)
        return view.sync_id


def test_sync_skips_existing_completed_record_idempotently() -> None:
    request = _request()
    existing = JsonToDbSyncAuditView(
        sync_id=build_json_to_db_sync_id(request),
        recompute_run_id=request.recompute_run_id,
        dataset_id=request.dataset.dataset_id,
        status=JsonToDbSyncStatus.COMPLETED,
        input_hashes=dict(request.input_hashes),
        before_refs=dict(request.before_refs),
        after_refs={"dataset": "dataset-1"},
        written_refs={"dataset": "dataset-1"},
        skipped_refs={},
        blocking_reasons=(),
        requested_by="test",
        sync_reason="test-sync",
        created_at="2026-04-28T00:00:00+00:00",
        completed_at="2026-04-28T00:00:01+00:00",
    )
    repository = _FakeRepository(existing_sync=existing)

    result = sync_json_recompute_to_db(repository=repository, request=request)

    assert result.status is JsonToDbSyncStatus.SKIPPED_IDEMPOTENT
    assert repository.saved_bundle_count == 0
    assert repository.saved_recompute_count == 0


def test_sync_rejects_stale_input_hash_before_writing() -> None:
    request = _request()
    repository = _FakeRepository(artifact_hashes={"artifact-1": "new-hash"})

    result = sync_json_recompute_to_db(repository=repository, request=request)

    assert result.status is JsonToDbSyncStatus.FAILED
    assert result.blocking_reasons == ("stale_input_hash: artifact-1",)
    assert repository.saved_bundle_count == 0
    assert repository.saved_recompute_count == 0


def test_sync_rejects_db_source_artifact_mismatch_before_writing() -> None:
    request = _request()
    repository = _FakeRepository(db_source_artifact_ids=("artifact-2",))

    result = sync_json_recompute_to_db(repository=repository, request=request)

    assert result.status is JsonToDbSyncStatus.FAILED
    assert result.blocking_reasons == ("db_source_artifact_mismatch",)
    assert repository.saved_bundle_count == 0
    assert repository.saved_recompute_count == 0


def test_sync_rejects_stale_before_ref_before_writing() -> None:
    request = _request()
    repository = _FakeRepository(
        current_before_refs={"dataset": "dataset-hash-2", "recompute_run": "none"}
    )

    result = sync_json_recompute_to_db(repository=repository, request=request)

    assert result.status is JsonToDbSyncStatus.FAILED
    assert result.blocking_reasons == ("stale_before_ref: dataset",)
    assert repository.saved_bundle_count == 0
    assert repository.saved_recompute_count == 0


def test_sync_writes_pending_metadata_before_payload_writes() -> None:
    request = _request()
    repository = _FakeRepository()

    result = sync_json_recompute_to_db(repository=repository, request=request)

    assert result.status is JsonToDbSyncStatus.COMPLETED
    assert [view.status for view in repository.saved_syncs] == [
        JsonToDbSyncStatus.PENDING,
        JsonToDbSyncStatus.COMPLETED,
    ]
    assert repository.saved_bundle_count == 1
    assert repository.saved_recompute_count == 1
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_json_to_db_sync.py -q
```

Expected: fail because `sync_json_recompute_to_db` and `compute_extracted_artifact_hash` protocol behavior do not exist.

- [ ] **Step 3: Add repository protocol and service implementation**

Extend `p5/json_to_db_sync.py`:

```python
class JsonToDbSyncRepository(Protocol):
    def load_dataset_audit_view(self, dataset_id: str): ...

    def load_current_json_to_db_before_refs(self, dataset_id: str) -> dict[str, str]: ...

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


def sync_json_recompute_to_db(
    *,
    repository: JsonToDbSyncRepository,
    request: JsonToDbSyncRequest,
) -> JsonToDbSyncResult:
    validate_json_to_db_sync_request(request)
    dataset_review_surface = request.dataset_review_surface
    if dataset_review_surface is None:
        raise P5ArtifactRepositoryError("after dataset review surface is required")
    sync_id = build_json_to_db_sync_id(request)
    existing = repository.load_latest_json_to_db_sync_for_recompute_run(
        request.recompute_run_id
    )
    if _is_same_completed_sync(existing, sync_id, request):
        return _result_from_view(
            existing,
            status=JsonToDbSyncStatus.SKIPPED_IDEMPOTENT,
            skipped_refs={"sync_id": existing.sync_id},
        )

    stale_reasons = _stale_input_hash_reasons(repository, request)
    stale_reasons.extend(_db_source_artifact_reasons(repository, request))
    stale_reasons.extend(_stale_before_ref_reasons(repository, request))
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
    written_refs: dict[str, str] = {}
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
    try:
        repository.save_p5_assembly_bundle(
            dataset=request.dataset,
            dataset_review_surface=dataset_review_surface,
            lineage_records=request.lineage_records,
            turtle_export=request.turtle_export,
            turtle_export_review_surface=request.turtle_export_review_surface,
        )
        written_refs.update(after_refs)
        repository.save_recompute_result(
            run_id=request.recompute_run_id,
            plan=request.plan,
            result=request.recompute_result,
            lifecycle_recompute_audit=request.lifecycle_recompute_audit,
        )
        written_refs["recompute_run"] = request.recompute_run_id
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
            completed_at=None,
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
    repository.save_json_to_db_sync_result(view)
    return _result_from_view(view)
```

Add helper functions in the same module:

```python
def _is_same_completed_sync(
    existing: JsonToDbSyncAuditView | None,
    sync_id: str,
    request: JsonToDbSyncRequest,
) -> bool:
    return (
        existing is not None
        and existing.sync_id == sync_id
        and existing.status is JsonToDbSyncStatus.COMPLETED
        and existing.input_hashes == dict(request.input_hashes)
    )


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
    refs = {"dataset": request.dataset.dataset_id}
    if request.turtle_export is not None:
        refs["turtle_export"] = request.turtle_export.dataset_id
    if request.lineage_records:
        refs["lineage_records"] = str(len(request.lineage_records))
    return refs


def _build_sync_view(
    *,
    request: JsonToDbSyncRequest,
    sync_id: str,
    status: JsonToDbSyncStatus,
    after_refs: dict[str, str],
    written_refs: dict[str, str],
    skipped_refs: dict[str, str],
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
        after_refs=after_refs,
        written_refs=written_refs,
        skipped_refs=skipped_refs,
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
    skipped_refs: dict[str, str] | None = None,
) -> JsonToDbSyncResult:
    return JsonToDbSyncResult(
        sync_id=view.sync_id,
        recompute_run_id=view.recompute_run_id,
        dataset_id=view.dataset_id,
        status=view.status if status is None else status,
        input_hashes=view.input_hashes,
        before_refs=view.before_refs,
        after_refs=view.after_refs,
        written_refs=view.written_refs,
        skipped_refs=view.skipped_refs if skipped_refs is None else skipped_refs,
        blocking_reasons=view.blocking_reasons,
        requested_by=view.requested_by,
        sync_reason=view.sync_reason,
        created_at=view.created_at,
        completed_at=view.completed_at,
    )
```

- [ ] **Step 4: Add repository hash helper**

In `SqlAlchemyP5ArtifactRepository`, add:

```python
    def compute_extracted_artifact_hash(self, artifact_id: str) -> str:
        artifact = self.load_extracted_artifact(artifact_id)
        return compute_payload_hash(extracted_artifact_to_payload(artifact))

    def compute_dataset_artifact_hash(self, dataset_id: str) -> str:
        dataset = self.load_dataset_artifact(dataset_id)
        return compute_payload_hash(dataset_artifact_to_payload(dataset))

    def load_current_json_to_db_before_refs(self, dataset_id: str) -> dict[str, str]:
        refs = {"dataset": self.compute_dataset_artifact_hash(dataset_id)}
        latest_sync = self.load_latest_json_to_db_sync_for_dataset(dataset_id)
        refs["recompute_run"] = (
            latest_sync.recompute_run_id if latest_sync is not None else "none"
        )
        return refs
```

Import `compute_payload_hash` from `p5/json_to_db_sync.py`, and reuse existing
`dataset_artifact_to_payload(...)` from `p5/artifact_repository.py`.

- [ ] **Step 5: Add integration success test**

Extend `tests/integration/test_json_to_db_sync_integration.py` with a seeded repository test that reuses small P5 artifacts. If helpers already exist in `test_storage_query_audit_integration.py`, copy the minimal helper code into this file instead of importing private test helpers.

```python
def test_sync_service_writes_dataset_bundle_recompute_and_sync_metadata(tmp_path) -> None:
    repository, request = _seed_sync_request(tmp_path)

    result = sync_json_recompute_to_db(repository=repository, request=request)

    assert result.status is JsonToDbSyncStatus.COMPLETED
    assert repository.load_dataset_artifact(request.dataset.dataset_id) == request.dataset
    assert repository.load_recompute_result(request.recompute_run_id) == (
        request.recompute_result
    )
    latest = repository.load_latest_json_to_db_sync_for_dataset(request.dataset.dataset_id)
    assert latest is not None
    assert latest.sync_id == result.sync_id
    assert latest.status is JsonToDbSyncStatus.COMPLETED
```

- [ ] **Step 6: Run sync unit and integration tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_json_to_db_sync.py tests/integration/test_json_to_db_sync_integration.py -q
```

Expected: all sync tests pass.

- [ ] **Step 7: Commit Task 3**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/json_to_db_sync.py financial-report-analysis/src/financial_report_analysis/storage/repositories.py financial-report-analysis/tests/unit/test_json_to_db_sync.py financial-report-analysis/tests/integration/test_json_to_db_sync_integration.py
git commit -m "feat: sync json recompute outputs to db"
```

## Task 4: Expose Sync Metadata In Audit And Boundary Views

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/db_recompute_boundary.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Test: `financial-report-analysis/tests/unit/test_db_recompute_boundary.py`
- Test: `financial-report-analysis/tests/integration/test_api_storage_runtime.py`

- [ ] **Step 1: Add failing boundary unit test**

Extend `tests/unit/test_db_recompute_boundary.py`:

```python
from financial_report_analysis.p5.json_to_db_sync import (
    JsonToDbSyncAuditView,
    JsonToDbSyncStatus,
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
```

- [ ] **Step 2: Run boundary tests and verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_db_recompute_boundary.py -q
```

Expected: fail because `DatasetAuditView` and `DbRecomputeBoundaryView` do not expose sync metadata.

- [ ] **Step 3: Extend repository audit dataclasses**

Modify dataclasses in `storage/repositories.py`:

```python
@dataclass(frozen=True, slots=True)
class DatasetAuditView:
    dataset_id: str
    source_artifact_ids: tuple[str, ...]
    source_artifacts: tuple[SourceArtifactAuditRecord, ...]
    dataset_review_surface: P5DatasetReviewSurface | None
    turtle_export_review_surface: P5TurtleExportReviewSurface | None
    latest_recompute_run_id: str | None
    latest_recompute_reason: str | None
    latest_lifecycle_recompute_audit: MetricLifecycleRecomputeAudit | None
    latest_json_to_db_sync: JsonToDbSyncAuditView | None = None


@dataclass(frozen=True, slots=True)
class RecomputeRunAuditView:
    run_id: str
    result: P5RecomputeResult
    lifecycle_recompute_audit: MetricLifecycleRecomputeAudit | None
    latest_json_to_db_sync: JsonToDbSyncAuditView | None = None
```

Update `load_recompute_run_audit_view(...)` and `load_dataset_audit_view(...)` to populate `latest_json_to_db_sync`.

- [ ] **Step 4: Extend boundary view**

Modify `p5/db_recompute_boundary.py`:

```python
from financial_report_analysis.p5.json_to_db_sync import (
    JsonToDbSyncAuditView,
    JsonToDbSyncStatus,
)


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
    latest_json_to_db_sync_id: str | None = None
    latest_json_to_db_sync_status: JsonToDbSyncStatus | None = None
    json_to_db_sync_effective_status: JsonToDbSyncStatus = (
        JsonToDbSyncStatus.NOT_ATTEMPTED
    )
    json_to_db_sync_blocking_reasons: tuple[str, ...] = ()
```

Populate the sync fields from `audit_view.latest_json_to_db_sync`. The effective
status must be computed against `audit_view.latest_recompute_run_id`:

```python
def _effective_sync_status(
    *,
    latest_recompute_run_id: str | None,
    latest_sync: JsonToDbSyncAuditView | None,
) -> tuple[JsonToDbSyncStatus, tuple[str, ...]]:
    if latest_recompute_run_id is None:
        return (
            JsonToDbSyncStatus.NOT_ATTEMPTED,
            ("no recompute run has been recorded for this dataset",),
        )
    if latest_sync is None:
        return (
            JsonToDbSyncStatus.NOT_ATTEMPTED,
            ("json_to_db_sync_not_attempted",),
        )
    if latest_sync.recompute_run_id != latest_recompute_run_id:
        return (
            JsonToDbSyncStatus.OUT_OF_SYNC,
            ("sync_recompute_run_mismatch",),
        )
    if latest_sync.status is not JsonToDbSyncStatus.COMPLETED:
        return (latest_sync.status, latest_sync.blocking_reasons)
    return (JsonToDbSyncStatus.COMPLETED, ())
```

- [ ] **Step 5: Extend API schemas**

Add to `api/schemas.py`:

```python
class JsonToDbSyncStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sync_id: str
    recompute_run_id: str
    dataset_id: str
    status: str
    input_hashes: dict[str, str]
    before_refs: dict[str, str]
    after_refs: dict[str, str]
    written_refs: dict[str, str]
    skipped_refs: dict[str, str]
    blocking_reasons: tuple[str, ...]
    requested_by: str | None = None
    sync_reason: str
    created_at: str
    completed_at: str | None = None
```

Add fields:

```python
latest_json_to_db_sync: JsonToDbSyncStatusResponse | None = None
```

to `DatasetAuditResponse` and `RecomputeResultResponse`.

Add fields:

```python
latest_json_to_db_sync_id: str | None = None
latest_json_to_db_sync_status: str | None = None
json_to_db_sync_effective_status: str
json_to_db_sync_blocking_reasons: tuple[str, ...] = ()
```

to `DbRecomputeBoundaryResponse`.

- [ ] **Step 6: Extend route serializers**

In `api/routes.py`, add helper:

```python
def _json_to_db_sync_to_response(view: Any) -> JsonToDbSyncStatusResponse:
    return JsonToDbSyncStatusResponse(
        sync_id=view.sync_id,
        recompute_run_id=view.recompute_run_id,
        dataset_id=view.dataset_id,
        status=view.status.value,
        input_hashes=view.input_hashes,
        before_refs=view.before_refs,
        after_refs=view.after_refs,
        written_refs=view.written_refs,
        skipped_refs=view.skipped_refs,
        blocking_reasons=view.blocking_reasons,
        requested_by=view.requested_by,
        sync_reason=view.sync_reason,
        created_at=view.created_at,
        completed_at=view.completed_at,
    )
```

Wire it into `_dataset_audit_to_response(...)`, `_recompute_result_to_response(...)`, and `_db_recompute_boundary_to_response(...)`.

- [ ] **Step 7: Extend API integration test**

In `tests/integration/test_api_storage_runtime.py`, after seeding a sync record for `recompute-run-1`, assert:

```python
audit_response = client.get("/datasets/p5_seed_3_issuers_2_years/audit")
recompute_response = client.get("/recompute-runs/recompute-run-1")
boundary_response = client.get("/datasets/p5_seed_3_issuers_2_years/recompute-boundary")

assert audit_response.json()["latest_json_to_db_sync"]["status"] == "completed"
assert recompute_response.json()["latest_json_to_db_sync"]["sync_id"] == "sync-1"
assert boundary_response.json()["latest_json_to_db_sync_status"] == "completed"
assert boundary_response.json()["json_to_db_sync_effective_status"] == "completed"
```

Also seed a second recompute run without a matching sync record and assert:

```python
boundary_response = client.get("/datasets/p5_seed_3_issuers_2_years/recompute-boundary")

assert boundary_response.json()["latest_json_to_db_sync_status"] == "completed"
assert boundary_response.json()["json_to_db_sync_effective_status"] == "out_of_sync"
assert "sync_recompute_run_mismatch" in boundary_response.json()[
    "json_to_db_sync_blocking_reasons"
]
```

- [ ] **Step 8: Run API and boundary tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_db_recompute_boundary.py tests/integration/test_api_storage_runtime.py -q
```

Expected: tests pass and existing boundary response assertions are updated for the new nullable fields.

- [ ] **Step 9: Commit Task 4**

```bash
git add financial-report-analysis/src/financial_report_analysis/storage/repositories.py financial-report-analysis/src/financial_report_analysis/p5/db_recompute_boundary.py financial-report-analysis/src/financial_report_analysis/api/schemas.py financial-report-analysis/src/financial_report_analysis/api/routes.py financial-report-analysis/tests/unit/test_db_recompute_boundary.py financial-report-analysis/tests/integration/test_api_storage_runtime.py
git commit -m "feat: expose json to db sync metadata"
```

## Task 5: Partial Failure And No-Recompute Read Path Regressions

**Files:**
- Modify: `financial-report-analysis/tests/unit/test_json_to_db_sync.py`
- Modify: `financial-report-analysis/tests/integration/test_json_to_db_sync_integration.py`
- Modify: `financial-report-analysis/tests/integration/test_api_storage_runtime.py`

- [ ] **Step 1: Add unit test for partial failure status**

Append:

```python
class _FailingAfterBundleRepository(_FakeRepository):
    def save_recompute_result(self, **kwargs):
        raise RuntimeError("write recompute result failed")


def test_sync_records_partial_when_bundle_write_succeeds_then_recompute_write_fails() -> None:
    request = _request()
    repository = _FailingAfterBundleRepository()

    result = sync_json_recompute_to_db(repository=repository, request=request)

    assert result.status is JsonToDbSyncStatus.PARTIAL
    assert result.written_refs["dataset"] == "dataset-1"
    assert result.blocking_reasons == ("write recompute result failed",)
    assert repository.saved_sync is not None
    assert repository.saved_sync.status is JsonToDbSyncStatus.PARTIAL
```

- [ ] **Step 2: Add API no-write read path assertion**

In `test_storage_runtime_exposes_read_only_recompute_boundary`, keep the existing recompute run count assertion and add sync record count helper:

```python
from financial_report_analysis.storage.models import JsonToDbSyncRecord


def _sync_record_count(client: TestClient) -> int:
    repository = client.app.state.runtime.storage_repository
    assert repository is not None
    with Session(repository.engine) as session:
        return session.scalar(select(func.count()).select_from(JsonToDbSyncRecord)) or 0
```

Then assert:

```python
before_sync_count = _sync_record_count(client)
response = client.get("/datasets/p5_seed_3_issuers_2_years/recompute-boundary")
assert response.status_code == 200
assert _sync_record_count(client) == before_sync_count
```

- [ ] **Step 3: Run focused failure/read-only tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_json_to_db_sync.py tests/integration/test_api_storage_runtime.py::test_storage_runtime_exposes_read_only_recompute_boundary -q
```

Expected: tests pass.

- [ ] **Step 4: Commit Task 5**

```bash
git add financial-report-analysis/tests/unit/test_json_to_db_sync.py financial-report-analysis/tests/integration/test_api_storage_runtime.py
git commit -m "test: cover json to db sync failure boundaries"
```

## Task 6: Documentation, Full Verification, And Closeout

**Files:**
- Modify: `docs/superpowers/specs/active/2026-04-28-financial-report-analysis-explicit-json-to-db-sync-bridge-design.md`
- Modify: `docs/superpowers/plans/README.md`
- Modify: `docs/superpowers/plans/active/README.md`
- Move: `docs/superpowers/specs/active/2026-04-28-financial-report-analysis-explicit-json-to-db-sync-bridge-design.md` to `docs/superpowers/specs/archived/2026-04-28-financial-report-analysis-explicit-json-to-db-sync-bridge-design.md`
- Move: `docs/superpowers/plans/active/2026-04-28-financial-report-analysis-explicit-json-to-db-sync-bridge.md` to `docs/superpowers/plans/archived/2026-04-28-financial-report-analysis-explicit-json-to-db-sync-bridge.md`
- Modify: `docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/04-storage-api-recompute.md`
- Modify: `docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/05-risks-and-roadmap.md`

- [ ] **Step 1: Update design status after implementation**

When implementation passes verification, update the active spec header:

```markdown
> **状态:** Implemented baseline, pending archive
```

Add a short "实现状态" section:

```markdown
## 12. 实现状态

当前分支已实现 explicit JSON-to-DB sync bridge baseline：

- JSON-first recompute 仍是唯一 canonical executor。
- sync service 校验 source artifact hashes、dataset identity、after payloads 和 recompute run identity。
- sync metadata 持久化到 DB，并通过 dataset audit、recompute run read 和 recompute boundary views 读回。
- stale input hash fail closed。
- partial failure 可观测，read surfaces 不把 partial sync 误报为 completed。
```

- [ ] **Step 2: Archive completed spec and plan**

Move the implemented spec:

```bash
git mv docs/superpowers/specs/active/2026-04-28-financial-report-analysis-explicit-json-to-db-sync-bridge-design.md docs/superpowers/specs/archived/2026-04-28-financial-report-analysis-explicit-json-to-db-sync-bridge-design.md
```

Move this completed plan:

```bash
git mv docs/superpowers/plans/active/2026-04-28-financial-report-analysis-explicit-json-to-db-sync-bridge.md docs/superpowers/plans/archived/2026-04-28-financial-report-analysis-explicit-json-to-db-sync-bridge.md
```

- [ ] **Step 3: Update plan and spec indexes**

Modify `docs/superpowers/plans/README.md`:

```markdown
Current active implementation plans:

- None.
```

Modify `docs/superpowers/plans/active/README.md`:

```markdown
# Active Plans

There are no active implementation plans after the 2026-04-28 explicit
JSON-to-DB sync bridge closeout.
```

Modify `docs/superpowers/specs/README.md` to remove the archived sync bridge from current active entries and keep it under `archived/`.

Modify `docs/superpowers/specs/active/README.md` to remove the sync bridge from current active specs.

- [ ] **Step 4: Update architecture docs**

In `04-storage-api-recompute.md`, add under current DB-backed recompute boundary section:

```markdown
当前 explicit JSON-to-DB sync bridge 增加了：

- `p5/json_to_db_sync.py` 的 sync contract 和 service；
- JSON-first recompute after payloads 到 DB read surface 的显式同步；
- persisted sync metadata；
- dataset audit、recompute run read 和 recompute boundary views 的 sync status；
- stale input hash fail-closed 和 partial failure observability。
```

In `05-risks-and-roadmap.md`, update remaining risk from "需要设计 explicit JSON-to-DB sync bridge" to "sync bridge baseline 已完成，后续才评估 HTTP-triggered recompute/job boundary" after implementation is verified.

- [ ] **Step 5: Run focused test suite**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_json_to_db_sync.py tests/unit/test_db_recompute_boundary.py tests/integration/test_json_to_db_sync_integration.py tests/integration/test_api_storage_runtime.py tests/integration/test_storage_query_audit_integration.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Run broader recompute/storage/governance regressions**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_recompute.py tests/integration/test_storage_p5_parity.py tests/integration/test_metric_governance_api.py -q
```

Expected: all selected regression tests pass.

- [ ] **Step 7: Run Ruff**

Run:

```bash
cd financial-report-analysis
uv run ruff check src/financial_report_analysis/p5/json_to_db_sync.py src/financial_report_analysis/p5/db_recompute_boundary.py src/financial_report_analysis/storage/models.py src/financial_report_analysis/storage/repositories.py src/financial_report_analysis/api/schemas.py src/financial_report_analysis/api/routes.py tests/unit/test_json_to_db_sync.py tests/unit/test_db_recompute_boundary.py tests/integration/test_json_to_db_sync_integration.py tests/integration/test_api_storage_runtime.py
```

Expected: `All checks passed!`

- [ ] **Step 8: Run diff whitespace check**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 9: Commit docs closeout**

```bash
git add docs/superpowers/specs/README.md docs/superpowers/specs/active/README.md docs/superpowers/specs/archived/2026-04-28-financial-report-analysis-explicit-json-to-db-sync-bridge-design.md docs/superpowers/plans/README.md docs/superpowers/plans/active/README.md docs/superpowers/plans/archived/2026-04-28-financial-report-analysis-explicit-json-to-db-sync-bridge.md docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/04-storage-api-recompute.md docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/05-risks-and-roadmap.md
git commit -m "docs: close json to db sync bridge plan"
```

- [ ] **Step 10: Final status check**

Run:

```bash
git status --short --branch
```

Expected: clean worktree except branch ahead count.

## Plan Self-Review

- Spec coverage: Tasks cover sync contract, repository write boundary, service validation, idempotency, pending-first metadata, stale hash rejection, stale before refs, source artifact mismatch, malformed lifecycle audit, partial failure observability, out-of-sync read status, read surface exposure, API schema serialization, tests, docs, and verification.
- Scope check: Plan does not implement DB-native recompute, HTTP-triggered recompute, async jobs, product workflow lifecycle, field coverage, LLM assessment, or UI.
- Type consistency: Contract names stay consistent across tasks: `JsonToDbSyncRequest`, `JsonToDbSyncResult`, `JsonToDbSyncAuditView`, `JsonToDbSyncStatus`, and `sync_json_recompute_to_db`.
- Execution boundary: Public HTTP write routes are not added. Existing audit, recompute run, and boundary routes remain read-only.
