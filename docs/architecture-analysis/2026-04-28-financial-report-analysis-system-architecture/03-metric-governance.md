# Metric Governance Architecture

## Governance Flow

```text
table semantics
-> MetricMappingRegistry.match()
-> supported candidate fact
-> FactNormalizer
   -> MetricRegistry.resolve_metric()
   -> extensions.metric_governance
-> ConflictResolver guardrails
-> provisional review item
-> review decision or lifecycle decision
-> lifecycle recompute audit
-> explicit recompute with controlled consumption
-> dataset / Turtle rows with lifecycle provenance
```

## Registry Boundaries

`registries/metric_mapping.py::MetricMappingRegistry` is the deterministic
mapping layer. It maps table kind, normalized row label, period shape, and
market into supported standard metric ids. It does not generate custom ids or
persist lifecycle state.

`registries/metric_registry.py::MetricRegistry` is the identity layer. It
resolves raw labels to known standard identities where possible, otherwise
generates stable `custom::...` provisional ids. Conceptually this is the
`MetricIdentityRegistry` role described in the umbrella spec.

`registries/metric_governance.py` creates governance metadata. Standard metrics
are allowed for automatic analysis. Provisional custom metrics carry review
metadata and are blocked from automatic analysis.

## Phase 1 Guardrails

`services/fact_normalizer.py::FactNormalizer.normalize_candidates` writes
`extensions.metric_governance` onto candidate facts.

`services/conflict_resolver.py::ConflictResolver.resolve_with_review` blocks
provisional custom metrics from canonical promotion and emits review packets
with `provisional_metric_review_required`.

`adapters/report_adapter.py::ReportAdapter` excludes
`auto_analysis_allowed=false` facts from key facts and downstream API output.

These guardrails address the main pollution path:

```text
unknown metric
-> provisional custom identity
-> canonical promotion
-> key facts / derived facts / Turtle
-> downstream treats it as stable
```

## Phase 2 Review Surface

`services/metric_governance_review.py::MetricGovernanceReviewService` scans
persisted extracted artifacts for provisional candidate facts and emits
`MetricGovernanceReviewItem` records.

Phase 2 lightweight review decisions use
`models/governance.py::MetricGovernanceDecision` with decision types such as
`keep_provisional` and `map_to_standard`.

This layer is advisory. It is not the durable lifecycle state machine.

## Phase 3 Lifecycle Registry

`services/metric_lifecycle.py::MetricLifecycleService` implements durable
lifecycle state. It creates or loads lifecycle entries, links candidates to
entries, records decisions, and validates actor/reason/evidence/target metric
shape.

Storage tables live in `storage/models.py`:

- `MetricLifecycleEntryRecord`;
- `MetricLifecycleDecisionRecord`;
- `MetricLifecycleCandidateLinkRecord`.

Lifecycle states:

- `provisional`;
- `approved_custom`;
- `mapped_to_standard`;
- `deprecated`;
- `blacklisted`.

## Phase 4A Workflow API

`api/routes.py` exposes review-item scoped lifecycle workflow endpoints:

- create or load lifecycle entry;
- link candidate to lifecycle entry;
- record lifecycle decision;
- read review items with embedded lifecycle state.

Phase 4A intentionally did not change automatic outputs.

## Phase 4B Audit And Controlled Consumption

`services/metric_lifecycle_recompute.py` builds lifecycle recompute audit views.
It reports whether linked lifecycle decisions require recompute and, in dry-run
mode, whether consumption would map, suppress, skip, or conflict.

`services/metric_lifecycle_consumption.py` applies controlled consumption as an
in-memory overlay. It does not mutate stored extracted artifacts.

Consumption rules:

- `mapped_to_standard`: may synthesize a standard canonical fact from the
  linked candidate when there is no matching target canonical fact.
- `already_present`: no duplicate is added.
- `conflict`: no overwrite.
- `missing_candidate` / `missing_target`: no output mutation.
- `blacklisted`: suppresses matching custom canonical facts in the governed
  view.
- `approved_custom`, `deprecated`, and `provisional`: no automatic output change
  in Phase 4B.

Controlled consumption writes provenance under:

```text
extensions.metric_governance.lifecycle_consumption
```

## Current State

Completed:

- governance metadata contract;
- provisional custom guardrails;
- metric governance review item API;
- durable lifecycle registry;
- lifecycle workflow API;
- lifecycle recompute audit API;
- controlled consumption overlay;
- lifecycle recompute reason with explicit fail-fast audit requirement;
- dataset/API/Turtle lifecycle provenance.

## Risks And Boundaries

- `MetricMappingRegistry` and `MetricRegistry` names are still easy to confuse.
- Phase 2 decisions and lifecycle decisions coexist; Phase 2 decisions should
  remain advisory and should not be inferred as lifecycle state.
- Lifecycle impact only follows explicit candidate links; raw label or fuzzy
  matching is intentionally not used.
- `approved_custom` has no automatic output contract yet.
- `blacklisted` suppression currently uses candidate metric id; more granular
  suppression may be needed later.

## Suggested Next Slices

- Reconcile naming and docs around `MetricMappingRegistry` vs `MetricRegistry`.
- Define an explicit `approved_custom` output contract, or keep it review-only.
- Persist lifecycle recompute audit snapshots if output provenance needs durable
  run-level audit.
- Add finer-grained blacklist suppression keys if real data shows over-broad
  suppression.
