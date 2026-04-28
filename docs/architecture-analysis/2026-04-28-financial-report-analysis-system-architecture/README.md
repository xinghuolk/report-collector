# Financial Report Analysis System Architecture

> Date: 2026-04-28
> Scope: current architecture analysis after metric governance Phase 4B

This directory summarizes the current `financial-report-analysis` architecture.
It is based on the active unified roadmap, metric governance umbrella, current
code, and the latest Phase 4B implementation.

## Document Map

- [01-system-overview.md](01-system-overview.md): high-level architecture,
  module boundaries, current completion state.
- [02-extraction-data-flow.md](02-extraction-data-flow.md): PDF-to-fact,
  validation, P5 dataset, and Turtle export data flow.
- [03-metric-governance.md](03-metric-governance.md): deterministic mapping,
  identity governance, lifecycle registry, review APIs, and controlled
  consumption.
- [04-storage-api-recompute.md](04-storage-api-recompute.md): JSON/DB
  repositories, API runtime, review surfaces, lineage, recompute.
- [05-risks-and-roadmap.md](05-risks-and-roadmap.md): pause gates, correctness
  risks, fallback boundaries, future scope, recommended next slices.

## Current State

The system has moved past the original pre-P5 field coverage phase. The active
baseline now includes:

- table-driven extraction and canonical fact assembly;
- P5 dataset and Turtle export generation;
- storage-backed API runtime and DB persistence;
- review, lineage, recompute, and 3-5Y availability/read surfaces;
- metric governance Phase 1 through Phase 4B.

The current architecture is deterministic-first. LLM/Ollama fallback is allowed
only as bounded semantic assistance and must not create canonical facts,
lifecycle decisions, or recompute decisions.

## Top-Level Flow

```text
PDF
-> table structure recovery / semantic normalization
-> deterministic metric mapping and candidate facts
-> fact normalization and governance metadata
-> conflict resolution and canonical facts
-> derivation, validation, review packets
-> persisted extracted artifact
-> P5 dataset / Turtle export / API read surfaces
-> review, lineage, recompute, and lifecycle audit surfaces
```

## Current Architectural Boundary

The system is ready for controlled, reviewable fact consumption. It is not yet a
workflow product platform. These remain future scope unless a new business goal
requires them:

- async job orchestration;
- automatic report acquisition/backfill/retry;
- full approval workflow state machine;
- UI;
- whole-document LLM assessment as a production decision source;
- Postgres/object-storage productization beyond the current SQLite/JSON
  baseline.
