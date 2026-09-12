# Financial Report Analysis Lifecycle Recompute Audit Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist metric lifecycle recompute audit snapshots with recompute runs and expose them through recompute-run and dataset-audit read surfaces.

**Architecture:** Reuse the existing `recompute_runs.result_json` payload instead of adding a new table. Add explicit payload serializers for `MetricLifecycleRecomputeAudit`, add a repository audit view that loads `P5RecomputeResult` plus the optional snapshot, and surface that snapshot through existing API responses.

**Tech Stack:** Python 3.12, dataclasses, SQLAlchemy, Pydantic, pytest, Ruff, existing `financial_report_analysis` storage/API/P5 packages.

---

## File Structure

- Modify: `financial-report-analysis/src/financial_report_analysis/p5/recompute.py`
  - Add `metric_lifecycle_recompute_audit_to_payload(...)` and
    `metric_lifecycle_recompute_audit_from_payload(...)`.
  - Keep existing `recompute_result_to_payload(...)` backward-compatible.
- Modify: `financial-report-analysis/tests/unit/test_p5_recompute.py`
  - Add serializer round-trip tests for lifecycle recompute audit payloads.
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
  - Add `RecomputeRunAuditView`.
  - Add optional `lifecycle_recompute_audit` parameter to `save_recompute_result(...)`.
  - Add `load_recompute_run_audit_view(...)`.
  - Add `latest_lifecycle_recompute_audit` to `DatasetAuditView`.
- Modify: `financial-report-analysis/tests/integration/test_storage_query_audit_integration.py`
  - Verify persisted recompute run audit snapshots round-trip through repository.
  - Verify dataset audit view exposes the latest lifecycle snapshot.
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
  - Add optional lifecycle audit fields to `RecomputeResultResponse` and
    `DatasetAuditResponse`.
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
  - Use `load_recompute_run_audit_view(...)` for `/recompute-runs/{run_id}`.
  - Serialize `latest_lifecycle_recompute_audit` in dataset audit responses.
- Modify: `financial-report-analysis/tests/integration/test_api_storage_runtime.py`
  - Verify API responses expose persisted lifecycle recompute audit snapshots.
- Modify: `financial-report-analysis/tests/unit/test_public_exports.py`
  - Only if new public names are exported. Default plan does not require new
    package-level public exports.

## Task 1: Add Lifecycle Audit Payload Serializers

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/recompute.py`
- Test: `financial-report-analysis/tests/unit/test_p5_recompute.py`

- [ ] **Step 1: Write failing serializer round-trip test**

Append to `financial-report-analysis/tests/unit/test_p5_recompute.py`:

```python
def test_metric_lifecycle_recompute_audit_payload_round_trips() -> None:
    audit = _lifecycle_audit()

    payload = metric_lifecycle_recompute_audit_to_payload(audit)
    restored = metric_lifecycle_recompute_audit_from_payload(payload)

    assert restored == audit
    assert payload["summary"] == {
        "review_item_count": 1,
        "artifact_count": 1,
        "recompute_needed_count": 1,
        "dry_run_conflict_count": 0,
    }
    assert payload["items"][0]["latest_decision_action"] == "map_to_standard"
    assert payload["items"][0]["current_status"] == "mapped_to_standard"
```

Update the import block in the same file:

```python
from financial_report_analysis.p5.recompute import (
    build_recompute_plan,
    execute_recompute_plan,
    metric_lifecycle_recompute_audit_from_payload,
    metric_lifecycle_recompute_audit_to_payload,
)
```

- [ ] **Step 2: Run serializer test and verify failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_recompute.py::test_metric_lifecycle_recompute_audit_payload_round_trips -q
```

Expected: FAIL with `ImportError` because the serializer functions do not exist.

- [ ] **Step 3: Implement payload serializers**

In `financial-report-analysis/src/financial_report_analysis/p5/recompute.py`, extend imports:

```python
from financial_report_analysis.models import (
    MetricLifecycleRecomputeAudit,
    MetricLifecycleRecomputeAuditItem,
    MetricLifecycleRecomputeAuditSummary,
)
```

Add below `_strip_volatile_fields(...)`:

```python
def metric_lifecycle_recompute_audit_to_payload(
    audit: MetricLifecycleRecomputeAudit,
) -> dict[str, object]:
    return {
        "items": [
            {
                "review_item_id": item.review_item_id,
                "artifact_id": item.artifact_id,
                "issuer_id": item.issuer_id,
                "fiscal_year": item.fiscal_year,
                "report_type": item.report_type,
                "candidate_metric_id": item.candidate_metric_id,
                "raw_label": item.raw_label,
                "lifecycle_entry_id": item.lifecycle_entry_id,
                "current_status": item.current_status,
                "latest_decision_id": item.latest_decision_id,
                "latest_decision_action": item.latest_decision_action,
                "target_metric_id": item.target_metric_id,
                "recompute_needed": item.recompute_needed,
                "consumption_action": item.consumption_action,
                "conflict_state": item.conflict_state,
                "reason": item.reason,
            }
            for item in audit.items
        ],
        "summary": {
            "review_item_count": audit.summary.review_item_count,
            "artifact_count": audit.summary.artifact_count,
            "recompute_needed_count": audit.summary.recompute_needed_count,
            "dry_run_conflict_count": audit.summary.dry_run_conflict_count,
        },
    }


def metric_lifecycle_recompute_audit_from_payload(
    payload: dict[str, object],
) -> MetricLifecycleRecomputeAudit:
    summary_payload = payload["summary"]
    if not isinstance(summary_payload, dict):
        raise ValueError("lifecycle recompute audit summary must be an object")
    item_payloads = payload.get("items", ())
    if not isinstance(item_payloads, list):
        raise ValueError("lifecycle recompute audit items must be a list")

    return MetricLifecycleRecomputeAudit(
        items=tuple(
            _metric_lifecycle_recompute_audit_item_from_payload(item)
            for item in item_payloads
            if isinstance(item, dict)
        ),
        summary=MetricLifecycleRecomputeAuditSummary(
            review_item_count=int(summary_payload["review_item_count"]),
            artifact_count=int(summary_payload["artifact_count"]),
            recompute_needed_count=int(summary_payload["recompute_needed_count"]),
            dry_run_conflict_count=int(summary_payload["dry_run_conflict_count"]),
        ),
    )


def _metric_lifecycle_recompute_audit_item_from_payload(
    payload: dict[str, object],
) -> MetricLifecycleRecomputeAuditItem:
    return MetricLifecycleRecomputeAuditItem(
        review_item_id=str(payload["review_item_id"]),
        artifact_id=str(payload["artifact_id"]),
        issuer_id=str(payload["issuer_id"]),
        fiscal_year=int(payload["fiscal_year"]),
        report_type=str(payload["report_type"]),
        candidate_metric_id=str(payload["candidate_metric_id"]),
        raw_label=str(payload["raw_label"]),
        lifecycle_entry_id=(
            str(payload["lifecycle_entry_id"])
            if payload.get("lifecycle_entry_id") is not None
            else None
        ),
        current_status=payload.get("current_status"),  # type: ignore[arg-type]
        latest_decision_id=(
            str(payload["latest_decision_id"])
            if payload.get("latest_decision_id") is not None
            else None
        ),
        latest_decision_action=payload.get("latest_decision_action"),  # type: ignore[arg-type]
        target_metric_id=(
            str(payload["target_metric_id"])
            if payload.get("target_metric_id") is not None
            else None
        ),
        recompute_needed=bool(payload["recompute_needed"]),
        consumption_action=str(payload["consumption_action"]),  # type: ignore[arg-type]
        conflict_state=str(payload["conflict_state"]),  # type: ignore[arg-type]
        reason=str(payload["reason"]),
    )
```

- [ ] **Step 4: Run serializer test and verify pass**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_recompute.py::test_metric_lifecycle_recompute_audit_payload_round_trips -q
```

Expected: PASS.

- [ ] **Step 5: Commit serializers**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/recompute.py financial-report-analysis/tests/unit/test_p5_recompute.py
git commit -m "feat: serialize lifecycle recompute audit"
```

## Task 2: Persist Lifecycle Audit With Recompute Runs

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Test: `financial-report-analysis/tests/integration/test_storage_query_audit_integration.py`

- [ ] **Step 1: Write failing repository persistence test**

Append to `financial-report-analysis/tests/integration/test_storage_query_audit_integration.py`:

```python
def test_recompute_run_persists_lifecycle_recompute_audit_snapshot(
    tmp_path: Path,
) -> None:
    repository, dataset = _seed_repository_dataset(tmp_path)
    plan = P5RecomputePlan(
        manifest_id="manifest-1",
        dataset_id=dataset.dataset_id,
        target_artifact_ids=dataset.source_artifacts,
        rebuild_dataset=True,
        rebuild_turtle_export=True,
        reason="metric_lifecycle_decision_changed",
    )
    result = P5RecomputeResult(
        manifest_id="manifest-1",
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
    audit = _lifecycle_audit()

    repository.save_recompute_result(
        run_id="lifecycle-recompute-run-1",
        plan=plan,
        result=result,
        lifecycle_recompute_audit=audit,
    )

    view = repository.load_recompute_run_audit_view("lifecycle-recompute-run-1")

    assert view.run_id == "lifecycle-recompute-run-1"
    assert view.result == result
    assert view.lifecycle_recompute_audit == audit
```

Add imports if missing:

```python
from financial_report_analysis.models import (
    MetricLifecycleRecomputeAudit,
    MetricLifecycleRecomputeAuditItem,
    MetricLifecycleRecomputeAuditSummary,
)
from financial_report_analysis.p5.models import P5RecomputeDiffSummary
```

Add helper near the bottom of the test file:

```python
def _seed_repository_dataset(
    tmp_path: Path,
) -> tuple[SqlAlchemyP5ArtifactRepository, P5DatasetArtifact]:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)
    service = HistoricalIngestionService(engine)
    entries = (
        _entry(tmp_path, issuer_id="CN_601919", stock_code="601919", fiscal_year=2025),
        _entry(tmp_path, issuer_id="CN_600519", stock_code="600519", fiscal_year=2025),
        _entry(tmp_path, issuer_id="CN_000333", stock_code="000333", fiscal_year=2025),
    )
    manifest = P5Manifest(
        manifest_id="p5_seed_manifest",
        manifest_version="1.0",
        entries=entries,
    )
    service.register_manifest(manifest)
    artifacts = tuple(_artifact(entry) for entry in entries)
    for artifact in artifacts:
        repository.save_extracted_artifact(artifact)
    dataset = _dataset(artifacts)
    repository.save_dataset_artifact(dataset)
    repository.save_turtle_export(_turtle_export(dataset))
    return repository, dataset


def _lifecycle_audit() -> MetricLifecycleRecomputeAudit:
    return MetricLifecycleRecomputeAudit(
        items=(
            MetricLifecycleRecomputeAuditItem(
                review_item_id="CN_601919_2025:custom_receivables",
                artifact_id="CN_601919_2025",
                issuer_id="CN_601919",
                fiscal_year=2025,
                report_type="annual",
                candidate_metric_id="custom::receivables",
                raw_label="应收款项融资",
                lifecycle_entry_id="metric-lifecycle:1",
                current_status="mapped_to_standard",
                latest_decision_id="metric-lifecycle-decision:1",
                latest_decision_action="map_to_standard",
                target_metric_id="accounts_receiv",
                recompute_needed=True,
                consumption_action="map_to_standard",
                conflict_state="none",
                reason="lifecycle decision affects automatic outputs",
            ),
        ),
        summary=MetricLifecycleRecomputeAuditSummary(
            review_item_count=1,
            artifact_count=1,
            recompute_needed_count=1,
            dry_run_conflict_count=0,
        ),
    )
```

- [ ] **Step 2: Run repository test and verify failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_storage_query_audit_integration.py::test_recompute_run_persists_lifecycle_recompute_audit_snapshot -q
```

Expected: FAIL because `save_recompute_result(...)` does not accept
`lifecycle_recompute_audit` and `load_recompute_run_audit_view(...)` does not exist.

- [ ] **Step 3: Implement repository persistence view**

In `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`,
extend imports:

```python
from financial_report_analysis.models import (
    MetricLifecycleRecomputeAudit,
    MetricGovernanceDecision,
    MetricGovernanceDecisionType,
    MetricLifecycleAction,
    MetricLifecycleCandidateLink,
    MetricLifecycleConceptIdentity,
    MetricLifecycleDecision,
    MetricLifecycleEntry,
    MetricLifecycleStatus,
)
from financial_report_analysis.p5.recompute import (
    metric_lifecycle_recompute_audit_from_payload,
    metric_lifecycle_recompute_audit_to_payload,
    recompute_diff_summary_to_payload,
    recompute_result_from_payload,
    recompute_result_to_payload,
)
```

Add dataclass near `DatasetAuditView`:

```python
@dataclass(frozen=True, slots=True)
class RecomputeRunAuditView:
    run_id: str
    result: P5RecomputeResult
    lifecycle_recompute_audit: MetricLifecycleRecomputeAudit | None
```

Change `save_recompute_result(...)` signature:

```python
def save_recompute_result(
    self,
    *,
    run_id: str,
    plan: P5RecomputePlan,
    result: P5RecomputeResult,
    lifecycle_recompute_audit: MetricLifecycleRecomputeAudit | None = None,
) -> str:
```

Replace `result_json = json.dumps(...)` construction with:

```python
        result_payload = recompute_result_to_payload(result)
        if lifecycle_recompute_audit is not None:
            result_payload["lifecycle_recompute_audit"] = (
                metric_lifecycle_recompute_audit_to_payload(lifecycle_recompute_audit)
            )
        result_json = json.dumps(
            result_payload,
            ensure_ascii=False,
            sort_keys=True,
        )
```

Add repository method after `load_recompute_result(...)`:

```python
    def load_recompute_run_audit_view(self, run_id: str) -> RecomputeRunAuditView:
        with Session(self.engine) as session:
            record = session.get(RecomputeRunRecord, run_id)
            if record is None or record.result_json is None:
                raise P5ArtifactRepositoryError(
                    f"missing recompute result in DB repository: {run_id}"
                )
            payload = json.loads(record.result_json)
        return RecomputeRunAuditView(
            run_id=run_id,
            result=recompute_result_from_payload(payload),
            lifecycle_recompute_audit=_lifecycle_recompute_audit_from_result_payload(
                payload
            ),
        )
```

Add this private helper at module level, outside the
`SqlAlchemyP5ArtifactRepository` class, near the other payload helper functions:

```python
def _lifecycle_recompute_audit_from_result_payload(
    payload: dict[str, object],
) -> MetricLifecycleRecomputeAudit | None:
    audit_payload = payload.get("lifecycle_recompute_audit")
    if audit_payload is None:
        return None
    if not isinstance(audit_payload, dict):
        raise P5ArtifactRepositoryError("lifecycle_recompute_audit must be an object")
    return metric_lifecycle_recompute_audit_from_payload(audit_payload)
```

- [ ] **Step 4: Run repository test and verify pass**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_storage_query_audit_integration.py::test_recompute_run_persists_lifecycle_recompute_audit_snapshot -q
```

Expected: PASS.

- [ ] **Step 5: Run storage query/audit integration file**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_storage_query_audit_integration.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit repository persistence**

```bash
git add financial-report-analysis/src/financial_report_analysis/storage/repositories.py financial-report-analysis/tests/integration/test_storage_query_audit_integration.py
git commit -m "feat: persist lifecycle recompute audit snapshots"
```

## Task 3: Expose Latest Lifecycle Audit In Dataset Audit View

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Test: `financial-report-analysis/tests/integration/test_storage_query_audit_integration.py`

- [ ] **Step 1: Write failing dataset audit view test**

Append to `financial-report-analysis/tests/integration/test_storage_query_audit_integration.py`:

```python
def test_dataset_audit_view_exposes_latest_lifecycle_recompute_audit(
    tmp_path: Path,
) -> None:
    repository, dataset = _seed_repository_dataset(tmp_path)
    audit = _lifecycle_audit()
    plan = P5RecomputePlan(
        manifest_id="manifest-1",
        dataset_id=dataset.dataset_id,
        target_artifact_ids=dataset.source_artifacts,
        rebuild_dataset=True,
        rebuild_turtle_export=True,
        reason="metric_lifecycle_decision_changed",
    )
    result = P5RecomputeResult(
        manifest_id="manifest-1",
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

    audit_view = repository.load_dataset_audit_view(dataset.dataset_id)

    assert audit_view.latest_recompute_run_id == "lifecycle-recompute-run-1"
    assert audit_view.latest_recompute_reason == "metric_lifecycle_decision_changed"
    assert audit_view.latest_lifecycle_recompute_audit == audit
```

- [ ] **Step 2: Run dataset audit test and verify failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_storage_query_audit_integration.py::test_dataset_audit_view_exposes_latest_lifecycle_recompute_audit -q
```

Expected: FAIL because `DatasetAuditView` has no `latest_lifecycle_recompute_audit`.

- [ ] **Step 3: Add dataset audit field**

In `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`,
add field to `DatasetAuditView`:

```python
    latest_lifecycle_recompute_audit: MetricLifecycleRecomputeAudit | None
```

Inside `load_dataset_audit_view(...)`, before `return DatasetAuditView(...)`, compute:

```python
            latest_lifecycle_recompute_audit = None
            if recompute_record is not None and recompute_record.result_json is not None:
                latest_payload = json.loads(recompute_record.result_json)
                latest_lifecycle_recompute_audit = (
                    _lifecycle_recompute_audit_from_result_payload(latest_payload)
                )
```

Add constructor field:

```python
            latest_lifecycle_recompute_audit=latest_lifecycle_recompute_audit,
```

- [ ] **Step 4: Run dataset audit test and verify pass**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_storage_query_audit_integration.py::test_dataset_audit_view_exposes_latest_lifecycle_recompute_audit -q
```

Expected: PASS.

- [ ] **Step 5: Run focused repository tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_storage_query_audit_integration.py tests/integration/test_storage_p5_parity.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit dataset audit view**

```bash
git add financial-report-analysis/src/financial_report_analysis/storage/repositories.py financial-report-analysis/tests/integration/test_storage_query_audit_integration.py
git commit -m "feat: expose lifecycle audit in dataset audit view"
```

## Task 4: Expose Lifecycle Audit Through Existing API Responses

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Test: `financial-report-analysis/tests/integration/test_api_storage_runtime.py`

- [ ] **Step 1: Write failing API integration test**

Append to `financial-report-analysis/tests/integration/test_api_storage_runtime.py`:

```python
def test_storage_runtime_exposes_lifecycle_recompute_audit_snapshot(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(storage_db_path=tmp_path / "runtime.db"))
    _seed_runtime(client, tmp_path)
    repository = client.app.state.runtime.storage_repository
    assert repository is not None
    dataset = repository.load_dataset_artifact("p5_seed_3_issuers_2_years")
    audit = _lifecycle_audit()
    plan = P5RecomputePlan(
        manifest_id="manifest-1",
        dataset_id=dataset.dataset_id,
        target_artifact_ids=dataset.source_artifacts,
        rebuild_dataset=True,
        rebuild_turtle_export=True,
        reason="metric_lifecycle_decision_changed",
    )
    result = P5RecomputeResult(
        manifest_id="manifest-1",
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
    recompute_response = client.get("/recompute-runs/lifecycle-recompute-run-1")
    audit_response = client.get(f"/datasets/{dataset.dataset_id}/audit")

    assert recompute_response.status_code == 200
    assert recompute_response.json()["lifecycle_recompute_audit"]["summary"][
        "recompute_needed_count"
    ] == 1
    assert audit_response.status_code == 200
    assert audit_response.json()["latest_lifecycle_recompute_audit"]["items"][0][
        "latest_decision_id"
    ] == "metric-lifecycle-decision:1"
```

Reuse the `_lifecycle_audit()` helper from Task 2 in this test file, including the same
imports for metric lifecycle models.

- [ ] **Step 2: Run API test and verify failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_api_storage_runtime.py::test_storage_runtime_exposes_lifecycle_recompute_audit_snapshot -q
```

Expected: FAIL because API schemas/routes do not expose the snapshot.

- [ ] **Step 3: Add API schema fields**

In `financial-report-analysis/src/financial_report_analysis/api/schemas.py`, add this
field to `DatasetAuditResponse` immediately after `latest_recompute_reason`:

```python
latest_lifecycle_recompute_audit: MetricLifecycleRecomputeAuditResponse | None = None
```

Add this field to `RecomputeResultResponse` immediately after `diff_summary`:

```python
lifecycle_recompute_audit: MetricLifecycleRecomputeAuditResponse | None = None
```

- [ ] **Step 4: Wire API routes**

In `financial-report-analysis/src/financial_report_analysis/api/routes.py`, update
`get_recompute_result(...)`:

```python
def get_recompute_result(
    run_id: str,
    request: Request,
) -> RecomputeResultResponse:
    repository = _require_storage_repository(request)
    view = _load_or_404(repository.load_recompute_run_audit_view, run_id)
    return _recompute_result_to_response(
        run_id,
        view.result,
        lifecycle_recompute_audit=view.lifecycle_recompute_audit,
    )
```

Change helper signature:

```python
def _recompute_result_to_response(
    run_id: str,
    result: P5RecomputeResult,
    *,
    lifecycle_recompute_audit: MetricLifecycleRecomputeAudit | None = None,
) -> RecomputeResultResponse:
```

Add response field:

```python
        lifecycle_recompute_audit=(
            _metric_lifecycle_recompute_audit_to_response(lifecycle_recompute_audit)
            if lifecycle_recompute_audit is not None
            else None
        ),
```

In `_dataset_audit_to_response(...)`, add:

```python
        latest_lifecycle_recompute_audit=(
            _metric_lifecycle_recompute_audit_to_response(
                audit_view.latest_lifecycle_recompute_audit
            )
            if audit_view.latest_lifecycle_recompute_audit is not None
            else None
        ),
```

- [ ] **Step 5: Run API test and verify pass**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_api_storage_runtime.py::test_storage_runtime_exposes_lifecycle_recompute_audit_snapshot -q
```

Expected: PASS.

- [ ] **Step 6: Run API/storage regression**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_api_storage_runtime.py tests/integration/test_metric_governance_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit API surface**

```bash
git add financial-report-analysis/src/financial_report_analysis/api/schemas.py financial-report-analysis/src/financial_report_analysis/api/routes.py financial-report-analysis/tests/integration/test_api_storage_runtime.py
git commit -m "feat: expose lifecycle recompute audit snapshots"
```

## Task 5: Final Verification And Documentation Status

**Files:**
- Modify only if needed: `docs/superpowers/specs/active/2026-04-22-financial-report-analysis-unified-roadmap.md`
- Modify only if needed: `docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/05-risks-and-roadmap.md`

- [ ] **Step 1: Run focused unit tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_recompute.py -q
```

Expected: PASS.

- [ ] **Step 2: Run focused integration tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_storage_query_audit_integration.py tests/integration/test_storage_p5_parity.py tests/integration/test_api_storage_runtime.py tests/integration/test_metric_governance_api.py -q
```

Expected: PASS.

- [ ] **Step 3: Run P5 recompute review flow regression**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_p5_recompute_review_flow.py tests/unit/test_db_assembly_service.py -q
```

Expected: PASS.

- [ ] **Step 4: Run Ruff**

Run:

```bash
cd financial-report-analysis
uv run ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 5: Update roadmap status only after implementation passes**

If all verification passes, update the current-state sections to mark
`Lifecycle Recompute Audit Persistence` as completed:

- `docs/superpowers/specs/active/2026-04-22-financial-report-analysis-unified-roadmap.md`
- `docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/05-risks-and-roadmap.md`

Do not update roadmap status before implementation and verification are complete.

- [ ] **Step 6: Commit final status update**

```bash
git add docs/superpowers/specs/active/2026-04-22-financial-report-analysis-unified-roadmap.md docs/architecture-analysis/2026-04-28-financial-report-analysis-system-architecture/05-risks-and-roadmap.md
git commit -m "docs: mark lifecycle audit persistence complete"
```

## Final Review Checklist

- [ ] Lifecycle audit snapshot is saved with the recompute run that used it.
- [ ] `load_recompute_result(...)` remains backward-compatible.
- [ ] `load_recompute_run_audit_view(...)` exposes result plus optional snapshot.
- [ ] Dataset audit view reads persisted snapshot from latest recompute run, not live lifecycle state.
- [ ] API responses expose optional lifecycle audit snapshots.
- [ ] Non-lifecycle recompute runs return `None` / `null` audit fields.
- [ ] Existing lifecycle decision write APIs are unchanged.
- [ ] Existing P5 dataset, Turtle export, downstream governance, and recompute behavior are unchanged except for read-surface audit visibility.
- [ ] Focused pytest commands pass.
- [ ] `uv run ruff check .` passes.
