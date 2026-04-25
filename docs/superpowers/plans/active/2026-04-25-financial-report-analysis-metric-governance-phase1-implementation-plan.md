# Financial Report Analysis Metric Governance Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 1 of metric governance so provisional custom metrics are explicitly tagged, reviewable, and blocked from automatic core analysis.

**Architecture:** Keep `MetricMappingRegistry` as the deterministic supported-metric mapping path and treat `MetricRegistry` as the current metric identity resolver. Add a small governance helper module, propagate governance metadata during normalization, block provisional custom candidates before canonical promotion, and make validation/API surfaces report review-required status without changing Turtle field coverage or durable storage workflow.

**Tech Stack:** Python 3.11/3.12, pytest, Ruff, dataclasses, existing `financial_report_analysis` pipeline, services, adapters, and models.

---

## File Structure

Create:

- `financial-report-analysis/src/financial_report_analysis/registries/metric_governance.py`
  - Owns Phase 1 governance metadata constants and helper functions.
  - Does not persist lifecycle state.

Modify:

- `financial-report-analysis/src/financial_report_analysis/registries/__init__.py`
  - Exports the new helper functions and constants.
- `financial-report-analysis/src/financial_report_analysis/services/fact_normalizer.py`
  - Adds `metric_governance` metadata from `MetricRegistryEntry`.
- `financial-report-analysis/src/financial_report_analysis/services/conflict_resolver.py`
  - Blocks provisional custom candidates from canonical promotion and emits review packets.
- `financial-report-analysis/src/financial_report_analysis/models/governance.py`
  - Adds the Phase 1 provisional metric conflict state to the review packet contract.
- `financial-report-analysis/src/financial_report_analysis/services/validation_service.py`
  - Adds a validation issue when provisional metric review packets exist.
- `financial-report-analysis/src/financial_report_analysis/adapters/report_adapter.py`
  - Defensively excludes `auto_analysis_allowed=false` facts from `key_facts`.

Test:

- `financial-report-analysis/tests/unit/test_metric_governance.py`
- `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- `financial-report-analysis/tests/unit/test_report_adapter.py`

Do not modify:

- database schema;
- P5/Turtle export schema;
- Ollama fallback contracts;
- external registry loading.

## Task 1: Add Metric Governance Helper Contract

**Files:**

- Create: `financial-report-analysis/src/financial_report_analysis/registries/metric_governance.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/__init__.py`
- Test: `financial-report-analysis/tests/unit/test_metric_governance.py`

- [ ] **Step 1: Write failing helper tests**

Create `financial-report-analysis/tests/unit/test_metric_governance.py`:

```python
from __future__ import annotations

from financial_report_analysis.registries.metric_governance import (
    automatic_governance_metadata,
    governance_metadata_from_registry_entry,
    is_auto_analysis_allowed,
    is_provisional_custom_metric,
    standard_governance_metadata,
)
from financial_report_analysis.registries.metric_registry import MetricRegistryEntry


def test_governance_metadata_marks_standard_metric_as_auto_allowed() -> None:
    entry = MetricRegistryEntry(
        metric_id="revenue",
        raw_label="Revenue",
        statement_type="income_statement",
        accounting_standard="HKFRS",
        industry_slug="general",
        parent_metric_id=None,
        is_custom=False,
        registry_status="standard",
    )

    metadata = governance_metadata_from_registry_entry(entry)

    assert metadata == {
        "registry_status": "standard",
        "metric_namespace": "standard",
        "review_required": False,
        "auto_analysis_allowed": True,
        "governance_reason": "standard_metric",
    }
    assert is_auto_analysis_allowed({"metric_governance": metadata}) is True
    assert is_provisional_custom_metric({"metric_governance": metadata}) is False


def test_governance_metadata_marks_provisional_custom_metric_as_review_only() -> None:
    entry = MetricRegistryEntry(
        metric_id="custom::hkfrs::general::income-statement::root::loyalty-liabilities",
        raw_label="Customer loyalty liabilities",
        statement_type="income_statement",
        accounting_standard="HKFRS",
        industry_slug="general",
        parent_metric_id=None,
        is_custom=True,
        registry_status="provisional",
    )

    metadata = governance_metadata_from_registry_entry(entry)

    assert metadata == {
        "registry_status": "provisional",
        "metric_namespace": "custom",
        "review_required": True,
        "auto_analysis_allowed": False,
        "governance_reason": "provisional_custom_metric",
    }
    assert is_auto_analysis_allowed({"metric_governance": metadata}) is False
    assert is_provisional_custom_metric({"metric_governance": metadata}) is True


def test_automatic_governance_metadata_keeps_existing_governance_block() -> None:
    extensions = {
        "metric_governance": {
            "registry_status": "mapped_to_standard",
            "metric_namespace": "standard",
            "review_required": False,
            "auto_analysis_allowed": True,
            "governance_reason": "review_decision",
        }
    }

    assert automatic_governance_metadata(extensions) == extensions["metric_governance"]


def test_standard_governance_metadata_can_record_supported_mapping_reason() -> None:
    assert standard_governance_metadata(reason="supported_metric_mapping") == {
        "registry_status": "standard",
        "metric_namespace": "standard",
        "review_required": False,
        "auto_analysis_allowed": True,
        "governance_reason": "supported_metric_mapping",
    }
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_governance.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'financial_report_analysis.registries.metric_governance'`.

- [ ] **Step 3: Implement the helper module**

Create `financial-report-analysis/src/financial_report_analysis/registries/metric_governance.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from financial_report_analysis.registries.metric_registry import MetricRegistryEntry

STANDARD_STATUS = "standard"
PROVISIONAL_STATUS = "provisional"
STANDARD_NAMESPACE = "standard"
CUSTOM_NAMESPACE = "custom"
METRIC_GOVERNANCE_EXTENSION_KEY = "metric_governance"


def governance_metadata_from_registry_entry(
    entry: MetricRegistryEntry,
) -> dict[str, object]:
    if entry.is_custom or entry.registry_status == PROVISIONAL_STATUS:
        return {
            "registry_status": entry.registry_status,
            "metric_namespace": CUSTOM_NAMESPACE,
            "review_required": True,
            "auto_analysis_allowed": False,
            "governance_reason": "provisional_custom_metric",
        }
    metadata = standard_governance_metadata()
    metadata["registry_status"] = entry.registry_status
    return metadata


def standard_governance_metadata(
    *,
    reason: str = "standard_metric",
) -> dict[str, object]:
    return {
        "registry_status": STANDARD_STATUS,
        "metric_namespace": STANDARD_NAMESPACE,
        "review_required": False,
        "auto_analysis_allowed": True,
        "governance_reason": reason,
    }


def automatic_governance_metadata(
    extensions: Mapping[str, Any],
) -> dict[str, object]:
    existing = extensions.get(METRIC_GOVERNANCE_EXTENSION_KEY)
    if isinstance(existing, dict):
        return dict(existing)
    metric_id = str(extensions.get("metric_id", ""))
    if metric_id.startswith("custom::"):
        return {
            "registry_status": PROVISIONAL_STATUS,
            "metric_namespace": CUSTOM_NAMESPACE,
            "review_required": True,
            "auto_analysis_allowed": False,
            "governance_reason": "provisional_custom_metric",
        }
    return standard_governance_metadata()


def is_auto_analysis_allowed(extensions: Mapping[str, Any]) -> bool:
    metadata = automatic_governance_metadata(extensions)
    return bool(metadata.get("auto_analysis_allowed", True))


def is_provisional_custom_metric(extensions: Mapping[str, Any]) -> bool:
    metadata = automatic_governance_metadata(extensions)
    return (
        metadata.get("metric_namespace") == CUSTOM_NAMESPACE
        and metadata.get("registry_status") == PROVISIONAL_STATUS
    )
```

- [ ] **Step 4: Export helper functions**

Modify `financial-report-analysis/src/financial_report_analysis/registries/__init__.py` to include:

```python
from financial_report_analysis.registries.metric_governance import (
    METRIC_GOVERNANCE_EXTENSION_KEY,
    automatic_governance_metadata,
    governance_metadata_from_registry_entry,
    is_auto_analysis_allowed,
    is_provisional_custom_metric,
    standard_governance_metadata,
)
```

Add these names to `__all__`:

```python
    "METRIC_GOVERNANCE_EXTENSION_KEY",
    "automatic_governance_metadata",
    "governance_metadata_from_registry_entry",
    "is_auto_analysis_allowed",
    "is_provisional_custom_metric",
    "standard_governance_metadata",
```

- [ ] **Step 5: Run tests and verify green**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_governance.py -q
uv run ruff check src/financial_report_analysis/registries/metric_governance.py tests/unit/test_metric_governance.py
```

Expected: tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 6: Commit**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/registries/metric_governance.py \
  financial-report-analysis/src/financial_report_analysis/registries/__init__.py \
  financial-report-analysis/tests/unit/test_metric_governance.py
git commit -m "feat: add metric governance metadata helpers"
```

## Task 2: Propagate Governance Metadata During Normalization

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/services/fact_normalizer.py`
- Test: `financial-report-analysis/tests/unit/test_fact_pipeline.py`

- [ ] **Step 1: Add failing normalization tests**

Append these tests to `financial-report-analysis/tests/unit/test_fact_pipeline.py`:

```python
def test_fact_normalizer_adds_standard_metric_governance_metadata() -> None:
    normalized = FactNormalizer().normalize_candidates(
        [
            _candidate(
                fact_id="candidate-governance-standard",
                period_id="2025FY",
                source_rank_hint=1,
                numeric_value=100.0,
                metric_id="raw_revenue",
                metric_label_raw="Revenue",
            )
        ]
    )

    governance = normalized[0].extensions["metric_governance"]
    assert governance == {
        "registry_status": "standard",
        "metric_namespace": "standard",
        "review_required": False,
        "auto_analysis_allowed": True,
        "governance_reason": "standard_metric",
    }


def test_fact_normalizer_adds_provisional_custom_metric_governance_metadata() -> None:
    normalized = FactNormalizer().normalize_candidates(
        [
            _candidate(
                fact_id="candidate-governance-custom",
                period_id="2025FY",
                source_rank_hint=1,
                numeric_value=100.0,
                metric_id="unknown",
                metric_label_raw="Customer loyalty liabilities",
            )
        ]
    )

    fact = normalized[0]
    assert fact.metric_id.startswith("custom::")
    assert fact.extensions["metric_governance"] == {
        "registry_status": "provisional",
        "metric_namespace": "custom",
        "review_required": True,
        "auto_analysis_allowed": False,
        "governance_reason": "provisional_custom_metric",
    }
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py::test_fact_normalizer_adds_standard_metric_governance_metadata tests/unit/test_fact_pipeline.py::test_fact_normalizer_adds_provisional_custom_metric_governance_metadata -q
```

Expected: tests fail with `KeyError: 'metric_governance'`.

- [ ] **Step 3: Add governance metadata in `FactNormalizer`**

Modify imports in `financial-report-analysis/src/financial_report_analysis/services/fact_normalizer.py`:

```python
from financial_report_analysis.registries.metric_registry import (
    MetricRegistry,
    MetricRegistryEntry,
)
from financial_report_analysis.registries.metric_governance import (
    METRIC_GOVERNANCE_EXTENSION_KEY,
    standard_governance_metadata,
    governance_metadata_from_registry_entry,
)
```

Replace the existing `MetricRegistry` import with the grouped import above.

Add this helper near `_resolved_metric_id()`:

```python
    @staticmethod
    def _governance_metadata(
        *,
        candidate: CandidateFact,
        resolved_metric_id: str,
        registry_metric_id: str,
        metric_entry: MetricRegistryEntry,
    ) -> dict[str, object]:
        candidate_metric_id = str(candidate.metric_id or "").strip()
        if (
            candidate_metric_id
            and candidate_metric_id == resolved_metric_id
            and candidate_metric_id != registry_metric_id
            and candidate_metric_id != "unknown"
            and not candidate_metric_id.startswith("custom::")
            and not candidate_metric_id.startswith("raw_")
        ):
            return standard_governance_metadata(
                reason="supported_metric_mapping",
            )
        return governance_metadata_from_registry_entry(metric_entry)
```

This rule protects deterministic `MetricMappingRegistry` facts. If a candidate
already carries a supported non-raw, non-custom metric id, that supported mapping
wins over raw-label identity lookup for Phase 1 governance.

Inside `normalize_candidates()`, after `normalized_extensions = dict(candidate.extensions)`, add:

```python
            normalized_extensions.setdefault(
                METRIC_GOVERNANCE_EXTENSION_KEY,
                self._governance_metadata(
                    candidate=candidate,
                    resolved_metric_id=resolved_metric_id,
                    registry_metric_id=metric_entry.metric_id,
                    metric_entry=metric_entry,
                ),
            )
```

The block should appear before the per-share metadata handling so per-share
metadata and governance metadata can coexist.

- [ ] **Step 3a: Add supported mapping protection test**

Append this test to `financial-report-analysis/tests/unit/test_fact_pipeline.py`:

```python
def test_fact_normalizer_keeps_supported_mapped_metric_governance_standard() -> None:
    normalized = FactNormalizer().normalize_candidates(
        [
            _candidate(
                fact_id="candidate-supported-mapping",
                period_id="2025FY",
                source_rank_hint=1,
                numeric_value=100.0,
                metric_id="total_assets",
                metric_label_raw="Assets, totally weird issuer label",
                statement_type="balance_sheet",
            )
        ]
    )

    fact = normalized[0]
    assert fact.metric_id == "total_assets"
    assert fact.extensions["metric_governance"] == {
        "registry_status": "standard",
        "metric_namespace": "standard",
        "review_required": False,
        "auto_analysis_allowed": True,
        "governance_reason": "supported_metric_mapping",
    }
```

- [ ] **Step 4: Run focused tests and verify green**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py::test_fact_normalizer_adds_standard_metric_governance_metadata tests/unit/test_fact_pipeline.py::test_fact_normalizer_adds_provisional_custom_metric_governance_metadata -q
```

Expected: both tests pass.

Run the supported mapping protection test:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py::test_fact_normalizer_keeps_supported_mapped_metric_governance_standard -q
```

Expected: test passes.

- [ ] **Step 5: Run normalization regression tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py::test_fact_pipeline_normalizes_metric_and_unit tests/unit/test_fact_pipeline.py::test_fact_pipeline_normalizes_chinese_revenue_label -q
```

Expected: both existing tests still pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/services/fact_normalizer.py \
  financial-report-analysis/tests/unit/test_fact_pipeline.py
git commit -m "feat: propagate metric governance metadata"
```

## Task 3: Block Provisional Custom Metrics Before Canonical Promotion

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/services/conflict_resolver.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/models/governance.py`
- Test: `financial-report-analysis/tests/unit/test_fact_pipeline.py`

- [ ] **Step 1: Add failing pipeline guardrail test**

Append this test to `financial-report-analysis/tests/unit/test_fact_pipeline.py`:

```python
def test_analyze_report_blocks_provisional_custom_metric_from_canonical_facts() -> None:
    document = {
        "document_id": "doc-custom-governance",
        "market": "HK",
        "language": "en",
    }
    payload = {
        "candidate_facts": [
            {
                "fact_id": "candidate-custom-1",
                "metric_id": "unknown",
                "metric_label_raw": "Customer loyalty liabilities",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "comparison_axis": "current",
                "adjustment_basis": "reported",
                "period_id": "2025FY",
                "currency": "USD",
                "raw_value": 100.0,
                "numeric_value": 100.0,
                "raw_unit": "US$ millions",
                "normalized_unit": None,
                "precision": 0,
                "confidence": 0.9,
                "extensions": {},
                "document_id": "doc-custom-governance",
                "block_id": "block-1",
                "page_index": 1,
                "evidence_bundle_id": "bundle-1",
                "extraction_method": "table_semantics",
                "source_rank_hint": 1,
            }
        ]
    }

    result = analyze_report(document, payload)

    assert result.canonical_facts == []
    assert result.derived_facts == []
    assert result.quality_gate == "review"
    assert result.validation_report.overall_status == "review_required"
    assert "provisional_metric_review_required" in result.validation_report.issues
    assert len(result.review_packets) == 1
    assert result.review_packets[0].metric_id.startswith("custom::")
    assert result.review_packets[0].conflict_state == "provisional_metric_review_required"
    assert result.review_packets[0].evidence_bundle_id == "bundle-1"
```

Phase 1 does not extend `ReviewPacket` with raw label, table coordinates, or
governance metadata. The review path is: review packet -> `evidence_bundle_id`
and metric id -> persisted extracted artifact / candidate payload. A dedicated
metric-governance review surface with richer fields belongs to Phase 2.

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py::test_analyze_report_blocks_provisional_custom_metric_from_canonical_facts -q
```

Expected: test fails because a provisional custom candidate is promoted to a
canonical fact, or because no review packet/validation issue exists.

- [ ] **Step 3: Import governance helper in `ConflictResolver`**

First update `financial-report-analysis/src/financial_report_analysis/models/governance.py`
so the review packet contract accepts the new state:

```python
ConflictState = Literal[
    "none",
    "scope_not_surfaced",
    "scope_conflict",
    "source_conflict",
    "review_required",
    "blocked",
    "provisional_metric_review_required",
]
```

Modify imports in `financial-report-analysis/src/financial_report_analysis/services/conflict_resolver.py`:

```python
from financial_report_analysis.registries.metric_governance import (
    is_provisional_custom_metric,
)
```

- [ ] **Step 4: Filter provisional candidates before grouping**

At the beginning of `resolve_with_review()`, before `grouped_candidates` is
created, add:

```python
        eligible_candidates: list[CandidateFact] = []
        review_packets: list[ReviewPacket] = []
        for candidate in normalized_candidates:
            if is_provisional_custom_metric(candidate.extensions):
                review_packets.extend(
                    self._build_review_packets(
                        [candidate],
                        competing_candidates=[],
                        conflict_state="provisional_metric_review_required",
                        resolution_reason="blocked_provisional_metric",
                        review_reason="provisional custom metric requires review before automatic analysis",
                        policies={candidate.fact_id: "review_required"},
                    )
                )
                continue
            eligible_candidates.append(candidate)
```

Then change the loop that groups candidates from:

```python
        for candidate in normalized_candidates:
            grouped_candidates[self._business_key(candidate)].append(candidate)
```

to:

```python
        for candidate in eligible_candidates:
            grouped_candidates[self._business_key(candidate)].append(candidate)
```

Remove the later duplicate initialization `review_packets: list[ReviewPacket] = []`
inside the method, because the method now initializes it before grouping.

- [ ] **Step 5: Allow review packets without competing values**

If `_build_review_packets()` assumes non-empty `competing_candidates`, keep
`competing_values` as an empty tuple:

```python
        competing_values = tuple(
            candidate.numeric_value for candidate in competing_candidates
        )
```

No code change is needed if this line already works with an empty list.

- [ ] **Step 6: Run focused test and verify green**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py::test_analyze_report_blocks_provisional_custom_metric_from_canonical_facts -q
```

Expected: test passes.

- [ ] **Step 7: Run conflict regression tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py -q
```

Expected: all tests in `test_fact_pipeline.py` pass.

- [ ] **Step 8: Commit**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/services/conflict_resolver.py \
  financial-report-analysis/src/financial_report_analysis/models/governance.py \
  financial-report-analysis/tests/unit/test_fact_pipeline.py
git commit -m "feat: block provisional metrics from canonical promotion"
```

## Task 4: Add Validation Issue for Provisional Metric Review Packets

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/services/validation_service.py`
- Test: `financial-report-analysis/tests/unit/test_fact_pipeline.py`

- [ ] **Step 1: Add focused validation test**

Append this test to `financial-report-analysis/tests/unit/test_fact_pipeline.py`:

```python
def test_validation_reports_provisional_metric_review_issue() -> None:
    result = analyze_report(
        {"document_id": "doc-validation-custom", "market": "HK", "language": "en"},
        {
            "candidate_facts": [
                {
                    "fact_id": "candidate-custom-validation",
                    "metric_id": "unknown",
                    "metric_label_raw": "Customer loyalty liabilities",
                    "statement_type": "income_statement",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "USD",
                    "raw_value": 100.0,
                    "numeric_value": 100.0,
                    "raw_unit": "US$ millions",
                    "normalized_unit": None,
                    "precision": 0,
                    "confidence": 0.9,
                    "extensions": {},
                    "document_id": "doc-validation-custom",
                    "block_id": "block-1",
                    "page_index": 1,
                    "evidence_bundle_id": "bundle-1",
                    "extraction_method": "table_semantics",
                    "source_rank_hint": 1,
                }
            ]
        },
    )

    assert result.validation_report.issues.count("provisional_metric_review_required") == 1
```

- [ ] **Step 2: Run test and confirm current behavior**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py::test_validation_reports_provisional_metric_review_issue -q
```

Expected: after Task 3 this may already pass because `ValidationService` adds
packet conflict states. If it passes, do not modify production code in this
task. If it fails because the issue code differs or is missing, continue.

- [ ] **Step 3: Make validation issue explicit if needed**

If Step 2 fails, modify `ValidationService.validate()`:

```python
        for packet in review_packet_list:
            issue_code = packet.conflict_state
            if issue_code not in issues:
                issues.append(issue_code)
            if (
                packet.conflict_state == "provisional_metric_review_required"
                and "provisional_metric_review_required" not in issues
            ):
                issues.append("provisional_metric_review_required")
```

If the existing loop already appends `packet.conflict_state`, keep the smaller
existing implementation and skip this edit.

- [ ] **Step 4: Run validation tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py::test_validation_reports_provisional_metric_review_issue tests/unit/test_fact_pipeline.py::test_analyze_report_blocks_provisional_custom_metric_from_canonical_facts -q
```

Expected: both tests pass.

- [ ] **Step 5: Commit if production or test files changed**

If only the test was added, commit it:

```bash
git add financial-report-analysis/tests/unit/test_fact_pipeline.py
git commit -m "test: cover provisional metric validation issue"
```

If `validation_service.py` was changed, commit both files:

```bash
git add financial-report-analysis/src/financial_report_analysis/services/validation_service.py \
  financial-report-analysis/tests/unit/test_fact_pipeline.py
git commit -m "feat: report provisional metric validation issue"
```

## Task 5: Defensively Exclude Non-Auto Facts From API Key Facts

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/adapters/report_adapter.py`
- Test: `financial-report-analysis/tests/unit/test_report_adapter.py`

- [ ] **Step 1: Add failing ReportAdapter test**

If `financial-report-analysis/tests/unit/test_report_adapter.py` does not have a
helper for pipeline mappings, append this standalone test:

```python
from financial_report_analysis.adapters.report_adapter import ReportAdapter


def test_report_adapter_excludes_non_auto_analysis_facts_from_key_facts() -> None:
    result = ReportAdapter().build_analysis_result(
        document={"document_id": "doc-adapter"},
        pipeline_result={
            "canonical_fact_set_id": "fact-set-canonical",
            "derived_fact_set_id": "fact-set-derived",
            "validation_report_id": "validation-report",
            "quality_gate": "review",
            "canonical_facts": [
                {
                    "fact_id": "canonical-custom",
                    "metric_id": "custom::hkfrs::general::income-statement::root::customer-loyalty-liabilities",
                    "metric_label_raw": "Customer loyalty liabilities",
                    "statement_type": "income_statement",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "USD",
                    "raw_value": 100.0,
                    "numeric_value": 100.0,
                    "raw_unit": "US$ millions",
                    "normalized_unit": "USD",
                    "precision": 0,
                    "confidence": 0.9,
                    "validation_flags": [],
                    "quality_status": "ok",
                    "is_primary": True,
                    "extensions": {
                        "metric_governance": {
                            "registry_status": "provisional",
                            "metric_namespace": "custom",
                            "review_required": True,
                            "auto_analysis_allowed": False,
                            "governance_reason": "provisional_custom_metric",
                        }
                    },
                }
            ],
            "derived_facts": [],
            "validation_report": {
                "overall_status": "review_required",
                "canonical_fact_count": 1,
                "derived_fact_count": 0,
                "issues": ("provisional_metric_review_required",),
            },
            "review_packets": [],
        },
    )

    assert result["key_facts"] == []
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_report_adapter.py::test_report_adapter_excludes_non_auto_analysis_facts_from_key_facts -q
```

Expected: test fails because `_sanitize_fact()` currently drops `extensions`
before `_select_key_facts()` can inspect governance metadata.

- [ ] **Step 3: Inspect extensions before sanitizing public output**

Do not add `"extensions"` to `_KEY_FACT_FIELDS`. That field set is shared by
`_TTM_FACT_FIELDS`, so adding extensions there would leak internal governance
metadata into public `ttm_facts`.

Instead, modify `build_analysis_result()` so `key_facts` are selected from the
unsanitized canonical facts and sanitized only after selection:

```python
            "key_facts": self._select_key_facts(canonical_fact_items),
```

Keep the existing sanitized `canonical_facts` local variable for internal
consistency if other response fields need it later, but do not pass that
sanitized list into `_select_key_facts()`.

Then update `_select_key_facts()` so it strips extensions from selected public
facts:

```python
    @staticmethod
    def _select_key_facts(canonical_facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        consumable = [
            fact
            for fact in canonical_facts
            if fact.get("quality_status") in {None, "ok"}
            and not fact.get("validation_flags")
            and fact.get("entity_scope") not in {"unknown", "review_required"}
            and ReportAdapter._fact_allows_auto_analysis(fact)
        ]
        prioritized = [
            fact for fact in consumable if fact.get("metric_id") in _API_VISIBLE_METRICS
        ]
        remainder = [
            fact for fact in consumable if fact.get("metric_id") not in _API_VISIBLE_METRICS
        ]
        selected = [*prioritized, *remainder][:10]
        return [
            ReportAdapter._sanitize_fact(fact, allowed_fields=_KEY_FACT_FIELDS)
            for fact in selected
        ]
```

Add helper:

```python
    @staticmethod
    def _fact_allows_auto_analysis(fact: Mapping[str, Any]) -> bool:
        extensions = fact.get("extensions")
        if not isinstance(extensions, Mapping):
            return True
        governance = extensions.get("metric_governance")
        if not isinstance(governance, Mapping):
            return True
        return bool(governance.get("auto_analysis_allowed", True))
```

Add a regression assertion to
`test_report_adapter_excludes_non_auto_analysis_facts_from_key_facts()` or a
separate test to prove `ttm_facts` do not expose extensions:

```python
def test_report_adapter_does_not_expose_extensions_in_ttm_facts() -> None:
    result = ReportAdapter().build_analysis_result(
        document={"document_id": "doc-adapter"},
        pipeline_result={
            "canonical_fact_set_id": "fact-set-canonical",
            "derived_fact_set_id": "fact-set-derived",
            "validation_report_id": "validation-report",
            "quality_gate": "pass",
            "canonical_facts": [],
            "derived_facts": [
                {
                    "fact_id": "derived-revenue",
                    "metric_id": "revenue",
                    "metric_label_raw": "Revenue",
                    "statement_type": "income_statement",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "ttm::2025Q4",
                    "currency": "USD",
                    "raw_value": 100.0,
                    "numeric_value": 100.0,
                    "raw_unit": "US$ millions",
                    "normalized_unit": "USD",
                    "precision": 0,
                    "confidence": 0.9,
                    "validation_flags": [],
                    "quality_status": "ok",
                    "is_primary": True,
                    "derivation_type": "ttm",
                    "derivation_formula": "sum(last_4_quarters)",
                    "derivation_version": "v1",
                    "validation_status": "ok",
                    "consistency_check_against_fact_id": None,
                    "extensions": {
                        "metric_governance": {
                            "registry_status": "standard",
                            "metric_namespace": "standard",
                            "review_required": False,
                            "auto_analysis_allowed": True,
                            "governance_reason": "standard_metric",
                        }
                    },
                }
            ],
            "validation_report": {
                "overall_status": "ok",
                "canonical_fact_count": 0,
                "derived_fact_count": 1,
                "issues": (),
            },
            "review_packets": [],
        },
    )

    assert result["ttm_facts"]
    assert "extensions" not in result["ttm_facts"][0]
```

- [ ] **Step 4: Run focused test and key facts regressions**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_report_adapter.py::test_report_adapter_excludes_non_auto_analysis_facts_from_key_facts tests/unit/test_report_adapter.py::test_report_adapter_does_not_expose_extensions_in_ttm_facts -q
uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_promotes_table_semantic_candidates_to_canonical_facts -q
```

Expected: all tests pass. The API regression confirms standard facts still
appear in `key_facts`.

- [ ] **Step 5: Commit**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/adapters/report_adapter.py \
  financial-report-analysis/tests/unit/test_report_adapter.py
git commit -m "feat: exclude non-auto metrics from key facts"
```

## Task 6: Verify Derived Facts Stay Standard-Only

**Files:**

- Test: `financial-report-analysis/tests/unit/test_fact_pipeline.py`

- [ ] **Step 1: Add derived-fact guardrail test**

Append this test to `financial-report-analysis/tests/unit/test_fact_pipeline.py`:

```python
def test_provisional_custom_quarterly_candidates_do_not_produce_ttm_facts() -> None:
    candidate_payloads = []
    for quarter in range(1, 5):
        candidate_payloads.append(
            {
                "fact_id": f"candidate-custom-q{quarter}",
                "metric_id": "unknown",
                "metric_label_raw": "Customer loyalty liabilities",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "comparison_axis": "current",
                "adjustment_basis": "reported",
                "period_id": f"2025Q{quarter}",
                "currency": "USD",
                "raw_value": 100.0,
                "numeric_value": 100.0,
                "raw_unit": "US$ millions",
                "normalized_unit": None,
                "precision": 0,
                "confidence": 0.9,
                "extensions": {
                    "period_type": "DURATION",
                    "fiscal_year": 2025,
                    "reporting_scope": f"Q{quarter}",
                },
                "document_id": "doc-custom-ttm",
                "block_id": f"block-{quarter}",
                "page_index": quarter,
                "evidence_bundle_id": f"bundle-{quarter}",
                "extraction_method": "table_semantics",
                "source_rank_hint": 1,
            }
        )

    result = analyze_report(
        {"document_id": "doc-custom-ttm", "market": "HK", "language": "en"},
        {"candidate_facts": candidate_payloads},
    )

    assert result.canonical_facts == []
    assert result.derived_facts == []
    assert result.quality_gate == "review"
    assert "provisional_metric_review_required" in result.validation_report.issues
```

- [ ] **Step 2: Run test**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py::test_provisional_custom_quarterly_candidates_do_not_produce_ttm_facts -q
```

Expected: test passes after Task 3. If it fails, fix the Task 3 filter so no
provisional custom candidate reaches canonical promotion.

- [ ] **Step 3: Commit**

Run:

```bash
git add financial-report-analysis/tests/unit/test_fact_pipeline.py
git commit -m "test: cover provisional metric ttm guardrail"
```

## Task 7: Update Registry Boundary Documentation

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_registry.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- Modify: `docs/superpowers/specs/active/2026-04-25-financial-report-analysis-metric-governance-umbrella-design.md`

- [ ] **Step 1: Add module docstring to `metric_registry.py`**

Insert this module docstring below `from __future__ import annotations`:

```python
"""Metric identity resolution.

This module owns standard-vs-custom metric identity resolution. It can generate
stable provisional custom metric ids for unknown raw labels, but it does not own
deterministic table-semantics mapping or durable review lifecycle decisions.
"""
```

- [ ] **Step 2: Add module docstring to `metric_mapping.py`**

Insert this module docstring below `from __future__ import annotations`:

```python
"""Deterministic table-semantics-to-supported-metric mapping.

This module maps normalized table semantics to supported metric ids. It does not
generate provisional custom metric identities and does not store custom metric
review lifecycle decisions.
"""
```

- [ ] **Step 3: Mark Phase 1 plan linkage in umbrella spec**

In `docs/superpowers/specs/active/2026-04-25-financial-report-analysis-metric-governance-umbrella-design.md`, add this sentence under `## 14. Recommended Next Step`:

```markdown
The Phase 1 implementation plan is `docs/superpowers/plans/active/2026-04-25-financial-report-analysis-metric-governance-phase1-implementation-plan.md`.
```

- [ ] **Step 4: Run Ruff**

Run:

```bash
cd financial-report-analysis
uv run ruff check src/financial_report_analysis/registries/metric_registry.py src/financial_report_analysis/registries/metric_mapping.py
```

Expected: `All checks passed!`.

- [ ] **Step 5: Commit**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/registries/metric_registry.py \
  financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py \
  docs/superpowers/specs/active/2026-04-25-financial-report-analysis-metric-governance-umbrella-design.md
git commit -m "docs: clarify metric registry boundaries"
```

## Task 8: Final Verification

**Files:**

- No new files.

- [ ] **Step 1: Run focused unit tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_governance.py tests/unit/test_fact_pipeline.py tests/unit/test_report_adapter.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run targeted API regression**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_promotes_table_semantic_candidates_to_canonical_facts -q
```

Expected: test passes.

- [ ] **Step 3: Run lint**

Run:

```bash
cd financial-report-analysis
uv run ruff check src/financial_report_analysis/registries/metric_governance.py src/financial_report_analysis/registries/metric_registry.py src/financial_report_analysis/registries/metric_mapping.py src/financial_report_analysis/models/governance.py src/financial_report_analysis/services/fact_normalizer.py src/financial_report_analysis/services/conflict_resolver.py src/financial_report_analysis/services/validation_service.py src/financial_report_analysis/adapters/report_adapter.py tests/unit/test_metric_governance.py tests/unit/test_fact_pipeline.py tests/unit/test_report_adapter.py
```

Expected: `All checks passed!`.

- [ ] **Step 4: Inspect final diff**

Run:

```bash
git status --short
git diff --stat HEAD
```

Expected: only files from this plan are changed since the first Phase 1 commit.

- [ ] **Step 5: Final commit if needed**

If any verification-only fixes were needed, commit them:

```bash
git add financial-report-analysis/src/financial_report_analysis financial-report-analysis/tests docs/superpowers/specs/active/2026-04-25-financial-report-analysis-metric-governance-umbrella-design.md
git commit -m "test: verify metric governance phase1 guardrails"
```

## Self-Review

Spec coverage:

- Registry boundaries are covered by Tasks 1 and 7.
- Governance metadata propagation is covered by Task 2, including the important
  rule that deterministic supported mapped facts remain `standard` even when
  raw-label identity lookup would be provisional.
- Provisional custom blocking is covered by Tasks 3, 4, and 6, including the
  `ConflictState` model contract update.
- API key fact exclusion is covered by Task 5, including a TTM regression that
  prevents internal `extensions` leakage.
- Phase 1 reviewability is covered by Task 3 through review packets that expose
  `evidence_bundle_id`; richer raw-label/table-coordinate review surfaces remain
  Phase 2 scope.
- Durable lifecycle, approval workflow, and review APIs are intentionally out of
  Phase 1 and remain in the umbrella spec as later phases.

Placeholder scan:

- This plan contains no `TBD`, `TODO`, or unspecified implementation steps.

Type consistency:

- The plan consistently uses `extensions["metric_governance"]` as the metadata
  contract.
- The issue code is consistently `provisional_metric_review_required`.
- The guardrail helper names are consistently imported from
  `financial_report_analysis.registries.metric_governance`.
