# System Overview

## Architecture Layers

```text
HTTP / CLI input
-> PDF ingestion and table recovery
-> table semantic normalization
-> metric mapping / metric identity governance
-> candidate facts
-> fact normalization
-> conflict resolution and canonical facts
-> derivation and validation
-> review surfaces
-> P5 dataset and Turtle export
-> storage, lineage, recompute, availability, audit APIs
```

The system is organized around facts, not around a single endpoint. The central
contract is that extracted facts must remain traceable from PDF/table evidence
through candidate, canonical, dataset, Turtle, review, lineage, and recompute
surfaces.

## Main Path

The main extraction path starts at
`financial-report-analysis/src/financial_report_analysis/pipeline.py::analyze_report`.
It accepts candidate facts from ingestion, normalizes them, resolves conflicts,
derives TTM facts, validates the result, and returns a structured analysis
result.

Key modules:

- `ingestion/pdf_ingestion.py`: PDF reading, table extraction, note-disclosure
  candidates, text fallback.
- `ingestion/table_source.py`: raw table block extraction.
- `ingestion/table_structure.py`: parsed table recovery.
- `ingestion/table_header_parser.py`: header, period, unit, currency parsing.
- `ingestion/table_semantics.py`: normalized table semantics.
- `services/table_fact_builder.py`: normalized table rows to candidate facts.
- `services/fact_normalizer.py`: unit/currency normalization and metric
  governance metadata.
- `services/conflict_resolver.py`: canonical promotion and review packets.
- `services/derivation_service.py`: derived facts, currently focused on TTM.
- `services/validation_service.py`: quality gate and validation issues.
- `adapters/report_adapter.py`: API-facing analysis result and key facts.
- `p5/dataset.py`: P5 dataset rows from extracted artifacts.
- `p5/turtle_export.py`: Turtle export rows from dataset rows.

## Governance Path

Metric governance is a parallel control plane over the main fact path:

```text
MetricMappingRegistry / MetricRegistry
-> metric_governance metadata
-> provisional guardrails
-> metric governance review items
-> lifecycle entry/link/decision
-> lifecycle recompute audit
-> controlled consumption during explicit recompute
```

Key modules:

- `registries/metric_mapping.py`: deterministic table semantics to supported
  metric ids.
- `registries/metric_registry.py`: raw label identity resolution and stable
  provisional custom ids.
- `registries/metric_governance.py`: governance metadata helpers.
- `services/metric_governance_review.py`: provisional metric review items.
- `services/metric_lifecycle.py`: durable lifecycle service.
- `services/metric_lifecycle_recompute.py`: recompute/dry-run audit.
- `services/metric_lifecycle_consumption.py`: controlled output overlay.

## Storage And Read Path

The system has two storage modes:

- JSON artifact repository for local/offline P5 artifact workflows:
  `p5/artifact_repository.py::P5JsonArtifactRepository`.
- DB-backed API/runtime repository:
  `storage/repositories.py::SqlAlchemyP5ArtifactRepository`.

DB runtime is initialized in `api/runtime.py`. API routes in `api/routes.py`
read and write extracted artifacts, datasets, Turtle exports, review surfaces,
lineage, recompute runs, and metric governance state.

## Current Completion State

Completed capabilities:

- table-driven extraction baseline;
- P5 dataset and Turtle export;
- storage-backed API runtime;
- DB-backed extract persistence and lookup;
- review and lineage surfaces;
- deterministic recompute contracts;
- 3-5Y persisted availability/data provider baseline;
- metric governance Phase 1 through Phase 4B.

Not currently implemented as production workflows:

- async job orchestration;
- automatic multi-year report acquisition;
- automatic retry/rebuild lifecycle;
- full approval workflow;
- UI;
- whole-document LLM assessment as a canonical decision source.

## Key Boundary

The architecture is deterministic-first. Semantic fallback may assist bounded
classification tasks, but it must not become a fact source, lifecycle approver,
or recompute arbiter.
