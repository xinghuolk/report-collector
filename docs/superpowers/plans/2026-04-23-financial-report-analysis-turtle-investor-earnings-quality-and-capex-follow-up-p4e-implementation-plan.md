# P4E Turtle Investor Earnings Quality And Capex Follow-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining non-parent pre-P5 coverage gaps for Turtle by adding deterministic-first support for `fix_assets`, `cip`, `rd_exp`, `invest_income`, `asset_disp_income`, `n_recp_disp_fiolta`, and `c_recp_return_invest`.

**Architecture:** Preserve the existing main path: `pdf -> structure recovery -> normalized table semantics -> metric mapping registry -> candidate facts -> canonical facts`. Keep this phase statement-row first and avoid opening a new broad note/disclosure bridge.

**Tech Stack:** Python 3.12, pytest, Ruff, pypdf, existing `financial_report_analysis` table semantics / registry / ingestion / pipeline modules.

---

## Scope Check

This plan covers one narrow subsystem: non-parent pre-P5 earnings-quality and capex-follow-up fields only.

It does **not** cover:

- parent-company statement coverage
- broad note / disclosure expansion
- `minority_int`
- `non_oper_income` / `non_oper_exp`
- `receiv_tax_refund`
- multi-year dataset schema

## Source Policy

All tasks in this plan assume statement-row facts remain the primary path.

Priority order:

1. `statement_row`
2. bounded semantic fallback for local ambiguity only

This phase should not introduce a new free-text supplement path by default.

## Metric Set

Target canonical metric ids:

- `fix_assets`
- `cip`
- `rd_exp`
- `invest_income`
- `asset_disp_income`
- `n_recp_disp_fiolta`
- `c_recp_return_invest`

## Onboarding Requirement

Before implementation starts, create a dedicated onboarding artifact for the chosen anchors. It must follow:

- `docs/architecture-analysis/new-report-sample-onboarding-and-field-variance-process.md`

At minimum, it should record:

- one CN annual anchor with cleaner fixed-asset / investment rows
- one HK cleaner-format partial-positive anchor
- one mixed-format anchor for negative controls
- target metric set
- expected `present / absent / not_surfaced / out_of_scope`
- likely failure buckets if phase-entry diagnostics are not yet stable

## File Structure

Expected files to touch:

- `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
- `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- `financial-report-analysis/tests/unit/test_table_semantics.py`
- `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`
- onboarding artifact under `docs/architecture-analysis/`

Depending on diagnostics, the work may also touch:

- fallback tests only if strictly needed

---

### Task 0: Create P4E Onboarding Artifact

**Files:**

- Add: `docs/architecture-analysis/2026-04-23-turtle-investor-earnings-quality-and-capex-follow-up-p4e-sample-onboarding.md`

- [ ] **Step 1: Create the onboarding artifact**

Record the fixed anchors, target metric set, and current phase-entry expectations for:

- `fix_assets`
- `cip`
- `rd_exp`
- `invest_income`
- `asset_disp_income`
- `n_recp_disp_fiolta`
- `c_recp_return_invest`

- [ ] **Step 2: Classify each anchor**

For each anchor, record:

- `present`
- `absent`
- `not_surfaced`
- `out_of_scope`

and likely failure buckets:

- `structure_recovery_gap`
- `semantic_normalization_gap`
- `metric_mapping_gap`
- `statement_row_candidate_gap`
- `fallback_gap`

---

### Task 1: Lock Registry And Semantics Contract

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- Modify: `financial-report-analysis/tests/unit/test_table_semantics.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`

- [ ] **Step 1: Add failing registry and semantics tests**

Add focused tests for:

- `fix_assets`
- `cip`
- `rd_exp`
- `invest_income`
- `asset_disp_income`
- `n_recp_disp_fiolta`
- `c_recp_return_invest`

The tests should also lock negative controls against:

- investment properties
- right-of-use assets
- capitalized development costs
- interest income
- fair value changes
- generic investing cash inflows

- [ ] **Step 2: Implement the minimum contract additions**

Prefer explicit row families and explicit negative controls over broad token matching.

- [ ] **Step 3: Re-run the focused registry / semantics tests**

```bash
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py -q -o addopts=
```

---

### Task 2: Verify Candidate-Fact Emission

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_fact_pipeline.py`

- [ ] **Step 1: Add failing candidate-fact tests**

Add tests that prove:

- the target fields emit statement-row candidate facts
- statement type / table kind / period scope stay correct
- strong negative controls do not survive to candidate facts

- [ ] **Step 2: Implement only the minimum needed changes**

Prefer fixing semantics / registry interactions before touching broader ingestion behavior.

- [ ] **Step 3: Re-run the focused unit tests**

```bash
uv run pytest tests/unit/test_fact_pipeline.py -q -o addopts=
```

---

### Task 3: Add Focused Real-PDF Anchor Regressions

**Files:**

- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

- [ ] **Step 1: Add failing anchor regressions**

Assert only the current locked contract:

- which fields surface on the deterministic path
- which remain `absent`
- which remain `not_surfaced`
- that negative controls do not get promoted into the target set

- [ ] **Step 2: Run the new regressions and confirm failure**

```bash
uv run pytest tests/integration/test_semantic_recovery_regressions.py -q -o addopts=
```

Use targeted node selection while iterating.

- [ ] **Step 3: Make the minimum implementation changes needed for the anchors**

Adjust code only as needed so the anchor contracts pass without issuer-specific branches.

- [ ] **Step 4: Re-run the focused regressions**

Re-run only the targeted nodes added for `P4E`.

---

### Task 4: Fallback Review And Closeout

**Files:**

- Modify only if necessary:
  - fallback model/service files
  - paired tests

- [ ] **Step 1: Confirm whether new fallback is actually needed**

Only expand fallback if focused diagnostics show a stable local ambiguity that deterministic structure + semantics cannot resolve.

Likely non-fallback problems in this phase:

- missing row families
- semantics suppression gaps
- metric mapping gaps

- [ ] **Step 2: If needed, add the smallest bounded fallback support**

No new broad document-level fallback surfaces.

- [ ] **Step 3: Focused closeout verification**

At minimum, run:

```bash
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py -q -o addopts=
uv run pytest tests/unit/test_fact_pipeline.py -q -o addopts=
uv run pytest tests/integration/test_semantic_recovery_regressions.py -q -o addopts=
uv run ruff check src tests
```

Use targeted node selection for the real-PDF file while iterating.

## Definition Of Done

`P4E` is complete when:

- the 7 target metric families have explicit deterministic contracts
- candidate facts surface through the statement-row path where expected
- focused anchors lock the current baseline without issuer-specific branches
- fallback has not been expanded unless diagnostics proved it necessary
