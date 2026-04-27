# Financial Report Analysis Metric Governance Phase 4A Workflow Review API Design

> **Status:** Active phase spec
> **Date:** 2026-04-27
> **Scope Type:** Narrow design and implementation target
> **Parent Spec:** `docs/superpowers/specs/active/2026-04-25-financial-report-analysis-metric-governance-umbrella-design.md`
> **Implements:** Metric governance umbrella Phase 4A

## 1. Purpose

Phase 4A makes the Phase 3 lifecycle registry operable through the existing
metric-governance review API.

Phase 2 exposed provisional review items and lightweight review decisions.
Phase 3 added internal lifecycle contracts, storage, candidate links, and
service validation. Phase 4A connects those pieces through a review-item-first
workflow API.

Phase 4A must not change extraction, canonical facts, derived facts, P5 dataset
assembly, Turtle export, recompute, Ollama, or semantic fallback behavior.

## 2. Goal

The target workflow is:

```text
review item
-> explicit lifecycle entry creation/link
-> review item response shows lifecycle state
-> lifecycle decision write
-> review item response shows updated lifecycle state
```

The lifecycle state shown by review APIs is Phase 3 state only. Phase 2
`latest_decision` remains review history and advisory annotation.

## 3. In Scope

- add lifecycle state to existing review item list/detail responses;
- add a review-item-scoped endpoint to create or load a lifecycle entry and
  create the explicit candidate link;
- add a review-item-scoped endpoint to record a lifecycle decision;
- expose lifecycle decision history in the embedded lifecycle state;
- keep Phase 2 `latest_decision` and Phase 3 lifecycle state distinguishable;
- preserve existing Phase 2 decision endpoints and response fields;
- derive lifecycle concept identity deterministically from the review item;
- validate review item existence and provisional status before lifecycle writes;
- validate lifecycle decisions through `MetricLifecycleService`;
- return deterministic 404/422 errors for missing review items, missing links,
  invalid actions, invalid targets, and unsupported review item state.

## 4. Out of Scope

- recompute planning or execution;
- canonical promotion changes;
- key facts, derived facts, P5 dataset, or Turtle output changes;
- automatic backfill from Phase 2 decisions;
- automatic lifecycle linking by matching raw labels;
- approval queues, assignment workflow, UI, async job handles, or durable job
  status;
- lifecycle admin APIs that operate without a review item.

## 5. API Shape

P4A uses review-item-first endpoints because the review item is the user-facing
workflow object.

Existing endpoints remain:

```text
GET  /api/v1/metric-governance/review-items
GET  /api/v1/metric-governance/review-items/{review_item_id}
POST /api/v1/metric-governance/review-items/decision
```

New endpoints:

```text
POST /api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry
POST /api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision
```

### 5.1 Embedded Lifecycle State

`MetricGovernanceReviewItemResponse` gains a `lifecycle_state` field:

```json
{
  "entry": null,
  "latest_decision": null,
  "candidate_link": null,
  "decision_history": []
}
```

When a candidate link exists, `entry`, `candidate_link`, `latest_decision`, and
`decision_history` reflect the Phase 3 lifecycle service result.

When no candidate link exists, the state is explicit no-state:

```json
{
  "entry": null,
  "latest_decision": null,
  "candidate_link": null,
  "decision_history": []
}
```

The API must not infer lifecycle state from Phase 2 decisions, raw labels, or
matching concept identity. A caller can use the lifecycle-entry endpoint to make
the link explicit.

### 5.2 Lifecycle Entry Endpoint

Request:

```json
{
  "actor": "reviewer@example.com"
}
```

Behavior:

- load the review item;
- reject missing review items with 404;
- reject non-provisional review items with 422;
- build a `MetricLifecycleConceptIdentity` from the review item fields;
- call `MetricLifecycleService.create_or_load_entry`;
- create a `MetricLifecycleCandidateLink` for the review item and lifecycle
  entry;
- return the refreshed review item response with `lifecycle_state`.

The endpoint is idempotent for the same review item and concept. Repeating the
request returns the existing lifecycle entry and link.

Concept identity derivation is deterministic:

- `issuer_id`, `metric_id`, `raw_label`, `normalized_label`, and
  `statement_type` come directly from the review item;
- `accounting_standard`, `industry_slug`, and `parent_metric_id` come from the
  custom metric id when it follows the existing registry format
  `custom::<accounting_standard>::<industry_slug>::<statement_type>::<parent>::<slug>`;
- `parent_metric_id` is `null` when the parsed parent segment is `root`;
- if a legacy or malformed custom metric id cannot be parsed, use the same
  fallback semantics as current normalization: `accounting_standard="OTHER"`,
  `industry_slug="general"`, and `parent_metric_id=null`;
- the parsed metric-id `statement_type` does not override the review item's
  `statement_type`. If they differ, the implementation should keep the review
  item value and leave the discrepancy as evidence for later review rather than
  failing the API call.

### 5.3 Lifecycle Decision Endpoint

Request:

```json
{
  "action": "map_to_standard",
  "target_metric_id": "accounts_receiv",
  "reason": "Matches the supported receivables metric.",
  "actor": "reviewer@example.com",
  "effective_at": "2026-04-27T10:03:00+00:00"
}
```

Behavior:

- load the review item;
- reject missing review items with 404;
- reject non-provisional review items with 422;
- require an existing lifecycle candidate link for the review item;
- pass the review item's `evidence_bundle_id`, `review_item_id`, and
  `artifact_id` as lifecycle decision source context;
- call `MetricLifecycleService.record_decision`;
- return the written lifecycle decision plus the refreshed review item response.

`effective_at` is optional. If omitted, the service uses the current UTC
timestamp.

Allowed lifecycle actions are the Phase 3 actions only:

- `approve_custom` moves the lifecycle entry to `approved_custom`;
- `map_to_standard` moves the lifecycle entry to `mapped_to_standard` and
  requires `target_metric_id`;
- `deprecate` moves the lifecycle entry to `deprecated`;
- `blacklist` moves the lifecycle entry to `blacklisted`.

Only `map_to_standard` accepts `target_metric_id`. Other actions must reject a
non-null target.

## 6. Response Models

Add response models for:

- `MetricLifecycleConceptIdentityResponse`;
- `MetricLifecycleEntryResponse`;
- `MetricLifecycleDecisionResponse`;
- `MetricLifecycleCandidateLinkResponse`;
- `MetricLifecycleStateResponse`;
- `MetricLifecycleEntryWriteResponse`;
- `MetricLifecycleDecisionRequest`;
- `MetricLifecycleDecisionWriteResponse`.

The lifecycle response fields should mirror Phase 3 dataclass names so the API
stays transparent:

```text
lifecycle_entry_id
concept
current_status
mapped_standard_metric_id
created_at
updated_at
created_by
```

The Phase 2 `latest_decision` response remains unchanged and must not be renamed
or merged with lifecycle decision fields.

## 7. Error Handling

Use existing FastAPI patterns:

- 404 for missing review item;
- 422 for non-provisional review item;
- 422 for lifecycle decision before lifecycle entry/link creation;
- 422 when a review item is already linked to a different lifecycle entry;
- 422 for unsupported lifecycle action;
- 422 for unsupported `target_metric_id`;
- 422 for blank actor/reason or missing evidence/source context;
- 503 when storage repository is not configured.

The API should surface stable error text that can be asserted in tests.

## 8. Data Flow

### 8.1 Review Item List/Detail

```text
MetricGovernanceReviewService
-> MetricGovernanceReviewItem
-> MetricLifecycleService.load_state_by_review_item(review_item_id)
-> MetricGovernanceReviewItemResponse.lifecycle_state
```

The list endpoint may load lifecycle state per returned review item. P4A favors
contract clarity over premature batching because review surfaces are currently
narrow and internal.

### 8.2 Create/Link Lifecycle Entry

```text
review item
-> deterministic concept identity derived from review item and custom metric id
-> create_or_load_entry
-> candidate link
-> refreshed review item response with lifecycle_state
```

The candidate link is the only bridge from review item to lifecycle entry.
Loading lifecycle state for review responses must use this explicit link and
must not perform concept matching.

### 8.3 Record Lifecycle Decision

```text
review item
-> existing candidate link
-> record_decision
-> updated entry state and append-only decision
-> refreshed review item response with lifecycle_state
```

No Phase 2 decision is created or modified by this endpoint.

## 9. Testing Requirements

Add focused integration tests around the existing FastAPI test style:

- review list returns explicit no-state lifecycle state before linking;
- lifecycle entry endpoint creates entry and candidate link, then review detail
  shows lifecycle state;
- repeated lifecycle entry calls are idempotent for the same review item;
- lifecycle entry creation derives `accounting_standard`, `industry_slug`, and
  `parent_metric_id` from a registry-format custom metric id;
- lifecycle entry creation falls back to `OTHER/general/root` for malformed
  legacy custom metric ids;
- lifecycle decision endpoint records `map_to_standard` and refreshes lifecycle
  state;
- lifecycle decision endpoint rejects `target_metric_id` for non-mapping
  actions;
- lifecycle decision endpoint rejects missing lifecycle link;
- lifecycle endpoints reject missing review item and non-provisional review item;
- lifecycle decision endpoint rejects unsupported standard metric targets;
- existing Phase 2 decision write flow still works and still populates
  `latest_decision`;
- P5/recompute/guardrail regression tests remain unchanged.

## 10. Acceptance Criteria

Phase 4A is complete when:

- review item list/detail responses always include `lifecycle_state`;
- no-link review items return explicit no-state lifecycle state;
- a review item can explicitly create/load a lifecycle entry and candidate link;
- a linked review item can record lifecycle decisions through the API;
- Phase 2 `latest_decision` and Phase 3 lifecycle state remain separate fields;
- Phase 2 decision alone does not create lifecycle state;
- no recompute, canonical fact, P5 dataset, Turtle, extraction, Ollama, or
  semantic fallback behavior changes are introduced.

## 11. Recommended Next Step

Write a Phase 4A implementation plan:

```text
Metric Governance Phase 4A
-> lifecycle API schemas
-> review response lifecycle-state embedding
-> lifecycle entry/link endpoint
-> lifecycle decision endpoint
-> integration tests and no-output-change regressions
```
