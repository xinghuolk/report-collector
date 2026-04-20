# Financial Report Analysis Income Statement Core Metrics With Balance Sheet Baseline Design

## 1. Goal

This design defines the next focused step after the completed table-structure,
semantic-normalization, and limited fallback phase-2 baseline.

The immediate objective is to extend the system from a small set of
high-value, proof-of-path metrics into a more usable core financial-statement
coverage layer, while keeping the current architecture stable.

This step has two coordinated goals:

- make the income statement the first fully usable table-driven fact path
- validate that the same approach can extend cleanly into balance-sheet
  baseline metrics without turning the scope into a full three-statement
  expansion

The priority remains deterministic extraction and semantic mapping. This is
not a new fallback phase and not a shift to broader LLM-led interpretation.

## 2. Why This Step Exists

The current system now has:

- stable annual and quarterly structure recovery on the selected CN/HK anchors
- deterministic semantic normalization with preserved provenance
- gated `Ollama` ambiguity fallback with constrained outputs
- a working pipeline from parsed tables to candidate facts, canonical facts,
  and analysis API outputs

That means the primary blocker has shifted.

The next bottleneck is no longer basic structure collapse. It is limited metric
coverage.

At present, the table-driven path can produce a narrow set of important facts,
but it is still closer to a demonstration path than to a robust financial
statement extraction layer. The most natural next move is to deepen metric
coverage where the current substrate is already strongest.

The income statement is the best candidate for that next step.

## 3. Positioning

This design should be treated as the practical bridge between:

- the completed phase-2 extraction / semantic-fallback baseline
- the later broader three-statement expansion described in the phase-2 roadmap

It follows the roadmap's sequencing:

- first stabilize structure recovery and semantic normalization
- then build the income statement into the first complete statement path
- then generalize the approach to broader balance-sheet and cash-flow coverage

This design intentionally does **not** jump directly to a full parallel
three-statement implementation.

## 4. Scope

### 4.1 In Scope

This step is in scope for:

- extending metric-mapping registry coverage for income-statement core metrics
- strengthening deterministic row-label normalization for realistic CN/HK
  income-statement labels
- validating that the income-statement table-driven path can stably reach:
  - `candidate_facts`
  - `canonical_facts`
  - `key_facts`
- lightly extending the same approach to a balance-sheet baseline set:
  - `cash`
  - `total_assets`
  - `total_liabilities`
- preserving current contracts for:
  - candidate facts
  - canonical facts
  - analysis API output

### 4.2 Out Of Scope

This step is explicitly out of scope for:

- a full balance-sheet semantic expansion
- cash-flow-statement expansion beyond already supported metrics
- equity and attributable-equity governance
- direct support for:
  - `gross_margin`
  - `adjusted_net_profit`
  - `book value`
  - `equity attributable to owners`
- new `Ollama` fallback categories
- period-semantics fallback
- unit or currency propagation-strategy inference
- direct LLM candidate-fact or canonical-fact generation

## 5. Why Income Statement Is Primary

The income statement is the most suitable next primary statement because:

- its value columns are mostly duration-based and already align well with the
  current table model
- its core metrics are highly valuable to downstream analysis
- its label families are still varied, but the semantic space is tighter than
  the harder balance-sheet equity variants
- it is the clearest place to prove that the current architecture can move
  from a small high-value metric set to a reusable statement-level extraction
  pattern

This design therefore treats the income statement as the main implementation
target rather than one of several equal-priority tracks.

## 6. Why Balance Sheet Is Only Baseline Here

The balance sheet is included, but intentionally in a limited role.

That is because balance-sheet work quickly expands into more difficult
questions:

- point-in-time semantics must remain strict
- entity-scope drift becomes more dangerous
- equity terminology is more ambiguous than the selected baseline metrics
- summary-table interference can look deceptively similar to real core facts

A full balance-sheet expansion is still the right later direction, but this
step should only validate that the current pattern generalizes beyond the
income statement for a small, low-ambiguity baseline set.

## 7. Metrics Included

### 7.1 Income Statement Core Metrics

The target metric set for this step is:

- `revenue`
- `operating_cost`
- `operating_profit`
- `net_profit`

These four metrics provide a compact but meaningful statement path:

- top line
- direct operating cost base
- operating result
- bottom-line result

### 7.2 Balance Sheet Baseline Metrics

The target balance-sheet baseline set is:

- `cash`
- `total_assets`
- `total_liabilities`

These are chosen because they are:

- already partially represented in the current registry
- comparatively low ambiguity
- useful as a proof that the approach extends beyond the income statement

## 8. Deterministic-First Constraints

This design preserves the current deterministic-first architecture.

The expected priority remains:

`structure recovery -> deterministic semantic normalization -> registry match -> candidate facts -> canonical facts`

That means:

- metric coverage should be improved first through deterministic row-label
  normalization and registry expansion
- `Ollama` fallback must not become the main mechanism for the newly added
  statement metrics
- promoted fallback cases should remain a validation aid, not the main source
  of business coverage

## 9. Main Risks

This step has several important risks.

### 9.1 Summary / Growth Table Interference

As metric coverage expands, summary tables, ratio tables, and growth rows may
start matching core metric labels unless deterministic gating remains strict.

Examples:

- revenue growth
- operating margin
- profit increase
- ratio-only tables

These should not be allowed to silently turn into core financial facts.

### 9.2 Over-Broad Alias Families

Adding aliases too aggressively can make the registry look stronger while
actually lowering precision.

The target is not lexical breadth for its own sake. The target is high-signal
coverage on main-statement semantics.

### 9.3 Premature Balance-Sheet Expansion

If this step drifts into broader balance-sheet work, it will pull in equity,
scope, and statement-structure complications that deserve their own design
pass.

This design deliberately avoids that drift.

## 10. Sample Strategy

### 10.1 Primary Anchors

This step should continue to rely on the already established anchors:

- CN annual primary anchor:
  - `601919/annual/2024_年度报告.pdf`
- HK annual anchors:
  - `02498/annual/2022_annual_en.pdf`
  - `06862/annual/2024_annual_en.pdf`
  - `09987/annual/2024_annual_en.pdf`
- HK quarterly supplement:
  - `09987/quarterly/2025_quarterly_q3_en.pdf`

### 10.2 Reference Coverage

CN annual reference coverage should continue to include:

- `600519/annual/2024_年度报告.pdf`
- `600519/annual/2025_年度报告.pdf`
- `601919/annual/2025_年度报告.pdf`
- `688008/annual/2024_年度报告.pdf`
- `688008/annual/2025_年度报告.pdf`

These references should be used to guard against overfitting to a single CN
issuer or a single annual-report layout.

## 11. Verification Strategy

This step should verify at four levels.

### 11.1 Registry Coverage Regression

Verify that the selected income-statement and balance-sheet baseline metrics
match realistic CN/HK label families through deterministic registry logic.

### 11.2 Semantic Normalization Regression

Verify that row-label normalization produces stable, fact-agnostic semantic
labels that the registry can consume without overmatching ratios and summary
rows.

### 11.3 Statement-Path Regression

Verify that the selected metrics can travel through:

- parsed table
- normalized table semantics
- candidate facts
- canonical facts
- API `key_facts`

without contract drift.

### 11.4 Real-Sample Regression

Verify that the selected CN/HK anchors and references preserve:

- usable main-statement structure
- correct period-shape behavior
- stable provenance
- meaningful `quality_gate` output

## 12. Deliverable Definition

This design is considered complete when all of the following are true:

- the income statement supports a broader deterministic core metric set
- the selected income-statement metrics stably appear in the table-driven fact
  path on the target sample set
- balance-sheet baseline metrics remain stable and slightly broader, without
  causing scope expansion into harder equity semantics
- no breaking changes are introduced to current candidate/canonical/API
  contracts
- the work demonstrates a reusable path for later broader statement expansion

## 13. What Should Come Next

If this step succeeds, the next decision point should be between:

- a second income-statement expansion pass:
  - `gross_profit`
  - `adjusted_net_profit`
- a deeper balance-sheet phase:
  - `equity`
  - `equity attributable to owners`
- broader cash-flow expansion:
  - `investing_cash_flow`
  - `financing_cash_flow`

The default recommendation after this design is:

- finish the income statement first
- only then move into more ambiguous balance-sheet equity work

That sequencing remains the lowest-risk path consistent with the phase-2
roadmap.
