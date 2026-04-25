# Financial Report Analysis Metric Governance Umbrella Design

> **Status:** Active umbrella spec
> **Date:** 2026-04-25
> **Scope Type:** Architecture and multi-phase roadmap
> **Current Implementation Target:** Phase 1 only

## 1. Purpose

This spec defines the long-term metric governance architecture for
`financial-report-analysis`.

The project now has enough extraction, persistence, review, lineage, recompute,
availability, and Turtle export infrastructure that the next major risk is no
longer "can the system extract anything?". The sharper risk is:

```text
unknown or unsupported field
-> provisional/custom metric identity
-> canonical promotion
-> key facts / derived facts / Turtle export
-> downstream analysis silently treats it as stable
```

Metric governance prevents that failure mode. It establishes clear boundaries
between deterministic supported metric mapping, metric identity resolution,
custom/provisional lifecycle, automatic consumption rules, and human/agent review
surfaces.

This is an umbrella design. It intentionally covers the full lifecycle, but only
Phase 1 is intended for immediate implementation.

## 2. Current Architecture Analysis

### 2.1 Extraction and Mapping Path

The current table-driven path is:

```text
pdf
-> table structure recovery
-> normalized table semantics
-> MetricMappingRegistry
-> candidate facts
-> FactNormalizer / MetricRegistry
-> ConflictResolver
-> canonical facts
-> derived facts
-> validation / quality gate
-> ReportAdapter key facts
-> P5 dataset / Turtle export
```

The main statement extraction path uses
`financial_report_analysis.registries.metric_mapping.MetricMappingRegistry`.
That registry maps deterministic table semantics to supported metric ids. It is
where fields like `revenue`, `total_assets`, `accounts_receiv`, or
`restricted_cash` become first-class supported metrics.

Separately,
`financial_report_analysis.registries.metric_registry.MetricRegistry` can resolve
raw labels to standard metrics or generate `custom::...` ids with
`registry_status="provisional"`. This is the beginning of metric identity
governance, but it is not yet a full lifecycle.

### 2.2 Existing Strengths

The codebase already has several pieces that should be preserved:

- `MetricMappingRegistry` is deterministic and scoped by table kind, row label,
  period shape, and market.
- `MetricRegistry` can create stable provisional custom ids.
- fact `extensions` already carry semantic provenance such as
  `semantic_source`, `fallback_reason`, `unit_semantic_source`, and
  `currency_semantic_source`.
- `ConflictResolver` already produces review packets for source conflicts.
- `ValidationService` already turns validation issues into `review_required`.
- storage models already contain `MetricRegistryEntryRecord`, so durable metric
  registry state has a future landing zone.
- review, lineage, recompute, and availability surfaces already exist for P5 and
  persisted artifacts.

### 2.3 Current Gaps

The remaining gaps are governance gaps, not basic extraction gaps:

1. **Registry roles are ambiguous.**
   `MetricRegistry` and `MetricMappingRegistry` solve different problems, but
   the names and loader boundaries make that easy to miss.

2. **Provisional metadata is not a stable contract.**
   `MetricRegistryEntry.registry_status` exists, but normalized candidate facts
   do not consistently carry a governance metadata block that downstream
   services can enforce.

3. **Automatic consumption policy is incomplete.**
   Provisional/custom metrics can become canonical if they enter the pipeline.
   `ReportAdapter`, `DerivationService`, P5 dataset assembly, and Turtle export
   do not yet share a single policy for blocking unreviewed custom metrics.

4. **Review surface is not metric-governance-specific.**
   Source-conflict review packets exist, but there is no dedicated surface that
   lists provisional metric candidates, evidence, suggested action, and
   lifecycle status.

5. **Durable lifecycle is not yet implemented.**
   There is no approved/mapped/deprecated/blacklisted workflow, no durable
   mapping decision lookup, no shadow merge scoring, and no write API for metric
   review decisions.

## 3. Design Principles

### 3.1 Deterministic Supported Metrics Remain the Main Path

Supported metrics should enter automatic analysis only through deterministic,
test-covered definitions:

```text
normalized table semantics -> MetricMappingRegistry -> supported metric id
```

Adding a high-value Turtle field should normally mean adding deterministic
semantics and mapping coverage, not relying on provisional custom metrics.

### 3.2 Provisional Custom Metrics Are Review Signals

Unknown metrics may enter the fact ledger as reviewable signals. They must not
silently become automatic analysis inputs.

Before review, provisional custom metrics are allowed in:

- candidate facts
- review packets
- availability / diagnostic reports
- persisted extracted artifacts as reviewable evidence

Before review, they are not allowed in:

- `key_facts`
- derived facts / TTM / ratios
- Turtle formal export rows
- automatic core analysis
- quality-gate `pass` assertions

### 3.3 Lifecycle Decisions Are Governance Decisions

LLM fallback, table semantics, and note disclosure locators can help classify
evidence. They cannot approve a custom metric, map it to a standard metric, or
decide deprecation/blacklist state. Those are lifecycle decisions.

### 3.4 Governance Metadata Must Travel With Facts

Downstream services should not infer governance state from metric id string
prefixes alone. `custom::...` remains useful, but the stable contract should be
explicit metadata.

Minimum governance metadata:

```text
extensions.metric_governance.registry_status
extensions.metric_governance.metric_namespace
extensions.metric_governance.review_required
extensions.metric_governance.auto_analysis_allowed
extensions.metric_governance.governance_reason
```

For backward-compatible consumers, Phase 1 may also mirror selected fields at
top-level extension keys, but the nested `metric_governance` object is the
canonical contract.

## 4. Registry Boundaries

### 4.1 MetricMappingRegistry

Responsibility:

- deterministic supported metric mapping;
- table semantics to supported metric id;
- market aliases and negative-control-safe labels;
- period scope, table kind, and value type expectations.

Non-responsibilities:

- generating custom metric ids;
- approving provisional metrics;
- storing review decisions;
- mapping arbitrary prose to facts.

Current location:

`financial_report_analysis.registries.metric_mapping`

### 4.2 MetricIdentityRegistry

Responsibility:

- resolve a raw label into a known standard metric identity when possible;
- generate stable provisional custom ids for unknown raw labels;
- assign initial governance metadata.

Current implementation seed:

`financial_report_analysis.registries.metric_registry.MetricRegistry`

Recommended conceptual name:

`MetricIdentityRegistry`

The implementation does not need to rename the class in Phase 1. Phase 1 should
document the role and may introduce aliases or helper functions if that reduces
confusion without churn.

### 4.3 CustomMetricLifecycleRegistry

Responsibility:

- store review decisions;
- persist lifecycle state;
- map provisional custom metrics to supported standard metrics;
- deprecate or blacklist unsupported metrics;
- expose state for recompute and review.

This is a future durable component. Phase 1 should not implement the durable
registry.

## 5. Lifecycle States

The full lifecycle is:

```text
unknown raw label
-> provisional_custom
-> approved_custom
-> mapped_to_standard
-> deprecated
-> blacklisted
```

### 5.1 `standard`

A first-class supported metric. It may enter canonical facts, key facts,
derived facts, P5 datasets, and Turtle exports if it passes existing validation
and conflict rules.

### 5.2 `provisional_custom`

A stable custom metric identity generated from an unknown raw label. It is a
review signal, not an automatic analysis input.

### 5.3 `approved_custom`

A reviewed custom metric that remains custom because no standard metric is
appropriate. It may be exposed in review-approved outputs, but it does not
automatically enter Turtle formal exports unless a downstream contract opts in.

### 5.4 `mapped_to_standard`

A reviewed custom metric whose evidence should be consumed as a standard metric.
Future recompute should map the old custom identity to the selected standard
metric id.

### 5.5 `deprecated`

A metric identity retained for audit compatibility but no longer used for new
automatic outputs.

### 5.6 `blacklisted`

A metric identity or raw-label pattern that must not enter automatic outputs and
should normally produce a blocked/review signal if encountered again.

## 6. Consumption Policy

| State | Candidate facts | Canonical facts | Key facts | Derived/TTM | Turtle export | Quality gate |
| --- | --- | --- | --- | --- | --- | --- |
| `standard` | allowed | allowed | allowed | allowed | allowed | can pass |
| `provisional_custom` | allowed | Phase 1: blocked from canonical | blocked | blocked | blocked | review |
| `approved_custom` | allowed | allowed | blocked by default | blocked by default | blocked by default | review/pass depends on output contract |
| `mapped_to_standard` | allowed | allowed as standard | allowed | allowed | allowed | can pass |
| `deprecated` | review only | blocked by default | blocked | blocked | blocked | review |
| `blacklisted` | blocked/review only | blocked | blocked | blocked | blocked | review/fail depending on severity |

Phase 1 implements the `standard` and `provisional_custom` parts only.

## 7. Phase Roadmap

### Phase 1: Registry Boundary and Provisional Guardrails

Goal:

- make registry roles explicit;
- define the governance metadata contract;
- propagate provisional/custom status through normalization;
- prevent provisional custom metrics from entering canonical facts, key facts,
  derived facts, and Turtle formal outputs;
- surface validation/review signals.

Phase 1 does not implement durable review decisions.

### Phase 2: Review Surface and Mapping Decisions

Goal:

- list provisional metric candidates with evidence;
- show raw label, value, source table/page, governance state, and suggested
  actions;
- allow a reviewer to record conceptual decisions in a non-durable or
  lightweight durable form;
- keep API surface narrow and separate from `/api/v1/analysis/extract`.

### Phase 3: Durable Lifecycle Registry

Goal:

- persist custom metric lifecycle records;
- support approve, map-to-standard, deprecate, and blacklist decisions;
- preserve reviewer, timestamp, reason, evidence, and target mapping;
- make recompute read lifecycle decisions deterministically.

### Phase 4: Workflow, API, and Recompute Integration

Goal:

- expose review workflow endpoints;
- integrate lifecycle decisions into recompute;
- support audit and diff views;
- optionally support approval workflow and async job handles if business needs
  require them.

## 8. Phase 1 Detailed Scope

Phase 1 should create a narrow but enforceable guardrail.

In scope:

- document registry roles in package/module docstrings or dedicated docs;
- introduce governance metadata helper functions;
- make `FactNormalizer` add `metric_governance` metadata based on
  `MetricRegistryEntry`;
- keep deterministic supported candidate ids unchanged;
- block provisional custom candidates from canonical promotion in
  `ConflictResolver`;
- add review packets or validation issues for blocked provisional custom
  candidates;
- make `ValidationService` report a review-required status when provisional
  metric candidates are encountered;
- make `ReportAdapter` defensively exclude facts whose governance metadata says
  `auto_analysis_allowed=false`;
- add tests showing provisional custom metrics do not enter key facts or derived
  facts.

Out of scope:

- renaming public classes;
- external YAML/JSON/DB mapping registry loading;
- durable lifecycle decision storage;
- approve/map/deprecate/blacklist APIs;
- UI;
- whole-document LLM assessment;
- changing Turtle field coverage.

## 9. Interaction With Fallback

Semantic fallback may help resolve bounded ambiguities:

- table kind;
- currency/unit when deterministic context is ambiguous;
- row label among a closed set of supported labels;
- note/disclosure locator among target metrics.

Semantic fallback must not:

- create new metric lifecycle states;
- approve a provisional custom metric;
- map custom metrics to standard metrics;
- directly generate canonical facts;
- override governance consumption policy.

If fallback output produces a standard supported metric through an allowed closed
set, that fact follows standard metric policy. If fallback output cannot map to
a supported metric, it must remain a review signal.

## 10. Interaction With Storage

Current storage already has `MetricRegistryEntryRecord`, but Phase 1 should not
depend on durable registry state.

Future durable lifecycle state should preserve:

- metric id;
- raw label;
- normalized label;
- statement type;
- accounting standard;
- industry slug;
- parent metric id;
- lifecycle status;
- mapped standard metric id when applicable;
- reviewer / actor;
- decision reason;
- evidence pointers;
- created and updated timestamps.

## 11. Interaction With API and P5/Turtle

Phase 1 should protect existing API and P5/Turtle consumers:

- `key_facts` must not include provisional custom metrics.
- derived TTM facts must not be built from provisional custom canonical facts.
- P5 dataset and Turtle export should only see standard or explicitly allowed
  reviewed facts. Since reviewed custom output is not in Phase 1, only standard
  facts should flow through.
- analysis snapshots and review packets may include provisional review signals.

## 12. Acceptance Criteria

Phase 1 is complete when:

- a candidate with an unknown/raw/custom metric receives explicit
  `metric_governance` metadata;
- standard mapped candidates retain automatic consumption behavior;
- provisional custom metrics do not become canonical facts;
- provisional custom metrics do not appear in `key_facts`;
- provisional custom metrics do not produce derived TTM facts;
- validation/quality gate enters `review` when provisional custom candidates are
  present;
- Phase 1 review packets expose the metric id, candidate value, review reason,
  and `evidence_bundle_id`; the full candidate context remains inspectable
  through the persisted extracted artifact / candidate fact payload. Later phases
  may add raw label, table coordinates, extraction method, and governance
  metadata directly to a dedicated metric-governance review surface;
- existing real-PDF deterministic regression tests continue to pass.

## 13. Non-Goals

This umbrella spec does not require immediate implementation of:

- all v0.15 field gaps;
- new Turtle coverage phases;
- full custom metric UI;
- durable approval workflow;
- async job orchestration;
- Postgres migration;
- object storage;
- LLM-driven whole-document fact extraction.

## 14. Recommended Next Step

Write and execute a Phase 1 implementation plan:

```text
Metric Governance Phase 1
-> registry boundary documentation
-> governance metadata helpers
-> FactNormalizer propagation
-> ConflictResolver / ValidationService guardrails
-> ReportAdapter defensive exclusion
-> focused unit and integration tests
```

Only after Phase 1 is complete should the project return to post-P5 field
enhancement work or durable lifecycle workflow design.
