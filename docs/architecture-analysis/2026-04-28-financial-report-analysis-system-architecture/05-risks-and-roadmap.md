# Risks, Boundaries, And Roadmap

## Source Of Truth

The top-level roadmap is:

`docs/superpowers/specs/active/2026-04-22-financial-report-analysis-unified-roadmap.md`

The metric governance umbrella is:

`docs/superpowers/specs/active/2026-04-25-financial-report-analysis-metric-governance-umbrella-design.md`

The current implementation is ahead of the original umbrella note that only
Phase 1 was the immediate target. Metric governance Phase 1 through Phase 4B now
exists in code and tests. Documentation should be read with that implementation
history in mind.

## Current Completed Baseline

The roadmap now treats the DB-backed 3-5Y data provider baseline as complete:

- single-year PDF extraction can be persisted;
- extracted artifact, dataset, Turtle, review, and lineage surfaces can be read
  back;
- 3-5Y availability/data view can report persisted facts, missing states,
  coverage explanation, and lineage;
- read paths do not trigger extraction, recompute, dataset build, or Turtle
  build.

Metric governance also has a complete Phase 1-4B slice:

- registry metadata and provisional guardrails;
- metric governance review surface;
- durable lifecycle registry;
- lifecycle workflow API;
- recompute audit and dry-run;
- controlled consumption and provenance.

## Pause Gates

The roadmap defines five pause-gate categories:

- Foundation: issuer-specific branches, unstable row-value binding, weak
  period/unit/currency recovery.
- Governance: provisional/custom facts affecting automatic outputs, unclear
  registry roles, unsupported metric identities without review.
- Fallback: uncontrolled Ollama calls, expanded output space without tests,
  fallback returning values or canonical facts.
- Source precedence: note/summary/parent facts overriding primary statement or
  consolidated facts without explicit policy.
- API/Persistence: important decisions existing only in logs, missing review
  surfaces, recompute/audit being required for correctness but not modeled.

## Main Correctness Risk

The central silent-pollution risk remains:

```text
unknown or unsupported field
-> provisional/custom identity
-> canonical promotion
-> key facts / derived facts / Turtle export
-> downstream treats the value as stable
```

Current guardrails reduce this risk:

- `FactNormalizer` attaches metric governance metadata.
- `ConflictResolver` blocks provisional custom canonical promotion.
- `ReportAdapter` excludes `auto_analysis_allowed=false`.
- Lifecycle-controlled output changes require explicit audit and recompute.

Remaining risk:

- P5 dataset, Turtle export, and availability largely trust canonical facts.
  If a polluted canonical fact enters an artifact through another path, these
  downstream consumers may still treat it as present.

## Fallback Boundaries

Allowed fallback roles:

- table kind disambiguation;
- bounded row-label choice among supported labels;
- currency/unit ambiguity;
- note/disclosure locator among target metrics.

Forbidden fallback roles:

- create lifecycle states;
- approve provisional custom metrics;
- map custom metrics to standard metrics;
- directly generate canonical facts;
- override governance policy;
- decide recompute correctness.

Current code follows a bounded pattern through `semantic_fallback/config.py`,
`semantic_fallback/models.py`, and `semantic_fallback/service.py`.

## Future Scope

These should remain future scope unless a concrete business goal appears:

- 3-5Y job/workflow state;
- automatic report acquisition/backfill/retry/rebuild;
- product artifact lifecycle;
- full approval workflow state machine;
- UI;
- whole-document LLM assessment/diff review;
- broader object-storage/Postgres productization.

## Recommended Next Slices

1. **Active docs reconciliation.**
   Update active roadmap/umbrella status so it clearly reflects that metric
   governance Phase 1-4B is implemented, while approval workflow/UI/async jobs
   remain future scope.

2. **Downstream governance hardening.**
   Add explicit governance assertions or filters in P5 dataset, Turtle export,
   and availability so they do not rely only on upstream canonical purity.

3. **Lifecycle recompute audit persistence.**
   Persist audit snapshots or run-level metadata showing which lifecycle
   decisions affected a dataset/Turtle output.

4. **DB-backed recompute boundary.**
   Define whether recompute remains JSON-first with explicit DB sync or becomes
   DB-native. Avoid keeping two ambiguous recompute paths.

5. **One-field post-P5 onboarding slice.**
   Pick one field family from the gap list, run the sample-onboarding diagnosis,
   and only then decide whether to extend deterministic semantics, registry
   mappings, or review surfaces.

## What Not To Do Next

- Do not start a broad new field phase without checking governance and source
  precedence gates.
- Do not make Ollama produce values or canonical facts.
- Do not infer lifecycle impact from raw labels or fuzzy matching.
- Do not add async workflow/job infrastructure without a concrete workflow
  product requirement.
- Do not treat Phase 2 review decisions as lifecycle decisions without explicit
  candidate links and audit.
