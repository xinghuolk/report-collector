# Storage, API, Review, Lineage, And Recompute

## Flow

```text
POST /api/v1/analysis/extract
-> PdfIngestionAdapter
-> analyze_report
-> ReportAdapter
-> persist_analysis_extract_result
-> build_extracted_artifact_from_result
-> build_extracted_review_surface
-> SqlAlchemyP5ArtifactRepository.save_api_extract_bundle
-> DB-backed read surfaces
```

Optional P5/Turtle build:

```text
persisted extracted artifact
-> build_db_p5_outputs_for_artifact
-> assemble_dataset
-> build_dataset_review_surface
-> build_turtle_export
-> build_turtle_export_review_surface
-> build_dataset_lineage
-> save_p5_assembly_bundle
```

JSON P5 build:

```text
run_p5_dataset_build
-> P5JsonArtifactRepository
-> load/build extracted artifacts
-> assemble_dataset
-> save dataset JSON
-> build_turtle_export
-> save turtle JSON
```

Recompute:

```text
build_recompute_plan
-> execute_recompute_plan
-> read before payloads
-> run_p5_dataset_build or export-only rebuild
-> compare volatile-stripped JSON payloads
-> P5RecomputeResult
-> optional save_recompute_result
```

## Runtime And API

`api/runtime.py` initializes storage runtime from `FRA_STORAGE_DB_PATH` or an
explicit path. Without storage, storage-backed routes return unavailable
responses rather than silently switching behavior.

`api/routes.py` exposes:

- issuer report coverage;
- extracted artifacts;
- dataset artifacts;
- dataset audit;
- Turtle export surfaces;
- recompute run reads;
- metric governance review and lifecycle endpoints;
- analysis extract.

`api/schemas.py` defines request/response contracts for extraction, P5
artifacts, review surfaces, dataset rows, recompute results, and lifecycle audit
responses.

## JSON Repository

`p5/artifact_repository.py::P5JsonArtifactRepository` stores extracted
artifacts, datasets, and Turtle exports as JSON files. It owns serialization and
deserialization helpers used by both JSON and DB-backed storage.

This repository supports local/offline P5 workflows and deterministic recompute
tests.

## DB Repository

`storage/repositories.py::SqlAlchemyP5ArtifactRepository` stores artifacts and
surfaces in SQLite-backed tables. Many artifact bodies are still stored as JSON
payloads, while issuer/report/dataset/recompute/review/lineage metadata is
indexed relationally.

Key write responsibilities:

- API extract bundle persistence;
- extracted artifact persistence;
- P5 dataset/Turtle/review/lineage bundle persistence;
- recompute result persistence;
- lifecycle registry persistence.

Key read responsibilities:

- report coverage;
- extracted artifact lookup;
- dataset/Turtle lookup;
- dataset audit;
- lineage records;
- recompute run lookup;
- metric governance review and lifecycle lookup.

## Review Surfaces

`p5/review.py` builds extracted artifact, dataset, and Turtle review surfaces.
These summarize validation issues, review required signals, missing status, and
export review counts.

`services/metric_governance_review.py` builds metric-governance-specific review
items from provisional candidate facts in persisted extracted artifacts.

## Lineage

`p5/lineage.py::build_dataset_lineage` links dataset rows to source artifacts,
source facts, evidence bundles, and Turtle export rows.

Storage also records fact-level lineage such as candidate-to-canonical and
canonical-to-derived relationships.

## Recompute

`p5/recompute.py` defines recompute plans and execution. Recompute remains
deterministic: it depends on manifests, persisted artifacts, assembly rules, and
explicit reasons.

Phase 4B added:

- `metric_lifecycle_decision_changed`;
- required lifecycle consumption audit for that reason;
- `artifact_transform_func` injection into `p5/runner.py`;
- in-memory controlled consumption without persisting transformed extracted
  artifacts.

## Current State

Implemented:

- DB-backed extract persistence and lookup;
- storage-backed API runtime;
- P5 dataset/Turtle persistence;
- review and lineage persistence;
- recompute result model and readback;
- JSON repository for offline/local P5 build;
- 3-5Y persisted availability/data provider baseline.

Not implemented as a complete product workflow:

- HTTP-triggered recompute execution with locking/idempotency;
- async jobs;
- automatic acquisition/backfill;
- append-only lineage history;
- full run lifecycle/state machine.

## Risks And Boundaries

- JSON recompute and DB-backed API assembly are distinct execution paths.
- Many DB objects are still JSON payloads; high-cardinality fact queries are
  limited.
- `save_p5_assembly_bundle` rewrites lineage for a dataset snapshot rather than
  preserving full lineage history.
- API extract persistence currently assumes `pdf_path` for persisted extraction
  scenarios.
- Recompute run persistence stores result metadata but does not execute
  DB-native recompute.

## Suggested Next Slices

- Define a single DB-backed recompute executor or explicit JSON-to-DB sync
  boundary.
- Add stable recompute run ids, input hashes, and before/after artifact version
  references.
- Promote high-value audit fields from JSON payloads into relational columns.
- Add recompute-run-scoped lineage history.
- Design persisted `pdf_url` identity before supporting URL-backed persistence.
