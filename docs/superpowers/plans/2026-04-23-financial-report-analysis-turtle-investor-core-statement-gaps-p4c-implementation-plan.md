# P4C Turtle Investor Core Statement Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining pre-P5 core statement coverage gaps for Turtle by adding deterministic-first support for 12 high-value statement metrics: `revenue`, `oper_cost`, `operate_profit`, `n_income`, `total_assets`, `total_liab`, `total_hldr_eqy_exc_min_int`, `n_cashflow_act`, `n_cashflow_inv_act`, `n_cash_flows_fnc_act`, `c_pay_to_staff`, and `c_paid_for_taxes`.

**Architecture:** Preserve the existing main path: `pdf -> structure recovery -> normalized table semantics -> metric mapping registry -> candidate facts -> canonical facts`. Prefer statement-row deterministic coverage. Use bounded semantic fallback only for row-label ambiguity when the existing framework already supports it.

**Tech Stack:** Python 3.12, pytest, Ruff, pypdf, existing `financial_report_analysis` table semantics / registry / ingestion / pipeline modules.

---

## Scope Check

This plan covers one narrow subsystem: P4C investor core statement gaps for 12 main-statement metrics only.

It does **not** cover:

- parent-company statement expansion
- broad note/disclosure bridge work
- DPS / buyback / narrative policy parsing
- multi-year dataset schema
- new storage / lineage / recompute surfaces

## Source Policy

All tasks in this plan assume statement-row facts remain the primary path.

Priority order:

1. `statement_row`
2. bounded semantic fallback for local row-label ambiguity only

This phase should not introduce new note/disclosure supplement paths for the target metrics unless the paired spec is explicitly revised.

## Onboarding Requirement

Before implementation starts, create a dedicated onboarding artifact for the chosen anchors. It must follow:

- `docs/architecture-analysis/new-report-sample-onboarding-and-field-variance-process.md`

At minimum, it should record:

- one CN annual anchor
- one HK cleaner-format annual anchor
- one HK mixed-structure annual anchor
- target metric set
- expected `present / absent / not_surfaced / out_of_scope`
- failure classification by metric family if the phase-entry diagnostics are not yet fully stable

## File Structure

Expected files to touch:

- `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
- `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`
- `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- `financial-report-analysis/tests/unit/test_table_semantics.py`
- `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`
- onboarding artifact under `docs/architecture-analysis/`

Depending on what diagnostics show, the work may also touch:

- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py`
- `financial-report-analysis/src/financial_report_analysis/semantic_fallback/service.py`
- paired fallback tests

---

### Task 0: Create P4C Onboarding Artifact

**Files:**

- Add: `docs/architecture-analysis/2026-04-23-turtle-investor-core-statement-gaps-p4c-sample-onboarding.md`

- [ ] **Step 1: Create the onboarding artifact**

Record the fixed anchors, target metric set, and current phase-entry expectations for:

- `revenue`
- `oper_cost`
- `operate_profit`
- `n_income`
- `total_assets`
- `total_liab`
- `total_hldr_eqy_exc_min_int`
- `n_cashflow_act`
- `n_cashflow_inv_act`
- `n_cash_flows_fnc_act`
- `c_pay_to_staff`
- `c_paid_for_taxes`

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

- [ ] **Step 3: Commit onboarding if created**

```bash
git add docs/architecture-analysis/2026-04-23-turtle-investor-core-statement-gaps-p4c-sample-onboarding.md
git commit -m "docs: add turtle p4c onboarding artifact"
```

---

### Task 1: Lock Registry Contract For The 12 P4C Metrics

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_metric_mapping_registry.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`

- [ ] **Step 1: Add failing registry tests**

Add focused tests that assert the registry can match representative HK/CN row families for all 12 metrics.

Include examples such as:

- `revenue`:
  - `revenue`
  - `turnover`
  - `营业收入`
- `oper_cost`:
  - `cost of sales`
  - `cost of revenue`
  - `营业成本`
- `operate_profit`:
  - `operating profit`
  - `profit from operations`
  - `营业利润`
- `n_income`:
  - `net income`
  - `profit for the year`
  - `净利润`
- `total_assets`:
  - `total assets`
  - `资产总计`
- `total_liab`:
  - `total liabilities`
  - `负债合计`
- `total_hldr_eqy_exc_min_int`:
  - `equity attributable to owners of the parent`
  - `归属于母公司股东权益`
- `n_cashflow_act`:
  - `net cash generated from operating activities`
  - `经营活动产生的现金流量净额`
- `n_cashflow_inv_act`:
  - `net cash used in investing activities`
  - `投资活动产生的现金流量净额`
- `n_cash_flows_fnc_act`:
  - `net cash generated from financing activities`
  - `筹资活动产生的现金流量净额`
- `c_pay_to_staff`:
  - `cash paid to and on behalf of employees`
  - `支付给职工以及为职工支付的现金`
- `c_paid_for_taxes`:
  - `taxes paid`
  - `支付的各项税费`

- [ ] **Step 2: Add negative controls**

Add negative-control tests to ensure the new label families do not swallow:

- `gross profit`
- `ebitda`
- `adjusted net profit`
- `profit for the year attributable to owners of the parent`
- `profit attributable to owners of the parent`
- `归属于母公司股东的净利润`
- `other income`
- `investment income`
- `cash and cash equivalents`
- `total equity` when owner-attributable scope is unclear

- [ ] **Step 3: Implement the minimum registry additions**

Update `metric_mapping.py` with minimal, explicit mapping definitions for the 12 target metrics.

- [ ] **Step 4: Re-run the focused registry tests**

```bash
uv run pytest tests/unit/test_metric_mapping_registry.py -q -o addopts=
```

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py financial-report-analysis/tests/unit/test_metric_mapping_registry.py
git commit -m "feat: add turtle p4c metric registry coverage"
```

---

### Task 2: Lock Row-Normalization Contract

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_table_semantics.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py`

- [ ] **Step 1: Add failing row-normalization tests**

Add focused tests to ensure the target row families normalize into stable labels without collapsing into the wrong metric families.

- [ ] **Step 2: Implement the minimum normalization support**

Add only the normalization rules needed for the 12 metrics.

Do not:

- collapse owner-attributable equity into generic `total equity`
- collapse `n_income` into `n_income_attr_p`
- collapse `operate_profit` into `total_profit`

- [ ] **Step 3: Re-run the focused semantics tests**

```bash
uv run pytest tests/unit/test_table_semantics.py -q -o addopts=
```

- [ ] **Step 4: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/table_semantics.py financial-report-analysis/tests/unit/test_table_semantics.py
git commit -m "feat: add turtle p4c row semantics"
```

---

### Task 3: Verify Table Fact Builder And Ingestion Contract

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py` only if needed

- [ ] **Step 1: Add failing unit tests for candidate-fact emission**

Add unit tests that prove the table fact path emits correctly typed candidate facts for:

- income statement metrics
- balance sheet totals
- cash flow metrics

The tests should verify:

- `statement_type`
- `period_id`
- `entity_scope`
- `extensions.table_kind`
- deterministic provenance

- [ ] **Step 2: Add a focused ingestion smoke if needed**

If any target metric family is not flowing cleanly through `PdfIngestionAdapter`, add a narrow ingestion-level unit test similar to the existing P4B pattern.

- [ ] **Step 3: Implement only the minimum needed changes**

Prefer fixing registry / normalization / table-fact-builder interactions before touching ingestion wiring.

- [ ] **Step 4: Re-run the focused unit tests**

```bash
uv run pytest tests/unit/test_fact_pipeline.py -q -o addopts=
```

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/tests/unit/test_fact_pipeline.py financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py
git commit -m "feat: wire turtle p4c statement candidates"
```

Skip `pdf_ingestion.py` in the commit if it did not change.

---

### Task 4: Add Focused Real-PDF Anchor Regressions

**Files:**

- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

- [ ] **Step 1: Add failing anchor regressions**

Add focused regressions for the chosen CN/HK anchors from the onboarding artifact.

The regressions should assert only the current locked contract:

- which target metrics are surfaced
- which remain `absent`
- which remain `not_surfaced`
- deterministic-first provenance where applicable

Do not over-assert every possible field in the statement.

- [ ] **Step 2: Run the new regressions and confirm failure**

```bash
uv run pytest tests/integration/test_semantic_recovery_regressions.py -q -o addopts=
```

Use targeted node selection while iterating.

- [ ] **Step 3: Make the minimum implementation changes needed for the anchors**

Adjust code only as needed so the anchor contracts pass without issuer-specific branches.

- [ ] **Step 4: Re-run the focused regressions**

Re-run only the targeted nodes added for P4C.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py
git commit -m "feat: add turtle p4c anchor regressions"
```

Include code files too if Task 4 required more than test edits.

---

### Task 5: Add Bounded Fallback Support Only If Needed

**Files:**

- Modify only if necessary:
  - `financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py`
  - `financial-report-analysis/src/financial_report_analysis/semantic_fallback/service.py`
  - paired fallback tests

- [ ] **Step 1: Decide whether fallback work is necessary**

If the P4C anchors are stable with deterministic coverage, mark this task `not needed` and skip to Task 6.

- [ ] **Step 2: If needed, add failing fallback tests**

Restrict new tests to:

- bounded output space
- explicit trigger
- explicit budget
- negative controls

- [ ] **Step 3: Implement only the minimum bounded fallback extension**

Fallback must stay limited to row-label ambiguity resolution. It must not become a free-form extraction path for the 12 metrics.

- [ ] **Step 4: Re-run the focused fallback tests**

```bash
uv run pytest tests/unit/test_semantic_fallback_models.py tests/unit/test_semantic_fallback_service.py -q -o addopts=
```

- [ ] **Step 5: Commit only if Task 5 was needed**

```bash
git add financial-report-analysis/src/financial_report_analysis/semantic_fallback/models.py financial-report-analysis/src/financial_report_analysis/semantic_fallback/service.py financial-report-analysis/tests/unit/test_semantic_fallback_models.py financial-report-analysis/tests/unit/test_semantic_fallback_service.py
git commit -m "feat: add bounded turtle p4c fallback support"
```

---

### Task 6: Close Out P4C With Focused Verification

**Files:**

- Modify if needed: this plan file only to mark outcomes or notes

- [ ] **Step 1: Run focused unit regressions**

```bash
uv run pytest tests/unit/test_metric_mapping_registry.py tests/unit/test_table_semantics.py tests/unit/test_fact_pipeline.py -q -o addopts=
```

Add fallback tests here only if Task 5 was required.

- [ ] **Step 2: Run focused real-PDF anchor regressions**

Run only the P4C regression nodes added in Task 4.

- [ ] **Step 3: Run non-regression checks for earlier Turtle phases**

Select the smallest prior-phase regressions that are at risk from the P4C changes.

- [ ] **Step 4: Run Ruff**

```bash
uv run ruff check src tests
```

- [ ] **Step 5: Record whether Task 5 was needed**

If deterministic coverage closed the anchors, explicitly note that Task 5 was skipped.

---

## Definition of Done

P4C is complete when:

- the 12 target metrics have stable registry / semantics contracts
- focused anchors pass with deterministic-first behavior
- missing-status expectations are recorded in the onboarding artifact
- no issuer-specific branches were introduced
- P5 can rely on these metrics as the main multi-year statement skeleton

## Execution Notes

- Prefer subagent-driven execution, but Tasks 1, 2, 3, and 4 should generally run serially because they touch overlapping registry / semantics / regression surfaces.
- Do not start P4D or P5 implementation from this plan.
- If diagnostics show that one or more metrics are actually blocked by parent-scope or note-bridge work, stop and reclassify them rather than widening P4C.
