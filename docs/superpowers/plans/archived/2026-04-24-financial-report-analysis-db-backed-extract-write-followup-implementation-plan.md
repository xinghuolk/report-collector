# DB-Backed Extract Write Follow-Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `/api/v1/analysis/extract` into the first durable DB-backed write path by persisting extracted artifacts, report/document identity, and extraction-run metadata while preserving the existing read API contracts.

**Architecture:** Build on the current remote implementation instead of reviving the superseded DB-P1 `core_repository.py` route. Keep the route thin, add a small orchestration service that uses `HistoricalIngestionService` and `SqlAlchemyP5ArtifactRepository`, and return stable lookup IDs that current GET endpoints can read back.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy, SQLite-first storage, pytest, Ruff.

---

## Scope Decision

The earlier local DB-P1 files are superseded and should not be merged as-is:

- Do not add `financial-report-analysis/src/financial_report_analysis/storage/core_repository.py`.
- Do not restore `docs/superpowers/plans/2026-04-23-financial-report-analysis-db-p1-core-extraction-persistence-implementation-plan.md`.
- Reuse the already-remote repository methods:
  - `HistoricalIngestionService.register_report`
  - `SqlAlchemyP5ArtifactRepository.ensure_document_version`
  - `SqlAlchemyP5ArtifactRepository.save_extraction_run`
  - `SqlAlchemyP5ArtifactRepository.save_extracted_artifact`

Preserved backup references from the superseded local work:

- `/tmp/financial-report-analysis-local-db-p1-superseded.patch`
- `/tmp/financial-report-analysis-db-p1-core-extraction-persistence-implementation-plan.superseded.md`
- `/tmp/financial-report-analysis-core_repository.superseded.py`

## File Structure

### New files

- `financial-report-analysis/src/financial_report_analysis/api/write_service.py`
  - Owns the DB-backed extract orchestration.
  - Converts request identity into a `P5ManifestEntry`.
  - Runs extraction and analysis using existing adapters.
  - Persists report, document version, extraction run, and extracted artifact.

- `financial-report-analysis/tests/unit/test_analysis_write_service.py`
  - Covers source identity validation, persistence calls, and failure status behavior.

- `financial-report-analysis/tests/integration/test_db_backed_extract_write_api.py`
  - Verifies `POST /api/v1/analysis/extract` writes to DB and current GET endpoints read the result back.

### Existing files to modify

- `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
  - Add durable report identity fields to `AnalysisExtractRequest`.
  - Add nullable durable lookup fields to `AnalysisExtractResponse`.

- `financial-report-analysis/src/financial_report_analysis/api/routes.py`
  - Delegate durable `pdf_path` requests with explicit identity to `write_service`.
  - Keep existing immediate extract behavior for non-durable compatibility paths.

- `financial-report-analysis/src/financial_report_analysis/api/runtime.py`
  - No behavior change expected; use existing runtime dependencies.

- `financial-report-analysis/src/financial_report_analysis/storage/historical_ingestion.py`
  - Only modify if a focused rollback test reveals a transaction gap in the current remote implementation.

## Task 1: Extend Extract Request/Response Contracts

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Test: `financial-report-analysis/tests/unit/test_api_storage_runtime.py`

- [ ] **Step 1: Write failing schema tests**

Add tests that prove durable identity fields are accepted and invalid report types are rejected:

```python
def test_extract_request_accepts_durable_report_identity() -> None:
    request = AnalysisExtractRequest(
        pdf_path="/tmp/CN_601919_2025.pdf",
        issuer_id="CN_601919",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        market="CN",
    )

    assert request.issuer_id == "CN_601919"
    assert request.fiscal_year == 2025
    assert request.report_type == "annual"


def test_extract_response_can_include_durable_lookup_ids() -> None:
    response = AnalysisExtractResponse(
        document={"document_id": "/tmp/CN_601919_2025.pdf"},
        canonical_fact_set_id="canonical",
        derived_fact_set_id="derived",
        validation_report_id="validation",
        quality_gate="pass",
        key_facts=[],
        ttm_facts=[],
        analysis_snapshot={},
        blocked_items=[],
        persisted=True,
        artifact_id="CN_601919_2025",
        report_id=1,
        extraction_run_id="run-1",
    )

    assert response.persisted is True
    assert response.artifact_id == "CN_601919_2025"
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_api_storage_runtime.py -k "extract_request or extract_response" -v
```

Expected: fail because the new fields are not defined yet.

- [ ] **Step 3: Add the schema fields**

Update `AnalysisExtractRequest`:

```python
issuer_id: str | None = None
stock_code: str | None = None
fiscal_year: int | None = Field(default=None, ge=1900, le=2100)
report_type: str | None = None
company_name: str | None = None
report_language: str | None = None
persist: bool = False
```

Update `AnalysisExtractResponse`:

```python
persisted: bool = False
artifact_id: str | None = None
report_id: int | None = None
extraction_run_id: str | None = None
```

- [ ] **Step 4: Re-run the focused tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_api_storage_runtime.py -k "extract_request or extract_response" -v
```

Expected: pass.

## Task 2: Add The DB-Backed Write Service

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/api/write_service.py`
- Test: `financial-report-analysis/tests/unit/test_analysis_write_service.py`

- [ ] **Step 1: Write a failing service test**

Create a test that injects a temp DB runtime, calls the service with a local PDF path and explicit identity, and asserts persisted IDs are returned.

Use this shape:

```python
def test_write_service_persists_extracted_artifact_and_run(tmp_path: Path) -> None:
    db_path = tmp_path / "storage.db"
    runtime = build_api_runtime(db_path)
    pdf_path = tmp_path / "CN_601919_2025.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    result = extract_and_persist_analysis(
        request=AnalysisExtractRequest(
            pdf_path=str(pdf_path),
            issuer_id="CN_601919",
            stock_code="601919",
            fiscal_year=2025,
            report_type="annual",
            market="CN",
            company_name="中远海控",
            report_language="zh",
            persist=True,
        ),
        runtime=runtime,
    )

    assert result.persisted is True
    assert result.artifact_id == "CN_601919_2025"
    assert result.report_id is not None
    assert result.extraction_run_id is not None
    assert runtime.storage_repository.load_extracted_artifact("CN_601919_2025")
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_analysis_write_service.py::test_write_service_persists_extracted_artifact_and_run -v
```

Expected: fail because `write_service.py` does not exist.

- [ ] **Step 3: Implement the service**

Create `write_service.py` with these responsibilities:

```python
def extract_and_persist_analysis(
    *,
    request: AnalysisExtractRequest,
    runtime: ApiRuntime,
) -> AnalysisExtractResponse:
    validate runtime.storage_repository and runtime.historical_ingestion_service
    validate request.persist is true
    validate request.pdf_path is present and request.pdf_url is absent
    validate issuer_id, stock_code, fiscal_year, report_type, and market are present
    build P5ManifestEntry
    register report with HistoricalIngestionService
    ensure document version with SqlAlchemyP5ArtifactRepository
    save extraction run with status="running"
    run PdfIngestionAdapter + analyze_report + ReportAdapter
    build P5ExtractedArtifact from the analysis result and extracted payload
    save extracted artifact
    save extraction run with status="completed"
    return AnalysisExtractResponse with persisted IDs
```

Use the current durable IDs:

```python
artifact_id = entry.artifact_id
pipeline_version = "api-extract-v1"
document_version = repository.ensure_document_version(
    report_id=registration.report_id,
    file_path=str(entry.pdf_path),
)
run = repository.save_extraction_run(
    document_version_id=document_version.document_version_id,
    pipeline_version=pipeline_version,
    status="running",
)
```

- [ ] **Step 4: Re-run the service test**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_analysis_write_service.py -v
```

Expected: pass.

## Task 3: Wire The Route Without Breaking Compatibility

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Test: `financial-report-analysis/tests/integration/test_db_backed_extract_write_api.py`

- [ ] **Step 1: Write the integration test**

Add a test that posts with `persist=true`, then reads the stored artifact and report coverage back through existing endpoints:

```python
def test_extract_with_persistence_can_be_read_back(tmp_path: Path) -> None:
    db_path = tmp_path / "storage.db"
    pdf_path = tmp_path / "CN_601919_2025.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    client = TestClient(create_app(storage_db_path=db_path))

    post_response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(pdf_path),
            "issuer_id": "CN_601919",
            "stock_code": "601919",
            "fiscal_year": 2025,
            "report_type": "annual",
            "market": "CN",
            "company_name": "中远海控",
            "report_language": "zh",
            "persist": True,
        },
    )

    assert post_response.status_code == 200
    body = post_response.json()
    assert body["persisted"] is True
    assert body["artifact_id"] == "CN_601919_2025"
    assert body["extraction_run_id"]

    artifact_response = client.get("/api/v1/artifacts/CN_601919_2025")
    assert artifact_response.status_code == 200

    coverage_response = client.get("/api/v1/reports/CN_601919/2025/annual")
    assert coverage_response.status_code == 200
    coverage = coverage_response.json()
    assert coverage["report_registered"] is True
    assert coverage["extracted_artifact_available"] is True
    assert coverage["extracted_artifact_ids"] == ["CN_601919_2025"]
```

- [ ] **Step 2: Run the integration test and confirm it fails**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_db_backed_extract_write_api.py::test_extract_with_persistence_can_be_read_back -v
```

Expected: fail because the route does not call the write service.

- [ ] **Step 3: Delegate durable requests to the write service**

In `extract_analysis`, keep existing immediate behavior unless `request.persist is True`.

Add this branch near the start after basic `pdf_path` / `pdf_url` validation:

```python
if request.persist:
    try:
        return extract_and_persist_analysis(
            request=request,
            runtime=get_runtime(http_request),
        ).model_dump()
    except DurableExtractInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DurableExtractRuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
```

- [ ] **Step 4: Re-run route tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_db_backed_extract_write_api.py tests/integration/test_api_storage_runtime.py -v
```

Expected: pass.

## Task 4: Preserve The Strong Rollback Semantics From Superseded Local Work

**Files:**
- Modify: `financial-report-analysis/tests/unit/test_historical_ingestion.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/historical_ingestion.py` only if needed.

- [ ] **Step 1: Add rollback coverage for document-ledger side effects**

Extend the current atomic manifest test so it checks these tables also roll back:

```python
with Session(engine) as session:
    report_file_count = session.scalar(select(func.count()).select_from(ReportFileRecord))
    document_count = session.scalar(select(func.count()).select_from(DocumentRecord))
    version_count = session.scalar(select(func.count()).select_from(DocumentVersionRecord))

assert report_file_count == 0
assert document_count == 0
assert version_count == 0
```

- [ ] **Step 2: Run the focused test**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_historical_ingestion.py::test_register_manifest_is_atomic_when_a_later_entry_fails -v
```

Expected: pass if current remote implementation is already safe; otherwise fail with persisted side effects.

- [ ] **Step 3: Fix only if the test fails**

If side effects remain, keep registration inside the existing session boundary. Do not introduce `core_repository.py`; instead add a session-aware helper to the existing repository only if absolutely required.

## Task 5: Metric Registry And Evidence DB Persistence Follow-Up

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Test: `financial-report-analysis/tests/unit/test_document_ledger_repository.py`

- [ ] **Step 1: Add tests for metric registry persistence**

Write tests for:

```python
repository.save_metric_registry_entry(
    metric_registry_id="standard:revenue",
    metric_id="revenue",
    display_name="Revenue",
    review_status="approved",
    payload={"aliases": ["营业收入"]},
)

assert repository.list_metric_registry_entries()[0]["metric_registry_id"] == "standard:revenue"
```

- [ ] **Step 2: Add tests for DB-backed evidence bundle persistence**

Write tests that persist an `EvidenceBundle` and linked `EvidenceItem` records to the SQL tables, not the current in-memory repository.

- [ ] **Step 3: Implement the minimal repository methods**

Add only these methods with these contracts:

- `save_metric_registry_entry(self, *, metric_registry_id: str, metric_id: str, display_name: str, review_status: str, payload: dict[str, object] | None = None) -> str`
- `list_metric_registry_entries(self) -> tuple[dict[str, object]]`
- `save_evidence_bundle(self, bundle: EvidenceBundle) -> str`
- `load_evidence_bundle(self, evidence_bundle_id: str) -> EvidenceBundle | None`

Do not add workflow or approval-state transitions in this task.

## Verification

- [ ] Run focused API tests:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_analysis_write_service.py tests/integration/test_db_backed_extract_write_api.py -v
```

- [ ] Run storage regression tests:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_historical_ingestion.py tests/unit/test_document_ledger_repository.py tests/unit/test_storage_repository.py -v
```

- [ ] Run Ruff:

```bash
cd financial-report-analysis
uv run ruff check src tests
```

## Exit Criteria

- `POST /api/v1/analysis/extract` with `persist=true` writes an extracted artifact to DB.
- Response includes `persisted`, `artifact_id`, `report_id`, and `extraction_run_id`.
- Existing GET endpoints can read the freshly persisted artifact and report coverage.
- No `core_repository.py` or superseded DB-P1 plan is reintroduced.
- Strong rollback semantics from the superseded local work are either verified or implemented against the current remote architecture.
