# Turtle Asset Quality P3 Sample Onboarding

> Status: Draft for review
> Scope: P3 Task 0 onboarding artifact only
> Important: The classifications below are current expected onboarding classifications, not confirmed extraction results.

## Purpose

This artifact records the three fixed P3 anchors, their minimum onboarding metadata, and the current expected missing-status / failure-classification expectations required by the P3 design and implementation plan.

Target phase scope for this artifact:

- Primary statement-row metrics: `money_cap`, `trad_asset`, `inventories`, `goodwill`, `intang_assets`
- Bounded note-only supplement metrics: `contract_assets`, `other_non_current_assets`

Status vocabulary used in this artifact:

- `present`: expected to be independently disclosed and intended to surface in the current P3 scope
- `absent`: expected not to have independent disclosure in the sample
- `not_surfaced`: may exist in the sample family, but current P3 onboarding expectation treats it as not yet reliably surfaced by the supported path
- `out_of_scope`: intentionally excluded from the current P3 extraction target for this anchor

Failure classification vocabulary used in this artifact:

- `structure_recovery_gap`
- `semantic_normalization_gap`
- `metric_mapping_gap`
- `note_disclosure_supplement_gap`

## Common P3 Metric Set

`target_metric_ids` for all three anchors:

- `money_cap`
- `trad_asset`
- `inventories`
- `goodwill`
- `intang_assets`
- `contract_assets`
- `other_non_current_assets`

## Anchor 1: CN 601919 2025

### Metadata

- `sample_id`: `cn-601919-2025-annual-zh`
- `market`: `CN`
- `language`: `zh`
- `issuer_code`: `601919`
- `report_type`: `annual`
- `period_end`: `2025-12-31`
- `report_family`: `cn_standard_balance_sheet_statement_row`
- `target_phase`: `Turtle Asset Quality Inputs P3`
- `target_metric_ids`: `money_cap`, `trad_asset`, `inventories`, `goodwill`, `intang_assets`, `contract_assets`, `other_non_current_assets`

### Current Expected Onboarding Classification

- `present`: `money_cap`, `trad_asset`, `inventories`, `goodwill`, `intang_assets`
- `absent`: none currently expected at plan level
- `not_surfaced`: none currently expected for the primary statement-row path
- `out_of_scope`: none at anchor scope; `contract_assets` and `other_non_current_assets` remain in-scope P3 metrics, but are not primary statement-row targets

### Current Expected Failure Classification

- `structure_recovery_gap`: no plan-level expectation for this anchor
- `semantic_normalization_gap`: possible only if CN balance-sheet labels for primary asset rows do not normalize cleanly; not the expected main gap
- `metric_mapping_gap`: possible for any missing primary asset row alias; this is the most likely early-fix bucket if statement rows are recovered but do not map
- `note_disclosure_supplement_gap`: not the expected main gap for this anchor

### Anchor Notes

- This anchor is the CN deterministic statement-row anchor for the five primary P3 asset metrics.
- `contract_assets` and `other_non_current_assets` should not be promoted into the primary statement-row path for this anchor.

## Anchor 2: HK 02498 2022

### Metadata

- `sample_id`: `hk-02498-2022-annual-en`
- `market`: `HK`
- `language`: `en`
- `issuer_code`: `02498`
- `report_type`: `annual`
- `period_end`: `2022-12-31`
- `report_family`: `hk_statement_row_asset_quality`
- `target_phase`: `Turtle Asset Quality Inputs P3`
- `target_metric_ids`: `money_cap`, `trad_asset`, `inventories`, `goodwill`, `intang_assets`, `contract_assets`, `other_non_current_assets`

### Current Expected Onboarding Classification

- `present`: `inventories`, `goodwill`, `intang_assets`
- `absent`: none currently expected at plan level
- `not_surfaced`: `money_cap`, `trad_asset`
- `out_of_scope`: none at anchor scope; `contract_assets` and `other_non_current_assets` remain bounded note-only metrics rather than primary statement-row targets

### Current Expected Failure Classification

- `structure_recovery_gap`: possible for asset fields that appear elsewhere in the report family but are not stably surfaced as consolidated balance-sheet statement rows in the current anchor
- `semantic_normalization_gap`: possible if English balance-sheet labels are recovered but normalized inconsistently across HK statement rows
- `metric_mapping_gap`: possible for HK aliases such as trading-asset or intangible-asset row variants; not the expected main gap for the currently surfaced subset
- `note_disclosure_supplement_gap`: not the expected main gap for this anchor

### Anchor Notes

- This anchor is the HK deterministic statement-row anchor for the five primary P3 asset metrics.
- Current real-sample probing indicates `inventories`, `goodwill`, and `intang_assets` are the stable consolidated balance-sheet statement-row subset for this anchor, while `money_cap` and `trad_asset` are not currently surfaced through the same path.
- Negative-control rows should stay outside the P3 target set even if they appear near target asset rows.

## Anchor 3: HK 09987 2025

### Metadata

- `sample_id`: `hk-09987-2025-annual-en`
- `market`: `HK`
- `language`: `en`
- `issuer_code`: `09987`
- `report_type`: `annual`
- `period_end`: `2025-12-31`
- `report_family`: `hk_mixed_structure_note_disclosure_asset_supplement`
- `target_phase`: `Turtle Asset Quality Inputs P3`
- `target_metric_ids`: `money_cap`, `trad_asset`, `inventories`, `goodwill`, `intang_assets`, `contract_assets`, `other_non_current_assets`

### Current Expected Onboarding Classification

- `present`: none currently expected at plan level
- `absent`: `contract_assets`, `other_non_current_assets`
- `not_surfaced`: `money_cap`, `trad_asset`, `inventories`, `goodwill`, `intang_assets` when the mixed-structure statement path is insufficient and P3 does not yet treat this anchor as the primary deterministic statement-row proof point
- `out_of_scope`: none currently expected at anchor scope

### Current Expected Failure Classification

- `structure_recovery_gap`: possible if the main statement itself is not stably recovered enough to support downstream row reasoning
- `semantic_normalization_gap`: possible if asset rows or disclosure labels are recovered but remain too ambiguous for deterministic handling
- `metric_mapping_gap`: possible, but not the primary planned gap for this anchor
- `note_disclosure_supplement_gap`: primary planned gap bucket for this anchor when note-only asset fields are independently disclosed but not yet surfaced

### Anchor Notes

- This anchor represents the mixed-structure family where main-statement completeness is weaker and bounded note/disclosure supplement is more important.
- This anchor should not be treated as an issuer-specific exception. The intended behavior is a reusable note/disclosure supplement path with statement-row precedence preserved.
- Current onboarding expectation is an exact note-only asset absence state for this sample: surfaced subset `none`, `contract_assets = absent`, `other_non_current_assets = absent`.

## Review Notes

- This artifact intentionally separates plan-level expectation from confirmed extraction evidence.
- If later diagnostics show that any anchor has a truly independent `absent` or `not_surfaced` metric outside the expectations above, this file should be updated before implementation tasks rely on that assumption.
