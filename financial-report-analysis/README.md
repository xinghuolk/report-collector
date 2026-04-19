# Financial Report Analysis Service

Independent analysis service for Phase-1 financial-report normalization and
quality-gated output.

## Scope

- Primary delivery form: standalone FastAPI analysis service
- Main endpoint: `POST /api/v1/analysis/extract`
- Health check: `GET /health`
- Phase-1 supported scope:
  - CN listed-company Chinese reports
  - HK listed-company English reports
- Phase-1 unsupported scope:
  - HK non-English reports are surfaced as
    `unsupported_in_phase1` with `quality_gate=review`

## Input Path

- Happy path: `pdf_path`
- Compatible inputs: `pdf_url`
- The service owns its own ingestion path and does not import `report`'s
  extractor implementation

## Output Contract

The service returns a stable analysis envelope containing:

- `document`
- `canonical_fact_set_id`
- `derived_fact_set_id`
- `validation_report_id`
- `quality_gate`
- `key_facts`
- `ttm_facts`
- `analysis_snapshot`
- `blocked_items`
