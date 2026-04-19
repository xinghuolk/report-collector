# Financial Report Semantic Recovery and Normalization Design

## 1. Goal

This design defines the next phase of `financial_report_analysis` as a semantic
recovery and normalization effort rather than a sample-specific compatibility
patch.

The immediate operational goal is to restore structurally usable and
semantically stable inputs for:

- CN annual reports
- HK annual reports
- HK quarterly reports with more complex period layout as a protected
  supplement path

The most urgent blocker is HK annual report recovery, but the design is not
limited to a single issuer or a single report family.

## 2. Scope

This phase is in scope for:

- upstream structure recovery hardening for annual-report core statements
- semantic normalization hardening
- metric mapping registry upgrade from alias table to semantic mapping entry
  point
- limited `Ollama` semantic fallback for ambiguity handling
- preservation of the current candidate-fact and canonical-fact contract
- real-sample validation against multiple CN and HK annual reports

This phase is not in scope for:

- universal extraction guarantees across all financial reports
- issuer-specific extraction branches as the primary extension strategy
- OCR- or vision-heavy recovery for image-first PDFs
- direct LLM candidate fact generation
- LLM-driven canonical resolution or validation
- broad metric-catalog expansion beyond the current high-value metric set

## 3. Positioning

This phase does not claim universal extraction across all financial reports.
It establishes the unified architecture intended to scale across CN, HK, and
future report families.
New report families should be integrated by extending structure recovery,
semantic normalization, registry coverage, and gated semantic fallback, rather
than by adding issuer-specific extraction branches.

## 4. Problem Statement

The current table-semantic path was validated primarily on structurally
friendlier anchors, especially HK quarterly samples such as `Q3` and `Q4_FY`.
That skew created a false sense of readiness for HK annual reports.

The current gaps now separate into three distinct classes:

### 4.1 HK Annual Gap

HK annual reports are the primary blocker.

For several HK annual samples, the current `PdfTableSource` and upstream table
recovery path lose usable row labels and column headers on the three core
statements. Once that happens:

- `ParsedTable` no longer contains stable row-to-value bindings
- `period_columns` may be empty or underspecified
- downstream semantic normalization cannot recover metric identity
- registry matching and fact building cannot produce reliable candidate or
  canonical facts

This is a structure-recovery problem first, not a registry problem.

### 4.2 CN Annual Gap

CN annual reports are structurally more usable than HK annual reports, but they
still suffer from normalization gaps:

- numbered row-label prefixes
- CN label variants such as `营业总收入`, `营业收入`, `资产总计`
- summary-table and main-statement interference

The main CN problem is semantic cleanup and mapping stability, not total
structure collapse.

### 4.3 HK Quarterly Semantic Gap

HK Q3-style reports preserve much more visible structure, but current semantic
handling still underspecifies:

- multi-row header hierarchy
- `current` versus `prior` comparison roles
- `YTD` versus `single-quarter` distinction
- point-in-time versus duration-shaped values

This is a semantic-normalization gap, not complete upstream failure.

## 5. Architecture

The target pipeline for this phase is:

`pdf -> raw table blocks -> structure recovery -> normalized table semantics -> metric mapping registry -> candidate facts -> canonical facts`

Responsibilities are split as follows:

- `structure recovery`
  restores table blocks, header hierarchy, row labels, column bindings, and
  local unit/currency context
- `normalized table semantics`
  turns recovered tables into stable semantic inputs such as `table_kind`,
  normalized row labels, and column roles
- `metric mapping registry`
  maps stable semantics to supported metric identities
- `candidate/canonical` layers
  continue to own fact construction, resolution, validation, and derivation

`Ollama` semantic fallback is allowed only inside the semantic-normalization
zone and only for explicitly gated ambiguity cases.

## 6. Structure Recovery Layer

The structure recovery layer remains rule- and parser-driven.

Its responsibilities are:

- recover usable `table blocks`
- recover `header hierarchy`
- preserve `row labels`
- preserve `row-to-value bindings`
- preserve `local unit/currency context`
- preserve `statement_scope_guess`
- preserve continuation metadata conservatively

The design goal is not to recover every PDF perfectly. The goal is to maximize
stable structure recovery for mainstream CN and HK annual reports without
sliding into issuer-specific formatting patches.

When recovery is uncertain, the preferred behavior is:

- preserve ambiguity explicitly
- avoid forced merges
- avoid silently collapsing structure into misleading low-entropy output

## 7. Semantic Normalization Layer

This phase strengthens normalized table semantics into an explicit and durable
intermediate layer.

That layer should stabilize:

- `table_kind`
- `normalized_row_label`
- `column_semantics`
- `period/value context`
- `table-local unit/currency interpretation`
- `statement_scope_guess`

This layer must remain semantically rich but fact-agnostic:

- it should not emit `metric_id`
- it should not emit `canonical_value`
- it should not decide canonical winners

Its role is to answer:

- what kind of table this is
- what a row most likely means
- what role a column most likely carries

not:

- which final financial fact should be trusted

## 8. Metric Mapping Registry Position

The registry in this phase should be treated as a semantic mapping entry point,
not as a flat alias table and not as a universal patch layer.

The registry consumes stable normalized semantics, including:

- `table_kind`
- `normalized_row_label`
- `column_semantics`
- `period/value context`

The registry should evolve toward:

- metric identity mapping
- minimal semantic constraints
- market-aware label families

It should not replace:

- structure recovery
- semantic normalization
- candidate/canonical conflict resolution

## 9. Limited Ollama Semantic Fallback

`Ollama` semantic fallback is in scope for ambiguous semantic normalization
only.

It may assist with:

- `table kind disambiguation`
- `normalized row label inference`

It is not the primary extraction path and does not replace:

- table structure parsing
- metric mapping registry
- candidate fact building
- canonical resolution
- validation

### 9.1 First-Phase Fallback Output Limits

For `table kind`, fallback output is restricted to:

- `income_statement`
- `balance_sheet`
- `cash_flow_statement`
- `key_metrics`
- `unknown`

For `row label normalization`, fallback output is restricted to:

- `revenue`
- `operating_profit`
- `net_profit`
- `operating_cash_flow`
- `cash`
- `total_assets`
- `total_liabilities`
- `none`

### 9.2 Trigger Conditions

Fallback must be gated and opt-in.

Default behavior is:

- structure recovery runs first
- deterministic semantic normalization runs first
- fallback is called only when ambiguity conditions are met

Examples of valid first-phase triggers:

- rule-based table classification returns `unknown`
- multiple table-kind candidates remain unresolved
- alias and normalization rules cannot map a row label stably
- multiple supported metric candidates remain unresolved for a row

### 9.3 Provenance Requirements

Every fallback-assisted result must preserve provenance, including at minimum:

- `semantic_source = "llm_fallback"`
- `semantic_confidence`
- `fallback_reason`

This is required so the system can distinguish:

- fully deterministic outcomes
- fallback-assisted outcomes
- cases that should later be backfilled into rules or registry coverage

### 9.4 Explicitly Out of Scope for This Phase

The first `Ollama` fallback phase does not include:

- column or period semantic disambiguation
- unit or currency interpretation
- direct candidate fact generation
- canonical resolution

Those can be considered only after the first fallback phase is stable and
measurable.

## 10. Sample Strategy

This phase uses two sample classes:

- primary anchors
- reference sets

Primary anchors are used for stronger target assertions.
Reference sets are used for structure, semantic-variability, and smoke
coverage, without forcing every file into the same target-level contract.

### 10.1 Primary Anchors

CN annual primary anchor:

- `601919/annual/2024_年度报告.pdf`

HK annual primary anchors:

- `02498/annual/2022_annual_en.pdf`
- `06862/annual/2024_annual_en.pdf`
- `09987/annual/2024_annual_en.pdf`

HK complex supplement:

- `09987/quarterly/2025_quarterly_q3_en.pdf`

### 10.2 CN Annual Reference Set

Additional CN annual reference coverage should include:

- `600519/annual/2024_年度报告.pdf`
- `600519/annual/2025_年度报告.pdf`
- `601919/annual/2025_年度报告.pdf`
- `688008/annual/2024_年度报告.pdf`
- `688008/annual/2025_年度报告.pdf`

These reference samples exist to prevent the semantic-recovery design from
collapsing into a single-issuer CN optimization.

## 11. Verification Strategy

This phase should verify at four levels.

### 11.1 Structure Recovery Verification

Verify that CN annual and HK annual core statements no longer collapse into
unusable numeric-only output for the primary anchors.

The recovered structure should expose enough signal for downstream consumption,
including:

- stable `table_kind`
- stable row labels
- non-empty or usable column structure
- stable row-to-value bindings

### 11.2 Semantic Normalization Verification

Verify that normalized semantics are stable enough to support registry matching
without issuer-specific branches.

This includes:

- `table_kind`
- `normalized_row_label`
- preserved `statement_scope_guess`
- stable semantic provenance

### 11.3 Fallback Verification

Verify that:

- `Ollama` fallback is triggered only under explicit ambiguity conditions
- fallback result space stays within the first-phase constrained outputs
- fallback results preserve provenance
- fallback does not silently replace deterministic paths

### 11.4 Candidate and Canonical Contract Verification

Verify that:

- candidate-fact and canonical-fact contracts remain structurally compatible
- the current analysis service contract remains stable
- new recovery behavior does not regress the existing CN/HK paths
- target assertions remain future-oriented rather than freezing today's weak
  outputs as intended behavior

## 12. Deliverable Definition

This phase is complete when all of the following are true:

- HK annual primary anchors no longer fail primarily due to total upstream
  structure collapse on the three core statements
- CN annual and HK annual both produce materially more stable normalized table
  semantics than the current path
- the registry operates as a semantic mapping entry point rather than a flat
  alias-only mechanism
- the first `Ollama` fallback phase is integrated in gated form for `table
  kind` and `row label` ambiguity only
- fallback outputs are provenance-preserving and measurable
- candidate/canonical contracts remain compatible with the current analysis
  pipeline

## 13. Non-Goals

This phase does not promise:

- support for all financial reports
- issuer-agnostic perfection across all CN and HK layouts
- complete OCR/vision recovery for image-heavy files
- full LLM-based semantic handling
- LLM-based final fact generation
- complete metric coverage across all statements

The purpose of this phase is to establish a scalable recovery and normalization
framework, not to claim universal extraction maturity.
