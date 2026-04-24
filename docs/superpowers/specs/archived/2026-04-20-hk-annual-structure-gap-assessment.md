# HK Annual Structure Gap Assessment

> This document is a blocker assessment and replan note for the current
> task-6 path. It explains why the main task-6 target regressions should pause
> and what capability work must happen before those target regressions become a
> healthy red-green cycle again.

## Summary

As of April 20, 2026, the task-4 and task-5 table-semantic path is working for the current CN annual and HK Q3 anchors, but task 6 should be paused before writing the main real-sample target regressions.

The blocker is not primarily in the task-6 test layer. The main issue is that the current HK annual sample (`02498`, annual English report) does not produce stable parsed table structure for the core statements. The table-semantic, metric-mapping, and table-fact-builder layers cannot recover canonical metrics if the upstream table extraction already loses row labels and period headers.

## Current State

Completed and locally verified:

- parsed-table semantic model hardening
- statement-scope and continuation metadata
- normalized table semantics
- minimal metric mapping registry
- table fact builder and ingestion wiring
- regression coverage for comparison-column preservation and continuation metadata

Observed sample-level behavior:

- CN annual (`688008`, annual): canonical output currently includes `revenue`
- HK annual (`02498`, annual): canonical output currently includes `revenue`
- HK Q3 (`09987`, quarterly Q3): candidate output currently includes `operating_profit`, but canonical output is still missing the expected task-6 target facts

Here, `canonical output` refers to the currently exposed canonical/key-fact
path used by the analysis service, not to an arbitrary internal storage layer.

## Evidence

### CN Annual

The CN annual sample is structurally usable enough for the current table path, but some target metrics are still missed because row-label normalization and aliases are incomplete.

Examples observed in parsed rows:

- `一、营业总收入`
- `五、净利润（净亏损以“－”号填列）`
- `货币资金 七、`
- `资产总计`

This indicates the CN path is closer to completion. The main gaps are semantic cleanup and registry coverage rather than total structure loss.

### HK Q3

The HK Q3 sample preserves much more structure than HK annual, but the current parser still underspecifies multi-row period semantics.

Observed income-statement header shape:

- row 1: `Quarter Ended ... % Change ... Year to Date Ended ... % Change`
- row 2: `9/30/2025 ... 9/30/2024 ... 9/30/2025 ... 9/30/2024`

Observed consequences:

- the parser currently keeps `2025Q3` / `2024Q3`, but not `2025Q3_YTD` / `2024Q3_YTD`
- some non-period numeric columns appear before the actual period columns
- balance-sheet values are currently being treated as duration-shaped values in some cases where point-in-time semantics are required

This means HK Q3 is blocked by table-header semantics, not by complete upstream table failure.

### HK Annual

The HK annual sample is the most serious blocker.

When inspecting raw table blocks for the core statements, many extracted blocks degrade into single-column numeric lists with the title preserved but the usable grid structure lost.

Representative examples:

- `Consolidated Balance Sheet ...` block with only numeric rows
- `Consolidated Income Statement ...` block with only numeric rows
- `Consolidated Cash Flow Statement ...` block with only numeric rows

Observed result:

- `period_columns` are empty for the supposed HK annual core statement tables
- row labels and column headers are not available to the semantic layer
- downstream registry matching cannot identify metrics such as `net_profit`, `cash`, `total_assets`, or `total_liabilities`

This is upstream of task 6. The semantic and canonical layers cannot fix
structure that is already missing when `PdfTableSource` returns the raw table
blocks.

This is not primarily a registry or canonical-resolution issue; it is a
structure-recovery failure before semantic normalization can operate.

## Why Task 6 Should Pause

Task 6 expects real-sample target regressions such as:

- CN annual includes `revenue` and `total_assets`
- HK annual includes `revenue`, `net_profit`, and `cash`
- HK Q3 preserves `2025Q3_YTD` for `revenue`

Writing those as the main regression tests right now would not be a healthy
red-green cycle for the current codebase. The failures would mostly reflect
missing upstream capabilities rather than small compatibility gaps in task 6
itself.

The main risk is accidentally freezing today's weak output as the intended
behavior. Task 6 should stay target-oriented, and the missing capabilities
should be fixed before the main sample assertions are added.

## Recommended Next Step

Pause the main task-6 target regression work and add a separate
capability-recovery step focused on HK annual structure recovery.

Priority order:

1. Improve upstream extraction or structure recovery for HK annual core statements.
2. Strengthen row-label normalization and aliases for CN annual and HK annual labels.
3. Improve HK multi-row header parsing so Q3/Q3_YTD and point-in-time versus duration semantics are preserved correctly.
4. After those capabilities are working, return to task 6 and write the intended real-sample target regressions.

This pause applies to the main task-6 target regressions, not to all work in
the surrounding area. Capability work should continue until the target
regressions become meaningful.

The recovery work should prioritize reusable structure-recovery and
semantic-normalization improvements, rather than issuer-specific extraction
branches.

## Temporary Testing Guidance

Until the capability work is complete, only thin smoke coverage should be added to prevent the current path from completely regressing.

The main task-6 real-sample assertions should remain target-level assertions, not downgraded to lock the currently incomplete outputs.

## Exit Criteria for Resuming Task 6

Task 6 main target regressions should resume only when all of the following are
true:

- HK annual core statements expose usable row labels and usable period/header
  structure on the selected annual anchors.
- HK Q3 preserves YTD-aware semantics for multi-row header cases strongly
  enough to support target assertions.
- CN/HK annual row-label normalization covers the seven target metrics on the
  selected anchor samples at the semantic-input level.
- The analysis service key-fact path can surface non-empty target facts for the
  selected anchors without freezing today's weak output as intended behavior.
