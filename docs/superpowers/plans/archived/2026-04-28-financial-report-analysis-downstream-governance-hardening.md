# Financial Report Analysis Downstream Governance Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent non-consumable governed facts from becoming P5 dataset present rows, Turtle stable rows, or availability present metrics.

**Architecture:** Add one shared downstream governance policy helper that evaluates canonical fact dictionaries using `extensions.metric_governance`. Wire that helper into P5 dataset assembly and 3-5Y availability, while keeping Turtle export as a dataset-only consumer that preserves lifecycle provenance and never reads extracted artifacts directly.

**Tech Stack:** Python 3.12, dataclasses, pytest, Ruff, existing `financial_report_analysis.p5` package.

---

## File Structure

- Create: `financial-report-analysis/src/financial_report_analysis/p5/governance_policy.py`
  - Owns downstream fact-consumption policy.
  - Does not access repositories, DB sessions, lifecycle services, or raw PDFs.
- Create: `financial-report-analysis/tests/unit/test_p5_governance_policy.py`
  - Unit tests for standard allowed, provisional/custom blocked, missing/malformed metadata blocked, lifecycle controlled consumption allowed, and blacklisted/deprecated blocked.
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/dataset.py`
  - Filter canonical facts before `_present_row_from_fact`.
  - Add governance blocked summaries to `quality_summary`.
- Modify: `financial-report-analysis/tests/unit/test_p5_dataset.py`
  - Add standard governance metadata to existing positive fixtures.
  - Add blocked fact regression tests.
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/availability.py`
  - Apply the same downstream policy before marking a required metric `present`.
- Modify: `financial-report-analysis/tests/unit/test_p5_availability.py`
  - Add standard governance metadata to existing positive fixtures.
  - Add false-present regression tests for blocked facts.
- Read only: `financial-report-analysis/src/financial_report_analysis/p5/turtle_export.py`
  - Confirm Turtle export remains dataset-driven. This plan does not change Turtle export implementation.
- Modify: `financial-report-analysis/tests/unit/test_p5_turtle_export.py`
  - Verify Turtle export does not bypass dataset governance and still preserves lifecycle provenance.
- Modify: `financial-report-analysis/tests/unit/test_public_exports.py`
  - Assert the new policy helper is available through the explicit P5 public exports.

## Task 1: Add Shared Downstream Governance Policy

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/p5/governance_policy.py`
- Test: `financial-report-analysis/tests/unit/test_p5_governance_policy.py`

- [ ] **Step 1: Write failing policy tests**

Create `financial-report-analysis/tests/unit/test_p5_governance_policy.py`:

```python
from __future__ import annotations

from financial_report_analysis.p5.governance_policy import (
    DownstreamGovernanceDecision,
    evaluate_downstream_fact_consumption,
    is_downstream_consumable_fact,
)


def _fact(metric_governance: object | None) -> dict[str, object]:
    extensions: dict[str, object] = {"period_scope": "duration"}
    if metric_governance is not None:
        extensions["metric_governance"] = metric_governance
    return {
        "fact_id": "fact-1",
        "metric_id": "revenue",
        "extensions": extensions,
    }


def test_standard_metric_is_downstream_consumable() -> None:
    fact = _fact(
        {
            "registry_status": "standard",
            "metric_namespace": "standard",
            "review_required": False,
            "auto_analysis_allowed": True,
            "governance_reason": "standard_metric",
        }
    )

    decision = evaluate_downstream_fact_consumption(fact)

    assert decision == DownstreamGovernanceDecision(
        allowed=True,
        reason="auto_analysis_allowed",
        governance_metadata={
            "registry_status": "standard",
            "metric_namespace": "standard",
            "review_required": False,
            "auto_analysis_allowed": True,
            "governance_reason": "standard_metric",
        },
    )
    assert is_downstream_consumable_fact(fact) is True


def test_provisional_custom_metric_is_blocked() -> None:
    fact = _fact(
        {
            "registry_status": "provisional",
            "metric_namespace": "custom",
            "review_required": True,
            "auto_analysis_allowed": False,
            "governance_reason": "provisional_custom_metric",
        }
    )

    decision = evaluate_downstream_fact_consumption(fact)

    assert decision.allowed is False
    assert decision.reason == "auto_analysis_not_allowed"
    assert is_downstream_consumable_fact(fact) is False


def test_missing_governance_metadata_is_blocked() -> None:
    decision = evaluate_downstream_fact_consumption(_fact(None))

    assert decision == DownstreamGovernanceDecision(
        allowed=False,
        reason="missing_metric_governance",
        governance_metadata={},
    )


def test_malformed_governance_metadata_is_blocked() -> None:
    decision = evaluate_downstream_fact_consumption(_fact(["bad"]))

    assert decision == DownstreamGovernanceDecision(
        allowed=False,
        reason="malformed_metric_governance",
        governance_metadata={},
    )


def test_controlled_map_to_standard_consumption_is_allowed() -> None:
    fact = _fact(
        {
            "registry_status": "provisional",
            "metric_namespace": "custom",
            "review_required": True,
            "auto_analysis_allowed": False,
            "governance_reason": "mapped_lifecycle_decision",
            "lifecycle_consumption": {
                "source_review_item_id": "CN_601919_2025:candidate-1",
                "lifecycle_entry_id": "metric-lifecycle:1",
                "decision_id": "metric-lifecycle-decision:1",
                "decision_action": "map_to_standard",
                "source_candidate_metric_id": "custom::receivables",
                "target_metric_id": "accounts_receiv",
                "consumption_action": "map_to_standard",
            },
        }
    )

    decision = evaluate_downstream_fact_consumption(fact)

    assert decision.allowed is True
    assert decision.reason == "controlled_consumption:map_to_standard"
    assert is_downstream_consumable_fact(fact) is True


def test_blacklisted_or_deprecated_metric_is_blocked_even_with_auto_allowed_flag() -> None:
    for registry_status in ("blacklisted", "deprecated"):
        decision = evaluate_downstream_fact_consumption(
            _fact(
                {
                    "registry_status": registry_status,
                    "metric_namespace": "custom",
                    "review_required": True,
                    "auto_analysis_allowed": True,
                    "governance_reason": registry_status,
                }
            )
        )

        assert decision.allowed is False
        assert decision.reason == f"blocked_registry_status:{registry_status}"


def test_custom_namespace_is_blocked_without_controlled_consumption() -> None:
    decision = evaluate_downstream_fact_consumption(
        _fact(
            {
                "registry_status": "approved_custom",
                "metric_namespace": "custom",
                "review_required": False,
                "auto_analysis_allowed": True,
                "governance_reason": "approved_custom_metric",
            }
        )
    )

    assert decision.allowed is False
    assert decision.reason == "custom_namespace_without_controlled_consumption"
```

- [ ] **Step 2: Run policy tests and verify failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_governance_policy.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'financial_report_analysis.p5.governance_policy'`.

- [ ] **Step 3: Implement policy helper**

Create `financial-report-analysis/src/financial_report_analysis/p5/governance_policy.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from financial_report_analysis.registries.metric_governance import (
    METRIC_GOVERNANCE_EXTENSION_KEY,
)

_BLOCKED_REGISTRY_STATUSES = {"blacklisted", "deprecated"}
_ALLOWED_CONSUMPTION_ACTIONS = {"map_to_standard"}


@dataclass(frozen=True, slots=True)
class DownstreamGovernanceDecision:
    allowed: bool
    reason: str
    governance_metadata: dict[str, Any]


def evaluate_downstream_fact_consumption(
    fact: Mapping[str, Any],
) -> DownstreamGovernanceDecision:
    extensions = fact.get("extensions")
    if not isinstance(extensions, Mapping):
        return DownstreamGovernanceDecision(
            allowed=False,
            reason="missing_extensions",
            governance_metadata={},
        )

    metadata = extensions.get(METRIC_GOVERNANCE_EXTENSION_KEY)
    if metadata is None:
        return DownstreamGovernanceDecision(
            allowed=False,
            reason="missing_metric_governance",
            governance_metadata={},
        )
    if not isinstance(metadata, Mapping):
        return DownstreamGovernanceDecision(
            allowed=False,
            reason="malformed_metric_governance",
            governance_metadata={},
        )

    governance_metadata = dict(metadata)
    registry_status = governance_metadata.get("registry_status")
    if registry_status in _BLOCKED_REGISTRY_STATUSES:
        return DownstreamGovernanceDecision(
            allowed=False,
            reason=f"blocked_registry_status:{registry_status}",
            governance_metadata=governance_metadata,
        )

    lifecycle_consumption = governance_metadata.get("lifecycle_consumption")
    if isinstance(lifecycle_consumption, Mapping):
        consumption_action = lifecycle_consumption.get("consumption_action")
        if consumption_action in _ALLOWED_CONSUMPTION_ACTIONS:
            return DownstreamGovernanceDecision(
                allowed=True,
                reason=f"controlled_consumption:{consumption_action}",
                governance_metadata=governance_metadata,
            )

    if governance_metadata.get("metric_namespace") == "custom":
        return DownstreamGovernanceDecision(
            allowed=False,
            reason="custom_namespace_without_controlled_consumption",
            governance_metadata=governance_metadata,
        )

    if governance_metadata.get("auto_analysis_allowed") is True:
        return DownstreamGovernanceDecision(
            allowed=True,
            reason="auto_analysis_allowed",
            governance_metadata=governance_metadata,
        )

    return DownstreamGovernanceDecision(
        allowed=False,
        reason="auto_analysis_not_allowed",
        governance_metadata=governance_metadata,
    )


def is_downstream_consumable_fact(fact: Mapping[str, Any]) -> bool:
    return evaluate_downstream_fact_consumption(fact).allowed
```

- [ ] **Step 4: Run policy tests and verify pass**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_governance_policy.py -q
```

Expected: `7 passed`.

- [ ] **Step 5: Commit policy helper**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/governance_policy.py financial-report-analysis/tests/unit/test_p5_governance_policy.py
git commit -m "feat: add downstream governance policy"
```

## Task 2: Apply Policy In P5 Dataset Assembly

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/dataset.py`
- Modify: `financial-report-analysis/tests/unit/test_p5_dataset.py`

- [ ] **Step 1: Add standard governance helper to dataset tests**

Modify `financial-report-analysis/tests/unit/test_p5_dataset.py` near imports:

```python
def _standard_extensions(period_scope: str) -> dict[str, object]:
    return {
        "period_scope": period_scope,
        "metric_governance": {
            "registry_status": "standard",
            "metric_namespace": "standard",
            "review_required": False,
            "auto_analysis_allowed": True,
            "governance_reason": "standard_metric",
        },
    }
```

Replace positive fixture extension blocks in existing tests from:

```python
"extensions": {"period_scope": "duration"},
```

to:

```python
"extensions": _standard_extensions("duration"),
```

Replace:

```python
"extensions": {"period_scope": "point_in_time"},
```

to:

```python
"extensions": _standard_extensions("point_in_time"),
```

- [ ] **Step 2: Write failing dataset blocked-fact tests**

Append to `financial-report-analysis/tests/unit/test_p5_dataset.py`:

```python
def test_assemble_dataset_blocks_non_consumable_governed_canonical_facts(
    tmp_path: Path,
) -> None:
    artifact = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(
            {
                "fact_id": "fact-custom-revenue",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 100.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-custom",
                "extensions": {
                    "period_scope": "duration",
                    "metric_governance": {
                        "registry_status": "provisional",
                        "metric_namespace": "custom",
                        "review_required": True,
                        "auto_analysis_allowed": False,
                        "governance_reason": "provisional_custom_metric",
                    },
                },
            },
        ),
        missing_status={
            "working_capital_missing_status": {"revenue": "present"},
        },
    )

    dataset = assemble_dataset(
        dataset_id="p5_seed",
        artifacts=(artifact,),
        required_metric_ids=("revenue",),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert len(dataset.rows) == 1
    row = dataset.rows[0]
    assert row.metric_id == "revenue"
    assert row.missing_status == "not_surfaced"
    assert row.source_fact_id is None
    assert dataset.quality_summary["present_row_count"] == 0
    assert dataset.quality_summary["governance_blocked_fact_count"] == 1
    assert dataset.quality_summary["governance_blocked_by_metric"] == {"revenue": 1}
    assert dataset.quality_summary["governance_blocked_by_reason"] == {
        "auto_analysis_not_allowed": 1
    }
    assert dataset.quality_summary["governance_blocked_source_fact_ids"] == [
        "fact-custom-revenue"
    ]


def test_assemble_dataset_blocks_missing_governance_metadata_by_default(
    tmp_path: Path,
) -> None:
    artifact = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(
            {
                "fact_id": "fact-legacy-revenue",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 100.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-legacy",
                "extensions": {"period_scope": "duration"},
            },
        ),
    )

    dataset = assemble_dataset(
        dataset_id="p5_seed",
        artifacts=(artifact,),
        required_metric_ids=("revenue",),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert dataset.rows[0].missing_status == "unknown"
    assert dataset.quality_summary["governance_blocked_fact_count"] == 1
    assert dataset.quality_summary["governance_blocked_by_reason"] == {
        "missing_metric_governance": 1
    }
```

- [ ] **Step 3: Run dataset tests and verify failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_dataset.py -q
```

Expected: FAIL because blocked facts are still emitted as present rows and `governance_blocked_fact_count` is missing.

- [ ] **Step 4: Filter facts and add blocked summary in dataset assembly**

Modify imports in `financial-report-analysis/src/financial_report_analysis/p5/dataset.py`:

```python
from financial_report_analysis.p5.governance_policy import (
    DownstreamGovernanceDecision,
    evaluate_downstream_fact_consumption,
)
```

Replace the `present_rows` construction in `assemble_dataset` with:

```python
    consumable_facts, blocked_facts = _split_governed_facts(artifacts)
    present_rows = [
        _present_row_from_fact(artifact, fact)
        for artifact, fact, _decision in consumable_facts
    ]
```

Change the `quality_summary=` call to:

```python
        quality_summary=_quality_summary(
            artifacts=artifacts,
            present_rows=tuple(present_rows),
            rows=rows,
            blocked_facts=tuple(blocked_facts),
        ),
```

Add this helper below `assemble_dataset`:

```python
def _split_governed_facts(
    artifacts: tuple[P5ExtractedArtifact, ...],
) -> tuple[
    list[tuple[P5ExtractedArtifact, Mapping[str, Any], DownstreamGovernanceDecision]],
    list[tuple[P5ExtractedArtifact, Mapping[str, Any], DownstreamGovernanceDecision]],
]:
    consumable: list[
        tuple[P5ExtractedArtifact, Mapping[str, Any], DownstreamGovernanceDecision]
    ] = []
    blocked: list[
        tuple[P5ExtractedArtifact, Mapping[str, Any], DownstreamGovernanceDecision]
    ] = []
    for artifact in artifacts:
        for fact in artifact.canonical_facts:
            decision = evaluate_downstream_fact_consumption(fact)
            target = consumable if decision.allowed else blocked
            target.append((artifact, fact, decision))
    return consumable, blocked
```

Change `_quality_summary` signature:

```python
def _quality_summary(
    *,
    artifacts: tuple[P5ExtractedArtifact, ...],
    present_rows: tuple[P5DatasetRow, ...],
    rows: tuple[P5DatasetRow, ...],
    blocked_facts: tuple[
        tuple[P5ExtractedArtifact, Mapping[str, Any], DownstreamGovernanceDecision],
        ...,
    ],
) -> dict[str, Any]:
```

Inside `_quality_summary`, before `return`, compute:

```python
    governance_blocked_by_metric: dict[str, int] = defaultdict(int)
    governance_blocked_by_reason: dict[str, int] = defaultdict(int)
    governance_blocked_source_fact_ids: list[str] = []
    for _artifact, fact, decision in blocked_facts:
        metric_id = fact.get("metric_id")
        if isinstance(metric_id, str):
            governance_blocked_by_metric[metric_id] += 1
        governance_blocked_by_reason[decision.reason] += 1
        fact_id = fact.get("fact_id")
        if isinstance(fact_id, str):
            governance_blocked_source_fact_ids.append(fact_id)
```

Add these keys to the returned dict:

```python
        "governance_blocked_fact_count": len(blocked_facts),
        "governance_blocked_by_metric": dict(
            sorted(governance_blocked_by_metric.items())
        ),
        "governance_blocked_by_reason": dict(
            sorted(governance_blocked_by_reason.items())
        ),
        "governance_blocked_source_fact_ids": sorted(
            governance_blocked_source_fact_ids
        ),
```

- [ ] **Step 5: Run focused tests and verify pass**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_governance_policy.py tests/unit/test_p5_dataset.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit dataset hardening**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/dataset.py financial-report-analysis/tests/unit/test_p5_dataset.py
git commit -m "feat: apply downstream governance to p5 dataset"
```

## Task 3: Apply Policy In Multi-Year Availability

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/availability.py`
- Modify: `financial-report-analysis/tests/unit/test_p5_availability.py`

- [ ] **Step 1: Update availability positive fixture with standard governance**

In `_artifact()` inside `financial-report-analysis/tests/unit/test_p5_availability.py`, replace:

```python
"extensions": {"period_scope": "fy"},
```

with:

```python
"extensions": {
    "period_scope": "fy",
    "metric_governance": {
        "registry_status": "standard",
        "metric_namespace": "standard",
        "review_required": False,
        "auto_analysis_allowed": True,
        "governance_reason": "standard_metric",
    },
},
```

- [ ] **Step 2: Write blocked availability regression test**

Append to `financial-report-analysis/tests/unit/test_p5_availability.py`:

```python
def test_availability_does_not_mark_blocked_governance_fact_present() -> None:
    artifact = _artifact(
        fiscal_year=2024,
        missing_status={"working_capital_missing_status": {"revenue": "present"}},
    )
    blocked_fact = dict(artifact.canonical_facts[0])
    blocked_fact["extensions"] = {
        "period_scope": "fy",
        "metric_governance": {
            "registry_status": "provisional",
            "metric_namespace": "custom",
            "review_required": True,
            "auto_analysis_allowed": False,
            "governance_reason": "provisional_custom_metric",
        },
    }
    artifact = P5ExtractedArtifact(
        artifact_id=artifact.artifact_id,
        artifact_version=artifact.artifact_version,
        pipeline_version=artifact.pipeline_version,
        manifest_entry=artifact.manifest_entry,
        source_pdf_path=artifact.source_pdf_path,
        document=artifact.document,
        document_metadata=artifact.document_metadata,
        candidate_facts=artifact.candidate_facts,
        canonical_facts=(blocked_fact,),
        derived_facts=artifact.derived_facts,
        validation_report=artifact.validation_report,
        review_packets=artifact.review_packets,
        quality_gate=artifact.quality_gate,
        missing_status=artifact.missing_status,
        created_at=artifact.created_at,
    )
    repository = FakeReadRepository(
        coverages={
            ("HK_09987", 2024, "annual"): _coverage(
                fiscal_year=2024,
                artifact_ids=("HK_09987_2024",),
            )
        },
        artifacts={"HK_09987_2024": artifact},
        loaded_artifact_ids=[],
    )

    view = build_multi_year_availability_view(
        repository=repository,
        request=MultiYearAvailabilityRequest(
            issuer_id="HK_09987",
            start_year=2024,
            end_year=2024,
            metric_profile="turtle_core",
            required_metric_ids=("revenue",),
        ),
    )

    metric = view.years[0].metrics[0]
    assert metric.metric_id == "revenue"
    assert metric.status == "unknown"
    assert metric.value is None
    assert view.coverage_summary["present_metric_count"] == 0
```

- [ ] **Step 3: Run availability test and verify failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_availability.py::test_availability_does_not_mark_blocked_governance_fact_present -q
```

Expected: FAIL because availability currently returns `status == "present"` for the blocked fact.

- [ ] **Step 4: Apply policy in availability present scan**

Modify imports in `financial-report-analysis/src/financial_report_analysis/p5/availability.py`:

```python
from financial_report_analysis.p5.governance_policy import (
    is_downstream_consumable_fact,
)
```

In `_availability_metrics`, change the fact loop condition from:

```python
            if (
                not isinstance(metric_id, str)
                or metric_id not in required_metric_id_set
                or metric_id in metrics_by_id
            ):
                continue
            metrics_by_id[metric_id] = _present_metric(artifact.artifact_id, fact)
```

to:

```python
            if (
                not isinstance(metric_id, str)
                or metric_id not in required_metric_id_set
                or metric_id in metrics_by_id
                or not is_downstream_consumable_fact(fact)
            ):
                continue
            metrics_by_id[metric_id] = _present_metric(artifact.artifact_id, fact)
```

- [ ] **Step 5: Run focused availability tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_availability.py tests/unit/test_p5_governance_policy.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit availability hardening**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/availability.py financial-report-analysis/tests/unit/test_p5_availability.py
git commit -m "feat: apply downstream governance to availability"
```

## Task 4: Document Turtle Export Remains Dataset-Governed

**Files:**
- Modify: `financial-report-analysis/tests/unit/test_p5_turtle_export.py`

- [ ] **Step 1: Add Turtle non-present diagnostic regression**

Append to `financial-report-analysis/tests/unit/test_p5_turtle_export.py`:

```python
def test_build_turtle_export_does_not_invent_values_for_missing_rows() -> None:
    dataset = P5DatasetArtifact(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00",
        issuer_count=1,
        periods=(2025,),
        metrics=("revenue",),
        rows=(
            P5DatasetRow(
                issuer_id="CN_601919",
                market="CN",
                stock_code="601919",
                fiscal_year=2025,
                metric_id="revenue",
                entity_scope="consolidated",
                period_scope="unknown",
                statement_type="metrics",
                value=None,
                currency=None,
                unit=None,
                quality_status=None,
                missing_status="not_surfaced",
                source_fact_id=None,
                source_artifact_id="CN_601919_2025",
                evidence_bundle_id=None,
            ),
        ),
        quality_summary={
            "governance_blocked_fact_count": 1,
            "governance_blocked_by_metric": {"revenue": 1},
        },
        source_artifacts=("CN_601919_2025",),
    )

    export = build_turtle_export(dataset)

    assert export.rows == (
        {
            "issuer_id": "CN_601919",
            "market": "CN",
            "stock_code": "601919",
            "fiscal_year": 2025,
            "metric_id": "revenue",
            "entity_scope": "consolidated",
            "period_scope": "unknown",
            "statement_type": "metrics",
            "value": None,
            "currency": None,
            "unit": None,
            "quality_status": None,
            "missing_status": "not_surfaced",
            "source_fact_id": None,
            "source_artifact_id": "CN_601919_2025",
            "evidence_bundle_id": None,
            "lifecycle_consumption": None,
            "canonical_metric_id": "revenue",
            "turtle_field": "revenue",
        },
    )
```

- [ ] **Step 2: Run Turtle export tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_turtle_export.py -q
```

Expected: PASS. Current dataset-driven export preserves non-present rows without inventing values.

- [ ] **Step 3: Run Turtle and dataset tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_turtle_export.py tests/unit/test_p5_dataset.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit Turtle verification**

```bash
git add financial-report-analysis/tests/unit/test_p5_turtle_export.py
git commit -m "test: document turtle export governance boundary"
```

## Task 5: Full Verification And Public Export Check

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/__init__.py`
- Modify: `financial-report-analysis/tests/unit/test_public_exports.py`

- [ ] **Step 1: Add public export test**

Append to `financial-report-analysis/tests/unit/test_public_exports.py`:

```python
def test_p5_governance_policy_public_exports() -> None:
    from financial_report_analysis.p5 import (
        evaluate_downstream_fact_consumption,
        is_downstream_consumable_fact,
    )

    assert callable(evaluate_downstream_fact_consumption)
    assert callable(is_downstream_consumable_fact)
```

- [ ] **Step 2: Run public export test and verify failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_public_exports.py::test_p5_governance_policy_public_exports -q
```

Expected: FAIL with `ImportError` because the new policy helpers are not exported from `financial_report_analysis.p5`.

- [ ] **Step 3: Export governance policy helpers**

Modify `financial-report-analysis/src/financial_report_analysis/p5/__init__.py`.

Add imports:

```python
from financial_report_analysis.p5.governance_policy import (
    DownstreamGovernanceDecision,
    evaluate_downstream_fact_consumption,
    is_downstream_consumable_fact,
)
```

Add names to `__all__`:

```python
"DownstreamGovernanceDecision",
"evaluate_downstream_fact_consumption",
"is_downstream_consumable_fact",
```

- [ ] **Step 4: Run focused full verification**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_governance_policy.py tests/unit/test_p5_dataset.py tests/unit/test_p5_availability.py tests/unit/test_p5_turtle_export.py tests/unit/test_public_exports.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Run governance API integration regression**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_metric_governance_api.py -q
```

Expected: all tests pass. This verifies lifecycle controlled consumption remains compatible with API-level governance flows.

- [ ] **Step 6: Run P5 runner/recompute/storage regression**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_p5_runner.py tests/unit/test_p5_recompute.py tests/unit/test_db_assembly_service.py tests/integration/test_p5_recompute_review_flow.py -q
```

Expected: all tests pass. This verifies the dataset policy does not break P5 runner, recompute, DB assembly, or persisted recompute review flows.

- [ ] **Step 7: Run Ruff**

Run:

```bash
cd financial-report-analysis
uv run ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 8: Commit public export and verification adjustments**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/__init__.py financial-report-analysis/tests/unit/test_public_exports.py
git commit -m "chore: expose downstream governance policy"
```

## Final Review Checklist

- [ ] `evaluate_downstream_fact_consumption()` is the only new policy decision point.
- [ ] P5 dataset filters blocked facts before present row creation.
- [ ] P5 dataset quality summary includes blocked fact audit keys.
- [ ] Availability does not mark blocked facts as present.
- [ ] Turtle export remains dataset-driven and preserves lifecycle provenance.
- [ ] Missing or malformed governance metadata is blocked by default.
- [ ] No extraction, metric mapping, lifecycle write API, or recompute audit contract changed.
- [ ] Focused pytest commands pass.
- [ ] `uv run ruff check .` passes.
