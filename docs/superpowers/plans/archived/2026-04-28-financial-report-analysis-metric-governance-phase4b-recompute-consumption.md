# Metric Governance Phase 4B Recompute And Consumption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add audit-first lifecycle recompute planning and explicit controlled consumption for mapped and blacklisted metric lifecycle decisions.

**Architecture:** P4B adds a read-only audit layer first, then an opt-in governed artifact overlay used by recompute. Existing extraction, normal recompute reasons, Phase 1 provisional guardrails, P5 dataset assembly, and Turtle export behavior remain unchanged unless lifecycle consumption is explicitly requested.

**Tech Stack:** Python 3, FastAPI, Pydantic, dataclasses, pytest, Ruff.

---

## File Structure

- Create `financial-report-analysis/src/financial_report_analysis/services/metric_lifecycle_recompute.py`: builds audit items, summaries, and optional dry-run consumption impact from review items, lifecycle state, and persisted artifacts.
- Create `financial-report-analysis/src/financial_report_analysis/services/metric_lifecycle_consumption.py`: applies an opt-in governed artifact overlay for `mapped_to_standard` and `blacklisted` using the same matching rules as dry-run audit.
- Modify `financial-report-analysis/src/financial_report_analysis/models/governance.py`: add audit and consumption dataclasses.
- Modify `financial-report-analysis/src/financial_report_analysis/models/__init__.py`: export new governance dataclasses.
- Modify `financial-report-analysis/src/financial_report_analysis/api/schemas.py`: add audit API response schemas.
- Modify `financial-report-analysis/src/financial_report_analysis/api/routes.py`: add read-only lifecycle recompute audit endpoint and preserve lifecycle provenance in dataset row responses.
- Modify `financial-report-analysis/src/financial_report_analysis/p5/recompute.py`: add lifecycle recompute reason and optional lifecycle consumption context for execution.
- Modify `financial-report-analysis/src/financial_report_analysis/p5/dataset.py`: preserve lifecycle provenance from governed canonical facts into dataset rows.
- Modify `financial-report-analysis/src/financial_report_analysis/p5/turtle_export.py`: preserve lifecycle provenance from dataset rows into Turtle rows.
- Test `financial-report-analysis/tests/unit/test_metric_lifecycle_recompute.py`.
- Test `financial-report-analysis/tests/unit/test_metric_lifecycle_consumption.py`.
- Test `financial-report-analysis/tests/integration/test_metric_governance_api.py`.
- Test `financial-report-analysis/tests/unit/test_p5_recompute.py`.
- Test existing P5 dataset/Turtle tests where provenance behavior is asserted.

## Task 1: Audit Models And Service

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/models/governance.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/models/__init__.py`
- Create: `financial-report-analysis/src/financial_report_analysis/services/metric_lifecycle_recompute.py`
- Test: `financial-report-analysis/tests/unit/test_metric_lifecycle_recompute.py`

- [ ] **Step 1: Add failing audit service tests**

Create `tests/unit/test_metric_lifecycle_recompute.py` with tests for these cases:

```python
def test_audit_returns_empty_summary_without_links() -> None:
    audit = build_metric_lifecycle_recompute_audit(
        review_items=(),
        lifecycle_state_loader=lambda _review_item_id: MetricLifecycleState(
            entry=None,
            latest_decision=None,
            candidate_link=None,
            decision_history=(),
        ),
    )

    assert audit.items == ()
    assert audit.summary.review_item_count == 0
    assert audit.summary.recompute_needed_count == 0
```

```python
def test_audit_marks_mapped_and_blacklisted_items_recompute_needed() -> None:
    mapped_id = build_review_item_id("CN_601919_2025", "candidate-mapped")
    blacklisted_id = build_review_item_id("CN_601919_2025", "candidate-blacklisted")
    mapped_item = _review_item(
        mapped_id,
        artifact_id="CN_601919_2025",
        metric_id="custom::cn::general::balance-sheet::root::deposit",
    )
    blacklisted_item = _review_item(
        blacklisted_id,
        artifact_id="CN_601919_2025",
        metric_id="custom::cn::general::income-statement::root::bad",
    )

    audit = build_metric_lifecycle_recompute_audit(
        review_items=(mapped_item, blacklisted_item),
        lifecycle_state_loader=lambda review_item_id: {
            mapped_id: _state("mapped_to_standard", action="map_to_standard"),
            blacklisted_id: _state("blacklisted", action="blacklist"),
        }[review_item_id],
    )

    assert [item.consumption_action for item in audit.items] == [
        "map_to_standard",
        "suppress_blacklisted",
    ]
    assert all(item.recompute_needed for item in audit.items)
    assert audit.summary.artifact_count == 1
    assert audit.summary.recompute_needed_count == 2
```

```python
def test_audit_leaves_non_output_states_not_recompute_needed() -> None:
    approved_id = build_review_item_id("CN_601919_2025", "candidate-approved")
    deprecated_id = build_review_item_id("CN_601919_2025", "candidate-deprecated")
    provisional_id = build_review_item_id("CN_601919_2025", "candidate-provisional")
    items = (
        _review_item(approved_id),
        _review_item(deprecated_id),
        _review_item(provisional_id),
    )

    audit = build_metric_lifecycle_recompute_audit(
        review_items=items,
        lifecycle_state_loader=lambda review_item_id: {
            approved_id: _state("approved_custom", action="approve_custom"),
            deprecated_id: _state("deprecated", action="deprecate"),
            provisional_id: _state_without_decision("provisional"),
        }[review_item_id],
    )

    assert [item.recompute_needed for item in audit.items] == [False, False, False]
    assert [item.consumption_action for item in audit.items] == [
        "none",
        "none",
        "none",
    ]
```

The test file should define small `_review_item`, `_state`, and
`_state_without_decision` helpers using existing governance dataclasses. Import
`build_review_item_id` from
`financial_report_analysis.services.metric_governance_review`; do not use
synthetic review item ids that cannot be parsed by `parse_review_item_id`.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle_recompute.py -q
```

Expected: FAIL because the module and dataclasses do not exist.

- [ ] **Step 3: Add audit dataclasses**

In `models/governance.py`, add:

```python
MetricLifecycleConsumptionAction = Literal[
    "none",
    "map_to_standard",
    "already_present",
    "conflict",
    "suppress_blacklisted",
]
MetricLifecycleDryRunConflictState = Literal[
    "none",
    "already_present",
    "conflict",
    "missing_candidate",
    "missing_target",
]


@dataclass(frozen=True, slots=True)
class MetricLifecycleRecomputeAuditItem:
    review_item_id: str
    artifact_id: str
    issuer_id: str
    fiscal_year: int
    report_type: str
    candidate_metric_id: str
    raw_label: str
    lifecycle_entry_id: str | None
    current_status: MetricLifecycleStatus | None
    latest_decision_id: str | None
    latest_decision_action: MetricLifecycleAction | None
    target_metric_id: str | None
    recompute_needed: bool
    consumption_action: MetricLifecycleConsumptionAction
    conflict_state: MetricLifecycleDryRunConflictState
    reason: str


@dataclass(frozen=True, slots=True)
class MetricLifecycleRecomputeAuditSummary:
    review_item_count: int
    artifact_count: int
    recompute_needed_count: int
    dry_run_conflict_count: int


@dataclass(frozen=True, slots=True)
class MetricLifecycleRecomputeAudit:
    items: tuple[MetricLifecycleRecomputeAuditItem, ...]
    summary: MetricLifecycleRecomputeAuditSummary
```

Export these names from `models/__init__.py`.

- [ ] **Step 4: Implement audit service**

Create `services/metric_lifecycle_recompute.py`:

```python
from __future__ import annotations

from collections.abc import Callable

from financial_report_analysis.models import (
    MetricGovernanceReviewItem,
    MetricLifecycleRecomputeAudit,
    MetricLifecycleRecomputeAuditItem,
    MetricLifecycleRecomputeAuditSummary,
    MetricLifecycleState,
)
from financial_report_analysis.p5.models import P5ExtractedArtifact


def build_metric_lifecycle_recompute_audit(
    *,
    review_items: tuple[MetricGovernanceReviewItem, ...],
    lifecycle_state_loader: Callable[[str], MetricLifecycleState],
    dry_run_artifact_loader: Callable[[str], P5ExtractedArtifact | None] | None = None,
) -> MetricLifecycleRecomputeAudit:
    items: list[MetricLifecycleRecomputeAuditItem] = []
    for review_item in review_items:
        state = lifecycle_state_loader(review_item.review_item_id)
        if state.candidate_link is None:
            continue
        item = _audit_item(review_item, state)
        if dry_run_artifact_loader is not None:
            artifact = dry_run_artifact_loader(item.artifact_id)
            if artifact is not None:
                item = _with_dry_run_consumption(item, artifact)
        items.append(item)
    return MetricLifecycleRecomputeAudit(
        items=tuple(items),
        summary=MetricLifecycleRecomputeAuditSummary(
            review_item_count=len(items),
            artifact_count=len({item.artifact_id for item in items}),
            recompute_needed_count=sum(1 for item in items if item.recompute_needed),
            dry_run_conflict_count=sum(
                1 for item in items if item.conflict_state == "conflict"
            ),
        ),
    )
```

Implement `_audit_item` as:

```python
def _audit_item(
    review_item: MetricGovernanceReviewItem,
    state: MetricLifecycleState,
) -> MetricLifecycleRecomputeAuditItem:
    status = state.entry.current_status if state.entry is not None else None
    decision = state.latest_decision
    consumption_action: MetricLifecycleConsumptionAction = "none"
    recompute_needed = False
    reason = "lifecycle decision does not affect automatic outputs"
    if status == "mapped_to_standard":
        consumption_action = "map_to_standard"
        recompute_needed = True
        reason = "lifecycle decision affects automatic outputs"
    elif status == "blacklisted":
        consumption_action = "suppress_blacklisted"
        recompute_needed = True
        reason = "lifecycle decision affects automatic outputs"

    return MetricLifecycleRecomputeAuditItem(
        review_item_id=review_item.review_item_id,
        artifact_id=review_item.artifact_id,
        issuer_id=review_item.issuer_id,
        fiscal_year=review_item.fiscal_year,
        report_type=review_item.report_type,
        candidate_metric_id=review_item.metric_id,
        raw_label=review_item.raw_label,
        lifecycle_entry_id=state.entry.lifecycle_entry_id
        if state.entry is not None
        else None,
        current_status=status,
        latest_decision_id=decision.decision_id if decision is not None else None,
        latest_decision_action=decision.action if decision is not None else None,
        target_metric_id=decision.target_metric_id if decision is not None else None,
        recompute_needed=recompute_needed,
        consumption_action=consumption_action,
        conflict_state="none",
        reason=reason,
    )
```

Implement `_with_dry_run_consumption` so:

- `mapped_to_standard` returns `recompute_needed=True`,
  `consumption_action="map_to_standard"`, `conflict_state="none"`;
- `blacklisted` returns `recompute_needed=True`,
  `consumption_action="suppress_blacklisted"`, `conflict_state="none"`;
- all other states return `recompute_needed=False`,
  `consumption_action="none"`, `conflict_state="none"`.
- `map_to_standard` with no target metric returns
  `conflict_state="missing_target"`, `consumption_action="conflict"`;
- `map_to_standard` with a missing candidate fact returns
  `conflict_state="missing_candidate"`, `consumption_action="conflict"`;
- `map_to_standard` with an existing target canonical fact and the same value
  returns `conflict_state="already_present"`,
  `consumption_action="already_present"`;
- `map_to_standard` with an existing target canonical fact and a different
  value returns `conflict_state="conflict"`, `consumption_action="conflict"`;
- `blacklisted` remains `conflict_state="none"` and
  `consumption_action="suppress_blacklisted"`.

Use `dataclasses.replace` to return modified frozen audit items from
`_with_dry_run_consumption`. Import `P5ExtractedArtifact` from
`financial_report_analysis.p5.models`.

Add dry-run tests in `tests/unit/test_metric_lifecycle_recompute.py` before
moving to the API task:

```python
def test_dry_run_reports_already_present_and_conflict() -> None:
    same_value_id = build_review_item_id("CN_601919_2025", "candidate-same")
    conflict_id = build_review_item_id("CN_601919_2025", "candidate-conflict")
    artifact = _artifact(
        artifact_id="CN_601919_2025",
        candidate_facts=(
            _candidate_fact("candidate-same", numeric_value=100),
            _candidate_fact("candidate-conflict", numeric_value=200),
        ),
        canonical_facts=(
            _canonical_fact("accounts_receiv", numeric_value=100),
            _canonical_fact("accounts_receiv", numeric_value=999),
        ),
    )

    audit = build_metric_lifecycle_recompute_audit(
        review_items=(
            _review_item(same_value_id),
            _review_item(conflict_id),
        ),
        lifecycle_state_loader=lambda _review_item_id: _state(
            "mapped_to_standard",
            action="map_to_standard",
            target_metric_id="accounts_receiv",
        ),
        dry_run_artifact_loader=lambda _artifact_id: artifact,
    )

    assert [item.consumption_action for item in audit.items] == [
        "already_present",
        "conflict",
    ]
    assert [item.conflict_state for item in audit.items] == [
        "already_present",
        "conflict",
    ]
    assert audit.summary.dry_run_conflict_count == 1
```

```python
def test_dry_run_reports_missing_target_and_missing_candidate() -> None:
    missing_target_id = build_review_item_id("CN_601919_2025", "candidate-target")
    missing_candidate_id = build_review_item_id("CN_601919_2025", "candidate-missing")
    artifact = _artifact(
        artifact_id="CN_601919_2025",
        candidate_facts=(_candidate_fact("candidate-target", numeric_value=100),),
        canonical_facts=(),
    )

    audit = build_metric_lifecycle_recompute_audit(
        review_items=(
            _review_item(missing_target_id),
            _review_item(missing_candidate_id),
        ),
        lifecycle_state_loader=lambda review_item_id: {
            missing_target_id: _state(
                "mapped_to_standard",
                action="map_to_standard",
                target_metric_id=None,
            ),
            missing_candidate_id: _state(
                "mapped_to_standard",
                action="map_to_standard",
                target_metric_id="accounts_receiv",
            ),
        }[review_item_id],
        dry_run_artifact_loader=lambda _artifact_id: artifact,
    )

    assert [item.consumption_action for item in audit.items] == [
        "conflict",
        "conflict",
    ]
    assert [item.conflict_state for item in audit.items] == [
        "missing_target",
        "missing_candidate",
    ]
```

```python
def test_dry_run_reports_blacklisted_suppression() -> None:
    review_item_id = build_review_item_id("CN_601919_2025", "candidate-blacklisted")
    artifact = _artifact(
        artifact_id="CN_601919_2025",
        candidate_facts=(_candidate_fact("candidate-blacklisted", numeric_value=100),),
        canonical_facts=(
            _canonical_fact(
                "custom::cn::general::income-statement::root::bad",
                numeric_value=100,
            ),
        ),
    )

    audit = build_metric_lifecycle_recompute_audit(
        review_items=(
            _review_item(
                review_item_id,
                metric_id="custom::cn::general::income-statement::root::bad",
            ),
        ),
        lifecycle_state_loader=lambda _review_item_id: _state(
            "blacklisted",
            action="blacklist",
        ),
        dry_run_artifact_loader=lambda _artifact_id: artifact,
    )

    assert audit.items[0].consumption_action == "suppress_blacklisted"
    assert audit.items[0].conflict_state == "none"
```

Extend the test helpers so `_artifact`, `_candidate_fact`, and `_canonical_fact`
create the minimum fields used by dry-run matching:

```python
def _candidate_fact(fact_id: str, *, numeric_value: int) -> dict[str, object]:
    return {
        "fact_id": fact_id,
        "metric_id": "custom::cn::general::balance-sheet::root::deposit",
        "numeric_value": numeric_value,
        "entity_scope": "consolidated",
        "extensions": {"period_scope": "fy"},
        "statement_type": "balance_sheet",
    }
```

```python
def _canonical_fact(metric_id: str, *, numeric_value: int) -> dict[str, object]:
    return {
        "fact_id": f"canonical-{metric_id}-{numeric_value}",
        "metric_id": metric_id,
        "numeric_value": numeric_value,
        "entity_scope": "consolidated",
        "extensions": {"period_scope": "fy"},
        "statement_type": "balance_sheet",
    }
```

- [ ] **Step 5: Run audit tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle_recompute.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/models/governance.py financial-report-analysis/src/financial_report_analysis/models/__init__.py financial-report-analysis/src/financial_report_analysis/services/metric_lifecycle_recompute.py financial-report-analysis/tests/unit/test_metric_lifecycle_recompute.py
git commit -m "feat: add metric lifecycle recompute audit"
```

## Task 2: Audit API Endpoint

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Test: `financial-report-analysis/tests/integration/test_metric_governance_api.py`

- [ ] **Step 1: Add failing API test**

Add a test that creates a lifecycle entry and a `map_to_standard` decision using
the P4A endpoints, then calls:

```text
GET /api/v1/metric-governance/lifecycle-recompute-audit?issuer_id=CN_601919
```

Assert:

```python
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["review_item_count"] == 1
    assert payload["summary"]["recompute_needed_count"] == 1
    assert payload["items"][0]["current_status"] == "mapped_to_standard"
    assert payload["items"][0]["target_metric_id"] == "accounts_receiv"
    assert payload["items"][0]["consumption_action"] == "map_to_standard"
```

- [ ] **Step 2: Run API test and verify it fails**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_recompute_audit_reports_mapped_decision -q
```

Expected: FAIL with 404 because the audit endpoint does not exist.

- [ ] **Step 3: Add schemas**

Add Pydantic response models:

```python
class MetricLifecycleRecomputeAuditItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_item_id: str
    artifact_id: str
    issuer_id: str
    fiscal_year: int
    report_type: str
    candidate_metric_id: str
    raw_label: str
    lifecycle_entry_id: str | None = None
    current_status: str | None = None
    latest_decision_id: str | None = None
    latest_decision_action: str | None = None
    target_metric_id: str | None = None
    recompute_needed: bool
    consumption_action: str
    conflict_state: str
    reason: str


class MetricLifecycleRecomputeAuditSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_item_count: int
    artifact_count: int
    recompute_needed_count: int
    dry_run_conflict_count: int


class MetricLifecycleRecomputeAuditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[MetricLifecycleRecomputeAuditItemResponse]
    summary: MetricLifecycleRecomputeAuditSummaryResponse
```

- [ ] **Step 4: Add route**

Add route:

```python
@router.get(
    "/api/v1/metric-governance/lifecycle-recompute-audit",
    response_model=MetricLifecycleRecomputeAuditResponse,
)
def get_metric_lifecycle_recompute_audit(
    request: Request,
    issuer_id: str | None = None,
    fiscal_year: int | None = None,
    dry_run: bool = False,
) -> MetricLifecycleRecomputeAuditResponse:
    repository = _require_storage_repository(request)
    review_service = MetricGovernanceReviewService(repository)
    lifecycle_service = MetricLifecycleService(repository)
    artifact_loader: Callable[[str], P5ExtractedArtifact | None] | None = None
    if dry_run:
        def load_dry_run_artifact(artifact_id: str) -> P5ExtractedArtifact | None:
            return _load_artifact_for_lifecycle_dry_run(repository, artifact_id)
        artifact_loader = load_dry_run_artifact

    audit = build_metric_lifecycle_recompute_audit(
        review_items=tuple(
            review_service.list_review_items(
                issuer_id=issuer_id,
                fiscal_year=fiscal_year,
            )
        ),
        lifecycle_state_loader=lifecycle_service.load_state_by_review_item,
        dry_run_artifact_loader=artifact_loader,
    )
    return _metric_lifecycle_recompute_audit_to_response(audit)
```

Import `Callable` from `collections.abc`. Add response conversion helpers in
`routes.py`. Wrap dry-run artifact loading so a missing artifact returns `None`
instead of leaking repository-specific exceptions:

```python
def _load_artifact_for_lifecycle_dry_run(
    repository: object,
    artifact_id: str,
) -> P5ExtractedArtifact | None:
    try:
        load_artifact = getattr(repository, "load_extracted_artifact")
        return load_artifact(artifact_id)
    except (AttributeError, FileNotFoundError, KeyError, P5ArtifactRepositoryError):
        return None
```

Pass `_load_artifact_for_lifecycle_dry_run` through a lambda when `dry_run` is
true. When `dry_run` is false, pass `None`.

- [ ] **Step 5: Run API tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_metric_governance_api.py -q
uv run ruff check src/financial_report_analysis/api/schemas.py src/financial_report_analysis/api/routes.py tests/integration/test_metric_governance_api.py
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/api/schemas.py financial-report-analysis/src/financial_report_analysis/api/routes.py financial-report-analysis/tests/integration/test_metric_governance_api.py
git commit -m "feat: expose metric lifecycle recompute audit"
```

## Task 3: Controlled Consumption Overlay

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/services/metric_lifecycle_consumption.py`
- Test: `financial-report-analysis/tests/unit/test_metric_lifecycle_consumption.py`

- [ ] **Step 1: Add failing consumption tests**

Create tests for:

- `mapped_to_standard` creates a governed canonical fact when no target metric
  canonical fact exists;
- `already_present` audit items do not duplicate canonical facts;
- `conflict`, `missing_candidate`, and `missing_target` audit items do not add
  or overwrite canonical facts;
- `blacklisted` suppresses matching custom canonical facts in the governed
  artifact view.

Each governed fact must include:

```python
extensions["metric_governance"]["lifecycle_consumption"] == {
    "source_review_item_id": review_item_id,
    "lifecycle_entry_id": lifecycle_entry_id,
    "decision_id": decision_id,
    "decision_action": "map_to_standard",
    "source_candidate_metric_id": custom_metric_id,
    "target_metric_id": "accounts_receiv",
    "consumption_action": "map_to_standard",
}
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle_consumption.py -q
```

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement consumption overlay**

Create:

```python
from dataclasses import replace


def apply_metric_lifecycle_consumption(
    *,
    artifact: P5ExtractedArtifact,
    audit: MetricLifecycleRecomputeAudit,
) -> P5ExtractedArtifact:
    canonical_facts = list(artifact.canonical_facts)
    for item in audit.items:
        if item.artifact_id != artifact.artifact_id:
            continue
        if item.consumption_action == "suppress_blacklisted":
            canonical_facts = [
                fact
                for fact in canonical_facts
                if str(fact.get("metric_id", "")) != item.candidate_metric_id
            ]
            continue
        if item.consumption_action != "map_to_standard":
            continue
        if item.target_metric_id is None:
            continue
        candidate = _candidate_fact_for_review_item(artifact, item.review_item_id)
        if candidate is None:
            continue
        existing = _matching_canonical_facts(
            canonical_facts,
            target_metric_id=item.target_metric_id,
            candidate=candidate,
        )
        if existing:
            continue
        canonical_facts.append(_governed_canonical_fact(candidate, item))
    return replace(artifact, canonical_facts=tuple(canonical_facts))
```

Rules:

- The function returns a new `P5ExtractedArtifact` instance.
- It never mutates `artifact`.
- It does not return a report. Dry-run audit is the only component that reports
  `already_present`, `conflict`, `missing_candidate`, and `missing_target`.
- It appends governed canonical facts only for `map_to_standard` audit items
  with no conflict.
- It removes custom canonical facts matching blacklisted audit items.
- It preserves all unrelated candidate, canonical, derived, validation, review,
  quality, and missing status fields.
- `_candidate_fact_for_review_item` parses the review item id with the existing
  `parse_review_item_id` helper and matches `candidate["fact_id"]`.
- `_matching_canonical_facts` compares metric id, entity scope, period scope,
  and statement type. A separate `_same_numeric_value` helper compares the
  value in the dry-run audit service when deciding whether a match is
  `already_present` or `conflict`.
- `_governed_canonical_fact` copies candidate value, unit, currency, statement
  type, source fields, and evidence bundle into a canonical-fact-shaped dict
  with `metric_id=item.target_metric_id` and lifecycle provenance.
- `conflict` and `already_present` audit items do not modify canonical facts.
- `suppress_blacklisted` removes canonical facts whose `metric_id` equals
  `item.candidate_metric_id`, and leaves unrelated canonical facts intact.

- [ ] **Step 4: Run consumption tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle_consumption.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/services/metric_lifecycle_consumption.py financial-report-analysis/tests/unit/test_metric_lifecycle_consumption.py
git commit -m "feat: apply controlled metric lifecycle consumption"
```

## Task 4: Recompute Integration And Output Provenance

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/recompute.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/runner.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/models.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/artifact_repository.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/dataset.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/turtle_export.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Test: `financial-report-analysis/tests/unit/test_p5_recompute.py`
- Test: `financial-report-analysis/tests/unit/test_p5_dataset.py`
- Test: `financial-report-analysis/tests/unit/test_p5_turtle_export.py`
- Test: `financial-report-analysis/tests/integration/test_metric_governance_api.py`

- [ ] **Step 1: Add failing recompute tests**

Add tests showing:

```python
def test_build_recompute_plan_marks_lifecycle_decision_changes_for_dataset_and_export() -> None:
    plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=("CN_601919_2025",),
        reason="metric_lifecycle_decision_changed",
    )

    assert plan.rebuild_dataset is True
    assert plan.rebuild_turtle_export is True
    assert plan.target_artifact_ids == ("CN_601919_2025",)
```

Add this execution test:

```python
def test_execute_recompute_plan_passes_lifecycle_artifact_transform_only_for_lifecycle_reason(
    tmp_path: Path,
) -> None:
    calls: dict[str, object] = {}

    def fake_run_p5_dataset_build(**kwargs):
        calls.update(kwargs)
        return type(
            "Result",
            (),
            {
                "manifest_id": "p5_seed",
                "extracted_artifact_ids": ("CN_601919_2025",),
                "dataset_path": tmp_path / "p5_seed.json",
                "turtle_export_path": tmp_path / "p5_seed_turtle_export.json",
            },
        )()

    plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=("CN_601919_2025",),
        reason="metric_lifecycle_decision_changed",
    )

    execute_recompute_plan(
        plan=plan,
        manifest_path=tmp_path / "manifest.json",
        artifact_root=tmp_path / "data" / "p5",
        pdf_root=tmp_path,
        lifecycle_consumption_audit=_audit_for_recompute(),
        run_p5_dataset_build_func=fake_run_p5_dataset_build,
    )

    assert calls["artifact_transform_func"] is not None
```

Add this fail-fast test:

```python
def test_execute_recompute_plan_requires_lifecycle_audit_for_lifecycle_reason(
    tmp_path: Path,
) -> None:
    plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=("CN_601919_2025",),
        reason="metric_lifecycle_decision_changed",
    )

    with pytest.raises(
        ValueError,
        match="lifecycle_consumption_audit is required for lifecycle recompute",
    ):
        execute_recompute_plan(
            plan=plan,
            manifest_path=tmp_path / "manifest.json",
            artifact_root=tmp_path / "data" / "p5",
            pdf_root=tmp_path,
        )
```

The test file should define `_audit_for_recompute()` as a one-item
`MetricLifecycleRecomputeAudit` whose item has
`artifact_id="CN_601919_2025"`, `consumption_action="map_to_standard"`,
`target_metric_id="accounts_receiv"`, and `recompute_needed=True`.

- [ ] **Step 2: Run recompute tests and verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_recompute.py -q
```

Expected: FAIL because lifecycle reason/context is not implemented.

- [ ] **Step 3: Implement recompute reason**

In `_rebuild_flags_for_reason`, add:

```python
"metric_lifecycle_decision_changed": (True, True),
```

Add an optional `lifecycle_consumption_audit` parameter to
`execute_recompute_plan`. For existing reasons the value is ignored. For
`metric_lifecycle_decision_changed`, pass an `artifact_transform_func` to
`run_p5_dataset_build_func`.

If `plan.reason.strip().lower() == "metric_lifecycle_decision_changed"` and
`lifecycle_consumption_audit is None`, raise:

```python
ValueError("lifecycle_consumption_audit is required for lifecycle recompute")
```

Modify `run_p5_dataset_build` in `p5/runner.py` to accept:

```python
artifact_transform_func: Callable[[P5ExtractedArtifact], P5ExtractedArtifact] | None = None
```

After `_load_or_build_artifact`, apply:

```python
if artifact_transform_func is not None:
    artifact = artifact_transform_func(artifact)
```

Do not persist the transformed artifact. The transform affects only dataset and
Turtle outputs for the current recompute run.

- [ ] **Step 4: Preserve provenance in dataset and Turtle rows**

Add this field to `P5DatasetRow`:

```python
lifecycle_consumption: dict[str, object] | None = None
```

In `_present_row_from_fact`, read:

```python
lifecycle_consumption = (
    _mapping_value(extensions.get("metric_governance"))
    .get("lifecycle_consumption")
)
```

Set `lifecycle_consumption` on the row when that value is a mapping, otherwise
`None`.

In `_missing_rows`, set `lifecycle_consumption=None`.

In `artifact_repository._row_to_json`, include `lifecycle_consumption`. In
`_row_from_json`, read it back as a `dict[str, object] | None`.

In `api/schemas.py`, add the same field to `DatasetRowResponse`:

```python
lifecycle_consumption: dict[str, object] | None = None
```

In `api/routes.py`, set `lifecycle_consumption=row.lifecycle_consumption` in
`_dataset_row_to_response`.

`build_turtle_export` already uses `asdict(row)`, so governed rows will include
the field automatically. Add a Turtle test asserting non-governed rows serialize
`lifecycle_consumption=None` and governed rows preserve the provenance object.

- [ ] **Step 5: Run focused P5 tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_recompute.py tests/unit/test_p5_dataset.py tests/unit/test_p5_turtle_export.py tests/integration/test_metric_governance_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/recompute.py financial-report-analysis/src/financial_report_analysis/p5/runner.py financial-report-analysis/src/financial_report_analysis/p5/models.py financial-report-analysis/src/financial_report_analysis/p5/artifact_repository.py financial-report-analysis/src/financial_report_analysis/p5/dataset.py financial-report-analysis/src/financial_report_analysis/p5/turtle_export.py financial-report-analysis/src/financial_report_analysis/api/schemas.py financial-report-analysis/src/financial_report_analysis/api/routes.py financial-report-analysis/tests/unit/test_p5_recompute.py financial-report-analysis/tests/unit/test_p5_dataset.py financial-report-analysis/tests/unit/test_p5_turtle_export.py financial-report-analysis/tests/integration/test_metric_governance_api.py
git commit -m "feat: integrate metric lifecycle consumption with recompute"
```

## Task 5: Verification And Guardrails

**Files:**
- Modify only if verification exposes a P4B defect in files touched by Tasks
  1-4.

- [ ] **Step 1: Run governance API tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_metric_governance_api.py -q
```

Expected: PASS.

- [ ] **Step 2: Run lifecycle unit tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle.py tests/unit/test_metric_lifecycle_repository.py tests/unit/test_metric_lifecycle_service.py tests/unit/test_metric_lifecycle_recompute.py tests/unit/test_metric_lifecycle_consumption.py -q
```

Expected: PASS.

- [ ] **Step 3: Run P5 recompute/output tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_recompute.py tests/unit/test_p5_dataset.py tests/unit/test_p5_turtle_export.py tests/unit/test_p5_lineage.py -q
```

Expected: PASS.

- [ ] **Step 4: Run no-output-change guardrails**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py::test_analyze_report_blocks_provisional_custom_metric_from_canonical_facts tests/unit/test_fact_pipeline.py::test_provisional_custom_quarterly_candidates_do_not_produce_ttm_facts tests/unit/test_report_adapter.py::test_report_adapter_excludes_non_auto_analysis_facts_from_key_facts tests/unit/test_report_adapter.py::test_report_adapter_does_not_expose_extensions_in_ttm_facts -q
```

Expected: PASS.

- [ ] **Step 5: Run Ruff**

Run:

```bash
cd financial-report-analysis
uv run ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 6: Commit verification fixes if needed**

If verification required changes, commit:

```bash
git add financial-report-analysis/src/financial_report_analysis financial-report-analysis/tests
git commit -m "fix: stabilize metric lifecycle recompute consumption"
```

If no files changed, do not create an empty commit.

## Self-Review

- Spec coverage: audit models/service and read-only API are covered by Tasks 1
  and 2; controlled consumption is covered by Task 3; recompute and output
  provenance are covered by Task 4; guardrails are covered by Task 5.
- Scope check: P4B does not add UI, async jobs, backfill, raw-label matching,
  extraction, Ollama, semantic fallback, or broad scheduler changes.
- Type consistency: plan uses `MetricLifecycleRecomputeAudit`,
  `MetricLifecycleRecomputeAuditItem`,
  `MetricLifecycleRecomputeAuditSummary`, and
  `metric_lifecycle_decision_changed` consistently.
