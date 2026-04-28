# DB-backed Recompute Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only DB-backed recompute boundary surface that makes the current JSON-first executor boundary explicit and prevents DB assembly from being mistaken for DB-native recompute.

**Architecture:** Add a focused `p5/db_recompute_boundary.py` service with a small enum and view dataclass. The service reads existing dataset audit/recompute metadata from `SqlAlchemyP5ArtifactRepository`, classifies the required execution mode, and is exposed through a read-only API endpoint. No recompute execution, DB sync bridge, async job, lifecycle state mutation, or DB-native executor is introduced.

**Tech Stack:** Python 3.12, dataclasses, `enum.StrEnum`, FastAPI, Pydantic v2, SQLAlchemy-backed test repository, pytest, Ruff, mypy.

---

## File Structure

- Create `financial-report-analysis/src/financial_report_analysis/p5/db_recompute_boundary.py`
  - Owns `RecomputeExecutionMode`, `DbRecomputeBoundaryView`, reason classification, and `build_db_recompute_boundary_view(...)`.
- Create `financial-report-analysis/tests/unit/test_db_recompute_boundary.py`
  - Fast unit tests with a fake repository for reason classification and fail-fast behavior.
- Modify `financial-report-analysis/tests/integration/test_storage_query_audit_integration.py`
  - Adds DB-backed service tests against the real SQLite repository and existing seeded dataset helpers.
- Modify `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
  - Adds `DbRecomputeBoundaryResponse`.
- Modify `financial-report-analysis/src/financial_report_analysis/api/routes.py`
  - Adds `GET /datasets/{dataset_id}/recompute-boundary` and conversion helper.
- Modify `financial-report-analysis/tests/integration/test_api_storage_runtime.py`
  - Adds endpoint tests, including a read-only recompute run count assertion and missing dataset 404 coverage.
- Modify docs after code lands:
  - `docs/superpowers/specs/active/2026-04-28-financial-report-analysis-db-backed-recompute-boundary-design.md`
  - `docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/04-storage-api-recompute.md`
  - `docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/05-risks-and-roadmap.md`
  - `docs/superpowers/specs/active/2026-04-22-financial-report-analysis-unified-roadmap.md`

---

### Task 1: Boundary Service Unit Slice

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/p5/db_recompute_boundary.py`
- Create: `financial-report-analysis/tests/unit/test_db_recompute_boundary.py`

- [ ] **Step 1: Write failing unit tests**

Create `financial-report-analysis/tests/unit/test_db_recompute_boundary.py`:

```python
from __future__ import annotations

from typing import cast

import pytest

from financial_report_analysis.models import MetricLifecycleRecomputeAudit
from financial_report_analysis.p5.db_recompute_boundary import (
    RecomputeExecutionMode,
    build_db_recompute_boundary_view,
)
from financial_report_analysis.storage.repositories import DatasetAuditView


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
    latest_recompute_reason: str | None = None,
    lifecycle_audit_present: bool = False,
) -> DatasetAuditView:
    return DatasetAuditView(
        dataset_id="dataset-1",
        source_artifact_ids=source_artifact_ids,
        source_artifacts=(),
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


def test_empty_source_artifacts_fail_fast() -> None:
    with pytest.raises(ValueError, match="dataset has no source artifacts"):
        build_db_recompute_boundary_view(
            repository=_FakeRepository(_audit_view(source_artifact_ids=())),
            dataset_id="dataset-1",
        )
```

- [ ] **Step 2: Run unit test to verify it fails**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_db_recompute_boundary.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'financial_report_analysis.p5.db_recompute_boundary'`.

- [ ] **Step 3: Implement the minimal boundary service**

Create `financial-report-analysis/src/financial_report_analysis/p5/db_recompute_boundary.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

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
        raise ValueError(f"dataset has no source artifacts: {dataset_id}")

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
```

- [ ] **Step 4: Run unit tests and static checks for the new service**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_db_recompute_boundary.py -q
uv run ruff check src/financial_report_analysis/p5/db_recompute_boundary.py tests/unit/test_db_recompute_boundary.py
```

Expected: both commands pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/db_recompute_boundary.py financial-report-analysis/tests/unit/test_db_recompute_boundary.py
git commit -m "feat: add db recompute boundary service"
```

---

### Task 2: DB Repository Integration Coverage

**Files:**
- Modify: `financial-report-analysis/tests/integration/test_storage_query_audit_integration.py`

- [ ] **Step 1: Write failing integration tests against the real repository**

Add this import near the existing P5 imports in `financial-report-analysis/tests/integration/test_storage_query_audit_integration.py`:

```python
from financial_report_analysis.p5.db_recompute_boundary import (
    RecomputeExecutionMode,
    build_db_recompute_boundary_view,
)
```

Add this test after `test_dataset_audit_view_exposes_latest_lifecycle_recompute_audit`:

```python
def test_db_recompute_boundary_view_reads_persisted_dataset_and_lifecycle_audit(
    tmp_path: Path,
) -> None:
    repository, dataset = _seed_repository_dataset(tmp_path)
    audit = _lifecycle_audit()
    plan = P5RecomputePlan(
        manifest_id="p5_seed_manifest",
        dataset_id=dataset.dataset_id,
        target_artifact_ids=dataset.source_artifacts,
        rebuild_dataset=True,
        rebuild_turtle_export=True,
        reason="metric_lifecycle_decision_changed",
    )
    result = P5RecomputeResult(
        manifest_id="p5_seed_manifest",
        extracted_artifact_ids=dataset.source_artifacts,
        dataset_path=tmp_path / "dataset.json",
        turtle_export_path=tmp_path / "turtle.json",
        diff_summary=P5RecomputeDiffSummary(
            reason="metric_lifecycle_decision_changed",
            target_artifact_ids=dataset.source_artifacts,
            dataset_changed=True,
            turtle_export_changed=True,
            rebuilt_dataset=True,
            rebuilt_turtle_export=True,
        ),
    )
    repository.save_recompute_result(
        run_id="lifecycle-recompute-run-1",
        plan=plan,
        result=result,
        lifecycle_recompute_audit=audit,
    )

    view = build_db_recompute_boundary_view(
        repository=repository,
        dataset_id=dataset.dataset_id,
        requested_reason="metric_lifecycle_decision_changed",
    )

    assert view.dataset_id == dataset.dataset_id
    assert view.latest_recompute_run_id == "lifecycle-recompute-run-1"
    assert view.latest_recompute_reason == "metric_lifecycle_decision_changed"
    assert view.latest_lifecycle_audit_present is True
    assert view.source_artifact_ids == dataset.source_artifacts
    assert view.required_mode is RecomputeExecutionMode.JSON_FIRST_REQUIRED
    assert view.supported_modes == (RecomputeExecutionMode.JSON_FIRST_REQUIRED,)
    assert view.blocking_reasons == (
        "reason metric_lifecycle_decision_changed requires the JSON-first "
        "recompute executor",
        "DB assembly is currently limited to persisted single-artifact assembly "
        "and is not a recompute executor",
    )
```

- [ ] **Step 2: Run the targeted integration test**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_storage_query_audit_integration.py::test_db_recompute_boundary_view_reads_persisted_dataset_and_lifecycle_audit -q
```

Expected after Task 1: PASS. If it fails, the failure should identify a real mismatch between repository audit data and the service contract.

- [ ] **Step 3: Run the related storage audit integration group**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_storage_query_audit_integration.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 4: Commit Task 2**

```bash
git add financial-report-analysis/tests/integration/test_storage_query_audit_integration.py
git commit -m "test: cover db recompute boundary persistence view"
```

---

### Task 3: API Read Surface

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Modify: `financial-report-analysis/tests/integration/test_api_storage_runtime.py`

- [ ] **Step 1: Write failing API integration tests**

Add imports to `financial-report-analysis/tests/integration/test_api_storage_runtime.py`:

```python
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from financial_report_analysis.storage.models import RecomputeRunRecord
```

Add this helper near the other test helpers:

```python
def _recompute_run_count(client: TestClient) -> int:
    repository = client.app.state.runtime.storage_repository
    assert repository is not None
    with Session(repository.engine) as session:
        return (
            session.scalar(select(func.count()).select_from(RecomputeRunRecord))
            or 0
        )
```

Add this test after `test_storage_runtime_exposes_lifecycle_recompute_audit_snapshot`:

```python
def test_storage_runtime_exposes_read_only_recompute_boundary(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(storage_db_path=tmp_path / "runtime.db"))
    _seed_runtime(client, tmp_path)
    before_run_count = _recompute_run_count(client)

    response = client.get(
        "/datasets/p5_seed_3_issuers_2_years/recompute-boundary",
        params={"requested_reason": "metric_lifecycle_decision_changed"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "dataset_id": "p5_seed_3_issuers_2_years",
        "latest_recompute_run_id": None,
        "latest_recompute_reason": None,
        "latest_lifecycle_audit_present": False,
        "source_artifact_ids": [
            "CN_601919_2025",
            "CN_600519_2025",
            "CN_000333_2025",
        ],
        "supported_modes": ["json_first_required"],
        "required_mode": "json_first_required",
        "blocking_reasons": [
            "reason metric_lifecycle_decision_changed requires the JSON-first "
            "recompute executor",
            "DB assembly is currently limited to persisted single-artifact assembly "
            "and is not a recompute executor",
        ],
    }
    assert _recompute_run_count(client) == before_run_count
```

Extend `test_storage_backed_routes_return_404_for_missing_objects` with:

```python
    boundary_response = client.get("/datasets/missing-dataset/recompute-boundary")
    assert boundary_response.status_code == 404
    assert (
        "missing dataset artifact in DB repository"
        in boundary_response.json()["detail"]
    )
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_api_storage_runtime.py::test_storage_runtime_exposes_read_only_recompute_boundary tests/integration/test_api_storage_runtime.py::test_storage_backed_routes_return_404_for_missing_objects -q
```

Expected: FAIL with 404 for `/datasets/p5_seed_3_issuers_2_years/recompute-boundary` because the route does not exist yet.

- [ ] **Step 3: Add API response schema**

In `financial-report-analysis/src/financial_report_analysis/api/schemas.py`, add this class after `DatasetAuditResponse`:

```python
class DbRecomputeBoundaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    latest_recompute_run_id: str | None
    latest_recompute_reason: str | None
    latest_lifecycle_audit_present: bool
    source_artifact_ids: tuple[str, ...]
    supported_modes: tuple[str, ...]
    required_mode: str
    blocking_reasons: tuple[str, ...]
```

- [ ] **Step 4: Add route imports**

In `financial-report-analysis/src/financial_report_analysis/api/routes.py`, add the service import near other `p5` imports:

```python
from financial_report_analysis.p5.db_recompute_boundary import (
    DbRecomputeBoundaryView,
    build_db_recompute_boundary_view,
)
```

Add `DbRecomputeBoundaryResponse` to the schema import list:

```python
    DbRecomputeBoundaryResponse,
```

- [ ] **Step 5: Add the read-only endpoint**

In `financial-report-analysis/src/financial_report_analysis/api/routes.py`, add this route immediately after `get_dataset_audit(...)`:

```python
@router.get(
    "/datasets/{dataset_id}/recompute-boundary",
    response_model=DbRecomputeBoundaryResponse,
)
def get_dataset_recompute_boundary(
    dataset_id: str,
    request: Request,
    requested_reason: str | None = None,
) -> DbRecomputeBoundaryResponse:
    repository = _require_storage_repository(request)
    boundary_view = _load_or_404(
        build_db_recompute_boundary_view,
        repository=repository,
        dataset_id=dataset_id,
        requested_reason=requested_reason,
    )
    return _db_recompute_boundary_to_response(boundary_view)
```

- [ ] **Step 6: Add route response converter**

In `financial-report-analysis/src/financial_report_analysis/api/routes.py`, add this helper near `_dataset_audit_to_response(...)`:

```python
def _db_recompute_boundary_to_response(
    view: DbRecomputeBoundaryView,
) -> DbRecomputeBoundaryResponse:
    return DbRecomputeBoundaryResponse(
        dataset_id=view.dataset_id,
        latest_recompute_run_id=view.latest_recompute_run_id,
        latest_recompute_reason=view.latest_recompute_reason,
        latest_lifecycle_audit_present=view.latest_lifecycle_audit_present,
        source_artifact_ids=view.source_artifact_ids,
        supported_modes=tuple(mode.value for mode in view.supported_modes),
        required_mode=view.required_mode.value,
        blocking_reasons=view.blocking_reasons,
    )
```

- [ ] **Step 7: Run targeted API tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_api_storage_runtime.py::test_storage_runtime_exposes_read_only_recompute_boundary tests/integration/test_api_storage_runtime.py::test_storage_backed_routes_return_404_for_missing_objects -q
```

Expected: both tests pass.

- [ ] **Step 8: Run related API runtime tests and lint**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_api_storage_runtime.py -q
uv run ruff check src/financial_report_analysis/api/schemas.py src/financial_report_analysis/api/routes.py tests/integration/test_api_storage_runtime.py
```

Expected: both commands pass.

- [ ] **Step 9: Commit Task 3**

```bash
git add financial-report-analysis/src/financial_report_analysis/api/schemas.py financial-report-analysis/src/financial_report_analysis/api/routes.py financial-report-analysis/tests/integration/test_api_storage_runtime.py
git commit -m "feat: expose db recompute boundary view"
```

---

### Task 4: Documentation Closeout And Full Verification

**Files:**
- Modify: `docs/superpowers/specs/active/2026-04-28-financial-report-analysis-db-backed-recompute-boundary-design.md`
- Modify: `docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/04-storage-api-recompute.md`
- Modify: `docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/05-risks-and-roadmap.md`
- Modify: `docs/superpowers/specs/active/2026-04-22-financial-report-analysis-unified-roadmap.md`

- [ ] **Step 1: Update the DB-backed recompute boundary spec status**

In `docs/superpowers/specs/active/2026-04-28-financial-report-analysis-db-backed-recompute-boundary-design.md`, change:

```markdown
> **状态:** Active design spec
```

to:

```markdown
> **状态:** Implemented boundary/readiness contract
```

Add this paragraph to the end of section `7. 完成标准`:

```markdown

实现收口后，`GET /datasets/{dataset_id}/recompute-boundary` 是只读 readiness surface。
它返回 `json_first_required`、`db_assembly_available` 或 `db_native_unsupported`
相关状态说明，但不触发 recompute，不写入 recompute run，也不执行 DB-native recompute。
```

- [ ] **Step 2: Update storage/recompute architecture analysis**

In `docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/04-storage-api-recompute.md`, update the recompute/current-state section so it contains this bullet list:

```markdown
当前 DB-backed recompute boundary/readiness contract 增加了：

- `p5/db_recompute_boundary.py` 的 `DbRecomputeBoundaryView`；
- `RecomputeExecutionMode`，明确 `json_first_required`、`db_assembly_available` 和
  `db_native_unsupported`；
- `GET /datasets/{dataset_id}/recompute-boundary` 只读 endpoint；
- endpoint 不触发 recompute，不创建 recompute run，不执行 DB-native recompute；
- DB assembly path 继续只表示 persisted artifact assembly，不表示 recompute executor。
```

- [ ] **Step 3: Update roadmap status**

In `docs/superpowers/specs/active/2026-04-22-financial-report-analysis-unified-roadmap.md`, replace the current `DB-backed Recompute Boundary` status bullet with:

```markdown
- `DB-backed Recompute Boundary` 已完成 boundary/readiness contract。JSON-first
  recompute executor 继续作为唯一 canonical executor；DB 负责
  persistence/readback/audit/boundary readiness，并通过只读 endpoint 明确
  DB-native recompute 在本阶段 unsupported。
```

In the later next-direction paragraph, keep the existing three-stage direction but make clear that the first stage is complete:

```markdown
`DB-backed recompute boundary` 的后续方向固定为三段，其中第一段已经完成：
```

- [ ] **Step 4: Update architecture risk/roadmap follow-up**

In `docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/05-risks-and-roadmap.md`, update the first suggested follow-up to:

```markdown
1. **Explicit JSON-to-DB sync bridge。**
   DB-backed recompute boundary/readiness contract 已明确：当前仍是 JSON-first
   canonical executor，DB-native recompute unsupported。下一步如果产品需要让
   JSON-first recompute 结果稳定进入 DB read surface，应设计 explicit JSON-to-DB
   sync bridge，包括 input hashes、before/after artifact references、overwrite
   semantics 和 partial failure recovery。
```

- [ ] **Step 5: Run focused verification**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_db_recompute_boundary.py tests/integration/test_storage_query_audit_integration.py tests/integration/test_api_storage_runtime.py -q
uv run ruff check src/financial_report_analysis/p5/db_recompute_boundary.py src/financial_report_analysis/api/schemas.py src/financial_report_analysis/api/routes.py tests/unit/test_db_recompute_boundary.py tests/integration/test_storage_query_audit_integration.py tests/integration/test_api_storage_runtime.py
```

Expected: both commands pass.

- [ ] **Step 6: Run regression verification**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_recompute.py tests/integration/test_storage_p5_parity.py tests/integration/test_metric_governance_api.py -q
uv run mypy src/financial_report_analysis
```

Expected: both commands pass. If mypy reports pre-existing unrelated errors, capture the exact output and do not claim mypy passed.

- [ ] **Step 7: Check documentation diff**

Run:

```bash
git diff --check
rg -n "DB recompute 已实现|db_assembly_service 是 recompute executor|DB-backed recompute endpoint 会执行 recompute|UNRESOLVED|PLACEHOLDER" docs/superpowers/specs/active/2026-04-28-financial-report-analysis-db-backed-recompute-boundary-design.md docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/04-storage-api-recompute.md docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/05-risks-and-roadmap.md docs/superpowers/specs/active/2026-04-22-financial-report-analysis-unified-roadmap.md
```

Expected: `git diff --check` passes. The `rg` command should return no matches except quoted forbidden phrases that remain in a “must avoid these phrases” section; if matches appear outside that context, rewrite them.

- [ ] **Step 8: Commit Task 4**

```bash
git add docs/superpowers/specs/active/2026-04-28-financial-report-analysis-db-backed-recompute-boundary-design.md docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/04-storage-api-recompute.md docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/05-risks-and-roadmap.md docs/superpowers/specs/active/2026-04-22-financial-report-analysis-unified-roadmap.md
git commit -m "docs: mark db recompute boundary contract complete"
```

---

## Execution Notes

- Keep the implementation read-only. No task should call `execute_recompute_plan(...)`, `save_recompute_result(...)` from the API endpoint, or `build_db_p5_outputs_for_artifact(...)` from the boundary service.
- Keep DB-native recompute explicitly unsupported. The correct behavior is to return/read a boundary view, not to silently fallback to a hidden executor.
- Preserve current route style: existing storage-backed routes use top-level paths such as `/datasets/{dataset_id}/audit`, so this plan uses `/datasets/{dataset_id}/recompute-boundary`.
- Preserve current repository error style. Missing datasets should surface through `_load_or_404(...)` as HTTP 404 in API tests.
- Do not introduce migrations or new tables for this slice.

## Final Verification Checklist

- [ ] `uv run pytest tests/unit/test_db_recompute_boundary.py tests/integration/test_storage_query_audit_integration.py tests/integration/test_api_storage_runtime.py -q`
- [ ] `uv run pytest tests/unit/test_p5_recompute.py tests/integration/test_storage_p5_parity.py tests/integration/test_metric_governance_api.py -q`
- [ ] `uv run ruff check src/financial_report_analysis/p5/db_recompute_boundary.py src/financial_report_analysis/api/schemas.py src/financial_report_analysis/api/routes.py tests/unit/test_db_recompute_boundary.py tests/integration/test_storage_query_audit_integration.py tests/integration/test_api_storage_runtime.py`
- [ ] `uv run mypy src/financial_report_analysis`
- [ ] `git diff --check`
