# Turtle P4D Parent Scope And Notes Follow-up Sample Onboarding

> **Status:** Updated baseline after Task 5 focused anchors
> **Phase:** Turtle Parent Scope And Notes Follow-up P4D
> **Date:** 2026-04-23

## 1. Purpose

This onboarding artifact records the initial anchor set for `P4D`, which is focused on:

- `parent_company` statement-row extraction
- parent/consolidated scope separation
- bounded notes bridge hardening only where already justified by `P4B`

It started as a phase-entry artifact and has now been updated to reflect the current focused real-PDF baseline:

- `present`: currently expected to be independently disclosed and intended to surface through the supported `P4D` path
- `absent`: the current sample family appears not to disclose the metric independently in the relevant scope
- `not_surfaced`: the sample family likely contains the metric or track, but the current supported path does not yet stably surface it
- `out_of_scope`: the metric/track is not a valid expectation for this anchor in the current phase

## 2. Target Metric Set

Canonical metric ids for `P4D`:

- parent `cash`
- `lt_eqt_invest`
- parent `st_borr`
- parent `lt_borr`
- parent `bond_payable`
- parent `non_cur_liab_due_1y`
- parent `total_assets`
- parent `total_liabilities`
- parent `equity`
- parent `equity_attributable_to_owners` only when explicitly disclosed on the parent track
- `restricted_cash`
- `time_deposits_or_wealth_products`
- `interest_paid_cash`

Parent-scope naming note:

- Turtle parent `money_cap` continues to map to canonical `cash` with `entity_scope = parent_company`
- `lt_eqt_invest` is the `P4D`-introduced canonical id for parent long-term equity investments

## 3. Anchor Selection

`P4D` uses three anchors:

1. `601919 2025`
   CN annual anchor with explicit parent statements; primary deterministic parent-scope proof point
2. `02498 2022`
   HK cleaner-format annual anchor; useful for confirming when parent-scope expectations are truly `out_of_scope`
3. `09987 2025`
   HK mixed-structure annual anchor; useful for stressing parent/consolidated separation and notes-bridge precedence

---

## Anchor 1: CN 601919 2025

### Metadata

- `sample_id`: `cn-601919-2025-annual-zh`
- `market`: `CN`
- `language`: `zh`
- `issuer_code`: `601919`
- `report_type`: `annual`
- `period_end`: `2025-12-31`
- `report_family`: `cn_parent_and_consolidated_statement_row`
- `target_phase`: `Turtle Parent Scope And Notes Follow-up P4D`
- `target_metric_ids`: `cash`, `lt_eqt_invest`, `st_borr`, `lt_borr`, `bond_payable`, `non_cur_liab_due_1y`, `total_assets`, `total_liabilities`, `equity`, `equity_attributable_to_owners`, `restricted_cash`, `time_deposits_or_wealth_products`, `interest_paid_cash`
- `known_special_shape`: `Explicit parent_only balance sheet / income statement / cash flow statement blocks are already recovered`

### Current Expected Scope Availability

- `consolidated`: clearly available
- `parent_company`: clearly available

### Current Expected Onboarding Classification

- `present`:
  - parent `cash`
  - `lt_eqt_invest`
  - parent `total_assets`
- `absent`: none currently expected at phase-entry
- `not_surfaced`:
  - parent `st_borr`
  - parent `lt_borr`
  - parent `bond_payable`
  - parent `non_cur_liab_due_1y`
  - parent `total_liabilities`
  - parent `equity`
  - parent `equity_attributable_to_owners`
  - `restricted_cash`
  - `time_deposits_or_wealth_products`
  - `interest_paid_cash`
- `out_of_scope`: none at anchor scope

### Current Expected Failure Classification

- `structure_recovery_gap`: not the expected main blocker; parent tables are already present
- `scope_detection_gap`: partially relevant because parent facts must stay separate from consolidated facts
- `semantic_normalization_gap`: likely for parent-specific row families once scope is known
- `metric_mapping_gap`: now reduced for `lt_eqt_invest`; still likely for parent liabilities / equity families
- `statement_row_candidate_gap`: likely for parent liabilities / equity rows after scope detection
- `note_bridge_gap`: possible for any parent-scope extension of the existing cash-health family

### Anchor Notes

- This is the primary `P4D` deterministic proof anchor because current diagnostics already show explicit `parent_only` tables for balance sheet, income statement, and cash flow statement.
- Current extraction probes already surface parent `cash`, `lt_eqt_invest`, and parent `total_assets`, but the broader parent metric family is not yet under a stable `P4D` contract.
- This anchor should be treated as the main place to validate scope detection, parent candidate-fact emission, and precedence between parent/consolidated tracks.

---

## Anchor 2: HK 02498 2022

### Metadata

- `sample_id`: `hk-02498-2022-annual-en`
- `market`: `HK`
- `language`: `en`
- `issuer_code`: `02498`
- `report_type`: `annual`
- `period_end`: `2022-12-31`
- `report_family`: `hk_cleaner_format_consolidated_only`
- `target_phase`: `Turtle Parent Scope And Notes Follow-up P4D`
- `target_metric_ids`: `cash`, `lt_eqt_invest`, `st_borr`, `lt_borr`, `bond_payable`, `non_cur_liab_due_1y`, `total_assets`, `total_liabilities`, `equity`, `equity_attributable_to_owners`, `restricted_cash`, `time_deposits_or_wealth_products`, `interest_paid_cash`
- `known_special_shape`: `Cleaner HK annual format with stable consolidated statement-row coverage but no confirmed parent_only statement blocks in current diagnostics`

### Current Expected Scope Availability

- `consolidated`: clearly available
- `parent_company`: not currently confirmed

### Current Expected Onboarding Classification

- `present`: none currently locked for the parent track
- `absent`:
  - `restricted_cash`
  - `time_deposits_or_wealth_products`
  - `interest_paid_cash`
- `not_surfaced`: none currently expected at phase-entry
- `out_of_scope`:
  - parent `cash`
  - `lt_eqt_invest`
  - parent `st_borr`
  - parent `lt_borr`
  - parent `bond_payable`
  - parent `non_cur_liab_due_1y`
  - parent `total_assets`
  - parent `total_liabilities`
  - parent `equity`
  - parent `equity_attributable_to_owners`

### Current Expected Failure Classification

- `structure_recovery_gap`: not the expected main blocker for the consolidated track
- `scope_detection_gap`: this is the main relevant question; current diagnostics do not show a stable parent track
- `semantic_normalization_gap`: not the expected main blocker at phase-entry
- `metric_mapping_gap`: low-priority until a parent track is confirmed
- `statement_row_candidate_gap`: low-priority until a parent track is confirmed
- `note_bridge_gap`: not the main blocker; current cash-health contract already points to `absent`

### Anchor Notes

- This anchor is useful because it prevents `P4D` from over-assuming that every HK annual must expose a parent track.
- It should be treated as the cleaner-format negative-control anchor for parent scope.
- If later diagnostics find stable separate-company statements here, the likely change is to move specific parent metrics from `out_of_scope` to `not_surfaced`, not to expand phase scope.

---

## Anchor 3: HK 09987 2025

### Metadata

- `sample_id`: `hk-09987-2025-annual-en`
- `market`: `HK`
- `language`: `en`
- `issuer_code`: `09987`
- `report_type`: `annual`
- `period_end`: `2025-12-31`
- `report_family`: `hk_mixed_structure_parent_and_note_bridge_stress`
- `target_phase`: `Turtle Parent Scope And Notes Follow-up P4D`
- `target_metric_ids`: `cash`, `lt_eqt_invest`, `st_borr`, `lt_borr`, `bond_payable`, `non_cur_liab_due_1y`, `total_assets`, `total_liabilities`, `equity`, `equity_attributable_to_owners`, `restricted_cash`, `time_deposits_or_wealth_products`, `interest_paid_cash`
- `known_special_shape`: `Current diagnostics show a strong notes bridge path and only weak parent_only table evidence`

### Current Expected Scope Availability

- `consolidated`: clearly available
- `parent_company`: weakly indicated but not yet a stable deterministic proof path

### Current Expected Onboarding Classification

- `present`:
  - `restricted_cash`
  - `time_deposits_or_wealth_products`
  - `interest_paid_cash`
- `absent`: none currently expected at phase-entry
- `not_surfaced`:
  - parent `cash`
  - `lt_eqt_invest`
  - parent `st_borr`
  - parent `lt_borr`
  - parent `bond_payable`
  - parent `non_cur_liab_due_1y`
  - parent `total_assets`
  - parent `total_liabilities`
  - parent `equity`
  - parent `equity_attributable_to_owners`
- `out_of_scope`: none at anchor scope

### Current Expected Failure Classification

- `structure_recovery_gap`: likely the main blocker for parent statement rows
- `scope_detection_gap`: highly relevant because mixed-structure documents can blur parent/consolidated separation
- `semantic_normalization_gap`: possible once a parent-only block is recovered
- `metric_mapping_gap`: possible for `lt_eqt_invest` or parent equity once row families surface
- `statement_row_candidate_gap`: possible after scope recovery
- `note_bridge_gap`: not the expected main blocker because the existing `P4B` notes family is already strong here

### Anchor Notes

- This is the mixed-structure stress anchor for `P4D`, similar to how `09987` has been used in earlier note/disclosure phases.
- Current diagnostics show the notes bridge is already strong, while the parent track is still too weak to count as a stable deterministic statement-row proof path.
- This anchor is mainly for validating:
  - parent/consolidated separation
  - statement-row vs note precedence
  - not over-promoting notes-based positives into parent-statement success

---

## 4. Current Baseline Summary

Current `P4D` phase-entry expectations are:

- `601919 2025`:
  primary deterministic parent-scope anchor
- `02498 2022`:
  cleaner-format HK anchor where parent track is currently `out_of_scope`
- `09987 2025`:
  mixed-structure stress anchor where notes bridge is already positive but parent statement-row coverage is still `not_surfaced`

## 5. Implementation Guardrails

- Do not use issuer-specific branches.
- Do not let notes bridge silently override parent statement-row facts.
- Do not treat weak `parent_only` hints as proof that a parent metric is already `present`.
- If later implementation expands the parent metric family further, re-run focused diagnostics and update this artifact before broadening the locked anchor contract.
