# Financial Report Extraction And Semantic Fallback Phase 2 Design

## 1. Goal

This phase continues from the completed semantic-recovery baseline and focuses
on two coordinated objectives:

- strengthen the foundational extraction path for annual and quarterly
  financial reports
- evaluate and selectively extend `Ollama` semantic fallback phase 2

The primary objective is stronger and more stable base extraction. The
secondary objective is to evaluate and limitedly integrate the next fallback
scope, prioritizing:

- `table kind`
- `row label`
- limited `unit / currency interpretation`

This phase does not assume that `unit / currency` fallback must become a
dominant or mandatory capability. It is a bounded enhancement layered on top of
the deterministic extraction and semantic-normalization path.

## 2. Scope

This phase is in scope for the following deliverables:

- stronger annual and quarterly structure recovery for mainstream CN and HK
  reports
- stronger row-to-value binding, header hierarchy, and local semantic context
- stronger deterministic semantic normalization for:
  - `table_kind`
  - `normalized_row_label`
  - local `unit`
  - local `currency`
- evaluation and limited integration of `Ollama` fallback phase 2 for:
  - `table kind`
  - `row label`
  - local `unit / currency interpretation`
- broader real-sample validation across CN and HK anchors and reference sets
- preservation of the current candidate-fact, canonical-fact, and analysis API
  contracts

## 3. Positioning

This phase is not a sample-specific patch cycle and not a shift to LLM-led
extraction.

It extends the unified architecture already established in the previous phase:

- deterministic structure recovery remains the primary extraction path
- deterministic semantic normalization remains the primary semantic path
- `Ollama` remains a gated ambiguity fallback, not a replacement for
  extraction, mapping, or canonical resolution

The intent is to make the framework more scalable across report families while
keeping the architecture structured, auditable, and regression-friendly.

## 4. Current State

The current system already provides:

- usable annual-report structure recovery for the current CN and HK annual
  anchors
- normalized table semantics with provenance support
- a semantic mapping registry and table-driven fact path
- real `Ollama` fallback for:
  - `table kind`
  - `row label`
- real-report probe datasets, gated evaluation, and promoted always-on
  regressions for stable fallback cases

The main remaining enhancement opportunities are now:

- broader and more stable base extraction across more annual and quarterly
  layouts
- stronger local `unit / currency` interpretation
- clearer evaluation of where fallback meaningfully helps and where
  deterministic logic should be strengthened instead

At this stage, the main blocker is no longer total structure collapse on the
current anchors. The next work is about expanding robustness and reducing
semantic fragility.

## 5. Architecture

The primary pipeline remains:

`pdf -> structure recovery -> normalized table semantics -> metric mapping registry -> candidate facts -> canonical facts`

This phase preserves that architecture.

`normalized table semantics` must be produced primarily by deterministic
structure and semantic logic, with gated LLM fallback only for selected
ambiguous cases.

That means:

- the deterministic path remains the semantic default
- fallback is an auxiliary semantic plug-in within the normalization layer
- fallback does not create a parallel extraction path
- fallback does not directly emit candidate or canonical financial facts

## 6. Structure Recovery Enhancements

The structure-recovery layer should be extended to improve:

- annual and quarterly table-block recovery
- header hierarchy preservation
- row-label preservation
- row-to-value bindings
- local table context used for semantic interpretation
- explicit ambiguity markers where confidence is low

This layer should continue to avoid issuer-specific extraction branches as the
primary strategy.

The preferred behavior remains:

- recover as much stable structure as possible
- preserve uncertainty explicitly
- avoid silently flattening structure into misleading low-information output

## 7. Semantic Normalization Enhancements

The deterministic semantic-normalization layer should continue to strengthen:

- `table_kind`
- `normalized_row_label`
- local `unit`
- local `currency`
- value-shape and comparison-role interpretation where already supported by the
  deterministic path

This layer remains fact-agnostic:

- it should not emit final `metric_id`
- it should not emit final numeric transformations
- it should not decide canonical winners

Its job is to make the structure-recovery output semantically usable by the
registry and fact builder.

## 8. Ollama Semantic Fallback Phase 2

`Ollama` phase 2 remains a limited semantic fallback layer.

### 8.1 In Scope

Fallback may assist with:

- `table kind disambiguation`
- `row label normalization`
- local `unit / currency interpretation`

### 8.2 Out Of Scope

This phase does not include:

- `period semantics` fallback
- `unit propagation strategy`
- `currency propagation strategy`
- direct candidate fact generation
- direct canonical resolution
- LLM-driven validation or derivation

### 8.3 Trigger Model

Fallback must remain:

- gated
- opt-in
- ambiguity-driven
- provenance-preserving

The deterministic path runs first.
Fallback is only allowed when deterministic logic cannot confidently resolve the
local semantic question.

### 8.4 Provenance

Every fallback-assisted output must preserve at least:

- `semantic_source = "llm_fallback"`
- `semantic_confidence`
- `fallback_reason`

## 9. Output Limits

This phase keeps fallback outputs tightly constrained.

### 9.1 Table Kind

Allowed outputs:

- `income_statement`
- `balance_sheet`
- `cash_flow_statement`
- `key_metrics`
- `unknown`

### 9.2 Row Label

Allowed outputs:

- `revenue`
- `operating_profit`
- `net_profit`
- `operating_cash_flow`
- `cash`
- `total_assets`
- `total_liabilities`
- `none`

### 9.3 Currency

Allowed outputs:

- `CNY`
- `HKD`
- `USD`
- `unknown`

### 9.4 Unit

Allowed outputs:

- `yuan`
- `thousand`
- `million`
- `billion`
- `percent`
- `unknown`

These `unit / currency` outputs are local semantic interpretations only, not
document-wide or table-wide propagation decisions.

## 10. Sample Strategy

### 10.1 Primary Anchors

CN annual primary anchor:

- `601919/annual/2024_年度报告.pdf`

HK annual primary anchors:

- `02498/annual/2022_annual_en.pdf`
- `06862/annual/2024_annual_en.pdf`
- `09987/annual/2024_annual_en.pdf`

HK quarterly supplement:

- `09987/quarterly/2025_quarterly_q3_en.pdf`

### 10.2 Reference Sets

CN annual reference set:

- `600519/annual/2024_年度报告.pdf`
- `600519/annual/2025_年度报告.pdf`
- `601919/annual/2025_年度报告.pdf`
- `688008/annual/2024_年度报告.pdf`
- `688008/annual/2025_年度报告.pdf`

Additional quarterly or semiannual samples may be added later as reference
coverage, but they are not required to become target-level anchors in this
phase.

## 11. Verification Strategy

This phase should verify at five levels:

### 11.1 Structure Recovery Regression

Verify that annual and quarterly samples preserve usable:

- row labels
- row-to-value bindings
- header hierarchy
- local context for semantic interpretation

### 11.2 Deterministic Semantic Normalization Regression

Verify that deterministic logic remains the default source of semantics where
it is already adequate.

### 11.3 Fallback Evaluation

Verify that fallback:

- triggers only under explicit ambiguity
- stays within constrained output sets
- preserves provenance
- improves local semantic interpretation in realistic cases

### 11.4 Promotion Regression

Maintain a smaller set of stable, always-on promoted fallback cases for:

- positive label normalization
- negative controls
- any future promoted `unit / currency` fallback cases

### 11.5 Contract Regression

Verify that:

- candidate-fact structure remains compatible
- canonical-fact structure remains compatible
- analysis API output remains compatible
- `report/` forwarding semantics remain unchanged

## 12. Deliverable Definition

This phase is complete when all of the following are true:

- the base extraction path is more stable across the selected annual and
  quarterly sample set
- deterministic semantic normalization covers a broader set of realistic
  structures and local contexts
- limited `unit / currency` fallback is integrated in gated form, with
  constrained outputs and provenance
- the system preserves the current candidate/canonical/API contract
- fallback outcomes can be measured and, where appropriate, promoted back into
  deterministic rules or registry coverage

## 13. Non-Goals

This phase does not promise:

- universal extraction across all financial reports
- support for image-heavy OCR-first documents
- period-semantics fallback
- unit or currency propagation-strategy inference
- LLM-led extraction as the primary path
- direct LLM fact generation
- direct LLM canonical resolution
- full metric-catalog expansion beyond the current high-value focus

The goal is to deepen the framework, not to replace its structured core.
