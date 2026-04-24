# Financial Report Analysis Three-Statement High-Value Metrics Design

## 1. Goal

This design defines the next expansion step after the completed
income-statement core metrics plus balance-sheet baseline phase.

The next objective is to turn the current system from:

- one complete income-statement path
- one light balance-sheet baseline
- one minimal cash-flow foothold

into a more intentional three-statement high-value coverage layer.

This is still not a "full financial statement extractor" phase. It is a
controlled expansion that should prove the architecture can support broader
statement coverage without losing precision, provenance, or regression
stability.

## 2. Why This Step Exists

The current system already has the following in place:

- stable table-structure recovery on selected CN and HK anchors
- deterministic semantic normalization with bounded fallback
- working candidate-fact, canonical-fact, and API output paths
- stable support for:
  - `revenue`
  - `operating_cost`
  - `operating_profit`
  - `net_profit`
  - `operating_cash_flow`
  - `cash`
  - `total_assets`
  - `total_liabilities`

That means the main bottleneck has shifted again.

The current gap is no longer whether table-driven extraction works. The gap is
whether the same substrate can support a broader but still disciplined
three-statement metric layer that is useful for downstream analysis.

## 3. Positioning

This design should be treated as the first true three-statement expansion
layer in the phase-2 roadmap.

It bridges between:

- the completed deterministic table-semantic baseline
- a future broader statement-coverage phase

It should remain conservative in scope. The purpose is not maximum metric
breadth. The purpose is to prove that three-statement expansion can proceed in
bounded, testable slices.

This document is the umbrella design. It should be implemented together with
the following child designs:

- `docs/superpowers/specs/2026-04-21-financial-report-analysis-income-statement-second-batch-design.md`
- `docs/superpowers/specs/2026-04-21-financial-report-analysis-balance-sheet-equity-layer-design.md`
- `docs/superpowers/specs/2026-04-21-financial-report-analysis-cash-flow-core-completion-design.md`
- `docs/superpowers/specs/2026-04-21-financial-report-analysis-cross-statement-conflict-governance-design.md`

## 4. In Scope

This design is in scope for:

- expanding the income statement with a second small batch of
  high-value metrics
- expanding the balance sheet from baseline totals into a first equity-aware
  layer
- expanding the cash-flow statement from `operating_cash_flow` into the
  three main cash-flow sections
- tightening cross-statement conflict handling where broader metric coverage
  increases collision risk
- preserving provenance and deterministic-first behavior across candidate,
  canonical, and API layers

## 5. Out Of Scope

This design is explicitly out of scope for:

- a full all-lines statement extractor
- derived ratio generation
- note-table extraction as a first-class fact source
- direct LLM-led fact extraction
- broader attributable-ownership governance beyond the selected equity pair
- wide working-capital expansion such as inventory, receivables, payables,
  and note-level subcomponents
- period-semantics fallback
- unit or currency propagation redesign

## 6. Target Metric Set

### 6.1 Income Statement Second Batch

This step should add:

- `gross_profit`

This step may also standardize the normalization surface around:

- `adjusted_net_profit`

but `adjusted_net_profit` should be treated as stretch or gated scope, not as
the primary completion dependency for the whole design.

### 6.2 Balance Sheet Second Batch

This step should add:

- `equity`
- `equity_attributable_to_owners`

These two metrics are the smallest meaningful expansion beyond
`cash` / `total_assets` / `total_liabilities`, and they force the system to
handle the first genuinely ambiguous balance-sheet ownership semantics.

### 6.3 Cash Flow Core Completion

This step should add:

- `investing_cash_flow`
- `financing_cash_flow`

Together with the existing `operating_cash_flow`, this closes the three
primary cash-flow sections.

## 7. Recommended Sequencing

This design covers all three statements, but implementation should not treat
them as equal-priority parallel streams.

The recommended order is:

1. finish the income statement with `gross_profit`
2. extend the balance sheet into the minimal equity layer
3. finish the cash-flow statement main three-section coverage
4. then tighten cross-statement conflict and promotion behavior

This keeps the risk profile controlled while still producing a coherent
three-statement result.

## 8. Main Risks

### 8.1 Summary and Ratio Interference

As more metrics are added, summary tables, management highlights, and ratio
rows become more likely to collide with core metric aliases.

Examples include:

- gross margin versus gross profit
- adjusted profit summary rows versus main income-statement rows
- equity ratio rows versus point-in-time equity values
- cash-flow trend or variance rows versus statement values

These must remain blocked by deterministic gating and statement-aware context.

### 8.2 Balance-Sheet Ownership Ambiguity

`equity` and `equity_attributable_to_owners` are valuable, but they bring:

- consolidated versus parent-only drift
- attributable versus total equity ambiguity
- English and Chinese label-family variation

That is why this phase should stop at those two metrics rather than widening
the balance-sheet scope aggressively.

### 8.3 Cash-Flow Table Variants

Cash-flow statements often use more layout variation and abbreviated labels
than the current income-statement path.

The design must avoid turning cash-flow expansion into a bespoke parser phase.
The same deterministic normalization and registry model should still be the
main lever.

### 8.4 Cross-Statement Collisions

As coverage grows, broader aliases increase the chance that:

- summary tables compete with main statements
- key metrics tables compete with primary statement tables
- overlapping labels enter canonical selection with misleading provenance

This phase should address those conflicts explicitly, not only case-by-case.

## 9. Deterministic-First Constraints

The expected extraction order remains:

`structure recovery -> deterministic normalization -> registry match -> candidate facts -> canonical facts -> API`

That means:

- new coverage should come primarily from normalization and registry work
- semantic fallback may assist ambiguous local cases, but must not become the
  main source of new metric coverage
- statement-aware gating must stay explicit

## 10. Verification Strategy

This phase should verify at five levels.

### 10.1 Registry Coverage

Verify that the selected new metrics match realistic CN and HK label families
through deterministic registry logic.

### 10.2 Semantic Normalization

Verify that normalization produces canonical labels that are broad enough for
coverage but still strict enough to avoid ratio or summary drift.

### 10.3 Statement Path

Verify that each new metric can move through:

- parsed table
- normalized table semantics
- candidate facts
- canonical facts
- API `key_facts`

without contract drift.

### 10.4 Cross-Statement Conflict Control

Verify that main-statement facts still outrank summary, ratio, and secondary
table disclosures when the same metric family appears multiple times.

### 10.5 Real-Sample Regression

Verify the selected anchors and references across CN and HK annual and
quarterly samples, with emphasis on:

- provenance stability
- period-shape stability
- statement-source stability
- non-regression on existing covered metrics

## 11. Sample Strategy

The supported sample set for this design should be explicit and stable.

### 11.1 Primary Anchors

The primary anchors for this phase should be:

- CN annual primary anchor:
  - `601919/annual/2024_年度报告.pdf`
- HK annual anchors:
  - `02498/annual/2022_annual_en.pdf`
  - `06862/annual/2024_annual_en.pdf`
  - `09987/annual/2024_annual_en.pdf`
- HK quarterly supplement:
  - `09987/quarterly/2025_quarterly_q3_en.pdf`

### 11.2 CN Annual Reference Coverage

CN annual reference coverage should include:

- `600519/annual/2024_年度报告.pdf`
- `600519/annual/2025_年度报告.pdf`
- `601919/annual/2025_年度报告.pdf`
- `688008/annual/2024_年度报告.pdf`
- `688008/annual/2025_年度报告.pdf`

### 11.3 Tranche-to-Sample Expectations

Each tranche should still use the same shared sample matrix, but the emphasis
should differ:

- income-statement work should prioritize all anchors plus the CN annual
  references
- balance-sheet equity work should prioritize the CN annual primary anchor and
  the HK annual anchors where ownership labels are present
- cash-flow work should prioritize the CN annual primary anchor, HK annual
  anchors, and the HK quarterly supplement
- conflict-governance work should run against the full shared matrix

The phrases `supported sample set`, `primary anchors`, `reference set`, and
`target sample set` in this design and its child documents all refer back to
this explicit matrix unless a child design narrows the emphasis further.

## 12. Deliverable Definition

This design is considered complete when all of the following are true:

- `gross_profit` is stable on the supported income-statement sample set
- `equity` and `equity_attributable_to_owners` are stable on the supported
  balance-sheet sample set
- `investing_cash_flow` and `financing_cash_flow` are stable on the supported
  cash-flow sample set
- the existing covered metrics remain stable
- no breaking changes are introduced to candidate, canonical, or API contracts
- summary and ratio interference does not materially worsen

## 13. What Should Come Next

If this design succeeds, the next decision point should be between:

- broader balance-sheet working-capital expansion
- adjusted and derived profitability metrics
- note-table or disclosure-table support
- cross-period or multi-column semantic enrichment

The default recommendation after this design is:

- stabilize the three-statement high-value metric set first
- only then expand into denser statement detail or derived metrics
