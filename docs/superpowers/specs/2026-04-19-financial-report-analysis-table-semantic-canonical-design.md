# Financial Report Analysis Table Semantic Canonical Design

## 1. Goal

This design defines the next Phase-2 step for `financial_report_analysis`:

- harden the table-structure layer so it becomes a stable extraction substrate
- introduce a minimal metric mapping registry
- produce a reliable canonical-fact closed loop for a small, high-value metric set

This phase is intentionally focused on `financial_report_analysis` only. It does
not expand `report` responsibilities and does not redesign the existing
Phase-1 forwarding boundary.

## 2. Scope

This phase covers:

- stronger table-structure stability
- normalized table semantics as an explicit intermediate layer
- a minimal Python-backed metric mapping registry
- a table fact builder that turns normalized table semantics into candidate facts
- stable canonical facts for seven high-value metrics

This phase does not cover:

- broad extractor completeness across all report formats
- a large metric catalog
- evidence-policy redesign
- derivation-policy redesign
- moving registry storage to YAML, JSON, or a database
- changes to `report/src/**`

## 3. Real Sample Coverage

This phase is validated against three real-sample anchors:

- CN annual report
- HK English annual report
- HK `09987` Q3 English report

These anchors serve different purposes:

- CN annual report validates the Chinese annual-report path and point-in-time
  balance-sheet values
- HK English annual report validates the mainstream HK English full-year path
- HK `09987` Q3 validates more complex period semantics such as YTD versus
  single-quarter values and comparison-column handling

`Q4_FY` style quarterly reports are useful but are not treated as a required
precondition for this phase, because they are not the most common HK sample
shape in the current fixture set.

## 4. Architecture Boundary

All new capability in this phase lives inside `financial_report_analysis`.

The primary pipeline becomes:

`pdf -> raw table blocks -> parsed tables -> normalized table semantics -> metric mapping registry -> candidate facts -> canonical facts`

Responsibilities are split as follows:

- the table-structure layer restores stable table structure and table-level
  semantics from PDF data
- normalized table semantics turns parsed tables into stable row and column
  meaning
- the metric mapping registry maps stable table semantics to standard metrics
- the existing resolver, validation, and derivation layers continue to own
  candidate-fact resolution, quality checks, and derived outputs

`metric mapping registry` is not a universal fallback layer. It must not
replace table parsing, fact conflict resolution, validation, or derivation.

## 5. Stable Semantic Inputs

The metric mapping registry is allowed to consume only stable semantic inputs:

- `table_kind`
- `normalized_row_label`
- `column_semantics`
- `period/value context`

The registry must consume normalized table semantics, not raw OCR text and not
ad hoc field labels assembled in downstream code.

`period/value context` is required because table mapping in financial reports is
not determined by row labels alone. The same row family can represent:

- duration values
- point-in-time values
- current-period values
- comparison-period values
- current balance versus opening balance

These distinctions must be represented before registry matching occurs.

## 6. Time Semantics

This phase explicitly separates:

- reporting period semantics
- filing or publication date semantics

Examples:

- a report covering fiscal year 2025 must still map to `2025FY`
- that same annual report may be published during calendar year 2026
- publication year must never cause the extracted reporting period to drift from
  `2025FY` to `2026FY`

This distinction must hold across:

- CN annual reports
- HK English annual reports
- HK quarterly reports with YTD and single-quarter columns

## 7. Module Design

This phase adds or strengthens four focused modules.

### 7.1 Table Structure Layer

The existing table-structure implementation remains the upstream structural
layer. This phase strengthens it so that `ParsedTable` is reliable enough to
support canonical metric extraction.

Required properties:

- preserve row and column alignment
- preserve stable title text
- preserve local table unit and currency context
- preserve period-column semantics
- expose a lightweight `statement_scope_guess` such as `consolidated`,
  `parent_only`, or `unknown`
- preserve cross-page continuation behavior

### 7.2 Normalized Table Semantics

A new semantic layer is introduced between `ParsedTable` and metric mapping.

This layer produces normalized table semantics, not final metric judgments.

It should represent:

- normalized table kind
- normalized row labels
- column roles and comparison roles
- period scope and period identity
- unit and currency context
- value context such as duration versus point-in-time

`normalized_label_hint` remains a semantic hint only. It must not be treated as
the final metric mapping result and must not collapse into `metric_id` at this
layer.

Recommended module shape:

- `financial_report_analysis/models/table_semantics.py`
- `financial_report_analysis/ingestion/table_semantics.py`

### 7.3 Metric Mapping Registry

Registry entries are defined in Python using strong typing, with a loader
interface that allows future externalization without changing call sites.

Recommended module:

- `financial_report_analysis/registries/metric_mapping.py`

Recommended loader interface:

- `load_metric_registry(source=None)`
- `get_metric_definition(metric_id)`
- `iter_metric_definitions()`

In this phase:

- `source=None` loads the built-in Python registry
- external YAML, JSON, or database sources are not implemented yet
- the loader boundary is still defined now so later migration does not change
  higher-level code

The metric mapping registry consumes normalized table semantics produced by the
structure and semantics layers. Metric mapping itself is not part of the table
structure stage.

### 7.4 Table Fact Builder

A new builder turns normalized table semantics plus the metric mapping registry
into candidate facts for the supported metric set.

Recommended module:

- `financial_report_analysis/services/table_fact_builder.py`

Responsibilities:

- choose matching registry definitions
- emit candidate facts with stable metric identity and period semantics
- preserve enough source coordinates for downstream evidence continuity

It must not:

- perform candidate conflict resolution
- decide final canonical winners
- own derivation or validation policy

## 8. Minimal Registry Schema

The first registry version uses two strong types:

- `MetricMappingDefinition`
- `MetricRegistry`

Each metric definition should include:

- `metric_id`
- `statement_type`
- `allowed_table_kinds`
- `normalized_row_labels`
- `period_scope`
- `value_type`
- `unit_expectation`
- `sign_rule`
- `aliases_by_market`

Field intent:

- `metric_id`: canonical metric name
- `statement_type`: target statement family in canonical facts
- `allowed_table_kinds`: which table kinds may legally source the metric
- `normalized_row_labels`: primary semantic match anchors
- `period_scope`: duration versus point-in-time expectation
- `value_type`: amount, count, ratio, or similar semantic class
- `unit_expectation`: minimal unit constraint
- `sign_rule`: minimal sign-direction expectation
- `aliases_by_market`: small market-specific naming differences without
  changing schema shape

The registry should express recognition and basic semantic constraints. It
should not encode conflict resolution, evidence preference, or derivation
policy.

## 9. High-Value Metric Set

This phase guarantees canonical output for exactly these seven metrics:

- `revenue`
- `operating_profit`
- `net_profit`
- `operating_cash_flow`
- `cash`
- `total_assets`
- `total_liabilities`

These metrics are chosen because they:

- cover all three primary financial statements
- are widely consumed by downstream analysis
- provide a meaningful canonical-fact closed loop without expanding into a
  broad extractor program

This phase does not guarantee that every sample contains all seven metrics.
Instead, each sample must reliably produce the subset that should be present for
that report type and table coverage.

## 10. Canonical Fact Guarantee

This phase does not stop at candidate-fact recognition.

For the supported samples and supported metrics, the expected outcome is:

- metrics are extracted through the table-driven path
- they are normalized and resolved through the existing pipeline
- they land in canonical facts in a stable, consumable form

That is the required closed loop for this phase.

The goal is not "we recognized the right row." The goal is "the right metric is
available as a reliable canonical fact for downstream consumers."

## 11. False-Positive Protection

The table-driven path must explicitly avoid obvious semantic false positives.

Examples that must not be emitted as canonical versions of the high-value
metric set:

- `Deferred revenue` being treated as `revenue`
- `Revenue growth` being treated as `revenue`
- non-primary metric-summary rows overriding primary income-statement rows
- point-in-time rows being misclassified as duration metrics

This protection should come from the combination of:

- stable table semantics
- allowed table kinds
- period/value context
- minimal registry constraints

It should not rely on one-off ad hoc exceptions in downstream adapters.

This phase also keeps `ParsedTable` and related structures out of fact-layer
territory. They must not grow into semi-fact objects carrying fields such as
`metric_id`, `canonical_value`, or `fact_confidence`.

## 12. Verification Matrix

This phase should verify at four levels.

### 12.1 Table Structure Verification

Verify that:

- row and column alignment are preserved
- title extraction remains stable
- local unit and currency context is preserved
- period columns remain stable
- continuation stitching remains stable
- when continuation ownership is ambiguous, the parser prefers separation over
  forced merge and preserves a continuation suspicion marker or confidence

### 12.2 Semantic Layer Verification

Verify that normalized table semantics expose:

- `table_kind`
- `normalized_row_label`
- `column_semantics`
- `period/value context`
- `statement_scope_guess`

### 12.3 Registry and Fact Builder Verification

Verify that:

- the seven metrics can be matched from normalized table semantics
- false positives such as `Deferred revenue` and `Revenue growth` are rejected
- annual and quarterly period semantics stay correct
- filing year does not corrupt reporting-period identity

### 12.4 Canonical Output Verification

Verify that:

- supported metrics enter canonical facts
- existing validation behavior remains compatible
- existing API contract remains compatible
- existing unsupported-language semantics remain compatible

## 13. Deliverable Definition

This phase is complete when all of the following are true:

- the table structure layer is stable enough to support canonical extraction for
  the target sample set
- normalized table semantics exist as an explicit layer
- a minimal Python-backed metric mapping registry exists with a stable loader
  interface
- the seven supported metrics reliably appear as canonical facts on the target
  samples
- regression tests lock both the semantic layer and the canonical outputs
- `ParsedTable` exposes stable `table_kind`, period columns, unit/currency
  context, and row-to-value bindings consumable by the downstream fact builder

## 14. Out of Scope

This phase does not attempt to:

- become a complete HK or CN universal extractor
- support a broad metric catalog
- externalize the registry storage format
- redesign evidence policy
- redesign derivation policy
- redesign `report` forwarding behavior

Those can follow once the table-semantic substrate is stable.
