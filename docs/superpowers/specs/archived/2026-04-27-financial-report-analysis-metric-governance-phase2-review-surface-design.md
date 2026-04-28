# Financial Report Analysis Metric Governance Phase 2 Review Surface Design

> **Status:** Active phase spec
> **Date:** 2026-04-27
> **Scope Type:** Narrow design and implementation target
> **Parent Spec:** `docs/superpowers/specs/active/2026-04-25-financial-report-analysis-metric-governance-umbrella-design.md`
> **Implements:** Metric governance umbrella Phase 2

## 1. Purpose

This spec defines Phase 2 of metric governance for
`financial-report-analysis`.

Phase 1 established the guardrail:

```text
provisional custom metric
-> review-required signal
-> blocked from canonical / key facts / derived facts / Turtle
```

That guardrail is necessary, but by itself it leaves a product gap. The system
can detect provisional metrics, yet it still lacks a dedicated place to inspect
them, compare evidence, and record a first governance decision without changing
the canonical pipeline.

Phase 2 fills that gap by adding a focused metric-governance review surface and
a lightweight decision write path.

## 2. Phase 2 Goal

Phase 2 should make provisional metric candidates visible and actionable while
keeping canonical consumption rules unchanged.

The target workflow is:

```text
persisted extracted artifact / candidate facts
-> metric governance review list
-> reviewer inspects evidence and current governance state
-> reviewer records lightweight decision
-> subsequent reads show latest decision annotation
```

Phase 2 does not make the recorded decision automatically affect canonical
facts, key facts, derived facts, P5 datasets, Turtle exports, or recompute.

## 3. Problem Statement

After Phase 1, provisional custom metrics are correctly blocked from automatic
analysis, but the operator experience is still incomplete:

- there is no metric-governance-specific review list;
- provisional candidates must be inferred indirectly from extracted artifacts or
  generic review packets;
- there is no dedicated way to say "keep this provisional" or "this should map
  to `revenue`";
- there is no read model that shows the latest governance decision next to the
  candidate evidence.

This creates friction for both humans and agents. It also makes it harder to
prepare for later durable lifecycle work because the project has nowhere to
capture conceptual mapping decisions.

## 4. Design Principles

### 4.1 Keep Phase 1 Guardrails Intact

Phase 2 must not weaken Phase 1:

- provisional custom metrics remain blocked from canonical promotion;
- `key_facts` remain standard-only;
- derived facts / TTM remain standard-only;
- P5 and Turtle remain standard-only;
- quality-gate pass semantics do not expand.

### 4.2 Review Surface Must Be Separate From Extraction

The review surface is not part of `/api/v1/analysis/extract`.

Extraction remains a pipeline that produces facts, review packets, lineage, and
artifacts. Metric-governance review is a separate read/write surface that
consumes persisted outputs after extraction is complete.

### 4.3 Decisions Are Lightweight and Non-Executable

Phase 2 decisions are conceptual governance decisions, not lifecycle execution.

They may say:

- `keep_provisional`
- `map_to_standard`

But they do not yet:

- remap historical candidate facts;
- trigger recompute;
- authorize provisional facts for canonical output;
- replace the future durable lifecycle registry.

### 4.4 Read-Time Annotation Is Required

The review surface should not act like a write-only inbox.

When a decision has already been recorded, later review reads must show that
state directly so the reviewer can tell whether the candidate is still
untriaged, already marked for standard mapping, or explicitly retained as
provisional.

## 5. In Scope

- define a metric-governance review item contract for provisional candidates;
- expose a read surface for listing review items;
- expose a read surface for a single review item with evidence context;
- add a lightweight write API for governance decisions;
- persist decisions in a minimal database-backed record;
- annotate review reads with the latest persisted decision;
- keep the implementation narrow enough that Phase 3 can later replace or
  extend the decision model without breaking extraction contracts.

## 6. Out of Scope

- changing canonical promotion rules;
- consuming recorded decisions in recompute;
- automatically mapping provisional metrics into standard metrics;
- introducing `approved_custom`, `deprecated`, or `blacklisted` write flows;
- durable full lifecycle registry;
- approval workflow state machines;
- async review jobs;
- UI;
- changing Turtle field coverage.

## 7. Decision Model

Phase 2 supports exactly two decision types:

### 7.1 `keep_provisional`

Meaning:

- the reviewer confirms the candidate should remain a provisional custom metric
  for now;
- no standard mapping is selected;
- the candidate remains blocked from automatic analysis.

Required fields:

- decision type
- reviewer or actor identity
- reason

### 7.2 `map_to_standard`

Meaning:

- the reviewer believes this provisional candidate conceptually corresponds to a
  supported standard metric;
- the decision is advisory in Phase 2 and does not itself rewrite facts.

Required fields:

- decision type
- reviewer or actor identity
- reason
- target standard metric id

Validation rule:

- target metric id must resolve to a supported standard metric, not a custom or
  provisional metric.

## 8. Data Model Direction

Phase 2 should introduce a lightweight decision record in the existing database
layer.

This record is intentionally smaller than the future lifecycle registry. It only
needs enough data to support review reads and decision history.

Minimum fields:

- decision id
- issuer id or issuer key
- report id or extracted artifact id
- candidate metric id
- raw label
- normalized label when available
- statement type
- evidence bundle id
- decision type
- target standard metric id when applicable
- reason
- actor
- created at

The implementation may store a foreign key to the extracted artifact, candidate
group identifier, or another stable review item key, as long as the read path
can deterministically find the latest decision for a review item.

Phase 2 does not require:

- lifecycle status history beyond append-only decision records;
- merge scoring;
- deprecation metadata;
- reviewer assignment workflow.

## 9. Review Item Contract

The review list should expose a contract shaped around governance review rather
than generic extraction internals.

Each item should include at least:

- review item id
- issuer identity
- report identity
- provisional metric id
- raw label
- normalized label when available
- candidate value
- period label or fiscal context when available
- statement type
- source page
- source table identifier or locator
- evidence bundle id
- current `metric_governance` metadata
- latest decision annotation, if any

The latest decision annotation should include:

- decision type
- target standard metric id when present
- actor
- reason
- created at

The full extracted candidate payload may remain available through existing
artifact lookup surfaces rather than being duplicated into the review contract.

## 10. Read Surface

Phase 2 should expose a narrow API surface dedicated to metric governance.

Expected reads:

### 10.1 Review List

List provisional review items, with optional filters such as:

- issuer
- fiscal year
- report id
- statement type
- decision state (`unreviewed`, `has_decision`)

The response should be summary-friendly and annotate each item with the latest
decision if one exists.

### 10.2 Review Detail

Return one review item with richer evidence context, including candidate-level
fields needed to support a mapping decision.

The detail read may assemble its payload from existing extracted artifact and
candidate structures as long as the returned contract is stable.

## 11. Write Surface

Phase 2 should expose a lightweight decision write endpoint separate from
extraction.

Expected write:

### 11.1 Record Decision

Input:

- review item id
- decision type
- actor
- reason
- target standard metric id when decision type is `map_to_standard`

Behavior:

- validate that the referenced review item exists and is currently a provisional
  metric review item;
- reject writes for standard metrics or non-governance review packets;
- validate the target metric when mapping to standard;
- persist the decision record;
- return the stored decision and updated latest-decision annotation.

Phase 2 may allow multiple decisions over time for the same review item, but
read APIs should default to showing the latest one.

## 12. Service Boundaries

Phase 2 should add a focused service and repository boundary rather than mixing
logic into extraction services.

Recommended components:

- `MetricGovernanceReviewService`
  - assembles review list and review detail models from persisted artifacts and
    candidate payloads;
  - applies latest-decision annotation.
- `MetricGovernanceDecisionRepository`
  - stores and queries lightweight decision records.
- API handlers dedicated to metric-governance review.

Existing extraction services such as `FactNormalizer`, `ConflictResolver`,
`ValidationService`, `ReportAdapter`, and P5/Turtle paths should remain
unchanged except where they already provide the metadata Phase 2 consumes.

## 13. Interaction With Existing Surfaces

### 13.1 Extracted Artifacts

Phase 2 reads from persisted extracted artifacts and candidate payloads. It does
not require changing their persistence contract unless a stable provisional
review item key is missing.

### 13.2 Review Packets

Existing review packets may still exist, but they are not sufficient as the
Phase 2 public contract. Metric-governance review items should be assembled into
their own dedicated surface.

### 13.3 P5, Turtle, and Key Facts

No behavior change in Phase 2:

- provisional metrics remain excluded;
- recorded mapping decisions do not grant passage into downstream automatic
  outputs.

### 13.4 Recompute

Phase 2 decisions may later become inputs to Phase 3 or Phase 4, but in Phase 2
recompute should ignore them.

## 14. Error Handling

Phase 2 should explicitly handle:

- unknown review item id -> `404`
- attempt to write decision for non-provisional item -> `422`
- `map_to_standard` with unsupported or custom target metric id -> `422`
- malformed payload -> `422`
- storage unavailable -> `503`

Write failures must not affect extraction or previously persisted artifacts.

## 15. Testing Strategy

Phase 2 should add:

### 15.1 Unit Tests

- review item assembly from persisted provisional candidates;
- latest-decision annotation behavior;
- decision validation for `keep_provisional` and `map_to_standard`;
- rejection of unsupported target metric ids.

### 15.2 Integration Tests

- list endpoint returns provisional review items only;
- detail endpoint returns evidence context and latest decision annotation;
- write endpoint stores a decision and later reads reflect it;
- API remains separate from `/api/v1/analysis/extract`.

### 15.3 Regression Tests

- Phase 1 provisional guardrails still hold after a decision is recorded;
- `map_to_standard` in Phase 2 does not automatically create canonical facts,
  key facts, derived facts, P5 rows, or Turtle export rows.

## 16. Acceptance Criteria

Phase 2 is complete when:

- provisional metric candidates can be listed through a dedicated governance
  review surface;
- a single review item can be read with evidence context and governance
  metadata;
- reviewers can record `keep_provisional` and `map_to_standard` decisions
  through a dedicated write path;
- decisions persist in a lightweight database-backed record;
- later reads show the latest decision annotation;
- Phase 1 guardrails remain unchanged;
- extraction, canonical promotion, P5, Turtle, and recompute do not yet consume
  Phase 2 decisions automatically.

## 17. Recommended Next Step

Write an implementation plan focused on:

```text
Metric Governance Phase 2
-> review item contract
-> lightweight decision record and repository
-> review list/detail service
-> decision write endpoint
-> latest-decision annotation
-> focused unit and integration tests
```
