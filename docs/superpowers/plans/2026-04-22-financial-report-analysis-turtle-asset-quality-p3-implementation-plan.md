# Turtle Asset Quality Inputs P3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Turtle Phase 3 asset-quality extraction for five primary balance-sheet asset fields, plus two bounded note-only supplement fields used only when the primary statement-row path is insufficient, across CN annual, HK statement-row annual, and HK mixed-structure annual anchors.

**Architecture:** Keep the balance-sheet statement-row path as the primary path: table semantics -> metric registry -> candidate facts -> canonical resolver. Add a narrow deterministic note/disclosure supplement only for `contract_assets` and `other_non_current_assets`, with Ollama used only as a gated semantic locator for ambiguous asset disclosure rows and never as the direct source of canonical financial facts.

**Tech Stack:** Python 3.12, pytest, Ruff, pypdf, existing `financial_report_analysis` registry / table semantics / note-disclosure / semantic fallback modules, optional local Ollama through the existing semantic fallback client.

---

## Scope Check

This plan covers one coherent subsystem: Turtle Phase 3 asset-quality inputs for five primary statement-row fields:

- `money_cap`
- `trad_asset`
- `inventories`
- `goodwill`
- `intang_assets`

and two bounded note-only supplement fields:

- `contract_assets`
- `other_non_current_assets`

Parent-only scope, restricted cash, capitalized projects, dividend / buyback / notes bridge themes, and multi-year dataset work are explicitly out of scope.

## Source Precedence Policy

All tasks in this plan must preserve the following precedence:

1. `statement_row`
2. `deterministic_note_disclosure`
3. `llm_locator_assisted_note_disclosure`

Lower-priority sources may fill missing asset metric IDs only. They must not overwrite an existing higher-priority asset fact in the same document.

## Onboarding / Failure Classification Requirement

Every new anchor assertion added in this plan must reflect the onboarding process document:

- identify the anchor's report family
- classify failures before fixing them
- distinguish `present`, `absent`, `not_surfaced`, and `out_of_scope`

At minimum, Task 0, Task 3, and Task 4 must encode the correct missing-status behavior for note-only asset fields in a reviewable onboarding artifact.

## Execution Note

This plan is designed for subagent-driven execution, but Tasks 2 and 4 must be executed serially rather than in parallel because both touch `tests/integration/test_semantic_recovery_regressions.py`.

- Task 2 owns statement-row asset regressions only.
- Task 4 owns note-only supplement regressions and `pdf_ingestion.py` wiring only.

Do not dispatch Task 4 until Task 2 has landed and its review loop is complete.

## File Structure

Modify existing files:

- `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
  - Add only the five primary P3 asset-quality metric definitions.
- `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
  - Normalize CN/HK labels for the five primary P3 asset fields and suppress negative controls.
- `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
  - Add bounded asset note/disclosure parsing for `contract_assets` / `other_non_current_assets` only if deterministic note parsing is needed for the selected anchors.
- `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
  - Append bounded asset note/disclosure candidates after statement-row candidates while preserving precedence.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py`
  - Extend allowed disclosure-locator outputs only if deterministic note parsing cannot cover the bounded asset fields.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/service.py`
  - Gate asset disclosure locator calls if Task 5 is required.
- `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- `financial-report-analysis/tests/unit/test_table_semantics.py`
- `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`
- `financial-report-analysis/tests/unit/test_semantic_fallback_models.py`
- `financial-report-analysis/tests/unit/test_semantic_fallback_service.py`
- `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

Add one new documentation artifact:

- `docs/architecture-analysis/2026-04-22-turtle-asset-quality-p3-sample-onboarding.md`
  - Record anchor metadata, report family, target metric IDs, and per-anchor failure classification / missing-status expectations.

---

### Task 0: Record P3 Anchor Onboarding And Failure Classification

**Files:**

- Add: `docs/architecture-analysis/2026-04-22-turtle-asset-quality-p3-sample-onboarding.md`

- [ ] **Step 1: Create the onboarding artifact**

Create a reviewable markdown artifact at:

`docs/architecture-analysis/2026-04-22-turtle-asset-quality-p3-sample-onboarding.md`

- [ ] **Step 2: Record required metadata for each anchor**

For each of these anchors:

- CN `601919 2025`
- HK `02498 2022`
- HK `09987 2025`

record:

- `sample_id`
- `market`
- `language`
- `issuer_code`
- `report_type`
- `period_end`
- `report_family`
- `target_phase`
- `target_metric_ids`

- [ ] **Step 3: Record failure classification and missing-status expectations**

For each anchor, record the current expectation for:

- `present`
- `absent`
- `not_surfaced`
- `out_of_scope`

and classify current gaps using:

- `structure_recovery_gap`
- `semantic_normalization_gap`
- `metric_mapping_gap`
- `note_disclosure_supplement_gap`

- [ ] **Step 4: Commit**

```bash
git add docs/architecture-analysis/2026-04-22-turtle-asset-quality-p3-sample-onboarding.md
git commit -m "docs: record turtle asset quality p3 onboarding"
```

---

### Task 1: Lock P3 Registry And Row-Semantics Contract With Failing Tests

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- Modify: `financial-report-analysis/tests/unit/test_table_semantics.py`

- [ ] **Step 1: Add registry tests for five primary P3 mappings**

Append this test to `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`:

```python
import pytest


@pytest.mark.parametrize(
    ("metric_id", "market", "label"),
    [
        ("money_cap", "CN", "\u8d27\u5e01\u8d44\u91d1"),
        ("trad_asset", "CN", "\u4ea4\u6613\u6027\u91d1\u878d\u8d44\u4ea7"),
        ("inventories", "CN", "\u5b58\u8d27"),
        ("goodwill", "CN", "\u5546\u8a89"),
        ("intang_assets", "CN", "\u65e0\u5f62\u8d44\u4ea7"),
        ("money_cap", "HK", "cash and cash equivalents"),
        ("trad_asset", "HK", "trading assets"),
        ("inventories", "HK", "inventories"),
        ("goodwill", "HK", "goodwill"),
        ("intang_assets", "HK", "intangible assets"),
    ],
)
def test_metric_mapping_registry_matches_p3_asset_quality_fields(
    metric_id: str,
    market: str,
    label: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="balance_sheet",
        normalized_row_label=label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is not None
    assert definition.metric_id == metric_id
    assert definition.statement_type == "balance_sheet"
    assert definition.period_scope == "point_in_time"
```

- [ ] **Step 2: Add note-only boundary tests**

Append this test to `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`:

```python
@pytest.mark.parametrize(
    ("market", "label"),
    [
        ("CN", "\u5408\u540c\u8d44\u4ea7"),
        ("CN", "\u5176\u4ed6\u975e\u6d41\u52a8\u8d44\u4ea7"),
        ("HK", "contract assets"),
        ("HK", "other non-current assets"),
    ],
)
def test_metric_mapping_registry_does_not_promote_p3_note_only_asset_fields_into_primary_path(
    market: str,
    label: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="balance_sheet",
        normalized_row_label=label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is None
```

- [ ] **Step 3: Add registry negative-control tests**

Append this test to `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`:

```python
@pytest.mark.parametrize(
    ("market", "label"),
    [
        ("HK", "restricted cash"),
        ("HK", "assets held for sale"),
        ("HK", "investment properties"),
        ("HK", "prepayments"),
        ("HK", "right-of-use assets"),
        ("HK", "deferred tax assets"),
        ("HK", "capitalized development costs"),
        ("HK", "total non-current assets"),
        ("CN", "\u53d7\u9650\u8d44\u91d1"),
        ("CN", "\u6301\u6709\u5f85\u552e\u8d44\u4ea7"),
        ("CN", "\u6295\u8d44\u6027\u623f\u5730\u4ea7"),
        ("CN", "\u9884\u4ed8\u6b3e\u9879"),
        ("CN", "\u4f7f\u7528\u6743\u8d44\u4ea7"),
        ("CN", "\u9012\u5ef6\u6240\u5f97\u7a0e\u8d44\u4ea7"),
        ("CN", "\u5f00\u53d1\u652f\u51fa"),
        ("CN", "\u8d44\u4ea7\u603b\u8ba1"),
    ],
)
def test_metric_mapping_registry_rejects_p3_asset_negative_controls(
    market: str,
    label: str,
) -> None:
    registry = load_metric_registry()

    definition = registry.match(
        table_kind="balance_sheet",
        normalized_row_label=label,
        value_time_shape="point_in_time",
        statement_scope_guess="consolidated",
        market=market,
    )

    assert definition is None
```

- [ ] **Step 4: Add table-semantics normalization tests**

Append this test to `financial-report-analysis/tests/unit/test_table_semantics.py`:

```python
@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("\u8d27\u5e01\u8d44\u91d1", "cash and cash equivalents"),
        ("\u4ea4\u6613\u6027\u91d1\u878d\u8d44\u4ea7", "trading assets"),
        ("\u5b58\u8d27", "inventories"),
        ("\u5546\u8a89", "goodwill"),
        ("\u65e0\u5f62\u8d44\u4ea7", "intangible assets"),
        ("Cash and cash equivalents", "cash and cash equivalents"),
        ("Trading assets", "trading assets"),
        ("Inventories", "inventories"),
        ("Goodwill", "goodwill"),
        ("Intangible assets", "intangible assets"),
    ],
)
def test_table_semantics_normalizes_p3_asset_labels(
    label: str,
    expected: str,
) -> None:
    semantics = normalize_table_semantics(_balance_sheet_table_with_row(label))

    assert semantics.rows[0].normalized_row_label == expected
```

- [ ] **Step 5: Add note-only semantics boundary tests**

Append this test to `financial-report-analysis/tests/unit/test_table_semantics.py`:

```python
@pytest.mark.parametrize(
    "label",
    [
        "\u5408\u540c\u8d44\u4ea7",
        "\u5176\u4ed6\u975e\u6d41\u52a8\u8d44\u4ea7",
        "Contract assets",
        "Other non-current assets",
    ],
)
def test_table_semantics_keeps_p3_note_only_asset_labels_out_of_primary_row_semantics(
    label: str,
) -> None:
    semantics = normalize_table_semantics(_balance_sheet_table_with_row(label))

    assert semantics.rows[0].normalized_row_label is None
```

- [ ] **Step 6: Add table-semantics negative-control tests**

Append this test to `financial-report-analysis/tests/unit/test_table_semantics.py`:

```python
@pytest.mark.parametrize(
    "label",
    [
        "restricted cash",
        "assets held for sale",
        "investment properties",
        "prepayments",
        "right-of-use assets",
        "deferred tax assets",
        "capitalized development costs",
        "total non-current assets",
        "\u53d7\u9650\u8d44\u91d1",
        "\u6301\u6709\u5f85\u552e\u8d44\u4ea7",
        "\u6295\u8d44\u6027\u623f\u5730\u4ea7",
        "\u9884\u4ed8\u6b3e\u9879",
        "\u4f7f\u7528\u6743\u8d44\u4ea7",
        "\u9012\u5ef6\u6240\u5f97\u7a0e\u8d44\u4ea7",
        "\u5f00\u53d1\u652f\u51fa",
        "\u8d44\u4ea7\u603b\u8ba1",
    ],
)
def test_table_semantics_suppresses_p3_asset_negative_controls(label: str) -> None:
    semantics = normalize_table_semantics(_balance_sheet_table_with_row(label))

    assert semantics.rows[0].normalized_row_label is None
```

- [ ] **Step 7: Run tests to verify they fail**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py -q -o addopts=
```

Expected: failures for missing P3 mappings and missing asset normalization / negative-control behavior.

---

### Task 2: Implement Deterministic P3 Registry, Row Semantics, And Statement-Row Coverage

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
- Modify: `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

**Ownership:**

- This task owns deterministic statement-row coverage only.
- This task must not modify `note_disclosure.py`, `pdf_ingestion.py`, or `09987` note-only assertions.

- [ ] **Step 1: Add five primary P3 metric definitions**

Add five `MetricMappingDefinition` entries in `metric_mapping.py` for:

- `money_cap`
- `trad_asset`
- `inventories`
- `goodwill`
- `intang_assets`

Each definition must use:

```python
statement_type="balance_sheet"
allowed_table_kinds=("balance_sheet",)
period_scope="point_in_time"
value_type="amount"
unit_expectation="currency_amount"
sign_rule="allow_negative"
```

- [ ] **Step 2: Keep note-only asset fields out of primary statement-row registry**

Verify `contract_assets` and `other_non_current_assets` do not become generic primary statement-row metric definitions in `metric_mapping.py`. If helper comments are needed, add them, but do not introduce default balance-sheet registry entries for these two note-only fields in this task.

- [ ] **Step 3: Add deterministic asset row normalization**

Extend `table_semantics.py` so the following normalize deterministically:

```python
{
    "\u8d27\u5e01\u8d44\u91d1": "cash and cash equivalents",
    "\u4ea4\u6613\u6027\u91d1\u878d\u8d44\u4ea7": "trading assets",
    "\u5b58\u8d27": "inventories",
    "\u5546\u8a89": "goodwill",
    "\u65e0\u5f62\u8d44\u4ea7": "intangible assets",
    "cash and cash equivalents": "cash and cash equivalents",
    "trading assets": "trading assets",
    "inventories": "inventories",
    "goodwill": "goodwill",
    "intangible assets": "intangible assets",
}
```

- [ ] **Step 4: Add negative-control suppression**

Ensure labels such as these remain unmapped:

```python
"restricted cash"
"assets held for sale"
"investment properties"
"prepayments"
"right-of-use assets"
"deferred tax assets"
"capitalized development costs"
"total non-current assets"
"\u53d7\u9650\u8d44\u91d1"
"\u6301\u6709\u5f85\u552e\u8d44\u4ea7"
"\u6295\u8d44\u6027\u623f\u5730\u4ea7"
"\u9884\u4ed8\u6b3e\u9879"
"\u4f7f\u7528\u6743\u8d44\u4ea7"
"\u9012\u5ef6\u6240\u5f97\u7a0e\u8d44\u4ea7"
"\u5f00\u53d1\u652f\u51fa"
"\u8d44\u4ea7\u603b\u8ba1"
```

- [ ] **Step 5: Add statement-row candidate unit coverage**

Append a focused test to `financial-report-analysis/tests/unit/test_fact_pipeline.py` that builds a synthetic balance-sheet semantic table with:

- `cash and cash equivalents`
- `trading assets`
- `inventories`
- `goodwill`
- `intangible assets`

and asserts `build_table_candidate_facts(...)` emits all five metric IDs with `statement_type == "balance_sheet"` and `extraction_method == "table_semantics"`.

- [ ] **Step 6: Add CN/HK statement-row real-PDF regressions**

Append two tests to `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`:

- `test_cn_601919_2025_surfaces_p3_asset_quality_candidates()`
- `test_hk_02498_2022_surfaces_p3_statement_row_asset_candidates()`

Each test should:

- load the anchor sample with `_resolve_sample(...)`
- call `_extract_payload_for_pdf(...)`
- assert the expected deterministic asset metric IDs are present
- assert they come from `table_semantics` and `balance_sheet`

- [ ] **Step 7: Add asset negative-control integration assertion**

Append a test ensuring `02498` does not promote:

- `restricted cash`
- `investment properties`
- `right-of-use assets`

into the five primary P3 metrics.

- [ ] **Step 8: Run focused statement-row suite**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py tests/unit/test_fact_pipeline.py tests/integration/test_semantic_recovery_regressions.py::test_cn_601919_2025_surfaces_p3_asset_quality_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_surfaces_p3_statement_row_asset_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_does_not_promote_p3_asset_negative_control_rows -q -o addopts=
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py financial-report-analysis/tests/unit/test_metric_mapping_registry.py financial-report-analysis/tests/unit/test_table_semantics.py financial-report-analysis/tests/unit/test_fact_pipeline.py financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py
git commit -m "feat: add turtle asset quality statement-row semantics"
```

---

### Task 3: Inspect 09987 And Lock Bounded Note-Only Asset Contract

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

**Ownership:**

- This task owns the exact `09987` note-only asset contract only.
- This task must not change production code yet.

- [ ] **Step 1: Inspect the 09987 anchor for note-only asset disclosure**

Inspect `report/downloads/hk_stocks/09987/annual/2025_annual_en.pdf` and record whether these two fields are independently disclosed in note/disclosure rows:

- `contract_assets`
- `other_non_current_assets`

Expected: update `docs/architecture-analysis/2026-04-22-turtle-asset-quality-p3-sample-onboarding.md` with the exact independently disclosed subset. For the current `09987 2025` anchor, the exact expectation is:

- surfaced subset: none
- `contract_assets`: `absent`
- `other_non_current_assets`: `absent`

- [ ] **Step 2: Add bounded unit tests for asset note parsing**

Append deterministic parser tests to `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py` using bounded snippets such as:

```python
pages = [
    (
        210,
        '''
        Contract assets 2024 2023
        Contract assets 80 65
        '''
    )
]
```

and:

```python
pages = [
    (
        220,
        '''
        Other non-current assets 2024 2023
        Other non-current assets 120 95
        '''
    )
]
```

Assert `extraction_method == "note_disclosure"` and correct `metric_id`.

- [ ] **Step 3: Add negative-control note test**

Append a unit test ensuring rows like:

- `restricted cash`
- `investment properties`
- `prepayments`
- `deferred tax assets`
- `capitalized development costs`
- `summary asset rows`

do not emit any P3 asset metric IDs.

- [ ] **Step 4: Add failing 09987 integration target**

Append a real-PDF regression to `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`:

```python
def test_hk_09987_2025_surfaces_only_missing_p3_note_only_asset_candidates() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    expected_metric_ids = set()
    expected_missing_status = {
        "contract_assets": "absent",
        "other_non_current_assets": "absent",
    }
    asset_candidates = [
        candidate
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict)
        and candidate.get("metric_id") in expected_missing_status
    ]

    assert {candidate["metric_id"] for candidate in asset_candidates} == expected_metric_ids
    assert payload["document_metadata"]["asset_missing_status"] == expected_missing_status
    for candidate in asset_candidates:
        assert candidate["extraction_method"] == "note_disclosure"
        assert candidate["extensions"]["semantic_source"] in {"deterministic", "llm_fallback"}
```

This regression is intentionally exact for the current `09987 2025` anchor: no bounded note-only asset candidates should surface, and both metrics should remain `absent`. Do not assert facts the report does not independently disclose.

- [ ] **Step 5: Run tests to verify red state where expected**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_note_disclosure_ingestion.py tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_only_missing_p3_note_only_asset_candidates -q -o addopts=
```

Expected: fail before production note-only asset support is implemented.

---

### Task 4: Implement Bounded Note-Only Asset Supplement

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Modify: `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

**Ownership:**

- This task owns note-only `contract_assets` / `other_non_current_assets` supplement only.
- Keep it bounded to the selected asset fields.

- [ ] **Step 1: Add bounded asset note parser**

Extend `note_disclosure.py` with a narrow parser for:

- `contract_assets`
- `other_non_current_assets`

Keep it separate from debt and working-capital matching logic; share helpers only when genuinely common.

- [ ] **Step 2: Export the bounded parser**

Update `financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py` to export the new bounded asset note parser entry point.

- [ ] **Step 3: Wire bounded asset note candidates into PdfIngestionAdapter**

Modify `pdf_ingestion.py` so asset note/disclosure candidates are added only for missing P3 note-only metrics, after statement-row candidates and preserving precedence.

- [ ] **Step 4: Preserve provenance and missing status**

Ensure appended asset candidates retain:

```python
candidate["extraction_method"] == "note_disclosure"
candidate["extensions"]["semantic_source"] in {"deterministic", "llm_fallback"}
```

and `document_metadata` exposes bounded asset missing status with:

- `present`
- `absent`
- `not_surfaced`
- `out_of_scope` only if explicitly required

The `09987` regression must assert the exact surfaced subset, the exact `asset_missing_status` map for:

- `contract_assets`
- `other_non_current_assets`

and provenance for every surfaced note-only candidate.

- [ ] **Step 5: Add precedence regression**

Append a mocked regression proving that if a statement-row asset fact already exists, the note/disclosure supplement does not replace it, but still may append another missing bounded note-only asset field.

- [ ] **Step 6: Run focused note-only suite**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_note_disclosure_ingestion.py tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_only_missing_p3_note_only_asset_candidates -q -o addopts=
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py
git commit -m "feat: add turtle asset note supplement"
```

---

### Task 5: Add Bounded Asset Disclosure Locator Only If Deterministic Parsing Needs Help

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/service.py`
- Modify: `financial-report-analysis/tests/unit/test_semantic_fallback_models.py`
- Modify: `financial-report-analysis/tests/unit/test_semantic_fallback_service.py`

- [ ] **Step 1: Check whether existing disclosure locator contract already fits bounded asset fields**

If the current bounded disclosure locator can safely support `contract_assets` / `other_non_current_assets` without widening into free-form asset extraction, reuse it. Only extend outputs if the current contract cannot represent these two fields.

- [ ] **Step 2: Add failing model/service tests if expansion is required**

Add tests proving the locator can emit only:

- `contract_assets`
- `other_non_current_assets`
- `none`

and retains:

- `matched_label`
- `source_text_span`
- `semantic_source`
- `semantic_confidence`
- `fallback_reason`

- [ ] **Step 3: Implement minimal bounded expansion**

Keep behavior gated and narrow. Do not add free-text asset extraction or document-wide numeric reasoning.

- [ ] **Step 4: Run focused fallback tests**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_semantic_fallback_models.py tests/unit/test_semantic_fallback_service.py -q -o addopts=
```

Expected: all pass.

- [ ] **Step 5: Commit only if code changed**

```bash
git add financial-report-analysis/src/financial_report_analysis/semantic_fallback financial-report-analysis/tests/unit/test_semantic_fallback_models.py financial-report-analysis/tests/unit/test_semantic_fallback_service.py
git commit -m "feat: bound turtle asset disclosure locator"
```

Skip this commit if Task 5 required no code changes.

---

### Task 6: Final P3 Verification And Plan Closeout

**Files:**

- Inspect: `docs/superpowers/plans/2026-04-22-financial-report-analysis-turtle-asset-quality-p3-implementation-plan.md`

- [ ] **Step 1: Run focused unit suite**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py tests/unit/test_fact_pipeline.py tests/unit/test_note_disclosure_ingestion.py tests/unit/test_semantic_fallback_models.py tests/unit/test_semantic_fallback_service.py -q -o addopts=
```

Expected: all selected unit tests pass.

- [ ] **Step 2: Run focused integration suite**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_cn_601919_2025_surfaces_p3_asset_quality_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_surfaces_p3_statement_row_asset_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_does_not_promote_p3_asset_negative_control_rows tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_only_missing_p3_note_only_asset_candidates -q -o addopts=
```

Expected: all focused integration tests pass.

- [ ] **Step 3: Run non-regression checks**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_surfaces_phase1_api_visible_metrics tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_p2a_note_disclosure_candidates_without_hallucination tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_only_missing_p2b_note_disclosure_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_anchor_candidate_facts_do_not_map_growth_margin_ratio_rows -q -o addopts=
```

Expected: all pass. These are intentional cross-phase non-regression checks guarding P2A/P2B behavior while P3 lands.

- [ ] **Step 4: Run Ruff**

Run:

```powershell
cd financial-report-analysis
uv run ruff check src tests
```

Expected: no Ruff errors.

- [ ] **Step 5: Run live Ollama smoke only when the environment is healthy**

Run this command only when Ollama is healthy on `127.0.0.1:11434` and the local model is available:

```powershell
cd financial-report-analysis
$env:FRA_RUN_OLLAMA_SMOKE='1'
$env:FRA_SEMANTIC_FALLBACK_BASE_URL='http://127.0.0.1:11434'
$env:FRA_SEMANTIC_FALLBACK_MODEL='qwen3.5:9b'
uv run pytest tests/integration/test_semantic_recovery_regressions.py -k "asset and ollama" -q -o addopts=
```

Expected: pass when a live asset locator smoke exists; otherwise pytest should report no selected tests. Do not make live Ollama a default closure requirement.

- [ ] **Step 6: Commit final closeout edits**

Run this command if Task 6 changed tests or docs:

```powershell
git add docs/superpowers/plans/2026-04-22-financial-report-analysis-turtle-asset-quality-p3-implementation-plan.md financial-report-analysis/tests
git commit -m "test: close turtle asset quality p3 verification"
```

---

## Completion Criteria

P3 is complete only when:

- The five primary asset-quality metric IDs exist in the metric registry with point-in-time balance-sheet semantics.
- `contract_assets` and `other_non_current_assets` are handled only within the bounded note-only scope.
- `docs/architecture-analysis/2026-04-22-turtle-asset-quality-p3-sample-onboarding.md` exists and records anchor metadata, failure classifications, and exact missing-status expectations.
- CN `601919 2025` produces deterministic asset candidate facts from balance-sheet rows.
- HK `02498 2022` produces deterministic asset candidate facts from statement rows.
- HK `09987 2025` produces only independently disclosed bounded note-only asset facts when statement rows are insufficient.
- `present / absent / not_surfaced / out_of_scope` behavior is explicit where relevant.
- Summary asset rows, deferred tax assets, capitalized development costs, and other non-target asset disclosures do not get absorbed into the P3 metrics.
- Ollama locator output, if used, remains bounded, gated, provenance-carrying, and never directly becomes canonical facts.
- Existing Phase 1, P2A, and P2B paths continue to pass.
