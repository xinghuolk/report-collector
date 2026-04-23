# P4D Turtle Parent Scope And Notes Follow-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining pre-P5 parent-scope and notes-follow-up gaps for Turtle by adding deterministic-first support for parent-company `cash`, `lt_eqt_invest`, debt / total / equity families, plus the already-scoped notes bridge fields `restricted_cash`, `time_deposits_or_wealth_products`, and `interest_paid_cash`.

**Architecture:** Preserve the existing main path: `pdf -> structure recovery -> normalized table semantics -> metric mapping registry -> candidate facts -> canonical facts`, with note/disclosure supplements allowed only as bounded, lower-priority bridge outputs. Keep `consolidated` and `parent_company` on separate tracks.

**Tech Stack:** Python 3.12, pytest, Ruff, pypdf, existing `financial_report_analysis` table semantics / registry / ingestion / pipeline modules.

---

## Scope Check

This plan covers one narrow subsystem: parent-scope statement facts and already-authorized notes-follow-up work only.

It does **not** cover:

- new broad investor-core consolidated statement metrics
- broad narrative extraction
- DPS / buyback / capitalized R&D / capitalized interest text parsing
- multi-year dataset schema
- new storage / lineage / recompute surfaces

## Source Policy

All tasks in this plan assume parent statement-row facts remain the primary path.

Priority order:

1. `parent_statement_row`
2. bounded existing note/disclosure supplement for scoped fields only
3. bounded semantic fallback for local ambiguity only

This phase should not introduce a new free-text supplement path.

## Metric-Id Mapping Note

This plan should follow current codebase metric ids where they already exist.

Mapping:

- Turtle parent `money_cap` -> current code `cash` with `entity_scope = parent_company`
- Turtle parent debt -> `st_borr` / `lt_borr` / `bond_payable` / `non_cur_liab_due_1y`
- Turtle parent totals -> `total_assets` / `total_liabilities` / `equity` / `equity_attributable_to_owners`
- scoped note bridge -> `restricted_cash` / `time_deposits_or_wealth_products` / `interest_paid_cash`

Expected minimal new id in this phase:

- `lt_eqt_invest`

If downstream Turtle naming needs another alias, do that in a separate adapter layer rather than inside this coverage phase.

## Onboarding Requirement

Before implementation starts, create a dedicated onboarding artifact for the chosen anchors. It must follow:

- `docs/architecture-analysis/new-report-sample-onboarding-and-field-variance-process.md`

At minimum, it should record:

- one CN annual anchor with separate parent statements
- one HK cleaner-format annual anchor
- one HK mixed-structure annual anchor
- target metric set
- `consolidated` vs `parent_company` expectations
- expected `present / absent / not_surfaced / out_of_scope`
- failure classification by metric family if phase-entry diagnostics are not yet stable

## File Structure

Expected files to touch:

- `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`
- `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
- `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- `financial-report-analysis/tests/unit/test_table_structure.py`
- `financial-report-analysis/tests/unit/test_table_semantics.py`
- `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`
- onboarding artifact under `docs/architecture-analysis/`

Depending on diagnostics, the work may also touch:

- `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
- paired note-disclosure tests
- fallback tests only if strictly needed

---

### Task 0: Create P4D Onboarding Artifact

**Files:**

- Add: `docs/architecture-analysis/2026-04-23-turtle-parent-scope-and-notes-follow-up-p4d-sample-onboarding.md`

- [ ] **Step 1: Create the onboarding artifact**

Record the fixed anchors, target metric set, and current phase-entry expectations for:

- parent `cash`
- `lt_eqt_invest`
- parent `st_borr`
- parent `lt_borr`
- parent `bond_payable`
- parent `non_cur_liab_due_1y`
- parent `total_assets`
- parent `total_liabilities`
- parent `equity`
- parent `equity_attributable_to_owners` only when the sample family explicitly discloses it on the parent track
- `restricted_cash`
- `time_deposits_or_wealth_products`
- `interest_paid_cash`

- [ ] **Step 2: Classify each anchor**

For each anchor, record:

- `present`
- `absent`
- `not_surfaced`
- `out_of_scope`

and likely failure buckets:

- `structure_recovery_gap`
- `scope_detection_gap`
- `semantic_normalization_gap`
- `metric_mapping_gap`
- `statement_row_candidate_gap`
- `note_bridge_gap`

- [ ] **Step 3: Commit onboarding if created**

```bash
git add docs/architecture-analysis/2026-04-23-turtle-parent-scope-and-notes-follow-up-p4d-sample-onboarding.md
git commit -m "docs: add turtle p4d onboarding artifact"
```

---

### Task 1: Lock Parent Scope Detection Contract

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_table_structure.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`

- [ ] **Step 1: Add failing scope-detection tests**

Add focused tests that prove:

- separate-company statements normalize to `parent_only`
- attributable-owner labels do not accidentally imply `parent_only`
- mixed documents can preserve both `consolidated` and `parent_only` tables

- [ ] **Step 2: Implement the minimum scope-detection changes**

Only change the structure/scope heuristics needed to make `parent_only` statement blocks stable.

- [ ] **Step 3: Re-run the focused structure tests**

```bash
uv run pytest tests/unit/test_table_structure.py -q -o addopts=
```

- [ ] **Step 4: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py financial-report-analysis/tests/unit/test_table_structure.py
git commit -m "feat: stabilize turtle p4d parent scope detection"
```

---

### Task 2: Lock Parent Statement Metric Contract

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- Modify: `financial-report-analysis/tests/unit/test_table_semantics.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`

- [ ] **Step 1: Add failing registry and semantics tests**

Add focused tests for:

- parent `cash`
- `lt_eqt_invest`
- parent debt families
- parent totals / equity families

The tests should also lock negative controls against:

- consolidated-only totals
- lease liabilities
- trading assets
- goodwill
- restricted cash
- total equity rows with wrong scope

- [ ] **Step 2: Implement the minimum contract additions**

Prefer explicit row families and explicit scope-safe mappings over broad token matching.

- [ ] **Step 3: Re-run the focused registry / semantics tests**

```bash
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py -q -o addopts=
```

- [ ] **Step 4: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py financial-report-analysis/tests/unit/test_metric_mapping_registry.py financial-report-analysis/tests/unit/test_table_semantics.py
git commit -m "feat: add turtle p4d parent statement mappings"
```

---

### Task 3: Verify Parent Candidate-Fact And Precedence Contract

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py` only if needed

- [ ] **Step 1: Add failing unit tests for parent candidate-fact emission**

Add tests that prove:

- parent statement rows emit `entity_scope = parent_company`
- parent facts do not overwrite consolidated facts
- statement-row facts keep precedence over note supplements for the same metric/scope/period

- [ ] **Step 2: Add parent missing-status tests if needed**

If `P4D` introduces `parent_scope_missing_status`, add narrow ingestion-level tests for it.

Do not introduce a required parent `equity_attributable_to_owners` missing-status branch unless the onboarding anchors show that family is actually a stable parent-track target.

- [ ] **Step 3: Implement only the minimum needed changes**

Prefer fixing scope / registry / table-fact-builder interactions before touching broader ingestion behavior.

- [ ] **Step 4: Re-run the focused unit tests**

```bash
uv run pytest tests/unit/test_fact_pipeline.py -q -o addopts=
```

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/tests/unit/test_fact_pipeline.py financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py
git commit -m "feat: wire turtle p4d parent candidates"
```

Skip `pdf_ingestion.py` in the commit if it did not change.

---

### Task 4: Harden The Existing Cash-Health / Notes Bridge Only Where P4D Needs It

**Files:**

- Modify only if necessary:
  - `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
  - paired note-disclosure tests

- [ ] **Step 1: Add failing tests only for remaining parent-scope / precedence gaps**

Do not reopen already-passing `P4B` contracts.

The only valid reasons to touch this layer in `P4D` are:

- parent-scope note evidence is needed to fill a missing parent fact
- statement-row vs note precedence needs to be locked more tightly
- a new, explicitly scoped parent note missing-status contract is required by the chosen anchors

- [ ] **Step 2: Implement the minimum bounded hardening**

No new broad regex scans. No issuer-specific branches.

Do not extend consolidated `cash_health_missing_status` by default just because `P4D` exists; only add a parent note status surface if a real parent note path is introduced and tested.

- [ ] **Step 3: Re-run the focused note / ingestion tests**

```bash
uv run pytest tests/unit/test_note_disclosure_ingestion.py tests/unit/test_fact_pipeline.py -q -o addopts=
```

- [ ] **Step 4: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py financial-report-analysis/tests/unit/test_fact_pipeline.py
git commit -m "feat: harden turtle p4d notes bridge precedence"
```

Skip this task entirely if diagnostics show `P4B` contract is already sufficient.

---

### Task 5: Add Focused Real-PDF Anchor Regressions

**Files:**

- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

- [ ] **Step 1: Add failing anchor regressions**

Add focused regressions for the onboarding anchors.

The regressions should assert only the current locked contract:

- which parent metrics surface on the deterministic path
- which remain `absent`
- which remain `not_surfaced`
- that `parent_company` and `consolidated` are not silently collapsed
- statement-row precedence over notes where applicable

- [ ] **Step 2: Run the new regressions and confirm failure**

```bash
uv run pytest tests/integration/test_semantic_recovery_regressions.py -q -o addopts=
```

Use targeted node selection while iterating.

- [ ] **Step 3: Make the minimum implementation changes needed for the anchors**

Adjust code only as needed so the anchor contracts pass without issuer-specific branches.

- [ ] **Step 4: Re-run the focused regressions**

Re-run only the targeted nodes added for `P4D`.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py
git commit -m "feat: add turtle p4d anchor regressions"
```

Include code files too if Task 5 required more than test edits.

---

### Task 6: Fallback Review And Closeout

**Files:**

- Modify only if necessary:
  - fallback model/service files
  - paired tests

- [ ] **Step 1: Confirm whether new fallback is actually needed**

Only expand fallback if focused diagnostics show a stable local ambiguity that deterministic structure + semantics cannot resolve.

Likely non-fallback problems in this phase:

- parent/consolidated scope detection
- missing row families
- precedence bugs

- [ ] **Step 2: If needed, add the smallest bounded fallback support**

No new broad document-level fallback surfaces.

- [ ] **Step 3: Focused closeout verification**

At minimum, run:

```bash
uv run pytest tests/unit/test_table_structure.py tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py -q -o addopts=
uv run pytest tests/unit/test_fact_pipeline.py -q -o addopts=
uv run pytest tests/integration/test_semantic_recovery_regressions.py -q -o addopts=
uv run ruff check src tests
```

Use targeted node selection for the real-PDF file while iterating.

- [ ] **Step 4: Commit closeout if needed**

```bash
git add .
git commit -m "feat: close out turtle p4d parent scope follow-up"
```

## Definition Of Done

`P4D` is complete when:

- parent statement scope is stable and explicit
- the target parent metric families produce candidate facts with `entity_scope = parent_company`
- notes bridge does not override higher-priority parent statement facts
- focused anchors lock the current parent / notes contract
- fallback has not been expanded unless diagnostics proved it necessary
