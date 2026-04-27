# Financial Report Analysis Metric Governance Phase 3 Lifecycle Registry Design

> **Status:** Active phase spec
> **Date:** 2026-04-27
> **Scope Type:** Narrow design and implementation target
> **Parent Spec:** `docs/superpowers/specs/active/2026-04-25-financial-report-analysis-metric-governance-umbrella-design.md`
> **Implements:** Metric governance umbrella Phase 3

## 1. Purpose

This spec defines Phase 3 of metric governance for
`financial-report-analysis`.

Phase 1 established the guardrail:

```text
provisional custom metric
-> review-required signal
-> blocked from canonical / key facts / derived facts / Turtle
```

Phase 2 added a review surface and lightweight review-item-scoped decisions:

```text
persisted extracted artifact / candidate facts
-> metric governance review list/detail
-> reviewer records advisory decision
-> later review reads show latest decision annotation
```

Phase 3 introduces the durable lifecycle registry that will become the
authoritative source for custom metric lifecycle state. It does not yet make
those lifecycle decisions affect extraction, canonical facts, P5 datasets,
Turtle exports, or recompute output.

## 2. Phase 3 Goal

Phase 3 should create a durable, auditable lifecycle model for custom metric
concepts and a deterministic internal read contract.

The target workflow is:

```text
provisional candidate / review item
-> explicit candidate-to-lifecycle-entry link
-> append-only lifecycle decision
-> deterministic lifecycle state read
-> future Phase 4 recompute integration
```

Phase 3 is deliberately narrow. It creates the lifecycle registry and service
contracts that later phases can consume, but it does not expose a new external
lifecycle API and does not change downstream automatic outputs.

## 3. Problem Statement

After Phase 2, reviewers can inspect provisional candidates and record a
lightweight decision such as `keep_provisional` or advisory `map_to_standard`.
That is useful review history, but it is not enough to support durable
governance:

- Phase 2 decisions are scoped to one review item / artifact / candidate;
- Phase 2 decisions are advisory and explicitly non-executable;
- there is no concept-level lifecycle state for a custom metric;
- there is no durable link from a candidate to a governed concept;
- recompute has no deterministic registry contract it can later consume.

Phase 3 fills that gap by separating review annotations from lifecycle truth.

## 4. Design Principles

### 4.1 Preserve Phase 1 Guardrails

Phase 3 must not weaken Phase 1:

- provisional custom metrics remain blocked from canonical promotion;
- `key_facts` remain standard-only unless a later phase explicitly changes
  that rule;
- derived facts and TTM facts remain standard-only;
- P5 and Turtle outputs remain unchanged;
- quality-gate semantics do not expand.

### 4.2 Keep Phase 2 Decisions As Review History

Phase 2 `metric_governance_decisions` are review annotations. They are not
lifecycle registry records and must not be read as executable lifecycle state.

Phase 3 must preserve Phase 2 decisions for history and review context, but it
must not automatically backfill, promote, or reinterpret them during startup,
normal reads, normal writes, recompute, canonical assembly, P5 dataset assembly,
or Turtle export.

### 4.3 Make Lifecycle State Explicit

A custom metric affects Phase 3 lifecycle state only through explicit Phase 3
records:

- a concept-level lifecycle entry;
- an explicit candidate/review-item link to that entry;
- an append-only lifecycle decision.

No lifecycle state should be inferred only from a raw candidate payload, a Phase
2 decision, or the presence of provisional governance metadata.

### 4.4 Prefer Append-Only Audit

Lifecycle changes should be represented as append-only decisions. The current
entry may store denormalized latest state for efficient reads, but the decision
history remains the audit source.

### 4.5 Deterministic Reads First

Phase 3 should make lifecycle state readable in a stable, deterministic way
before wiring it into recompute. Sorting, tie-breaking, and no-state behavior
must be explicit and testable.

## 5. In Scope

- define Phase 3 lifecycle domain contracts;
- introduce durable storage records for lifecycle entries, lifecycle decisions,
  and candidate links;
- add repository methods for saving and reading lifecycle data;
- add a service layer for lifecycle validation, writes, and deterministic reads;
- model the four lifecycle actions from the umbrella spec:
  `approve_custom`, `map_to_standard`, `deprecate`, and `blacklist`;
- validate `map_to_standard` targets against supported standard metrics;
- provide lookup by concept identity;
- provide lookup by candidate/review-item link;
- keep Phase 2 decisions readable as review history but outside lifecycle
  authority;
- add unit tests and narrow storage integration tests.

## 6. Out of Scope

- external lifecycle API endpoints;
- UI;
- approval workflow or assignment queues;
- automatic Phase 2 decision backfill;
- migration tooling for historical Phase 2 decisions;
- recompute execution integration;
- canonical promotion changes;
- key facts, derived facts, P5 dataset, or Turtle output changes;
- Ollama or semantic fallback behavior changes;
- whole-document LLM metric lifecycle assessment.

## 7. Relationship To Phase 2

Phase 2 and Phase 3 records coexist.

```text
Phase 2 decision
= review-item-scoped annotation/history

Phase 3 lifecycle entry
= concept-level custom metric governance state

Phase 3 candidate link
= explicit bridge from review item / candidate fact to lifecycle entry
```

Rules:

- Phase 2 `keep_provisional` never automatically becomes Phase 3
  `approve_custom`.
- Phase 2 advisory `map_to_standard` never automatically becomes Phase 3
  executable `map_to_standard`.
- Phase 3 lifecycle reads must not consult Phase 2 decision records as fallback
  lifecycle state.
- Review surfaces may show Phase 2 latest decision and Phase 3 lifecycle state
  side by side, but those annotations must be distinguishable.
- A future backfill tool may promote selected Phase 2 decisions into Phase 3
  lifecycle records only through an explicit, opt-in, idempotent, auditable
  migration process.

Future backfill, if added, should preserve:

- source Phase 2 decision id;
- migration run id;
- migration actor;
- migration timestamp;
- migration reason;
- dry-run output;
- conflict handling rules.

## 8. Lifecycle Model

### 8.1 Lifecycle Status

Phase 3 should model these lifecycle statuses:

- `provisional`
- `approved_custom`
- `mapped_to_standard`
- `deprecated`
- `blacklisted`

`provisional` is the initial lifecycle state for a governed custom concept.
It does not authorize automatic downstream consumption.

`approved_custom` means the custom metric is an accepted custom concept, but
Phase 3 still does not expose it to key facts, P5, Turtle, or recompute output.
Consumption rules remain a later-phase decision.

`mapped_to_standard` means the custom concept has a formal target standard
metric id.

`deprecated` means the custom concept should no longer be selected for new
governance usage, but historical records remain auditable.

`blacklisted` means the custom concept should be suppressed from future
automatic lifecycle promotion and highlighted as blocked/rejected in review
contexts.

### 8.2 Lifecycle Actions

Phase 3 should model these lifecycle actions:

- `approve_custom`
- `map_to_standard`
- `deprecate`
- `blacklist`

Action effects:

- `approve_custom` sets status to `approved_custom`;
- `map_to_standard` sets status to `mapped_to_standard` and requires a target
  standard metric id;
- `deprecate` sets status to `deprecated`;
- `blacklist` sets status to `blacklisted`.

Validation rules:

- `map_to_standard` requires `target_metric_id`;
- `target_metric_id` must resolve to a supported standard metric;
- `approve_custom`, `deprecate`, and `blacklist` must not require
  `target_metric_id`;
- every lifecycle decision requires actor, reason, created timestamp, and at
  least one evidence pointer or candidate link;
- decisions record previous status and new status.

## 9. Data Model Direction

### 9.1 Lifecycle Entry

`MetricLifecycleEntry` represents a governed custom metric concept.

Minimum fields:

- lifecycle entry id;
- issuer id;
- metric id;
- raw label;
- normalized label;
- statement type;
- accounting standard;
- industry slug;
- parent metric id;
- current lifecycle status;
- mapped standard metric id when status is `mapped_to_standard`;
- created at;
- updated at;
- created by or source actor when available.

The concept identity should be stable across repeated extracted artifacts for
the same issuer and custom metric concept. The implementation plan should choose
a deterministic key using the existing custom metric identity components rather
than a review-item id.

### 9.2 Lifecycle Decision

`MetricLifecycleDecision` represents an append-only lifecycle transition.

Minimum fields:

- decision id;
- lifecycle entry id;
- action;
- previous status;
- new status;
- target metric id when applicable;
- actor;
- reason;
- evidence bundle id;
- source review item id when applicable;
- source artifact id when applicable;
- created at;
- effective at.

The latest lifecycle state must be deterministic under ties. Reads should order
by `effective_at`, then `created_at`, then `decision_id` unless the
implementation plan identifies an existing stronger ordering field.

### 9.3 Candidate Link

`MetricLifecycleCandidateLink` explicitly connects a review item or candidate
fact to a lifecycle entry.

Minimum fields:

- candidate link id;
- lifecycle entry id;
- review item id;
- artifact id;
- issuer id;
- fiscal year;
- report type;
- candidate metric id;
- raw label;
- normalized label;
- statement type;
- evidence bundle id;
- created at;
- created by or source actor when available.

The link gives Phase 3 a durable bridge without making candidate-level records
the lifecycle source of truth.

## 10. Service Contract

Phase 3 should introduce a focused lifecycle service. Suggested capabilities:

- create or load a lifecycle entry for a concept identity;
- link a review item / candidate to a lifecycle entry;
- record a lifecycle decision with validation;
- load lifecycle state by concept identity;
- load lifecycle state by review item / candidate link;
- list decision history for a lifecycle entry;
- return an explicit no-state result when no lifecycle entry exists.

The service should not call extraction, canonical promotion, P5 dataset
assembly, Turtle export, or live semantic fallback.

## 11. Repository Contract

The repository should provide storage operations that keep lifecycle persistence
separate from Phase 2 decisions:

- save / upsert lifecycle entry;
- load lifecycle entry by id;
- load lifecycle entry by concept identity;
- save lifecycle decision;
- list lifecycle decisions for an entry in deterministic order;
- load latest lifecycle decision for an entry;
- save candidate link;
- load candidate link by review item id;
- load candidate links for an entry.

Repository methods must not synthesize lifecycle state from
`metric_governance_decisions`.

## 12. Deterministic Read Contract

Phase 3 lifecycle reads should be deterministic and explicit:

- when an entry exists, read the current entry state and decision history;
- when multiple decisions exist, latest state is selected by stable ordering;
- when no entry exists, return no lifecycle state;
- when a Phase 2 decision exists but no Phase 3 entry exists, still return no
  lifecycle state;
- when a candidate link exists, resolve through the linked lifecycle entry;
- when a candidate link does not exist, do not infer a link from matching raw
  labels unless an explicit lookup-by-concept call is made.

This contract is the main Phase 3 handoff to Phase 4.

## 13. Interaction With Existing Components

### 13.1 MetricRegistry

The in-memory `MetricRegistry` remains responsible for resolving raw labels to
standard metrics or provisional custom metric ids. It does not own durable
lifecycle state.

Phase 3 lifecycle storage may reuse its identity fields, but it must remain a
separate persistent governance layer.

### 13.2 FactNormalizer, ConflictResolver, ValidationService, ReportAdapter

No behavior change in Phase 3.

These services should continue applying Phase 1 guardrails. They must not
consume lifecycle decisions until a later recompute/canonical integration phase.

### 13.3 MetricGovernanceReviewService

Phase 3 may add internal annotations that allow review reads to display linked
lifecycle state, but Phase 3 does not require changing the public Phase 2 review
API contract.

If review annotations are extended, Phase 2 latest decision and Phase 3
lifecycle state must remain separate fields.

### 13.4 P5 Recompute

No execution behavior change in Phase 3.

`build_recompute_plan` and `execute_recompute_plan` should not be required to
carry lifecycle snapshots, read lifecycle decisions, or alter dataset/Turtle
outputs. Phase 4 may introduce that integration.

## 14. Error Handling

The lifecycle service should reject:

- unknown lifecycle entry ids;
- candidate links that reference missing entries;
- lifecycle decisions that reference missing entries;
- `map_to_standard` decisions without a target metric id;
- `map_to_standard` decisions whose target metric id is unsupported,
  provisional, or custom;
- lifecycle decisions without actor or reason;
- ambiguous latest-state reads that cannot be ordered deterministically.

Storage errors should surface as repository/service errors and must not affect
extraction or previously persisted artifacts.

## 15. Testing Strategy

### 15.1 Unit Tests

- lifecycle action validation;
- `map_to_standard` target validation;
- action-to-status transitions;
- no-state read result when only Phase 2 decision exists;
- candidate link lookup;
- deterministic latest decision ordering;
- decision history ordering;
- invalid target/status/action rejection.

### 15.2 Storage Tests

- lifecycle entry round trip;
- lifecycle decision round trip;
- candidate link round trip;
- load by concept identity;
- load by review item id;
- latest decision tie-break behavior.

### 15.3 Integration Tests

- Phase 2 review item plus Phase 3 candidate link can resolve lifecycle state;
- Phase 2 decision alone does not resolve lifecycle state;
- existing extraction/key facts/P5/Turtle behavior remains unchanged in focused
  regression tests.

Real-PDF and live Ollama validation are not default Phase 3 close-out tests
because Phase 3 does not change extraction or fallback behavior.

## 16. Acceptance Criteria

Phase 3 is complete when:

- durable lifecycle entry, decision, and candidate link contracts exist;
- storage can persist and load lifecycle entries, decisions, and candidate
  links;
- lifecycle service can create/load entries, link candidates, record decisions,
  and read current lifecycle state deterministically;
- all four lifecycle actions are modeled and validated;
- `map_to_standard` only accepts supported standard metric targets;
- Phase 2 decisions remain review history and are not treated as lifecycle
  state;
- reads return explicit no-state when no Phase 3 entry exists;
- candidate links resolve to lifecycle entries without making candidates the
  lifecycle source of truth;
- existing Phase 1 guardrails and Phase 2 review contracts remain intact;
- no extraction, recompute, P5, Turtle, Ollama, or fallback behavior changes are
  introduced.

## 17. Non-Goals

Phase 3 does not require:

- a lifecycle management UI;
- lifecycle review queues;
- lifecycle API endpoints;
- recompute snapshotting;
- automatic output changes from lifecycle decisions;
- backfilling historical Phase 2 decisions;
- replacing the Phase 2 decision table;
- migration tooling for historical governance decisions;
- new Turtle field coverage.

## 18. Recommended Next Step

Write a Phase 3 implementation plan:

```text
Metric Governance Phase 3
-> lifecycle domain contracts
-> storage records and repository methods
-> lifecycle service and validation
-> candidate link bridge
-> deterministic lifecycle reads
-> focused unit/storage/integration tests
```

The plan should keep implementation scoped to internal contracts and avoid
external lifecycle API or recompute behavior changes.
