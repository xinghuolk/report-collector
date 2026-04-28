# Extraction And Data Flow

## High-Level Flow

```text
PDF path / URL
-> PdfIngestionAdapter.extract_candidate_facts()
-> pypdf text pages + pdfplumber table blocks
-> ParsedTable recovery
-> header / period / unit / currency parsing
-> normalize_table_semantics()
-> MetricMappingRegistry.match()
-> build_table_candidate_facts()
-> note disclosure candidates and bounded fallback
-> analyze_report()
-> FactNormalizer.normalize_candidates()
-> ConflictResolver.resolve_with_review()
-> canonical facts + review packets
-> DerivationService.derive_ttm()
-> ValidationService.validate()
-> ReportAdapter / P5ExtractedArtifact
-> assemble_dataset()
-> build_turtle_export()
```

## Ingestion And Table Recovery

`ingestion/pdf_ingestion.py::PdfIngestionAdapter.extract_candidate_facts` is the
main PDF ingestion entry. It reads PDF text pages and table blocks, then uses
table structure and semantic adapters to produce candidate facts.

Important files:

- `ingestion/table_source.py`: extracts `RawTableBlock` objects from PDFs.
- `ingestion/table_structure.py`: converts raw table blocks into `ParsedTable`.
- `ingestion/table_header_parser.py`: parses periods, units, currencies, and
  column shapes.
- `ingestion/table_stitcher.py`: stitches tables split across pages.
- `ingestion/table_semantics.py`: normalizes table kind, rows, cells, and
  semantic metadata.
- `services/table_fact_builder.py`: converts normalized table semantics into
  candidate fact dictionaries.

The extraction path is table-first. Text fallback and note-disclosure extraction
are supplemental, not the primary fact source.

## Candidate To Canonical

`pipeline.py::analyze_report` orchestrates the core transformation:

```text
candidate facts
-> FactNormalizer
-> ConflictResolver
-> canonical facts
-> DerivationService
-> ValidationService
```

`models/facts.py` defines `CandidateFact`, `CanonicalFact`, and `DerivedFact`.

`services/fact_normalizer.py::FactNormalizer.normalize_candidates` normalizes
candidate units/currencies and attaches `extensions.metric_governance`.

`services/conflict_resolver.py::ConflictResolver.resolve_with_review` promotes
eligible candidate facts to canonical facts. It also emits review packets for
source conflicts, scope conflicts, or provisional custom metrics.

`services/derivation_service.py::DerivationService.derive_ttm` derives TTM facts
from canonical quarterly facts where sufficient consecutive periods exist.

`services/validation_service.py::ValidationService.validate` produces validation
issues and quality gate status.

## API Adaptation

`adapters/report_adapter.py::ReportAdapter.build_analysis_result` converts the
pipeline result into API-facing output. It defensively excludes facts whose
governance metadata says `auto_analysis_allowed=false`.

This is one of the final guards preventing provisional/custom facts from
silently entering `key_facts`.

## P5 And Turtle

`p5/extraction.py::build_extracted_artifact` builds `P5ExtractedArtifact` from a
manifest entry and a PDF.

`p5/dataset.py::assemble_dataset` creates `P5DatasetArtifact` rows from
`artifact.canonical_facts`. It also produces missing rows for required metrics.
As of Phase 4B, dataset rows may carry
`lifecycle_consumption` provenance when controlled consumption synthesized a
governed canonical fact.

`p5/turtle_export.py::build_turtle_export` exports dataset rows through the
current alias mapping. It uses dataclass serialization, so dataset row fields
such as `lifecycle_consumption` flow into Turtle review/export rows.

## Current State

Implemented:

- PDF text/table ingestion;
- parsed table recovery;
- normalized table semantics;
- deterministic metric mapping;
- candidate/canonical/derived/validation path;
- note disclosure supplement paths;
- P5 extracted artifact, dataset, and Turtle export;
- DB-backed persistence for extracted artifact and optional P5/Turtle outputs.

## Key Risks And Boundaries

- `PdfIngestionAdapter` can fall back when table parsing fails; this needs
  metadata visibility so callers can distinguish missing facts from parser
  failure.
- `MetricMappingRegistry` external source loading is not implemented; most
  mappings remain code-defined.
- `assemble_dataset()` consumes canonical facts only. Derived facts are not
  automatically included in P5 dataset/Turtle outputs.
- Turtle export is alias-map driven and does not by itself enforce field
  completeness policy.
- Complex scope/source precedence still depends on review packets and tests,
  not on a full policy engine.

## Suggested Next Slices

- Add parse-failure metadata to quality/audit outputs.
- Decide whether derived facts should enter P5 datasets, and implement that as
  a focused contract if needed.
- Version external metric mappings before further broad field expansion.
- Reduce divergence between JSON P5 build and DB-backed P5 assembly flows.
