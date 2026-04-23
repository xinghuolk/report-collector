# Turtle Investor Core Statement Gaps P4C Sample Onboarding

> Status: Draft for review
> Scope: P4C onboarding artifact only
> Important: The classifications below are current phase-entry expectations and diagnostics, not confirmed extraction results.

## Purpose

This artifact records the three fixed P4C anchors, their minimum onboarding metadata, and the current expected missing-status / failure-classification expectations for the proposed Turtle Investor Core Statement Gaps phase.

Target P4C scope for this artifact:

- Income statement: `revenue`, `operating_cost`, `operating_profit`, `net_profit`
- Balance sheet: `total_assets`, `total_liabilities`, `equity_attributable_to_owners`
- Cash flow statement: `operating_cash_flow`, `investing_cash_flow`, `financing_cash_flow`, `c_pay_to_staff`, `c_paid_for_taxes`

These metrics are treated as main-statement, deterministic-first statement-row targets. P4C is not a broad notes bridge, not a parent-scope expansion phase, and not a multi-year dataset phase.

Status vocabulary used in this artifact:

- `present`: currently expected to be independently disclosed and intended to surface through the P4C statement-row path
- `absent`: currently expected not to have an independently recoverable row for the anchor within P4C scope
- `not_surfaced`: may exist in the sample family, but current phase-entry expectation treats it as not yet reliably surfaced by the supported path
- `out_of_scope`: intentionally excluded from the current P4C extraction target for this anchor

Failure classification vocabulary used in this artifact:

- `structure_recovery_gap`
- `semantic_normalization_gap`
- `metric_mapping_gap`
- `statement_row_candidate_gap`

## Common P4C Metric Set

`target_metric_ids` for all three anchors:

- `revenue`
- `operating_cost`
- `operating_profit`
- `net_profit`
- `total_assets`
- `total_liabilities`
- `equity_attributable_to_owners`
- `operating_cash_flow`
- `investing_cash_flow`
- `financing_cash_flow`
- `c_pay_to_staff`
- `c_paid_for_taxes`

## Anchor 1: CN 601919 2025

### Metadata

- `sample_id`: `cn-601919-2025-annual-zh`
- `market`: `CN`
- `language`: `zh`
- `issuer_code`: `601919`
- `report_type`: `annual`
- `period_end`: `2025-12-31`
- `report_family`: `cn_standard_main_statement_row`
- `target_phase`: `Turtle Investor Core Statement Gaps P4C`
- `target_metric_ids`: `revenue`, `operating_cost`, `operating_profit`, `net_profit`, `total_assets`, `total_liabilities`, `equity_attributable_to_owners`, `operating_cash_flow`, `investing_cash_flow`, `financing_cash_flow`, `c_pay_to_staff`, `c_paid_for_taxes`
- `known_special_shape`: `CN annual consolidated statements are expected to be the primary deterministic proof point for the full P4C metric family`

### Current Expected Onboarding Classification

- `present`: `revenue`, `total_assets`, `total_liabilities`, `operating_cash_flow`, `c_paid_for_taxes`
- `absent`: none currently expected at phase-entry
- `not_surfaced`: `operating_cost`, `operating_profit`, `net_profit`, `equity_attributable_to_owners`, `investing_cash_flow`, `financing_cash_flow`, `c_pay_to_staff`
- `out_of_scope`: none at anchor scope

### Current Expected Failure Classification

- `structure_recovery_gap`: not the expected main gap for this anchor
- `semantic_normalization_gap`: possible for Chinese row families such as `净利润` vs attributable-profit variants, but not the expected main blocker
- `metric_mapping_gap`: likely earliest-fix bucket if deterministic rows are recovered but one or more canonical ids do not map cleanly
- `statement_row_candidate_gap`: possible for cash-flow rows if row labels are recovered but candidate facts do not emit consistently

### Anchor Notes

- This anchor is the CN deterministic baseline for P4C and should be treated as the cleanest proof point for the full 12-metric family.
- Current expectation is based on report-family shape, prior CN statement-row behavior, and the P4C design scope, not on confirmed per-metric extraction evidence.
- Current focused diagnostics now confirm a broader deterministic statement-row subset than the original phase-entry estimate, including consolidated `c_paid_for_taxes`; `investing_cash_flow` and `financing_cash_flow` also appear in the sample but currently through `parent_only` rows rather than the consolidated proof path, so they remain `not_surfaced` for the main P4C anchor contract.

## Anchor 2: HK 02498 2022

### Metadata

- `sample_id`: `hk-02498-2022-annual-en`
- `market`: `HK`
- `language`: `en`
- `issuer_code`: `02498`
- `report_type`: `annual`
- `period_end`: `2022-12-31`
- `report_family`: `hk_cleaner_format_main_statement_row`
- `target_phase`: `Turtle Investor Core Statement Gaps P4C`
- `target_metric_ids`: `revenue`, `operating_cost`, `operating_profit`, `net_profit`, `total_assets`, `total_liabilities`, `equity_attributable_to_owners`, `operating_cash_flow`, `investing_cash_flow`, `financing_cash_flow`, `c_pay_to_staff`, `c_paid_for_taxes`
- `known_special_shape`: `HK annual with cleaner statement formatting; intended to prove English row-family normalization without relying on issuer-specific exceptions`

### Current Expected Onboarding Classification

- `present`: `total_assets`, `total_liabilities`
- `absent`: none currently locked at phase-entry
- `not_surfaced`: `revenue`, `operating_cost`, `operating_profit`, `net_profit`, `equity_attributable_to_owners`, `operating_cash_flow`, `investing_cash_flow`, `financing_cash_flow`, `c_pay_to_staff`, `c_paid_for_taxes`
- `out_of_scope`: none at anchor scope

### Current Expected Failure Classification

- `structure_recovery_gap`: expected main bucket for the income-statement family on this anchor
- `semantic_normalization_gap`: likely for English row families such as `profit for the year`, owner-attributable equity wording, or cash-flow wording variants
- `metric_mapping_gap`: possible for `operating_cash_flow`, `investing_cash_flow`, `financing_cash_flow`, and owner-attributable equity once rows are recovered well enough
- `statement_row_candidate_gap`: plausible for `c_pay_to_staff` and `c_paid_for_taxes` if row recovery succeeds but candidate facts remain too strict

### Anchor Notes

- This anchor is the HK cleaner-format proof point for P4C and should be used to verify that the phase generalizes across English statement-row families.
- Current focused diagnostics suggest that totals are the most reliable proof point here, while income-statement rows and lower-frequency cash-flow rows are still not stably surfacing.
- If `equity_attributable_to_owners` turns out to be stably present, the likely change is a narrower owner-attributable equity mapping contract rather than any scope expansion.

## Anchor 3: HK 09987 2025

### Metadata

- `sample_id`: `hk-09987-2025-annual-en`
- `market`: `HK`
- `language`: `en`
- `issuer_code`: `09987`
- `report_type`: `annual`
- `period_end`: `2025-12-31`
- `report_family`: `hk_mixed_structure_main_statement_row`
- `target_phase`: `Turtle Investor Core Statement Gaps P4C`
- `target_metric_ids`: `revenue`, `operating_cost`, `operating_profit`, `net_profit`, `total_assets`, `total_liabilities`, `equity_attributable_to_owners`, `operating_cash_flow`, `investing_cash_flow`, `financing_cash_flow`, `c_pay_to_staff`, `c_paid_for_taxes`
- `known_special_shape`: `mixed-structure HK annual where main statements may still be recoverable, but statement-row completeness is expected to be less stable than the CN and cleaner-HK anchors`

### Current Expected Onboarding Classification

- `present`: none currently locked at phase-entry
- `absent`: none currently locked at phase-entry
- `not_surfaced`: `revenue`, `operating_cost`, `operating_profit`, `net_profit`, `total_assets`, `total_liabilities`, `equity_attributable_to_owners`, `operating_cash_flow`, `investing_cash_flow`, `financing_cash_flow`, `c_pay_to_staff`, `c_paid_for_taxes`
- `out_of_scope`: none at anchor scope

### Current Expected Failure Classification

- `structure_recovery_gap`: primary expected gap bucket for this anchor when main statements are split, partially recovered, or less stable across pages
- `semantic_normalization_gap`: possible for English mixed wording such as `profit for the year`, owner-attributable equity labels, or staff/tax cash-flow rows
- `metric_mapping_gap`: possible, but not the first expected blocker for this anchor
- `statement_row_candidate_gap`: likely secondary gap bucket once table semantics are recovered well enough to identify target rows

### Anchor Notes

- This anchor represents the HK mixed-structure family for P4C, similar to how `09987` has been used as a stress anchor in earlier Turtle phases.
- It must not be treated as an issuer-specific special case. The intended outcome is a reusable mixed-structure statement-row path, with bounded semantic fallback only for local row-label ambiguity.
- Current focused diagnostics suggest this anchor should still be treated as the P4C mixed-structure stress sample, with most of the 12-metric family still `not_surfaced` until statement structure recovery improves.

## Review Notes

- This artifact intentionally separates current onboarding expectation from confirmed extraction evidence.
- If diagnostics show that one or more of the 12 metrics are actually blocked by parent-scope logic or note/disclosure-only evidence, those metrics should be reclassified rather than widening P4C implicitly.
- Before implementation tasks rely on these classifications, the team should run focused phase-entry diagnostics on the three anchors and update this file if any metric is confirmed as `present`, `absent`, `not_surfaced`, or `out_of_scope`.
