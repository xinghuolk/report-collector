# P4A Parent Scope Notes Conflict Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the P4A governance contract for parent/consolidated scope, note/disclosure source policy, conflict review packets, and quality-gate blocking before P4B field expansion.

**Architecture:** Add a small governance model that classifies source kind and policy from candidate metadata, then teach conflict resolution to apply policy before canonical promotion. Keep the existing extract API shape stable by exposing P4A review details inside `analysis_snapshot` and validation issues, not by adding a large review API.

**Tech Stack:** Python 3.11, dataclasses, pytest, existing `financial_report_analysis` models/services/adapters.

---

## File Structure

- Modify: `financial-report-analysis/src/financial_report_analysis/models/facts.py`
  - Expand `EntityScope` support to include `parent_company`, `unknown`, and `review_required`.
  - Keep legacy `parent` accepted only as an input compatibility value until call sites migrate.
- Create: `financial-report-analysis/src/financial_report_analysis/models/governance.py`
  - Define `SourceKind`, `SourcePolicy`, `ConflictState`, `ReviewPacket`, and helper functions that derive source metadata from a `CandidateFact`.
- Modify: `financial-report-analysis/src/financial_report_analysis/models/__init__.py`
  - Export the governance dataclasses and helper types.
- Modify: `financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py`
  - Emit `entity_scope="parent_company"` for `parent_only` tables and `entity_scope="unknown"` for ambiguous tables.
  - Add `source_kind` and `source_policy` extensions for table-derived candidates.
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`
  - Tighten scope guessing so `owners of the parent` does not imply parent-company scope.
  - Recognize `company statement` and `separate statement` as parent-company table scope.
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
  - Add `source_kind="deterministic_note_disclosure"` and default `source_policy="supplement_only"` to note candidates.
- Modify: `financial-report-analysis/src/financial_report_analysis/services/conflict_resolver.py`
  - Add `ConflictResolutionResult`.
  - Add `resolve_with_review()` while preserving `resolve()` as a compatibility wrapper.
  - Apply supplement, override, review, and blocked policy outcomes.
- Modify: `financial-report-analysis/src/financial_report_analysis/pipeline.py`
  - Carry `review_packets` through `PipelineResult`.
- Modify: `financial-report-analysis/src/financial_report_analysis/services/validation_service.py`
  - Accept review packets and add validation issues for `source_conflict`, `scope_conflict`, and `blocked`.
- Modify: `financial-report-analysis/src/financial_report_analysis/adapters/report_adapter.py`
  - Expose review packets under `analysis_snapshot["review_packets"]`.
  - Exclude review/blocked/scope-conflict facts from `key_facts`.
- Tests:
  - Modify `financial-report-analysis/tests/unit/test_models.py`
  - Modify `financial-report-analysis/tests/unit/test_table_fact_builder.py`
  - Modify `financial-report-analysis/tests/unit/test_table_structure.py`
  - Modify `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`
  - Modify `financial-report-analysis/tests/unit/test_fact_pipeline.py`
  - Modify `financial-report-analysis/tests/unit/test_report_adapter.py`

## Task 1: Entity Scope Contract

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/models/facts.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`
- Test: `financial-report-analysis/tests/unit/test_models.py`
- Test: `financial-report-analysis/tests/unit/test_table_fact_builder.py`
- Test: `financial-report-analysis/tests/unit/test_table_structure.py`

- [ ] **Step 1: Write failing scope model tests**

Append these tests to `financial-report-analysis/tests/unit/test_models.py`:

```python
def test_fact_accepts_p4a_entity_scope_values() -> None:
    for entity_scope in ("parent_company", "unknown", "review_required"):
        fact = CanonicalFact(
            fact_id=f"canonical::{entity_scope}",
            metric_id="cash",
            metric_label_raw="Cash",
            statement_type="balance_sheet",
            entity_scope=entity_scope,
            comparison_axis="current",
            adjustment_basis="reported",
            period_id="2025FY",
            currency="HKD",
            raw_value="100",
            numeric_value=100.0,
            raw_unit=None,
            normalized_unit=None,
            precision=0,
            confidence=0.9,
            source_candidate_fact_ids=[f"candidate::{entity_scope}"],
            evidence_bundle_id=f"bundle::{entity_scope}",
        )

        assert fact.entity_scope == entity_scope


def test_canonical_fact_business_key_distinguishes_parent_company_scope() -> None:
    fact = CanonicalFact(
        fact_id="canonical::parent-cash",
        metric_id="cash",
        metric_label_raw="Cash",
        statement_type="balance_sheet",
        entity_scope="parent_company",
        comparison_axis="current",
        adjustment_basis="reported",
        period_id="2025FY",
        currency="HKD",
        raw_value="100",
        numeric_value=100.0,
        raw_unit=None,
        normalized_unit=None,
        precision=0,
        confidence=0.9,
        source_candidate_fact_ids=["candidate::parent-cash"],
        evidence_bundle_id="bundle::parent-cash",
    )

    assert fact.business_key == "cash|2025FY|parent_company|current|reported|HKD"
```

- [ ] **Step 2: Write failing table scope tests**

Append these tests to `financial-report-analysis/tests/unit/test_table_structure.py`:

```python
from financial_report_analysis.ingestion.table_structure import PdfTableStructureAdapter


def test_statement_scope_does_not_treat_owners_of_parent_label_as_parent_company() -> None:
    scope = PdfTableStructureAdapter._guess_statement_scope(
        title_text="Consolidated Statement of Profit or Loss",
        local_context="Profit attributable to owners of the parent 100 90",
    )

    assert scope == "consolidated"


def test_statement_scope_detects_separate_company_statement_as_parent_company() -> None:
    scope = PdfTableStructureAdapter._guess_statement_scope(
        title_text="Company Statement of Financial Position",
        local_context="Company Statement of Financial Position\nCash 100 90",
    )

    assert scope == "parent_only"


def test_statement_scope_detects_separate_statement_as_parent_company() -> None:
    scope = PdfTableStructureAdapter._guess_statement_scope(
        title_text="Separate Statement of Financial Position",
        local_context="Separate Statement of Financial Position\nCash 100 90",
    )

    assert scope == "parent_only"
```

Append this complete test to `financial-report-analysis/tests/unit/test_table_fact_builder.py`:

```python
def test_table_fact_builder_maps_parent_only_scope_to_parent_company() -> None:
    table = NormalizedTableSemantics(
        table_id="table-parent",
        document_id="doc-parent",
        page_range=(1, 1),
        table_kind="balance_sheet",
        title_text="Company Statement of Financial Position",
        statement_scope_guess="parent_only",
        table_unit="ones",
        table_currency="HKD",
        columns=[
            NormalizedTableColumn(
                column_id="col-2025",
                header_text="2025",
                period_id="2025FY",
                comparison_axis="current",
                value_time_shape="point",
                is_current=True,
                is_comparison=False,
            )
        ],
        rows=[
            NormalizedTableRow(
                row_id="row-cash",
                label_raw="Cash",
                normalized_row_label="cash",
                values=[
                    NormalizedTableCellValue(
                        raw_text="100",
                        numeric_value=100.0,
                        period_id="2025FY",
                        comparison_axis="current",
                        value_time_shape="point",
                        row_index=1,
                        column_index=1,
                    )
                ],
            )
        ],
    )

    candidates = build_table_candidate_facts(
        [table],
        registry=load_metric_registry(),
        document_id="doc-parent",
        market="HK",
    )

    assert candidates[0]["entity_scope"] == "parent_company"
    assert candidates[0]["extensions"]["statement_scope_guess"] == "parent_only"
```

- [ ] **Step 3: Run scope tests and confirm failure**

Run from `financial-report-analysis/`:

```bash
uv run pytest tests/unit/test_models.py::test_fact_accepts_p4a_entity_scope_values tests/unit/test_models.py::test_canonical_fact_business_key_distinguishes_parent_company_scope tests/unit/test_table_structure.py::test_statement_scope_does_not_treat_owners_of_parent_label_as_parent_company tests/unit/test_table_structure.py::test_statement_scope_detects_separate_company_statement_as_parent_company tests/unit/test_table_structure.py::test_statement_scope_detects_separate_statement_as_parent_company tests/unit/test_table_fact_builder.py::test_table_fact_builder_maps_parent_only_scope_to_parent_company -q
```

Expected: failures for unsupported `entity_scope`, missing scope detection, or parent-only output still being `parent`.

- [ ] **Step 4: Implement entity scope values**

In `financial-report-analysis/src/financial_report_analysis/models/facts.py`, replace the `EntityScope` literal and `_ENTITY_SCOPES` set with:

```python
EntityScope = Literal[
    "consolidated",
    "parent_company",
    "unknown",
    "review_required",
    "parent",
    "segment",
    "other",
]
```

```python
_ENTITY_SCOPES = {
    "consolidated",
    "parent_company",
    "unknown",
    "review_required",
    "parent",
    "segment",
    "other",
}
```

Keeping `parent`, `segment`, and `other` accepted avoids breaking older serialized payloads during P4A. New production paths should emit `parent_company`, `consolidated`, or `unknown`.

- [ ] **Step 5: Implement table scope detection**

In `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`, replace `_guess_statement_scope()` with:

```python
    @staticmethod
    def _guess_statement_scope(*, title_text: str, local_context: str) -> str:
        haystack = f"{title_text}\n{local_context}".casefold()
        if "consolidated" in haystack or "合并" in haystack:
            return "consolidated"
        parent_scope_patterns = (
            r"\bparent\s+company\s+statement\b",
            r"\bcompany\s+statement\b",
            r"\bseparate\s+statement\b",
            r"\bstatement\s+of\s+financial\s+position\s+of\s+the\s+company\b",
            r"母公司",
        )
        if any(re.search(pattern, haystack, re.IGNORECASE) for pattern in parent_scope_patterns):
            return "parent_only"
        return "unknown"
```

The `consolidated` check remains first so a consolidated statement containing `owners of the parent` stays consolidated.

- [ ] **Step 6: Implement table fact parent-company output**

In `financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py`, replace `_entity_scope()` with:

```python
def _entity_scope(statement_scope_guess: str) -> str:
    if statement_scope_guess == "parent_only":
        return "parent_company"
    if statement_scope_guess == "consolidated":
        return "consolidated"
    return "unknown"
```

- [ ] **Step 7: Run scope tests and commit**

Run:

```bash
uv run pytest tests/unit/test_models.py tests/unit/test_table_structure.py tests/unit/test_table_fact_builder.py -q
```

Expected: all selected tests pass.

Commit:

```bash
git add src/financial_report_analysis/models/facts.py src/financial_report_analysis/ingestion/table_structure.py src/financial_report_analysis/services/table_fact_builder.py tests/unit/test_models.py tests/unit/test_table_structure.py tests/unit/test_table_fact_builder.py
git commit -m "feat: add P4A entity scope contract"
```

## Task 2: Governance Model

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/models/governance.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/models/__init__.py`
- Test: `financial-report-analysis/tests/unit/test_models.py`

- [ ] **Step 1: Write failing governance model tests**

Append these tests to `financial-report-analysis/tests/unit/test_models.py`:

```python
from financial_report_analysis.models.governance import (
    ReviewPacket,
    candidate_source_kind,
    candidate_source_policy,
)


def test_candidate_source_kind_detects_statement_note_and_locator_sources() -> None:
    statement = _candidate_fact(
        fact_id="candidate-statement",
        metric_id="cash",
        source_rank_hint=30,
        extraction_method="table_semantics",
        extensions={"table_kind": "balance_sheet", "semantic_source": "deterministic"},
    )
    note = _candidate_fact(
        fact_id="candidate-note",
        metric_id="cash",
        source_rank_hint=18,
        extraction_method="note_disclosure",
        extensions={"table_kind": "note_disclosure", "semantic_source": "deterministic"},
    )
    locator = _candidate_fact(
        fact_id="candidate-locator",
        metric_id="cash",
        source_rank_hint=18,
        extraction_method="note_disclosure",
        extensions={"table_kind": "note_disclosure", "semantic_source": "llm_fallback"},
    )

    assert candidate_source_kind(statement) == "statement_row"
    assert candidate_source_kind(note) == "deterministic_note_disclosure"
    assert candidate_source_kind(locator) == "llm_locator_assisted_note_disclosure"


def test_candidate_source_policy_defaults_to_supplement_only() -> None:
    candidate = _candidate_fact(
        fact_id="candidate-note",
        metric_id="cash",
        source_rank_hint=18,
        extraction_method="note_disclosure",
        extensions={"table_kind": "note_disclosure"},
    )

    assert candidate_source_policy(candidate) == "supplement_only"


def test_review_packet_serializes_minimum_p4a_surface() -> None:
    packet = ReviewPacket(
        document_id="doc-1",
        period_id="2025FY",
        metric_id="cash",
        entity_scope="parent_company",
        source_kind="deterministic_note_disclosure",
        source_policy="review_required",
        conflict_state="source_conflict",
        candidate_value=100.0,
        competing_candidate_values=(90.0,),
        evidence_bundle_id="bundle-1",
        resolution_reason="note_disclosure_requires_explicit_override_policy",
        review_reason="source_conflict",
    )

    assert packet.to_dict() == {
        "document_id": "doc-1",
        "period_id": "2025FY",
        "metric_id": "cash",
        "entity_scope": "parent_company",
        "source_kind": "deterministic_note_disclosure",
        "source_policy": "review_required",
        "conflict_state": "source_conflict",
        "candidate_value": 100.0,
        "competing_candidate_values": [90.0],
        "evidence_bundle_id": "bundle-1",
        "resolution_reason": "note_disclosure_requires_explicit_override_policy",
        "review_reason": "source_conflict",
    }
```

Use the existing `_candidate_fact()` helper in `test_fact_pipeline.py` as a reference. If `test_models.py` has no helper, add a local helper named `_candidate_fact` above these tests:

```python
def _candidate_fact(
    *,
    fact_id: str,
    metric_id: str,
    source_rank_hint: int | None,
    extraction_method: str | None,
    extensions: dict[str, object],
) -> CandidateFact:
    return CandidateFact(
        fact_id=fact_id,
        metric_id=metric_id,
        metric_label_raw=metric_id,
        statement_type="balance_sheet",
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        period_id="2025FY",
        currency="HKD",
        raw_value="100",
        numeric_value=100.0,
        raw_unit=None,
        normalized_unit=None,
        precision=0,
        confidence=0.9,
        document_id="doc-1",
        block_id=f"{fact_id}:block",
        page_index=1,
        evidence_bundle_id=f"{fact_id}:bundle",
        extraction_method=extraction_method,
        source_rank_hint=source_rank_hint,
        extensions=extensions,
    )
```

- [ ] **Step 2: Run governance tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_models.py::test_candidate_source_kind_detects_statement_note_and_locator_sources tests/unit/test_models.py::test_candidate_source_policy_defaults_to_supplement_only tests/unit/test_models.py::test_review_packet_serializes_minimum_p4a_surface -q
```

Expected: import failure for `financial_report_analysis.models.governance`.

- [ ] **Step 3: Implement governance model**

Create `financial-report-analysis/src/financial_report_analysis/models/governance.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from financial_report_analysis.models.facts import CandidateFact

SourceKind = Literal[
    "statement_row",
    "deterministic_note_disclosure",
    "llm_locator_assisted_note_disclosure",
    "summary_table",
    "derived",
]
SourcePolicy = Literal[
    "supplement_only",
    "override_allowed",
    "review_required",
    "blocked",
]
ConflictState = Literal[
    "none",
    "scope_not_surfaced",
    "scope_conflict",
    "source_conflict",
    "review_required",
    "blocked",
]

_SOURCE_KINDS = {
    "statement_row",
    "deterministic_note_disclosure",
    "llm_locator_assisted_note_disclosure",
    "summary_table",
    "derived",
}
_SOURCE_POLICIES = {
    "supplement_only",
    "override_allowed",
    "review_required",
    "blocked",
}


@dataclass(frozen=True, slots=True)
class ReviewPacket:
    document_id: str
    period_id: str
    metric_id: str
    entity_scope: str
    source_kind: SourceKind
    source_policy: SourcePolicy
    conflict_state: ConflictState
    candidate_value: float | int | None
    competing_candidate_values: tuple[float | int | None, ...]
    evidence_bundle_id: str | None
    resolution_reason: str
    review_reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "document_id": self.document_id,
            "period_id": self.period_id,
            "metric_id": self.metric_id,
            "entity_scope": self.entity_scope,
            "source_kind": self.source_kind,
            "source_policy": self.source_policy,
            "conflict_state": self.conflict_state,
            "candidate_value": self.candidate_value,
            "competing_candidate_values": list(self.competing_candidate_values),
            "evidence_bundle_id": self.evidence_bundle_id,
            "resolution_reason": self.resolution_reason,
            "review_reason": self.review_reason,
        }


def candidate_source_kind(candidate: CandidateFact) -> SourceKind:
    configured = candidate.extensions.get("source_kind")
    if isinstance(configured, str) and configured in _SOURCE_KINDS:
        return configured  # type: ignore[return-value]

    table_kind = str(candidate.extensions.get("table_kind") or "")
    semantic_source = str(candidate.extensions.get("semantic_source") or "")
    if candidate.extraction_method == "note_disclosure" or table_kind == "note_disclosure":
        if semantic_source == "llm_fallback":
            return "llm_locator_assisted_note_disclosure"
        return "deterministic_note_disclosure"
    if table_kind in {"key_metrics", "metrics", "summary_table"}:
        return "summary_table"
    return "statement_row"


def candidate_source_policy(candidate: CandidateFact) -> SourcePolicy:
    configured = candidate.extensions.get("source_policy")
    if isinstance(configured, str) and configured in _SOURCE_POLICIES:
        return configured  # type: ignore[return-value]
    return "supplement_only"
```

- [ ] **Step 4: Export governance model**

In `financial-report-analysis/src/financial_report_analysis/models/__init__.py`, add imports:

```python
from financial_report_analysis.models.governance import (
    ConflictState,
    ReviewPacket,
    SourceKind,
    SourcePolicy,
    candidate_source_kind,
    candidate_source_policy,
)
```

Add these names to `__all__`:

```python
    "ConflictState",
    "ReviewPacket",
    "SourceKind",
    "SourcePolicy",
    "candidate_source_kind",
    "candidate_source_policy",
```

- [ ] **Step 5: Run governance tests and commit**

Run:

```bash
uv run pytest tests/unit/test_models.py -q
```

Expected: all `test_models.py` tests pass.

Commit:

```bash
git add src/financial_report_analysis/models/governance.py src/financial_report_analysis/models/__init__.py tests/unit/test_models.py
git commit -m "feat: add P4A governance model"
```

## Task 3: Source Policy Conflict Resolution

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/services/conflict_resolver.py`
- Test: `financial-report-analysis/tests/unit/test_fact_pipeline.py`

- [ ] **Step 1: Write failing resolver policy tests**

Append these tests to `financial-report-analysis/tests/unit/test_fact_pipeline.py`:

```python
def test_conflict_resolver_preserves_statement_row_when_note_is_supplement_only() -> None:
    resolver = ConflictResolver()
    normalized = [
        _candidate_fact(
            fact_id="candidate-statement",
            metric_id="cash",
            numeric_value=100.0,
            source_rank_hint=30,
            extraction_method="table_semantics",
            extensions={
                "table_kind": "balance_sheet",
                "source_kind": "statement_row",
                "source_policy": "supplement_only",
            },
        ),
        _candidate_fact(
            fact_id="candidate-note",
            metric_id="cash",
            numeric_value=120.0,
            source_rank_hint=18,
            extraction_method="note_disclosure",
            extensions={
                "table_kind": "note_disclosure",
                "source_kind": "deterministic_note_disclosure",
                "source_policy": "supplement_only",
            },
        ),
    ]

    result = resolver.resolve_with_review(normalized)

    assert len(result.canonical_facts) == 1
    assert result.canonical_facts[0].numeric_value == 100.0
    assert result.canonical_facts[0].resolution_reason == "source_policy_supplement_only"
    assert result.review_packets == []


def test_conflict_resolver_allows_explicit_note_override() -> None:
    resolver = ConflictResolver()
    normalized = [
        _candidate_fact(
            fact_id="candidate-statement",
            metric_id="restricted_cash",
            numeric_value=100.0,
            source_rank_hint=30,
            extraction_method="table_semantics",
            extensions={
                "table_kind": "balance_sheet",
                "source_kind": "statement_row",
                "source_policy": "supplement_only",
            },
        ),
        _candidate_fact(
            fact_id="candidate-note",
            metric_id="restricted_cash",
            numeric_value=120.0,
            source_rank_hint=18,
            extraction_method="note_disclosure",
            extensions={
                "table_kind": "note_disclosure",
                "source_kind": "deterministic_note_disclosure",
                "source_policy": "override_allowed",
            },
        ),
    ]

    result = resolver.resolve_with_review(normalized)

    assert result.canonical_facts[0].numeric_value == 120.0
    assert result.canonical_facts[0].resolution_reason == "source_policy_override_allowed"
    assert result.canonical_facts[0].validation_flags == []
    assert result.review_packets == []


def test_conflict_resolver_emits_review_packet_for_review_required_source_conflict() -> None:
    resolver = ConflictResolver()
    normalized = [
        _candidate_fact(
            fact_id="candidate-statement",
            metric_id="cash",
            numeric_value=100.0,
            source_rank_hint=30,
            extraction_method="table_semantics",
            extensions={
                "table_kind": "balance_sheet",
                "source_kind": "statement_row",
                "source_policy": "supplement_only",
            },
        ),
        _candidate_fact(
            fact_id="candidate-note",
            metric_id="cash",
            numeric_value=120.0,
            source_rank_hint=18,
            extraction_method="note_disclosure",
            extensions={
                "table_kind": "note_disclosure",
                "source_kind": "deterministic_note_disclosure",
                "source_policy": "review_required",
            },
        ),
    ]

    result = resolver.resolve_with_review(normalized)

    assert result.canonical_facts[0].numeric_value == 100.0
    assert result.canonical_facts[0].validation_flags == ["source_conflict_review_required"]
    assert len(result.review_packets) == 1
    assert result.review_packets[0].to_dict()["conflict_state"] == "source_conflict"
    assert result.review_packets[0].to_dict()["candidate_value"] == 120.0
    assert result.review_packets[0].to_dict()["competing_candidate_values"] == [100.0]


def test_conflict_resolver_blocks_blocked_policy_candidate() -> None:
    resolver = ConflictResolver()
    normalized = [
        _candidate_fact(
            fact_id="candidate-statement",
            metric_id="cash",
            numeric_value=100.0,
            source_rank_hint=30,
            extraction_method="table_semantics",
            extensions={
                "table_kind": "balance_sheet",
                "source_kind": "statement_row",
                "source_policy": "supplement_only",
            },
        ),
        _candidate_fact(
            fact_id="candidate-note",
            metric_id="cash",
            numeric_value=120.0,
            source_rank_hint=18,
            extraction_method="note_disclosure",
            extensions={
                "table_kind": "note_disclosure",
                "source_kind": "deterministic_note_disclosure",
                "source_policy": "blocked",
            },
        ),
    ]

    result = resolver.resolve_with_review(normalized)

    assert result.canonical_facts[0].numeric_value == 100.0
    assert result.canonical_facts[0].validation_flags == ["blocked_competing_candidate"]
    assert len(result.review_packets) == 1
    assert result.review_packets[0].to_dict()["conflict_state"] == "blocked"
```

If `_candidate_fact()` in this file does not accept `extraction_method` or `extensions`, extend the helper signature and defaults so existing tests keep passing:

```python
def _candidate_fact(
    *,
    fact_id: str,
    metric_id: str,
    numeric_value: float,
    source_rank_hint: int | None,
    extraction_method: str | None = "table_semantics",
    extensions: dict[str, object] | None = None,
    entity_scope: str = "consolidated",
    statement_scope_guess: str = "consolidated",
) -> CandidateFact:
    resolved_extensions = {
        "table_kind": "balance_sheet",
        "semantic_source": "deterministic",
        "statement_scope_guess": statement_scope_guess,
    }
    if extensions:
        resolved_extensions.update(extensions)
    return CandidateFact(
        fact_id=fact_id,
        metric_id=metric_id,
        metric_label_raw=metric_id,
        statement_type="balance_sheet",
        entity_scope=entity_scope,
        comparison_axis="current",
        adjustment_basis="reported",
        period_id="2025FY",
        currency="HKD",
        raw_value=str(numeric_value),
        numeric_value=numeric_value,
        raw_unit=None,
        normalized_unit=None,
        precision=0,
        confidence=0.9,
        document_id="doc-1",
        block_id=f"{fact_id}:block",
        page_index=1,
        evidence_bundle_id=f"{fact_id}:bundle",
        extraction_method=extraction_method,
        source_rank_hint=source_rank_hint,
        extensions=resolved_extensions,
    )
```

- [ ] **Step 2: Run resolver tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_fact_pipeline.py::test_conflict_resolver_preserves_statement_row_when_note_is_supplement_only tests/unit/test_fact_pipeline.py::test_conflict_resolver_allows_explicit_note_override tests/unit/test_fact_pipeline.py::test_conflict_resolver_emits_review_packet_for_review_required_source_conflict tests/unit/test_fact_pipeline.py::test_conflict_resolver_blocks_blocked_policy_candidate -q
```

Expected: `ConflictResolver` has no `resolve_with_review`, or policy assertions fail.

- [ ] **Step 3: Implement conflict resolution result and policy-aware resolution**

In `financial-report-analysis/src/financial_report_analysis/services/conflict_resolver.py`, add imports:

```python
from dataclasses import dataclass
from financial_report_analysis.models.governance import (
    ReviewPacket,
    candidate_source_kind,
    candidate_source_policy,
)
```

Add this dataclass above `ConflictResolver`:

```python
@dataclass(frozen=True, slots=True)
class ConflictResolutionResult:
    canonical_facts: list[CanonicalFact]
    review_packets: list[ReviewPacket]
```

Replace `resolve()` and add `resolve_with_review()`:

```python
class ConflictResolver:
    def resolve(
        self,
        normalized_candidates: Iterable[CandidateFact],
    ) -> list[CanonicalFact]:
        return self.resolve_with_review(normalized_candidates).canonical_facts

    def resolve_with_review(
        self,
        normalized_candidates: Iterable[CandidateFact],
    ) -> ConflictResolutionResult:
        grouped_candidates: dict[tuple[str, str, str, str, str, str], list[CandidateFact]] = (
            defaultdict(list)
        )
        for candidate in normalized_candidates:
            grouped_candidates[self._business_key(candidate)].append(candidate)

        canonical_facts: list[CanonicalFact] = []
        review_packets: list[ReviewPacket] = []
        for business_key in sorted(grouped_candidates):
            candidates = grouped_candidates[business_key]
            winner, reason, validation_flags, packets = self._resolve_group(candidates)
            review_packets.extend(packets)
            canonical_facts.append(
                CanonicalFact(
                    fact_id=f"canonical::{winner.fact_id}",
                    metric_id=winner.metric_id,
                    metric_label_raw=winner.metric_label_raw,
                    statement_type=winner.statement_type,
                    entity_scope=winner.entity_scope,
                    comparison_axis=winner.comparison_axis,
                    adjustment_basis=winner.adjustment_basis,
                    period_id=winner.period_id,
                    currency=winner.currency,
                    raw_value=winner.raw_value,
                    numeric_value=winner.numeric_value,
                    raw_unit=winner.raw_unit,
                    normalized_unit=winner.normalized_unit,
                    precision=winner.precision,
                    confidence=winner.confidence,
                    extensions=dict(winner.extensions),
                    source_candidate_fact_ids=[candidate.fact_id for candidate in candidates],
                    resolution_reason=reason,
                    resolution_score=self._resolution_score(winner),
                    validation_flags=validation_flags,
                    quality_status="review" if validation_flags else "ok",
                    is_primary=not validation_flags,
                    evidence_bundle_id=winner.evidence_bundle_id,
                )
            )
        return ConflictResolutionResult(
            canonical_facts=canonical_facts,
            review_packets=review_packets,
        )
```

Add `_resolve_group()` and `_review_packet()` inside `ConflictResolver`:

```python
    def _resolve_group(
        self,
        candidates: list[CandidateFact],
    ) -> tuple[CandidateFact, str, list[str], list[ReviewPacket]]:
        blocked = [
            candidate
            for candidate in candidates
            if candidate_source_policy(candidate) == "blocked"
        ]
        active = [candidate for candidate in candidates if candidate not in blocked]
        if not active:
            blocked_winner = max(blocked, key=self._priority_key)
            return (
                blocked_winner,
                "source_policy_blocked",
                ["blocked_candidate"],
                [self._review_packet(blocked_winner, [], "blocked", "source_policy_blocked")],
            )

        review_required = [
            candidate
            for candidate in active
            if candidate_source_policy(candidate) == "review_required"
        ]
        override_candidates = [
            candidate
            for candidate in active
            if candidate_source_policy(candidate) == "override_allowed"
        ]
        statement_candidates = [
            candidate
            for candidate in active
            if candidate_source_kind(candidate) == "statement_row"
        ]

        packets = [
            self._review_packet(candidate, [other for other in candidates if other != candidate], "blocked", "source_policy_blocked")
            for candidate in blocked
        ]

        if review_required:
            winner_pool = statement_candidates or [
                candidate
                for candidate in active
                if candidate not in review_required
            ]
            winner = max(winner_pool or active, key=self._priority_key)
            packets.extend(
                self._review_packet(
                    candidate,
                    [other for other in active if other != candidate],
                    "source_conflict",
                    "source_policy_review_required",
                )
                for candidate in review_required
            )
            flags = ["source_conflict_review_required"]
            if blocked:
                flags.append("blocked_competing_candidate")
            return winner, "source_policy_review_required", flags, packets

        if override_candidates:
            winner = max(override_candidates, key=self._priority_key)
            flags = ["blocked_competing_candidate"] if blocked else []
            return winner, "source_policy_override_allowed", flags, packets

        if statement_candidates:
            winner = max(statement_candidates, key=self._priority_key)
            flags = ["blocked_competing_candidate"] if blocked else []
            return winner, "source_policy_supplement_only", flags, packets

        winner = max(active, key=self._priority_key)
        flags = ["blocked_competing_candidate"] if blocked else []
        return winner, "highest_source_rank", flags, packets

    @staticmethod
    def _review_packet(
        candidate: CandidateFact,
        competing_candidates: list[CandidateFact],
        conflict_state: str,
        review_reason: str,
    ) -> ReviewPacket:
        return ReviewPacket(
            document_id=candidate.document_id,
            period_id=candidate.period_id,
            metric_id=candidate.metric_id,
            entity_scope=candidate.entity_scope,
            source_kind=candidate_source_kind(candidate),
            source_policy=candidate_source_policy(candidate),
            conflict_state=conflict_state,  # type: ignore[arg-type]
            candidate_value=candidate.numeric_value,
            competing_candidate_values=tuple(
                competing.numeric_value for competing in competing_candidates
            ),
            evidence_bundle_id=candidate.evidence_bundle_id,
            resolution_reason=review_reason,
            review_reason=conflict_state,
        )
```

Run Ruff formatting for touched Python files after implementation:

```bash
uv run ruff format src/financial_report_analysis/services/conflict_resolver.py tests/unit/test_fact_pipeline.py
```

- [ ] **Step 4: Run resolver tests and commit**

Run:

```bash
uv run pytest tests/unit/test_fact_pipeline.py::test_conflict_resolver_keeps_highest_priority_candidate tests/unit/test_fact_pipeline.py::test_conflict_resolver_preserves_statement_row_when_note_is_supplement_only tests/unit/test_fact_pipeline.py::test_conflict_resolver_allows_explicit_note_override tests/unit/test_fact_pipeline.py::test_conflict_resolver_emits_review_packet_for_review_required_source_conflict tests/unit/test_fact_pipeline.py::test_conflict_resolver_blocks_blocked_policy_candidate -q
```

Expected: all selected resolver tests pass.

Commit:

```bash
git add src/financial_report_analysis/services/conflict_resolver.py tests/unit/test_fact_pipeline.py
git commit -m "feat: apply P4A source conflict policy"
```

## Task 4: Pipeline Validation And Review Surface

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/pipeline.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/services/validation_service.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/adapters/report_adapter.py`
- Test: `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- Test: `financial-report-analysis/tests/unit/test_report_adapter.py`

- [ ] **Step 1: Write failing pipeline and adapter tests**

Append this test to `financial-report-analysis/tests/unit/test_fact_pipeline.py`:

```python
def test_pipeline_carries_p4a_review_packets_and_sets_review_quality_gate() -> None:
    result = analyze_report(
        document_ref={"document_id": "doc-p4a", "market": "HK", "language": "en"},
        extracted_payload={
            "candidate_facts": [
                {
                    "fact_id": "candidate-statement",
                    "metric_id": "cash",
                    "metric_label_raw": "Cash",
                    "statement_type": "balance_sheet",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "HKD",
                    "raw_value": "100",
                    "numeric_value": 100.0,
                    "raw_unit": None,
                    "normalized_unit": None,
                    "precision": 0,
                    "confidence": 0.9,
                    "document_id": "doc-p4a",
                    "block_id": "statement:block",
                    "page_index": 1,
                    "evidence_bundle_id": "bundle-statement",
                    "extraction_method": "table_semantics",
                    "source_rank_hint": 30,
                    "extensions": {
                        "table_kind": "balance_sheet",
                        "source_kind": "statement_row",
                        "source_policy": "supplement_only",
                    },
                },
                {
                    "fact_id": "candidate-note",
                    "metric_id": "cash",
                    "metric_label_raw": "Cash note",
                    "statement_type": "balance_sheet",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "HKD",
                    "raw_value": "120",
                    "numeric_value": 120.0,
                    "raw_unit": None,
                    "normalized_unit": None,
                    "precision": 0,
                    "confidence": 0.9,
                    "document_id": "doc-p4a",
                    "block_id": "note:block",
                    "page_index": 20,
                    "evidence_bundle_id": "bundle-note",
                    "extraction_method": "note_disclosure",
                    "source_rank_hint": 18,
                    "extensions": {
                        "table_kind": "note_disclosure",
                        "source_kind": "deterministic_note_disclosure",
                        "source_policy": "review_required",
                    },
                },
            ]
        },
    )

    assert result.quality_gate == "review"
    assert result.validation_report.issues == ("source_conflict",)
    assert len(result.review_packets) == 1
    assert result.review_packets[0].to_dict()["metric_id"] == "cash"
```

Append this test to `financial-report-analysis/tests/unit/test_report_adapter.py`:

```python
def test_report_adapter_exposes_p4a_review_packets_and_excludes_review_facts_from_key_facts() -> None:
    adapter = ReportAdapter()
    result = adapter.build_analysis_result(
        document={"document_id": "doc-p4a", "market": "HK"},
        pipeline_result={
            "canonical_fact_set_id": "doc-p4a:canonical:v1",
            "derived_fact_set_id": "doc-p4a:derived:v1",
            "validation_report_id": "doc-p4a:validation:v1",
            "quality_gate": "review",
            "canonical_facts": [
                {
                    "metric_id": "cash",
                    "numeric_value": 100.0,
                    "quality_status": "review",
                    "validation_flags": ["source_conflict_review_required"],
                },
                {
                    "metric_id": "revenue",
                    "numeric_value": 200.0,
                    "quality_status": "ok",
                    "validation_flags": [],
                },
            ],
            "derived_facts": [],
            "validation_report": {
                "overall_status": "review_required",
                "issues": ["source_conflict"],
            },
            "review_packets": [
                {
                    "document_id": "doc-p4a",
                    "period_id": "2025FY",
                    "metric_id": "cash",
                    "entity_scope": "consolidated",
                    "source_kind": "deterministic_note_disclosure",
                    "source_policy": "review_required",
                    "conflict_state": "source_conflict",
                    "candidate_value": 120.0,
                    "competing_candidate_values": [100.0],
                    "evidence_bundle_id": "bundle-note",
                    "resolution_reason": "source_policy_review_required",
                    "review_reason": "source_conflict",
                }
            ],
        },
    )

    assert result["quality_gate"] == "review"
    assert result["key_facts"] == [
        {"metric_id": "revenue", "numeric_value": 200.0, "quality_status": "ok", "validation_flags": []}
    ]
    assert result["analysis_snapshot"]["review_packets"][0]["metric_id"] == "cash"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_fact_pipeline.py::test_pipeline_carries_p4a_review_packets_and_sets_review_quality_gate tests/unit/test_report_adapter.py::test_report_adapter_exposes_p4a_review_packets_and_excludes_review_facts_from_key_facts -q
```

Expected: `PipelineResult` lacks `review_packets`, validation does not accept packets, or adapter does not expose packets.

- [ ] **Step 3: Update validation service**

In `financial-report-analysis/src/financial_report_analysis/services/validation_service.py`, import `ReviewPacket`:

```python
from financial_report_analysis.models.governance import ReviewPacket
```

Change `validate()` signature and add review issue handling:

```python
    def validate(
        self,
        canonical_facts: Iterable[CanonicalFact],
        derived_facts: Iterable[DerivedFact],
        review_packets: Iterable[ReviewPacket] = (),
    ) -> ValidationReport:
        canonical_list = list(canonical_facts)
        derived_list = list(derived_facts)
        review_packet_list = list(review_packets)
```

After the existing lineage checks, add:

```python
        for packet in review_packet_list:
            if packet.conflict_state not in issues:
                issues.append(packet.conflict_state)
```

Leave the existing status mapping unchanged: any issue produces `overall_status="review_required"`.

- [ ] **Step 4: Update pipeline**

In `financial-report-analysis/src/financial_report_analysis/pipeline.py`, import `ReviewPacket`:

```python
from financial_report_analysis.models.governance import ReviewPacket
```

Add `review_packets` to `PipelineResult`:

```python
    review_packets: list[ReviewPacket]
```

Replace conflict resolution in `analyze_report()`:

```python
    conflict_result = ConflictResolver().resolve_with_review(normalized_candidates)
    canonical_facts = conflict_result.canonical_facts
    review_packets = conflict_result.review_packets
    derived_facts = DerivationService().derive_ttm(canonical_facts)
    validation_report = ValidationService().validate(
        canonical_facts,
        derived_facts,
        review_packets,
    )
```

Return `review_packets=review_packets` in `PipelineResult`.

In `_unsupported_language_result()`, return `review_packets=[]`.

- [ ] **Step 5: Update report adapter**

In `financial-report-analysis/src/financial_report_analysis/adapters/report_adapter.py`, add a helper:

```python
    @staticmethod
    def _coerce_review_packet(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        if is_dataclass(value):
            data = asdict(value)
            if isinstance(data.get("competing_candidate_values"), tuple):
                data["competing_candidate_values"] = list(data["competing_candidate_values"])
            return data
        if hasattr(value, "to_dict"):
            return dict(value.to_dict())
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
        raise TypeError("review packet values must be mappings or dataclass-like objects")
```

In `build_analysis_result()`, add:

```python
        review_packets = [
            self._coerce_review_packet(packet)
            for packet in pipeline_data.get("review_packets", [])
        ]
```

Change `analysis_snapshot` to:

```python
            "analysis_snapshot": {
                "summary": "",
                "blocked_items": blocked_items,
                "review_packets": review_packets,
            },
```

Change `_select_key_facts()` to exclude review/blocked facts:

```python
    @staticmethod
    def _select_key_facts(canonical_facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        consumable = [
            fact
            for fact in canonical_facts
            if fact.get("quality_status") in {None, "ok"}
            and not fact.get("validation_flags")
            and fact.get("entity_scope") not in {"unknown", "review_required"}
        ]
        prioritized = [
            fact for fact in consumable if fact.get("metric_id") in _API_VISIBLE_METRICS
        ]
        remainder = [
            fact for fact in consumable if fact.get("metric_id") not in _API_VISIBLE_METRICS
        ]
        return [*prioritized, *remainder][:10]
```

- [ ] **Step 6: Run pipeline and adapter tests, then commit**

Run:

```bash
uv run pytest tests/unit/test_fact_pipeline.py::test_pipeline_carries_p4a_review_packets_and_sets_review_quality_gate tests/unit/test_report_adapter.py -q
```

Expected: selected pipeline test and full report adapter tests pass.

Commit:

```bash
git add src/financial_report_analysis/pipeline.py src/financial_report_analysis/services/validation_service.py src/financial_report_analysis/adapters/report_adapter.py tests/unit/test_fact_pipeline.py tests/unit/test_report_adapter.py
git commit -m "feat: expose P4A conflict review packets"
```

## Task 5: Source Metadata Wiring

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
- Test: `financial-report-analysis/tests/unit/test_table_fact_builder.py`
- Test: `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`

- [ ] **Step 1: Write failing metadata tests**

Append to `financial-report-analysis/tests/unit/test_table_fact_builder.py`:

```python
def test_table_fact_builder_emits_p4a_source_metadata_for_statement_rows() -> None:
    table = NormalizedTableSemantics(
        table_id="table-1",
        document_id="doc-1",
        page_range=(1, 1),
        table_kind="balance_sheet",
        title_text="Consolidated Statement of Financial Position",
        statement_scope_guess="consolidated",
        table_unit="ones",
        table_currency="HKD",
        columns=[
            NormalizedTableColumn(
                column_id="col-2025",
                header_text="2025",
                period_id="2025FY",
                comparison_axis="current",
                value_time_shape="point",
                is_current=True,
                is_comparison=False,
            )
        ],
        rows=[
            NormalizedTableRow(
                row_id="row-cash",
                label_raw="Cash",
                normalized_row_label="cash",
                values=[
                    NormalizedTableCellValue(
                        raw_text="100",
                        numeric_value=100.0,
                        period_id="2025FY",
                        comparison_axis="current",
                        value_time_shape="point",
                        row_index=1,
                        column_index=1,
                    )
                ],
            )
        ],
    )

    candidates = build_table_candidate_facts(
        [table],
        registry=load_metric_registry(),
        document_id="doc-1",
        market="HK",
    )

    assert candidates[0]["extensions"]["source_kind"] == "statement_row"
    assert candidates[0]["extensions"]["source_policy"] == "supplement_only"
```

Append to `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`:

```python
def test_note_disclosure_candidates_emit_p4a_source_metadata() -> None:
    candidates, _ = build_debt_note_candidate_facts(
        pages=[
            (
                40,
                """
                Borrowings 2025 2024
                Short-term borrowings 100 90
                """,
            )
        ],
        document_id="doc-note",
        period_id="2025FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    assert candidates[0]["extensions"]["source_kind"] == "deterministic_note_disclosure"
    assert candidates[0]["extensions"]["source_policy"] == "supplement_only"
```

- [ ] **Step 2: Run metadata tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_table_fact_builder.py::test_table_fact_builder_emits_p4a_source_metadata_for_statement_rows tests/unit/test_note_disclosure_ingestion.py::test_note_disclosure_candidates_emit_p4a_source_metadata -q
```

Expected: source metadata keys are missing.

- [ ] **Step 3: Add table source metadata**

In `financial-report-analysis/src/financial_report_analysis/services/table_fact_builder.py`, inside the `extensions` dict returned by the candidate builder, add:

```python
            "source_kind": "statement_row",
            "source_policy": "supplement_only",
```

Do not change `source_rank_hint`.

- [ ] **Step 4: Add note/disclosure source metadata**

In `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`, inside `_candidate_payload()` under `extensions`, add:

```python
            "source_kind": (
                "llm_locator_assisted_note_disclosure"
                if semantic_source == "llm_fallback"
                else "deterministic_note_disclosure"
            ),
            "source_policy": "supplement_only",
```

Keep the current `extraction_method="note_disclosure"` and `source_rank_hint=18` unchanged.

- [ ] **Step 5: Run metadata tests and commit**

Run:

```bash
uv run pytest tests/unit/test_table_fact_builder.py tests/unit/test_note_disclosure_ingestion.py -q
```

Expected: both files pass.

Commit:

```bash
git add src/financial_report_analysis/services/table_fact_builder.py src/financial_report_analysis/ingestion/note_disclosure.py tests/unit/test_table_fact_builder.py tests/unit/test_note_disclosure_ingestion.py
git commit -m "feat: annotate P4A source metadata"
```

## Task 6: Focused Regression And Plan Closure

**Files:**
- Modify: `docs/superpowers/plans/2026-04-22-financial-report-analysis-parent-scope-notes-conflict-governance-p4a-implementation-plan.md`

- [ ] **Step 1: Run core unit regression**

Run from `financial-report-analysis/`:

```bash
uv run pytest tests/unit/test_models.py tests/unit/test_table_structure.py tests/unit/test_table_fact_builder.py tests/unit/test_note_disclosure_ingestion.py tests/unit/test_fact_pipeline.py tests/unit/test_report_adapter.py -q
```

Expected: all selected unit tests pass.

- [ ] **Step 2: Run Turtle P1-P3 focused regression**

Run:

```bash
uv run pytest tests/unit/test_metric_registry.py tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py tests/unit/test_fact_pipeline.py tests/unit/test_note_disclosure_ingestion.py -q
```

Expected: all selected Turtle foundation and note/disclosure tests pass.

- [ ] **Step 3: Run non-real-PDF semantic recovery regression**

Run:

```bash
uv run pytest tests/integration/test_semantic_recovery_regressions.py -k 'phase1 or p2a or p2b or p3 or asset or debt_note_disclosure_supplement_preserves_statement_row_precedence' -q -m 'not real_pdf'
```

Expected: selected non-real-PDF regression tests pass.

- [ ] **Step 4: Run focused real-PDF P3 guardrail regression**

Run:

```bash
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_cn_601919_2025_surfaces_p3_asset_quality_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_surfaces_p3_statement_row_asset_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_does_not_promote_p3_asset_negative_control_rows tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_only_missing_p3_note_only_asset_candidates -q -o addopts=
```

Expected: four focused P3 real-PDF tests pass. This command can take more than one minute.

- [ ] **Step 5: Add closure note to this plan**

After verification succeeds, add a short closure note near the top of this file:

```markdown
> **Completion Note:** Implemented in commits `<commit-range>`. Verified with core unit regression, Turtle P1-P3 focused unit regression, non-real-PDF semantic recovery regression, and focused P3 real-PDF guardrail regression.
```

Use the actual commit range and actual test outcomes from Steps 1-4.

- [ ] **Step 6: Commit closure note**

Run:

```bash
git add docs/superpowers/plans/2026-04-22-financial-report-analysis-parent-scope-notes-conflict-governance-p4a-implementation-plan.md
git commit -m "docs: close P4A governance implementation plan"
```

## Self-Review Checklist

- Spec coverage:
  - Entity scope contract is covered by Task 1.
  - Source kinds and source policy modes are covered by Task 2.
  - supplement-only, override, review, and blocked conflict outcomes are covered by Task 3.
  - review packet surface and quality gate behavior are covered by Task 4.
  - source metadata wiring for table and note paths is covered by Task 5.
  - P1-P3 regression protection is covered by Task 6.
- Scope check:
  - P4B fields are not implemented in this plan.
  - No durable storage, full review API, broad notes bridge, or multi-year dataset work is included.
  - The plan keeps `report/` untouched.
- Type consistency:
  - `parent_company`, `unknown`, and `review_required` are fact entity scopes.
  - `source_kind`, `source_policy`, and review packet fields are stored in candidate extensions or `ReviewPacket`.
  - `resolve_with_review()` returns `ConflictResolutionResult`, while `resolve()` remains a list-returning compatibility wrapper.
