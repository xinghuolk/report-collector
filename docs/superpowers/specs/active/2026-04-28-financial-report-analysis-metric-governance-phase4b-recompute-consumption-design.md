# Financial Report Analysis Metric Governance Phase 4B Recompute And Consumption Design

> **Status:** Active phase spec
> **Date:** 2026-04-28
> **Scope Type:** Narrow design and implementation target
> **Parent Spec:** `docs/superpowers/specs/active/2026-04-25-financial-report-analysis-metric-governance-umbrella-design.md`
> **Depends On:** `docs/superpowers/specs/active/2026-04-27-financial-report-analysis-metric-governance-phase4a-workflow-review-api-design.md`
> **Implements:** Metric governance umbrella Phase 4B

## 1. Purpose

Phase 4B makes lifecycle decisions operational for recompute planning and
controlled output consumption.

Phase 4A made lifecycle state writable and visible in review APIs. Phase 4B
must answer two follow-up questions:

```text
which persisted artifacts need recompute because lifecycle decisions changed?
what would controlled consumption do before it changes dataset/Turtle outputs?
```

P4B must remain audit-first. It should not silently rewrite persisted extracted
artifacts or mutate historical candidate facts. Output changes are allowed only
through explicit recompute/consumption paths with provenance and regression
tests.

## 2. Goal

The target workflow is:

```text
lifecycle decision
-> linked review item / artifact impact
-> recompute-needed audit view
-> dry-run consumption impact
-> controlled recompute applies mapped/blocked decisions
-> P5 dataset and Turtle output show explicit lifecycle provenance
```

## 3. Design Principles

- Audit before mutation: every output-affecting lifecycle decision must appear
  in a deterministic audit view before controlled consumption applies it.
- Explicit links only: P4B reads lifecycle impact through Phase 4A candidate
  links. It must not infer impact from raw label matching.
- No stored artifact rewrite: lifecycle consumption returns governed views or
  recompute outputs. It must not edit persisted extracted artifacts in place.
- Output provenance is mandatory: mapped or suppressed facts must carry
  lifecycle decision and source review item metadata.
- Conservative conflict behavior: if a mapped custom candidate conflicts with
  an existing standard canonical fact, the system reports a dry-run conflict
  and does not overwrite automatically.

## 4. In Scope

- Build a lifecycle recompute audit model that groups linked lifecycle decisions
  by source artifact and review item.
- Mark artifacts as recompute-needed when linked lifecycle state is
  `mapped_to_standard` or `blacklisted`.
- Expose a read-only review API for lifecycle recompute audit and dry-run
  consumption impact.
- Add a controlled consumption overlay for P5 recompute paths:
  `mapped_to_standard` can synthesize a standard canonical fact from a linked
  candidate fact when no conflicting standard fact exists.
- Add `blacklisted` suppression for matching custom canonical facts and linked
  candidate consumption.
- Add explicit provenance fields to governed output facts/rows.
- Keep `approved_custom`, `deprecated`, and `provisional` non-output-changing
  in P4B.
- Add focused regressions showing exactly which lifecycle decision affected
  dataset rows and Turtle export rows.

## 5. Out Of Scope

- UI.
- Async recompute job orchestration.
- Automatic historical Phase 2 decision backfill.
- Raw-label or fuzzy matching without an explicit candidate link.
- Approval workflow or reviewer assignment.
- Rewriting stored `P5ExtractedArtifact` records.
- Broad recompute scheduler changes.
- Changing extraction, Ollama, semantic fallback, or deterministic mapping.

## 6. Audit Contract

Add a read-only audit response:

```text
GET /api/v1/metric-governance/lifecycle-recompute-audit
```

Query parameters:

```text
issuer_id: optional string
fiscal_year: optional integer
dry_run: optional boolean, default false
```

Response shape:

```json
{
  "items": [
    {
      "review_item_id": "artifact-id:encoded-fact-id",
      "artifact_id": "CN_601919_2025_annual",
      "issuer_id": "CN_601919",
      "fiscal_year": 2025,
      "report_type": "annual",
      "candidate_metric_id": "custom::cn::general::income-statement::root::contract-assets",
      "raw_label": "Contract assets",
      "lifecycle_entry_id": "metric-lifecycle:6f4d2c",
      "current_status": "mapped_to_standard",
      "latest_decision_id": "metric-lifecycle-decision:ab12",
      "latest_decision_action": "map_to_standard",
      "target_metric_id": "accounts_receiv",
      "recompute_needed": true,
      "consumption_action": "map_to_standard",
      "conflict_state": "none",
      "reason": "lifecycle decision affects automatic outputs"
    }
  ],
  "summary": {
    "review_item_count": 1,
    "artifact_count": 1,
    "recompute_needed_count": 1,
    "dry_run_conflict_count": 0
  }
}
```

The audit endpoint is read-only. With `dry_run=false`, it only reports lifecycle
state impact. With `dry_run=true`, it also evaluates candidate/canonical facts
to report whether controlled consumption would map, suppress, skip, or conflict.
The dry-run audit is the source of truth for `already_present`, `conflict`,
`missing_candidate`, and `missing_target` decisions. Controlled consumption
must consume audit actions and must not invent a second reporting contract.

## 7. Consumption Rules

### 7.1 `mapped_to_standard`

When a linked lifecycle entry is `mapped_to_standard`:

- find the linked candidate fact by review item;
- require the lifecycle decision's `target_metric_id`;
- if no canonical fact already exists with the same artifact, issuer, period,
  entity scope, statement type, and target metric id, synthesize a governed
  canonical fact using the candidate value and evidence;
- if a matching standard canonical fact already exists with the same value,
  report `already_present` and do not duplicate;
- if a matching standard canonical fact exists with a different value, report
  `conflict` and do not overwrite;
- add provenance under `extensions.metric_governance.lifecycle_consumption`.

If dry-run reports `already_present`, `conflict`, `missing_candidate`, or
`missing_target`, controlled consumption must not add or overwrite canonical
facts for that item.

Minimum provenance:

```json
{
  "source_review_item_id": "artifact-id:encoded-fact-id",
  "lifecycle_entry_id": "metric-lifecycle:6f4d2c",
  "decision_id": "metric-lifecycle-decision:ab12",
  "decision_action": "map_to_standard",
  "source_candidate_metric_id": "custom::cn::general::balance-sheet::root::deposit",
  "target_metric_id": "accounts_receiv",
  "consumption_action": "map_to_standard"
}
```

### 7.2 `blacklisted`

When a linked lifecycle entry is `blacklisted`:

- linked custom candidates must not synthesize governed canonical facts;
- matching custom canonical facts in governed views are suppressed;
- suppression must be reported in dry-run audit with lifecycle decision
  provenance;
- existing stored extracted artifacts are not edited.

### 7.3 Non-output-changing states

P4B must not change outputs for:

- `provisional`
- `approved_custom`
- `deprecated`

These states may appear in audit views with `recompute_needed=false` unless a
future phase adds a separate output contract.

## 8. Recompute Integration

P4B should extend recompute with an explicit lifecycle reason:

```text
metric_lifecycle_decision_changed
```

For this reason:

- `build_recompute_plan` rebuilds dataset and Turtle export;
- target artifact ids come from lifecycle recompute audit items with
  `recompute_needed=true`;
- `execute_recompute_plan` applies lifecycle consumption only when the caller
  passes an explicit lifecycle consumption context;
- `execute_recompute_plan` fails fast if this reason is used without a
  lifecycle consumption context;
- normal recompute reasons continue to behave as they do today.

This keeps P4B opt-in and avoids changing existing recompute behavior.

## 9. Testing Requirements

Add focused tests for:

- audit reports no items when there are no lifecycle candidate links;
- audit marks `mapped_to_standard` linked candidates as recompute-needed;
- audit marks `blacklisted` linked candidates as recompute-needed;
- audit leaves `approved_custom`, `deprecated`, and `provisional` non-output
  changing;
- dry-run reports `map_to_standard`, `already_present`, `conflict`, and
  `suppress_blacklisted`;
- recompute plan maps `metric_lifecycle_decision_changed` to dataset and Turtle
  rebuild;
- controlled consumption adds a mapped standard dataset row with lifecycle
  provenance;
- controlled consumption does not duplicate an already-present standard fact;
- controlled consumption does not overwrite conflicting standard facts;
- Turtle export rows preserve lifecycle provenance for governed rows;
- existing P4A review APIs and Phase 1 provisional guardrails continue to pass.

## 10. Acceptance Criteria

Phase 4B is complete when:

- lifecycle decision impact can be audited without changing outputs;
- dry-run consumption shows deterministic action and conflict states;
- mapped lifecycle decisions can be consumed as standard metrics through an
  explicit recompute path;
- blacklisted lifecycle decisions suppress governed output consumption;
- output rows include lifecycle provenance;
- existing recompute behavior is unchanged unless lifecycle consumption is
  explicitly requested;
- no extraction, Ollama, semantic fallback, or raw-label matching behavior is
  introduced.

## 11. Recommended Next Step

Write and execute a Phase 4B implementation plan:

```text
Metric Governance Phase 4B
-> audit models and service
-> audit API
-> controlled consumption overlay
-> recompute integration
-> dataset/Turtle provenance regressions
```
