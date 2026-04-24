# Turtle Debt Inputs P2B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Phase 2B Turtle debt-input extraction for four core interest-bearing liability fields across CN annual reports, HK statement-row annual reports, and HK mixed-structure annual reports.

**Architecture:** Keep the balance-sheet statement-row path as the primary path: table semantics -> metric registry -> candidate facts -> canonical resolver. Add a narrow deterministic note/disclosure supplement for HK `09987 2025`, with Ollama used only as a gated semantic locator for ambiguous debt disclosure rows and never as the direct source of canonical financial facts.

For the current `09987 2025` anchor, the exact independently disclosed mixed-structure subset is `st_borr` only. Task 5 and Task 7 should therefore verify that the narrow note/disclosure supplement surfaces only that missing field for this anchor, without hallucinating the other three P2B metrics.

**Tech Stack:** Python 3.12, pytest, Ruff, pypdf, existing `financial_report_analysis` registry / table semantics / semantic fallback modules, optional local Ollama through the existing semantic fallback client.

---

## Scope Check

The approved spec covers one coherent subsystem: Turtle Phase 2B debt-input extraction for four core fields:

- `st_borr`
- `lt_borr`
- `bond_payable`
- `non_cur_liab_due_1y`

Deferred tax, lease liabilities, parent-only scope, and multi-year dataset work are explicitly out of scope and must not be implemented in this plan.

## Source Precedence Policy

All tasks in this plan must preserve the following precedence:

1. `statement_row`
2. `deterministic_note_disclosure`
3. `llm_locator_assisted_note_disclosure`

Lower-priority sources may fill missing debt metric IDs only. They must not overwrite an existing higher-priority debt fact in the same document.

## Execution Note

This plan is designed for subagent-driven execution, but Tasks 3 and 5 must be executed serially rather than in parallel because both touch `tests/integration/test_semantic_recovery_regressions.py`.

- Task 3 owns only the statement-row debt regressions for `601919` / `02498` plus the synthetic unit candidate-coverage test.
- Task 5 owns only the `09987` note/disclosure regressions and `pdf_ingestion.py` wiring.

Do not dispatch Task 5 until Task 3 has landed and its review loop is complete.

## File Structure

Modify existing files:

- `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
  - Add four P2B debt `MetricMappingDefinition` entries.
- `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
  - Normalize CN/HK debt row labels and suppress negative controls.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py`
  - Add debt disclosure locator outputs if missing from the bounded contract.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/client.py`
  - Extend the client protocol if debt locator-specific request handling is needed.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/service.py`
  - Gate debt disclosure locator calls.
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/ollama_client.py`
  - Add constrained debt locator prompt / output handling only if deterministic parsing is insufficient.
- `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
  - Add debt disclosure parsing alongside the existing working-capital supplement path.
- `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
  - Append debt note/disclosure candidates after statement-row candidates while preserving precedence.
- `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- `financial-report-analysis/tests/unit/test_table_semantics.py`
- `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`
- `financial-report-analysis/tests/unit/test_semantic_fallback_models.py`
- `financial-report-analysis/tests/unit/test_semantic_fallback_service.py`
- `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

---

### Task 1: Lock P2B Registry And Row-Semantics Contract With Failing Tests

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- Modify: `financial-report-analysis/tests/unit/test_table_semantics.py`

- [ ] **Step 1: Add registry tests for four positive P2B mappings**

Append this test to `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`:

```python
import pytest


@pytest.mark.parametrize(
    ("metric_id", "market", "label"),
    [
        ("st_borr", "CN", "\u77ed\u671f\u501f\u6b3e"),
        ("lt_borr", "CN", "\u957f\u671f\u501f\u6b3e"),
        ("bond_payable", "CN", "\u5e94\u4ed8\u503a\u5238"),
        ("non_cur_liab_due_1y", "CN", "\u4e00\u5e74\u5185\u5230\u671f\u7684\u975e\u6d41\u52a8\u8d1f\u503a"),
        ("st_borr", "HK", "short-term borrowings"),
        ("lt_borr", "HK", "long-term borrowings"),
        ("bond_payable", "HK", "bonds payable"),
        ("non_cur_liab_due_1y", "HK", "current portion of long-term debt"),
    ],
)
def test_metric_mapping_registry_matches_p2b_debt_fields(
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

- [ ] **Step 2: Add registry negative-control tests**

Append this test to `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`:

```python
@pytest.mark.parametrize(
    ("market", "label"),
    [
        ("HK", "lease liabilities"),
        ("HK", "accounts payable"),
        ("HK", "contract liabilities"),
        ("HK", "total borrowings"),
        ("CN", "\u79df\u8d41\u8d1f\u503a"),
        ("CN", "\u5e94\u4ed8\u8d26\u6b3e"),
        ("CN", "\u5408\u540c\u8d1f\u503a"),
        ("CN", "\u501f\u6b3e\u5408\u8ba1"),
    ],
)
def test_metric_mapping_registry_rejects_p2b_negative_controls(
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

- [ ] **Step 3: Add table-semantics normalization tests**

Append a debt-table helper and this test to `financial-report-analysis/tests/unit/test_table_semantics.py`:

```python
@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("\u77ed\u671f\u501f\u6b3e", "short-term borrowings"),
        ("\u957f\u671f\u501f\u6b3e", "long-term borrowings"),
        ("\u5e94\u4ed8\u503a\u5238", "bonds payable"),
        ("\u4e00\u5e74\u5185\u5230\u671f\u7684\u975e\u6d41\u52a8\u8d1f\u503a", "current portion of long-term debt"),
        ("Short-term borrowings", "short-term borrowings"),
        ("Long-term borrowings", "long-term borrowings"),
        ("Bonds payable", "bonds payable"),
        ("Current portion of long-term debt", "current portion of long-term debt"),
    ],
)
def test_table_semantics_normalizes_p2b_debt_labels(
    label: str,
    expected: str,
) -> None:
    semantics = normalize_table_semantics(_balance_sheet_table_with_row(label))

    assert semantics.rows[0].normalized_row_label == expected
```

- [ ] **Step 4: Add table-semantics negative-control tests**

Append this test to `financial-report-analysis/tests/unit/test_table_semantics.py`:

```python
@pytest.mark.parametrize(
    "label",
    [
        "lease liabilities",
        "accounts payable",
        "notes payable",
        "contract liabilities",
        "total borrowings",
        "\u79df\u8d41\u8d1f\u503a",
        "\u5e94\u4ed8\u8d26\u6b3e",
        "\u5e94\u4ed8\u7968\u636e",
        "\u5408\u540c\u8d1f\u503a",
        "\u501f\u6b3e\u53ca\u5176\u4ed6\u8d1f\u503a",
    ],
)
def test_table_semantics_suppresses_p2b_negative_controls(label: str) -> None:
    semantics = normalize_table_semantics(_balance_sheet_table_with_row(label))

    assert semantics.rows[0].normalized_row_label is None
```

- [ ] **Step 5: Run tests to verify they fail**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py -q -o addopts=
```

Expected: failures for missing P2B registry mappings and missing debt normalization / negative-control behavior.

---

### Task 2: Implement Deterministic P2B Registry And Row Semantics

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`

- [ ] **Step 1: Add four P2B metric definitions**

Add four `MetricMappingDefinition` entries in `metric_mapping.py` for:

- `st_borr`
- `lt_borr`
- `bond_payable`
- `non_cur_liab_due_1y`

Each definition must use:

```python
statement_type="balance_sheet"
allowed_table_kinds=("balance_sheet",)
period_scope="point_in_time"
value_type="amount"
unit_expectation="currency_amount"
sign_rule="allow_negative"
```

CN/HK aliases should cover only directly disclosed debt labels and should not include summary rows.

- [ ] **Step 2: Add debt row-label normalization in `table_semantics.py`**

Extend the balance-sheet normalization rules so the following normalize deterministically:

```python
{
    "\u77ed\u671f\u501f\u6b3e": "short-term borrowings",
    "\u957f\u671f\u501f\u6b3e": "long-term borrowings",
    "\u5e94\u4ed8\u503a\u5238": "bonds payable",
    "\u4e00\u5e74\u5185\u5230\u671f\u7684\u975e\u6d41\u52a8\u8d1f\u503a": "current portion of long-term debt",
    "short-term borrowings": "short-term borrowings",
    "long-term borrowings": "long-term borrowings",
    "bonds payable": "bonds payable",
    "current portion of long-term debt": "current portion of long-term debt",
}
```

- [ ] **Step 3: Add negative-control suppression**

Ensure labels such as these remain unmapped:

```python
"lease liabilities"
"accounts payable"
"notes payable"
"contract liabilities"
"total borrowings"
"\u79df\u8d41\u8d1f\u503a"
"\u5e94\u4ed8\u8d26\u6b3e"
"\u5e94\u4ed8\u7968\u636e"
"\u5408\u540c\u8d1f\u503a"
"\u501f\u6b3e\u53ca\u5176\u4ed6\u8d1f\u503a"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py -q -o addopts=
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py financial-report-analysis/tests/unit/test_metric_mapping_registry.py financial-report-analysis/tests/unit/test_table_semantics.py
git commit -m "feat: add turtle debt registry semantics"
```

---

### Task 3: Add Statement-Row Candidate Coverage For CN 601919 And HK 02498

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

**Ownership:**

- This task owns statement-row candidate coverage only.
- This task must not modify `note_disclosure.py`, `pdf_ingestion.py`, or any `09987`-specific assertions.
- Any production behavior change in this task must be limited to existing statement-row candidate emission via registry / table semantics.

- [ ] **Step 1: Add unit candidate-coverage test**

Append a focused test to `financial-report-analysis/tests/unit/test_fact_pipeline.py` that builds a synthetic balance-sheet semantic table with:

- `short-term borrowings`
- `long-term borrowings`
- `bonds payable`
- `current portion of long-term debt`

and asserts that `build_table_candidate_facts(...)` emits:

- `st_borr`
- `lt_borr`
- `bond_payable`
- `non_cur_liab_due_1y`

with `statement_type == "balance_sheet"` and `extraction_method == "table_semantics"`.

- [ ] **Step 2: Run the new unit test and verify it fails**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py -q -o addopts= -k debt
```

Expected: fail before implementation is complete.

- [ ] **Step 3: Make the minimal implementation pass through existing table-candidate path**

Use the registry / semantics definitions from Task 2. Do not add a separate debt-only candidate builder for statement rows.

- [ ] **Step 4: Add CN/HK real-PDF regression tests**

Append two tests to `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`:

- `test_cn_601919_2025_surfaces_p2b_debt_candidates()`
- `test_hk_02498_2022_surfaces_p2b_statement_row_debt_candidates()`

Each test should:

- load the anchor sample with `_resolve_sample(...)`
- call `_extract_payload_for_pdf(...)`
- assert expected P2B metric IDs are present in `candidate_facts`
- assert debt candidates come from `table_semantics` and `balance_sheet`

- [ ] **Step 5: Add negative-control integration assertion**

Append a test that ensures `02498` does not promote:

- `lease liabilities`
- `accounts payable`
- `contract liabilities`

into the four P2B metrics.

- [ ] **Step 6: Run the focused statement-row suite**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py tests/integration/test_semantic_recovery_regressions.py::test_cn_601919_2025_surfaces_p2b_debt_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_surfaces_p2b_statement_row_debt_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_does_not_promote_p2b_negative_control_rows -q -o addopts=
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add financial-report-analysis/tests/unit/test_fact_pipeline.py financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py
git commit -m "test: cover turtle debt statement-row anchors"
```

---

### Task 4: Add Deterministic Debt Note/Disclosure Supplement For HK 09987

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py`
- Modify: `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`

- [ ] **Step 1: Inspect the 09987 anchor and record independently disclosed debt metrics**

Before writing parser assertions, inspect `report/downloads/hk_stocks/09987/annual/2025_annual_en.pdf` and record which of the four P2B metrics are independently disclosed in note/disclosure rows:

- `st_borr`
- `lt_borr`
- `bond_payable`
- `non_cur_liab_due_1y`

Expected: a short note in the test comments or task implementation notes stating the exact independently disclosed subset for `09987 2025`.

- [ ] **Step 2: Add failing note/disclosure unit test**

Append a deterministic debt parser test to `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py` using a single page snippet like:

```python
pages = [
    (
        178,
        '''
        Borrowings 2024 2023
        Short-term borrowings 120 110
        Long-term borrowings 560 600
        Current portion of long-term debt 80 75
        '''
    )
]
```

and assert emission of:

- `st_borr`
- `lt_borr`
- `non_cur_liab_due_1y`

with `extraction_method == "note_disclosure"`.

- [ ] **Step 3: Make `bond_payable` explicit rather than implicit**

Based on Step 1, do exactly one of the following:

- If `09987 2025` independently discloses `bond_payable`, add a deterministic parser test for it in this task.
- If `09987 2025` does not independently disclose `bond_payable`, add an explicit negative assertion documenting that no `bond_payable` fact should be emitted for this anchor.

Do not leave `bond_payable` behavior unspecified.

- [ ] **Step 4: Add negative-control note test**

Append a unit test ensuring rows like:

- `Lease liabilities`
- `Accounts payable`
- `Contract liabilities`

do not emit any of the four P2B metric IDs.

- [ ] **Step 5: Implement deterministic debt note parsing**

Extend `note_disclosure.py` with a narrow parser for debt disclosure rows. Keep it separate from working-capital matching logic; share helpers only where they are genuinely common.

- [ ] **Step 6: Run focused unit tests**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_note_disclosure_ingestion.py -q -o addopts=
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py
git commit -m "feat: add turtle debt note disclosure parser"
```

---

### Task 5: Wire Debt Note/Disclosure Candidates Into PdfIngestionAdapter

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

**Ownership:**

- This task owns `09987` integration regressions and `pdf_ingestion.py` wiring only.
- This task begins only after Task 3 is complete.

- [ ] **Step 1: Convert 09987 sample inspection into an exact integration contract**

Using the Step 1 outcome from Task 4, write down the exact independently disclosed `09987 2025` debt metric subset that this anchor should surface.

Expected: one exact expected set for `09987 2025`, not an open-ended “refine later” placeholder.

- [ ] **Step 2: Add failing 09987 integration regression**

Append this integration target:

```python
def test_hk_09987_2025_surfaces_only_missing_p2b_note_disclosure_candidates() -> None:
    pdf_path = _resolve_sample("hk_stocks", "09987", "annual", "2025_annual_en.pdf")

    payload = _extract_payload_for_pdf(pdf_path, market="HK")
    metric_ids = _metric_ids_from_candidates(payload)

    assert metric_ids >= EXPECTED_09987_P2B_DEBT_METRICS
    assert _candidate_labels_for_metric(payload, "st_borr") <= EXPECTED_09987_ST_BORR_LABELS
```

Replace the placeholder constants with concrete expectations derived from Task 4’s anchor inspection. Do not assert facts that the report does not independently disclose.

- [ ] **Step 3: Add precedence assertion**

Append an integration assertion proving that any `09987` note/disclosure debt candidate:

- uses `extraction_method == "note_disclosure"`
- appears only for missing P2B metric IDs
- does not replace an already present `statement_row` debt fact

- [ ] **Step 4: Append note-disclosure candidates after statement-row candidates**

Modify `pdf_ingestion.py` so debt note/disclosure candidates are added only for missing P2B metric IDs, preserving the plan’s precedence policy.

- [ ] **Step 5: Preserve provenance**

Ensure debt supplement candidates retain:

```python
candidate["extraction_method"] == "note_disclosure"
candidate["extensions"]["semantic_source"] in {"deterministic", "llm_fallback"}
```

- [ ] **Step 6: Run focused 09987 regression**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_only_missing_p2b_note_disclosure_candidates -q -o addopts=
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py
git commit -m "feat: wire turtle debt disclosure candidates"
```

---

### Task 6: Add Bounded Debt Disclosure Locator Only If Deterministic Parsing Needs Help

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/client.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/service.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/semantic_fallback/ollama_client.py`
- Modify: `financial-report-analysis/tests/unit/test_semantic_fallback_models.py`
- Modify: `financial-report-analysis/tests/unit/test_semantic_fallback_service.py`

- [ ] **Step 1: Check whether existing disclosure locator contract already fits debt metrics**

If the current bounded disclosure locator can safely support the four debt metrics without widening its contract beyond the spec, reuse it. Only add new debt outputs if the contract is currently working-capital-only.

- [ ] **Step 2: Add failing model/service tests if contract expansion is required**

Add tests proving the locator can emit only:

- `st_borr`
- `lt_borr`
- `bond_payable`
- `non_cur_liab_due_1y`
- `none`

and retains:

- `matched_label`
- `source_text_span`
- `semantic_source`
- `semantic_confidence`
- `fallback_reason`

- [ ] **Step 3: Implement minimal bounded expansion**

Keep debt locator behavior gated and narrow. Do not add free-text debt extraction or document-wide numeric reasoning.

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
git commit -m "feat: bound turtle debt disclosure locator"
```

Skip this commit if Task 6 required no code changes.

---

### Task 7: Final P2B Verification And Plan Closeout

**Files:**

- Inspect: `docs/superpowers/plans/2026-04-22-financial-report-analysis-turtle-debt-inputs-p2b-implementation-plan.md`

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
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_cn_601919_2025_surfaces_p2b_debt_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_surfaces_p2b_statement_row_debt_candidates tests/integration/test_semantic_recovery_regressions.py::test_hk_02498_2022_does_not_promote_p2b_negative_control_rows tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_only_missing_p2b_note_disclosure_candidates -q -o addopts=
```

Expected: all focused integration tests pass.

- [ ] **Step 3: Run non-regression checks**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_surfaces_phase1_api_visible_metrics tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_surfaces_p2a_note_disclosure_candidates_without_hallucination tests/integration/test_semantic_recovery_regressions.py::test_hk_anchor_candidate_facts_do_not_map_growth_margin_ratio_rows -q -o addopts=
```

Expected: all pass.

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
uv run pytest tests/integration/test_semantic_recovery_regressions.py -k "debt and ollama" -q -o addopts=
```

Expected: pass when a live debt locator smoke exists; otherwise pytest should report no selected tests. Do not make live Ollama a default closure requirement.

- [ ] **Step 6: Commit final closeout edits**

Run this command if Task 7 changed tests or docs:

```powershell
git add docs/superpowers/plans/2026-04-22-financial-report-analysis-turtle-debt-inputs-p2b-implementation-plan.md financial-report-analysis/tests
git commit -m "test: close turtle debt inputs p2b verification"
```

---

## Completion Criteria

P2B is complete only when:

- All four debt metric IDs exist in the metric registry with point-in-time balance-sheet semantics.
- CN `601919 2025` produces deterministic debt candidate facts from balance-sheet rows.
- HK `02498 2022` produces deterministic debt candidate facts from statement rows.
- HK `09987 2025` produces only independently disclosed debt note/disclosure facts when statement rows are insufficient; for the current anchor floor, that means `st_borr` only.
- `non_cur_liab_due_1y` is emitted only when independently disclosed.
- Summary debt rows and non-debt liabilities do not get absorbed into the four P2B metrics.
- Ollama locator output, if used, remains bounded, gated, provenance-carrying, and never directly becomes canonical facts.
- Existing Phase 1 investor inputs, P2A working-capital paths, and prior high-value metrics continue to pass.
