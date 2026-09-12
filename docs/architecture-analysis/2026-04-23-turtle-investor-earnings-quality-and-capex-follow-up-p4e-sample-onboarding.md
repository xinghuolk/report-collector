# Turtle P4E Investor Earnings Quality And Capex Follow-up Sample Onboarding

> **Status:** Updated baseline after Task 3 focused anchors
> **Phase:** Turtle Investor Earnings Quality And Capex Follow-up P4E
> **Date:** 2026-04-23

## 1. Purpose

This onboarding artifact records the initial anchor set for `P4E`, which is focused on:

- non-parent statement-row extraction for earnings-quality and capex follow-up fields
- deterministic normalization / registry mapping / candidate-fact recovery
- keeping `P4E` inside a narrow statement-first scope instead of reopening a broad note/disclosure bridge

It started as a phase-entry artifact and has now been updated to reflect the current focused real-PDF baseline:

- `present`: currently expected to be independently disclosed and intended to surface through the supported `P4E` path
- `absent`: the current sample family appears not to disclose the metric independently in the relevant scope
- `not_surfaced`: the sample family likely contains the metric or row family, but the current supported path does not yet stably surface it
- `out_of_scope`: the metric/track is not a valid expectation for this anchor in the current phase

For this updated baseline, a metric should only remain `not_surfaced` when raw evidence exists or is suspected, but the current explicit `P4E` contract still does not stably emit the fact.

## 2. Target Metric Set

Canonical metric ids for `P4E`:

- `fix_assets`
- `cip`
- `rd_exp`
- `invest_income`
- `asset_disp_income`
- `n_recp_disp_fiolta`
- `c_recp_return_invest`

## 3. Anchor Selection

`P4E` uses three anchors:

1. `601919 2025`
   CN annual anchor with the cleanest currently observed statement-row evidence across the target field family
2. `02498 2022`
   HK cleaner-format annual anchor; useful for identifying the smaller English subset that is truly available without forcing a bridge phase
3. `09987 2025`
   HK mixed-format annual anchor; primarily a negative-control / not-surfaced stress sample for keeping `P4E` statement-first

---

## Anchor 1: CN 601919 2025

### Metadata

- `sample_id`: `cn-601919-2025-annual-zh`
- `market`: `CN`
- `language`: `zh`
- `issuer_code`: `601919`
- `report_type`: `annual`
- `period_end`: `2025-12-31`
- `report_family`: `cn_statement_row_earnings_quality_and_capex`
- `target_phase`: `Turtle Investor Earnings Quality And Capex Follow-up P4E`
- `target_metric_ids`: `fix_assets`, `cip`, `rd_exp`, `invest_income`, `asset_disp_income`, `n_recp_disp_fiolta`, `c_recp_return_invest`
- `known_special_shape`: `Current diagnostics show explicit consolidated statement rows for the full target family, plus parallel parent-only rows that are out of scope for P4E`

### Current Expected Scope Availability

- `consolidated`: clearly available
- `parent_company`: present in the sample family, but out of scope for `P4E`

### Current Expected Onboarding Classification

- `present`:
  - `fix_assets`
  - `cip`
  - `rd_exp`
  - `c_recp_return_invest`
- `absent`: none currently expected at phase-entry
- `not_surfaced`:
  - `invest_income`
  - `asset_disp_income`
  - `n_recp_disp_fiolta`
- `out_of_scope`:
  - the parent-company duplicates of the same family

### Current Expected Failure Classification

- `structure_recovery_gap`: low; the relevant rows are already visible in extracted statement tables
- `semantic_normalization_gap`: now mainly relevant to the remaining `invest_income`, `asset_disp_income`, and `n_recp_disp_fiolta` subset
- `metric_mapping_gap`: now mainly relevant to the remaining `invest_income`, `asset_disp_income`, and `n_recp_disp_fiolta` subset
- `statement_row_candidate_gap`: now mainly relevant to the remaining `invest_income`, `asset_disp_income`, and `n_recp_disp_fiolta` subset
- `fallback_gap`: not expected to be the primary blocker

### Anchor Notes

- This is the primary positive anchor for `P4E`.
- Current diagnostics now show a stable deterministic subset for `fix_assets`, `cip`, `rd_exp`, and `c_recp_return_invest`, while the remaining three metrics still do not surface through the current contract.
- `P4E` should continue using this sample to expand the deterministic subset without opening a new bridge path.

---

## Anchor 2: HK 02498 2022

### Metadata

- `sample_id`: `hk-02498-2022-annual-en`
- `market`: `HK`
- `language`: `en`
- `issuer_code`: `02498`
- `report_type`: `annual`
- `period_end`: `2022-12-31`
- `report_family`: `hk_cleaner_format_partial_statement_row_subset`
- `target_phase`: `Turtle Investor Earnings Quality And Capex Follow-up P4E`
- `target_metric_ids`: `fix_assets`, `cip`, `rd_exp`, `invest_income`, `asset_disp_income`, `n_recp_disp_fiolta`, `c_recp_return_invest`
- `known_special_shape`: `Current diagnostics show a cleaner English annual layout, but only a stable standalone construction-in-progress row was confirmed during phase-entry probes`

### Current Expected Scope Availability

- `consolidated`: clearly available
- `parent_company`: out of scope for `P4E`

### Current Expected Onboarding Classification

- `present`:
  - `fix_assets`
  - `cip`
- `absent`: none currently expected at phase-entry
- `not_surfaced`:
  - `rd_exp`
  - `invest_income`
  - `asset_disp_income`
  - `n_recp_disp_fiolta`
  - `c_recp_return_invest`
- `out_of_scope`:
  - parent/company-only tracks

### Current Expected Failure Classification

- `structure_recovery_gap`: likely for the remaining detailed English income-statement / cash-flow-detail rows
- `semantic_normalization_gap`: relevant for the remaining not-yet-surfaced subset
- `metric_mapping_gap`: relevant, but probably secondary to row visibility for the remaining subset
- `statement_row_candidate_gap`: likely for the remaining not-yet-surfaced subset
- `fallback_gap`: not expected to be the first thing to open

### Anchor Notes

- This anchor is useful because it stops `P4E` from overfitting to CN annual shapes.
- It remains a partial-positive anchor rather than a full-family proof sample.
- The current deterministic subset here is `fix_assets + cip`; the rest of the family should remain `not_surfaced` until proven otherwise.

---

## Anchor 3: HK 09987 2025

### Metadata

- `sample_id`: `hk-09987-2025-annual-en`
- `market`: `HK`
- `language`: `en`
- `issuer_code`: `09987`
- `report_type`: `annual`
- `period_end`: `2025-12-31`
- `report_family`: `hk_mixed_format_negative_control`
- `target_phase`: `Turtle Investor Earnings Quality And Capex Follow-up P4E`
- `target_metric_ids`: `fix_assets`, `cip`, `rd_exp`, `invest_income`, `asset_disp_income`, `n_recp_disp_fiolta`, `c_recp_return_invest`
- `known_special_shape`: `Current diagnostics show a mixed-format annual where the phase-entry keyword probe only found a noisy property-plant / lease-related row and no clean target-family surfacing`

### Current Expected Scope Availability

- `consolidated`: available, but not yet a stable proof path for the P4E target family
- `parent_company`: out of scope for `P4E`

### Current Expected Onboarding Classification

- `present`: none currently locked in the current baseline
- `absent`: none currently expected at phase-entry
- `not_surfaced`:
  - `fix_assets`
  - `cip`
  - `rd_exp`
  - `invest_income`
  - `asset_disp_income`
  - `n_recp_disp_fiolta`
  - `c_recp_return_invest`
- `out_of_scope`:
  - parent/company-only tracks

### Current Expected Failure Classification

- `structure_recovery_gap`: likely the primary blocker
- `semantic_normalization_gap`: relevant because mixed-format rows may blur target labels and strong negatives
- `metric_mapping_gap`: secondary at phase-entry
- `statement_row_candidate_gap`: likely after structure recovery
- `fallback_gap`: should stay secondary unless local ambiguity becomes stable and well-bounded

### Anchor Notes

- This is the mixed-format negative-control anchor for `P4E`.
- The main purpose here is to make sure we do not widen `P4E` into a bridge-heavy phase just to force positives.
- Strong negatives to watch in this family include:
  - right-of-use assets
  - investment properties
  - capitalized development costs
  - fair value changes
  - interest income
  - generic investing cash inflows

---

## 4. Current Baseline Summary

Current `P4E` baseline expectations are:

- `601919 2025`:
  primary positive anchor with a current deterministic subset of `fix_assets + cip + rd_exp + c_recp_return_invest`
- `02498 2022`:
  cleaner-format HK partial-positive anchor with current deterministic subset `fix_assets + cip`
- `09987 2025`:
  mixed-format negative-control / not-surfaced anchor

## 5. Implementation Guardrails

- Do not use issuer-specific branches.
- Keep `P4E` statement-first; do not reopen a broad note/disclosure bridge just because mixed-format anchors are weak.
- Treat strong negative-control labels as first-class contract requirements, not as optional cleanup.
- If later implementation expands the deterministic subset further, re-run focused diagnostics and update this artifact before broadening the locked anchor contract.
