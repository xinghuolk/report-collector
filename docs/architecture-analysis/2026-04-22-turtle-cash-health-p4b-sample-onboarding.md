# Turtle Cash-Health P4B Sample Onboarding

> Status: Draft for review
> Scope: P4B onboarding artifact only
> Important: The classifications below are planning expectations used to start P4B diagnostics. They are not confirmed extraction results.

## Purpose

This artifact records the fixed anchors, minimum onboarding metadata, and current expected missing-status / failure-classification expectations for the proposed P4B cash-health bridge phase.

Target P4B scope for this artifact:

- `restricted_cash`
- `interest_paid_cash`
- `time_deposits_or_wealth_products`

These metrics are treated as high-value note / disclosure bridge candidates driven by Turtle v0.15 cash-health needs, not as a broad parent-scope statement-coverage phase.

Status vocabulary used in this artifact:

- `present`: expected to be independently disclosed and intended to surface in the current P4B scope
- `absent`: expected not to have independent disclosure in the sample
- `not_surfaced`: may exist in the sample family, but current onboarding expectation treats it as not yet reliably surfaced by the supported path
- `out_of_scope`: intentionally excluded from the current P4B extraction target for this anchor

Failure classification vocabulary used in this artifact:

- `structure_recovery_gap`
- `semantic_normalization_gap`
- `metric_mapping_gap`
- `note_disclosure_supplement_gap`

## Common P4B Metric Set

`target_metric_ids` for all three anchors:

- `restricted_cash`
- `interest_paid_cash`
- `time_deposits_or_wealth_products`

## Anchor 1: CN 601919 2025

### Metadata

- `sample_id`: `cn-601919-2025-annual-zh`
- `market`: `CN`
- `language`: `zh`
- `issuer_code`: `601919`
- `report_type`: `annual`
- `period_end`: `2025-12-31`
- `report_family`: `cn_note_disclosure_cash_health`
- `target_phase`: `Turtle Cash-Health Notes Bridge P4B`
- `target_metric_ids`: `restricted_cash`, `interest_paid_cash`, `time_deposits_or_wealth_products`
- `known_special_shape`: `statement_row primary facts may exist, but target metrics are expected to rely on bounded note/disclosure or cash-flow supplement paths`

### Current Expected Onboarding Classification

- `present`: none currently locked at plan level
- `absent`: none currently locked at plan level
- `not_surfaced`: `restricted_cash`, `interest_paid_cash`, `time_deposits_or_wealth_products`
- `out_of_scope`: none currently expected at anchor scope

### Current Expected Failure Classification

- `structure_recovery_gap`: possible if note blocks, cash-flow supplement rows, or bounded tables are not stably recovered
- `semantic_normalization_gap`: possible for Chinese note labels with high wording variance
- `metric_mapping_gap`: possible after note rows are recovered but do not map into stable cash-health identities
- `note_disclosure_supplement_gap`: expected main bucket until bounded note/disclosure bridge is confirmed

### Anchor Notes

- This anchor is the CN planning anchor for P4B.
- Current diagnostics did not find stable text-level hits for `restricted_cash`, `interest_paid_cash`, or `time_deposits_or_wealth_products` in the current extraction probe, so the phase-entry expectation remains conservative.
- This phase should not promote broad parent-company note fields through this anchor.

## Anchor 2: HK 02498 2022

### Metadata

- `sample_id`: `hk-02498-2022-annual-en`
- `market`: `HK`
- `language`: `en`
- `issuer_code`: `02498`
- `report_type`: `annual`
- `period_end`: `2022-12-31`
- `report_family`: `hk_note_disclosure_cash_health`
- `target_phase`: `Turtle Cash-Health Notes Bridge P4B`
- `target_metric_ids`: `restricted_cash`, `interest_paid_cash`, `time_deposits_or_wealth_products`
- `known_special_shape`: `statement-row balance-sheet path may be stable, but target metrics are expected to come from bounded note/disclosure or cash-flow note paths`

### Current Expected Onboarding Classification

- `present`: `restricted_cash`
- `absent`: `interest_paid_cash`, `time_deposits_or_wealth_products`
- `not_surfaced`: none currently expected at plan level
- `out_of_scope`: none currently expected at anchor scope

### Current Expected Failure Classification

- `structure_recovery_gap`: not the expected main gap for `restricted_cash` based on current probe
- `semantic_normalization_gap`: possible for English label families such as restricted deposits or pledged cash if note rows are recovered but not normalized
- `metric_mapping_gap`: possible for `restricted_cash` once bounded rows are recovered
- `note_disclosure_supplement_gap`: still the expected main bucket for turning the restricted-cash disclosure into stable candidate / canonical behavior

### Anchor Notes

- This anchor is the HK cleaner-format planning anchor for P4B.
- It should prove the reusable HK note/disclosure bridge contract before mixed-structure handling is treated as stable.
- Current diagnostics found a clear restricted-cash style disclosure in the annual report, with wording equivalent to restricted cash / restricted monetary funds under restricted ownership or use.
- Current diagnostics did not find stable text-level hits for `interest_paid_cash` or `time_deposits_or_wealth_products`, so they are treated as `absent` for the current planning baseline unless later probing proves otherwise.

## Anchor 3: HK 09987 2025

### Metadata

- `sample_id`: `hk-09987-2025-annual-en`
- `market`: `HK`
- `language`: `en`
- `issuer_code`: `09987`
- `report_type`: `annual`
- `period_end`: `2025-12-31`
- `report_family`: `hk_mixed_structure_note_disclosure_cash_health`
- `target_phase`: `Turtle Cash-Health Notes Bridge P4B`
- `target_metric_ids`: `restricted_cash`, `interest_paid_cash`, `time_deposits_or_wealth_products`
- `known_special_shape`: `mixed statement and note family; target metrics are expected to depend on bounded note/disclosure supplement`

### Current Expected Onboarding Classification

- `present`: `restricted_cash`, `interest_paid_cash`, `time_deposits_or_wealth_products`
- `absent`: none currently locked at plan level
- `not_surfaced`: none currently expected at plan level
- `out_of_scope`: none currently expected at anchor scope

### Current Expected Failure Classification

- `structure_recovery_gap`: possible if mixed-structure note families are not stably recovered enough to feed bounded supplement logic
- `semantic_normalization_gap`: possible for bridging `restricted_cash` from restricted time-deposit language or for distinguishing deposit/investment subtypes
- `metric_mapping_gap`: possible once recovered note and supplemental cash-flow rows need deterministic mapping into the three P4B metrics
- `note_disclosure_supplement_gap`: primary planned gap bucket for this anchor

### Anchor Notes

- This anchor represents the mixed-structure family for P4B, similar to how `09987 2025` has been used in earlier bounded note/disclosure phases.
- It must not be treated as an issuer-specific exception. The intended behavior is a reusable bounded note/disclosure bridge path with statement-row precedence preserved.
- Current diagnostics found:
  - stable `interest_paid_cash` evidence via supplemental cash-flow disclosure (`cash paid for interest`)
  - stable `time_deposits_or_wealth_products` evidence via repeated time-deposit / long-term bank deposit disclosures
  - strong `restricted_cash` evidence via `restricted cash` cash-flow aggregation and note text indicating restricted time deposits
- This makes `09987 2025` the strongest initial positive anchor for the cash-health bridge family, but the implementation must still generalize by report-family behavior rather than issuer code.

## Review Notes

- This artifact intentionally separates plan-level expectation from confirmed extraction evidence.
- Before writing the formal P4B spec / plan, the team should run phase-entry diagnostics on these anchors and update this file if any metric is confirmed as `present`, `absent`, or `out_of_scope`.
- P4B should remain a narrow cash-health bridge phase. If diagnostics reveal that the main blocker is broad parent-company coverage or narrative policy parsing, the work should be reclassified into a later phase instead of widening P4B.
