# DB-Backed Extract Persistence And Lookup Slice Implementation Plan

> **Closeout status:** Completed. Focused unit, focused integration, and Ruff verification passed. This phase intentionally persists only the extracted artifact and lookup metadata; dataset/Turtle orchestration remains a later phase.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in DB-backed write slice to `/api/v1/analysis/extract` so an HTTP extract request can persist the extracted artifact and return stable lookup identifiers that existing GET endpoints can read back.

**Architecture:** Keep the existing extract route as the compatibility path, and enable persistence only when the request explicitly sets `persist_to_storage=true` and provides report identity fields. Reuse the existing `ApiRuntime`, `HistoricalIngestionService`, `SqlAlchemyP5ArtifactRepository`, P5 artifact payload shape, review surface builder, and document/extraction-run ledger methods. Do not introduce dataset/Turtle orchestration or a new storage abstraction in this slice.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy-backed P5 repository, pytest, Ruff.

---

## File Structure

### Existing files to modify

- `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
  - Add opt-in persistence request fields and a nullable storage result response contract.
- `financial-report-analysis/src/financial_report_analysis/api/routes.py`
  - Keep the route thin and delegate persistence to a service after the existing extraction/pipeline work succeeds.
- `financial-report-analysis/src/financial_report_analysis/p5/extraction.py`
  - Add a helper that builds `P5ExtractedArtifact` from an already computed extract/pipeline result, avoiding a second PDF extraction.
- `financial-report-analysis/tests/integration/test_analysis_api.py`
  - Add focused API integration tests for opt-in DB persistence, readback, missing identity, and no-storage runtime behavior.

### New files to create

- `financial-report-analysis/src/financial_report_analysis/api/extract_write_service.py`
  - Own the DB-backed write slice: request identity normalization, report registration, document ledger entry, extraction run entry, extracted artifact persistence, extracted review surface persistence, and response lookup metadata.
- `financial-report-analysis/tests/unit/test_extract_write_service.py`
  - Unit-test the service without FastAPI.

### Responsibility split

- `schemas.py` defines request/response contracts only.
- `routes.py` parses HTTP, runs existing extraction, calls the service only when persistence is requested, and assembles the final response.
- `extract_write_service.py` orchestrates persistence and returns a small serializable result.
- `p5/extraction.py` remains responsible for building the persisted `P5ExtractedArtifact` shape.
- This phase does not build datasets, Turtle exports, recompute runs, whole-document LLM assessment, or workflow approval APIs.

## Task 1: Add Opt-In Persistence API Schema Contract

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Test: `financial-report-analysis/tests/integration/test_analysis_api.py`

- [ ] **Step 1: Write the failing API contract tests**

Append these tests to `financial-report-analysis/tests/integration/test_analysis_api.py`:

```python
def test_extract_endpoint_requires_identity_when_persistence_is_requested() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": "ignored.pdf",
            "market": "CN",
            "persist_to_storage": True,
        },
    )

    assert response.status_code == 422
    assert "issuer_id" in response.text
    assert "fiscal_year" in response.text
    assert "stock_code" in response.text
    assert "report_type" in response.text


def test_extract_endpoint_rejects_non_annual_persisted_report_type() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": "ignored.pdf",
            "market": "CN",
            "persist_to_storage": True,
            "issuer_id": "CN_601919",
            "stock_code": "601919",
            "fiscal_year": 2025,
            "report_type": "quarterly",
        },
    )

    assert response.status_code == 422
    assert "report_type" in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `financial-report-analysis/`:

```bash
uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_requires_identity_when_persistence_is_requested tests/integration/test_analysis_api.py::test_extract_endpoint_rejects_non_annual_persisted_report_type -q -o addopts=
```

Expected: FAIL because `AnalysisExtractRequest` currently forbids the new fields.

- [ ] **Step 3: Add schema fields and validation**

Update `financial-report-analysis/src/financial_report_analysis/api/schemas.py`:

```python
from pydantic import BaseModel, ConfigDict, Field, model_validator
```

Replace `AnalysisExtractRequest` with:

```python
class AnalysisExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pdf_path: str | None = None
    pdf_url: str | None = None
    market: str | None = None
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    persist_to_storage: bool = False
    issuer_id: str | None = None
    stock_code: str | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    report_type: str | None = None
    company_name: str | None = None
    report_language: str | None = None
    source: str = "api"

    @model_validator(mode="after")
    def validate_persistence_identity(self) -> "AnalysisExtractRequest":
        if not self.persist_to_storage:
            return self

        missing_fields = [
            field_name
            for field_name in ("issuer_id", "stock_code", "fiscal_year", "report_type")
            if getattr(self, field_name) in (None, "")
        ]
        if missing_fields:
            raise ValueError(
                "persist_to_storage requires explicit report identity fields: "
                + ", ".join(missing_fields)
            )
        if self.report_type != "annual":
            raise ValueError("persist_to_storage currently supports report_type='annual' only")
        return self
```

Add the response model before `AnalysisExtractResponse`:

```python
class AnalysisStorageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted: bool
    artifact_id: str | None = None
    report_id: int | None = None
    document_id: str | None = None
    document_version_id: str | None = None
    extraction_run_id: str | None = None
    artifact_lookup_path: str | None = None
    report_lookup_path: str | None = None
```

Add this field to `AnalysisExtractResponse`:

```python
    storage: AnalysisStorageResult | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_requires_identity_when_persistence_is_requested tests/integration/test_analysis_api.py::test_extract_endpoint_rejects_non_annual_persisted_report_type -q -o addopts=
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/api/schemas.py financial-report-analysis/tests/integration/test_analysis_api.py
git commit -m "feat: add extract persistence request contract"
```

## Task 2: Build P5 Extracted Artifact From Existing Extract Result

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/extraction.py`
- Test: `financial-report-analysis/tests/unit/test_p5_extraction.py`

- [ ] **Step 1: Write the failing helper test**

Append to `financial-report-analysis/tests/unit/test_p5_extraction.py`:

```python
def test_build_extracted_artifact_from_result_reuses_existing_payload(tmp_path):
    from financial_report_analysis.p5.extraction import (
        build_extracted_artifact_from_result,
    )
    from financial_report_analysis.p5.models import P5ManifestEntry

    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=pdf_path,
        source="api",
        company_name="COSCO SHIPPING Holdings",
        report_language="zh",
    )
    document = {
        "document_id": str(pdf_path),
        "pdf_path": str(pdf_path),
        "market": "CN",
        "metadata": {"source": "api"},
    }
    extracted_payload = {
        "document_metadata": {
            "language": "zh",
            "cash_health_missing_status": {"restricted_cash": "not_surfaced"},
        },
        "candidate_facts": [{"fact_id": "candidate-1", "metric_id": "revenue"}],
    }
    pipeline_result = {
        "canonical_facts": [{"fact_id": "canonical-1", "metric_id": "revenue"}],
        "derived_facts": [],
        "validation_report": {"overall_status": "ok", "issues": []},
        "review_packets": [],
        "quality_gate": "pass",
    }

    artifact = build_extracted_artifact_from_result(
        entry=entry,
        document=document,
        extracted_payload=extracted_payload,
        pipeline_result=pipeline_result,
        now_func=lambda: "2026-04-24T00:00:00+00:00",
    )

    assert artifact.artifact_id == "CN_601919_2025"
    assert artifact.manifest_entry == entry
    assert artifact.document is not document
    assert artifact.document["document_id"] == str(pdf_path)
    assert artifact.candidate_facts == (
        {"fact_id": "candidate-1", "metric_id": "revenue"},
    )
    assert artifact.canonical_facts == (
        {"fact_id": "canonical-1", "metric_id": "revenue"},
    )
    assert artifact.missing_status == {
        "working_capital_missing_status": {},
        "debt_missing_status": {},
        "asset_missing_status": {},
        "cash_health_missing_status": {"restricted_cash": "not_surfaced"},
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/unit/test_p5_extraction.py::test_build_extracted_artifact_from_result_reuses_existing_payload -q -o addopts=
```

Expected: FAIL with missing `build_extracted_artifact_from_result`.

- [ ] **Step 3: Implement the helper**

In `financial-report-analysis/src/financial_report_analysis/p5/extraction.py`, add this function above `build_extracted_artifact`:

```python
def build_extracted_artifact_from_result(
    *,
    entry: P5ManifestEntry,
    document: dict[str, Any],
    extracted_payload: dict[str, Any],
    pipeline_result: Any,
    now_func: Callable[[], str] | None = None,
) -> P5ExtractedArtifact:
    document_metadata = _json_object(
        extracted_payload.get("document_metadata", {}),
        field_name="document_metadata",
    )
    missing_status = _missing_status_from_metadata(document_metadata)
    document_ref = _json_object(document, field_name="document")

    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version=_ARTIFACT_VERSION,
        pipeline_version=_PIPELINE_VERSION,
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document=document_ref,
        document_metadata=document_metadata,
        candidate_facts=_json_object_tuple(extracted_payload.get("candidate_facts", [])),
        canonical_facts=_json_object_tuple(_result_value(pipeline_result, "canonical_facts", [])),
        derived_facts=_json_object_tuple(_result_value(pipeline_result, "derived_facts", [])),
        validation_report=_json_object(
            _result_value(pipeline_result, "validation_report", {}),
            field_name="validation_report",
        ),
        review_packets=_json_object_tuple(_result_value(pipeline_result, "review_packets", [])),
        quality_gate=str(_result_value(pipeline_result, "quality_gate", "review")),
        missing_status=missing_status,
        created_at=now_func() if now_func is not None else _utc_now_iso(),
    )
```

Refactor `build_extracted_artifact()` to call this helper instead of duplicating artifact construction:

```python
    pipeline_result = analyze_report_func(document_ref, extracted_payload)

    return build_extracted_artifact_from_result(
        entry=entry,
        document=document_ref,
        extracted_payload=extracted_payload,
        pipeline_result=pipeline_result,
        now_func=now_func,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/test_p5_extraction.py::test_build_extracted_artifact_from_result_reuses_existing_payload tests/unit/test_p5_extraction.py -q -o addopts=
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/extraction.py financial-report-analysis/tests/unit/test_p5_extraction.py
git commit -m "feat: build p5 artifact from extract result"
```

## Task 3: Add DB-Backed Extract Write Service

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/api/extract_write_service.py`
- Test: `financial-report-analysis/tests/unit/test_extract_write_service.py`

- [ ] **Step 1: Write the failing service test**

Create `financial-report-analysis/tests/unit/test_extract_write_service.py`:

```python
from __future__ import annotations

from pathlib import Path

from financial_report_analysis.api.extract_write_service import (
    persist_analysis_extract_result,
)
from financial_report_analysis.api.schemas import AnalysisExtractRequest
from financial_report_analysis.api.runtime import build_api_runtime


def test_persist_analysis_extract_result_writes_report_artifact_and_review_surface(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    runtime = build_api_runtime(tmp_path / "storage.db")
    request = AnalysisExtractRequest(
        pdf_path=str(pdf_path),
        market="CN",
        persist_to_storage=True,
        issuer_id="CN_601919",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        company_name="COSCO SHIPPING Holdings",
        report_language="zh",
        source="api",
    )
    document = {
        "document_id": str(pdf_path),
        "pdf_path": str(pdf_path),
        "pdf_url": None,
        "market": "CN",
        "metadata": {"language": "zh"},
    }
    extracted_payload = {
        "document_metadata": {"language": "zh"},
        "candidate_facts": [{"fact_id": "candidate-1", "metric_id": "revenue"}],
    }
    pipeline_result = {
        "canonical_facts": [{"fact_id": "canonical-1", "metric_id": "revenue"}],
        "derived_facts": [],
        "validation_report": {"overall_status": "ok", "issues": []},
        "review_packets": [],
        "quality_gate": "pass",
    }

    result = persist_analysis_extract_result(
        runtime=runtime,
        request=request,
        document=document,
        extracted_payload=extracted_payload,
        pipeline_result=pipeline_result,
        now_func=lambda: "2026-04-24T00:00:00+00:00",
    )

    assert result.persisted is True
    assert result.artifact_id == "CN_601919_2025"
    assert result.report_id is not None
    assert result.document_id
    assert result.document_version_id
    assert result.extraction_run_id
    assert result.artifact_lookup_path == "/artifacts/CN_601919_2025"
    assert result.report_lookup_path == "/reports/CN_601919/2025/annual"

    assert runtime.storage_repository is not None
    artifact = runtime.storage_repository.load_extracted_artifact("CN_601919_2025")
    surface = runtime.storage_repository.load_extracted_review_surface("CN_601919_2025")
    coverage = runtime.storage_repository.get_report_coverage("CN_601919", 2025, "annual")

    assert artifact.canonical_facts == (
        {"fact_id": "canonical-1", "metric_id": "revenue"},
    )
    assert surface.quality_gate == "pass"
    assert coverage.extracted_artifact_available is True
    assert coverage.extracted_artifact_ids == ("CN_601919_2025",)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/unit/test_extract_write_service.py::test_persist_analysis_extract_result_writes_report_artifact_and_review_surface -q -o addopts=
```

Expected: FAIL with missing `financial_report_analysis.api.extract_write_service`.

- [ ] **Step 3: Implement the write service**

Create `financial-report-analysis/src/financial_report_analysis/api/extract_write_service.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from financial_report_analysis.api.runtime import ApiRuntime
from financial_report_analysis.api.schemas import AnalysisExtractRequest
from financial_report_analysis.p5.extraction import build_extracted_artifact_from_result
from financial_report_analysis.p5.models import P5ManifestEntry
from financial_report_analysis.p5.review import build_extracted_review_surface


@dataclass(frozen=True, slots=True)
class AnalysisExtractStorageResult:
    persisted: bool
    artifact_id: str
    report_id: int
    document_id: str
    document_version_id: str
    extraction_run_id: str
    artifact_lookup_path: str
    report_lookup_path: str

    def to_response_dict(self) -> dict[str, object]:
        return {
            "persisted": self.persisted,
            "artifact_id": self.artifact_id,
            "report_id": self.report_id,
            "document_id": self.document_id,
            "document_version_id": self.document_version_id,
            "extraction_run_id": self.extraction_run_id,
            "artifact_lookup_path": self.artifact_lookup_path,
            "report_lookup_path": self.report_lookup_path,
        }


def persist_analysis_extract_result(
    *,
    runtime: ApiRuntime,
    request: AnalysisExtractRequest,
    document: dict[str, Any],
    extracted_payload: dict[str, Any],
    pipeline_result: Any,
    now_func: Callable[[], str] | None = None,
) -> AnalysisExtractStorageResult:
    if runtime.storage_repository is None or runtime.historical_ingestion_service is None:
        raise RuntimeError("storage repository is not configured")

    entry = _manifest_entry_from_request(request)
    registration = runtime.historical_ingestion_service.register_report(
        entry,
        manifest_id="api_extract",
    )
    document_identity = runtime.storage_repository.ensure_document_version(
        report_id=registration.report_id,
        file_path=str(entry.pdf_path),
        version_label="api_extract",
        report_file_payload={"source": entry.source},
        document_payload=document,
        document_version_payload={"artifact_id": entry.artifact_id},
    )
    artifact = build_extracted_artifact_from_result(
        entry=entry,
        document=document,
        extracted_payload=extracted_payload,
        pipeline_result=pipeline_result,
        now_func=now_func,
    )
    extraction_run = runtime.storage_repository.save_extraction_run(
        document_version_id=document_identity.document_version_id,
        pipeline_version=artifact.pipeline_version,
        status=artifact.quality_gate,
        payload={
            "artifact_id": artifact.artifact_id,
            "quality_gate": artifact.quality_gate,
            "canonical_fact_count": len(artifact.canonical_facts),
            "candidate_fact_count": len(artifact.candidate_facts),
        },
    )
    runtime.storage_repository.save_extracted_artifact(artifact)
    runtime.storage_repository.save_extracted_review_surface(
        build_extracted_review_surface(artifact)
    )

    return AnalysisExtractStorageResult(
        persisted=True,
        artifact_id=artifact.artifact_id,
        report_id=registration.report_id,
        document_id=document_identity.document_id,
        document_version_id=document_identity.document_version_id,
        extraction_run_id=extraction_run.extraction_run_id,
        artifact_lookup_path=f"/artifacts/{artifact.artifact_id}",
        report_lookup_path=(
            f"/reports/{entry.issuer_id}/{entry.fiscal_year}/{entry.report_type}"
        ),
    )


def _manifest_entry_from_request(request: AnalysisExtractRequest) -> P5ManifestEntry:
    if request.pdf_path is None:
        raise ValueError("persist_to_storage requires pdf_path in this slice")
    if request.issuer_id is None:
        raise ValueError("persist_to_storage requires issuer_id")
    if request.stock_code is None:
        raise ValueError("persist_to_storage requires stock_code")
    if request.fiscal_year is None:
        raise ValueError("persist_to_storage requires fiscal_year")
    if request.report_type != "annual":
        raise ValueError("persist_to_storage currently supports annual reports only")
    if request.market not in {"CN", "HK", "US"}:
        raise ValueError("persist_to_storage requires market to be one of CN, HK, US")

    return P5ManifestEntry(
        issuer_id=request.issuer_id,
        market=request.market,
        stock_code=request.stock_code,
        fiscal_year=request.fiscal_year,
        report_type="annual",
        pdf_path=Path(request.pdf_path),
        source=request.source,
        company_name=request.company_name,
        report_language=request.report_language,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/test_extract_write_service.py -q -o addopts=
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/api/extract_write_service.py financial-report-analysis/tests/unit/test_extract_write_service.py
git commit -m "feat: add db backed extract write service"
```

## Task 4: Wire Persistence Into The Extract Route

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Test: `financial-report-analysis/tests/integration/test_analysis_api.py`

- [x] **Step 1: Write the failing route tests**

Append to `financial-report-analysis/tests/integration/test_analysis_api.py`:

```python
def test_extract_endpoint_returns_503_when_persistence_requested_without_storage(
    monkeypatch,
    tmp_path,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter

    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "extract_candidate_facts",
        lambda self, **kwargs: {
            "document_metadata": {"language": "zh"},
            "candidate_facts": [],
        },
    )

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(pdf_path),
            "market": "CN",
            "persist_to_storage": True,
            "issuer_id": "CN_601919",
            "stock_code": "601919",
            "fiscal_year": 2025,
            "report_type": "annual",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "storage repository is not configured"


def test_extract_endpoint_persists_to_storage_when_requested(
    monkeypatch,
    tmp_path,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter

    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "extract_candidate_facts",
        lambda self, **kwargs: {
            "document_metadata": {"language": "zh"},
            "candidate_facts": [
                {
                    "fact_id": "candidate-1",
                    "metric_id": "revenue",
                    "metric_label_raw": "Revenue",
                    "statement_type": "income_statement",
                    "entity_scope": "consolidated",
                    "period_id": "2025FY",
                    "currency": "CNY",
                    "raw_value": "100",
                    "numeric_value": 100.0,
                    "raw_unit": "yuan",
                    "normalized_unit": "currency_amount",
                    "confidence": 0.99,
                    "evidence_bundle_id": "bundle-1",
                }
            ],
        },
    )

    client = TestClient(create_app(storage_db_path=tmp_path / "storage.db"))
    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(pdf_path),
            "market": "CN",
            "min_confidence": 0.8,
            "persist_to_storage": True,
            "issuer_id": "CN_601919",
            "stock_code": "601919",
            "fiscal_year": 2025,
            "report_type": "annual",
            "company_name": "COSCO SHIPPING Holdings",
            "report_language": "zh",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["storage"]["persisted"] is True
    assert payload["storage"]["artifact_id"] == "CN_601919_2025"
    assert payload["storage"]["artifact_lookup_path"] == "/artifacts/CN_601919_2025"
    assert payload["storage"]["report_lookup_path"] == "/reports/CN_601919/2025/annual"
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_returns_503_when_persistence_requested_without_storage tests/integration/test_analysis_api.py::test_extract_endpoint_persists_to_storage_when_requested -q -o addopts=
```

Expected: FAIL because the route does not call the write service and does not include `storage` in the response.

- [x] **Step 3: Wire the route**

In `financial-report-analysis/src/financial_report_analysis/api/routes.py`, add imports:

```python
from financial_report_analysis.api.extract_write_service import (
    persist_analysis_extract_result,
)
```

Inside `extract_analysis()`, keep the existing `runtime = get_runtime(http_request)` call as a local variable:

```python
    runtime = get_runtime(http_request)
```

After `analysis_result = ReportAdapter().build_analysis_result(...)`, add:

```python
    analysis_result = ReportAdapter().build_analysis_result(
        document=document,
        pipeline_result=pipeline_result,
    )
    if request.persist_to_storage:
        if runtime.storage_repository is None or runtime.historical_ingestion_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="storage repository is not configured",
            )
        try:
            storage_result = persist_analysis_extract_result(
                runtime=runtime,
                request=request,
                document=document,
                extracted_payload=extracted_payload,
                pipeline_result=pipeline_result,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        analysis_result["storage"] = storage_result.to_response_dict()
    else:
        analysis_result["storage"] = None
    return analysis_result
```

Remove the old direct `return ReportAdapter().build_analysis_result(...)` block.

- [x] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_returns_503_when_persistence_requested_without_storage tests/integration/test_analysis_api.py::test_extract_endpoint_persists_to_storage_when_requested -q -o addopts=
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/api/routes.py financial-report-analysis/tests/integration/test_analysis_api.py
git commit -m "feat: persist extract route results to storage"
```

## Task 5: Verify Persisted HTTP Result Can Be Read Back

**Files:**
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`

- [x] **Step 1: Write the failing readback integration test**

Append to `financial-report-analysis/tests/integration/test_analysis_api.py`:

```python
def test_extract_endpoint_persisted_result_is_readable_by_storage_get_routes(
    monkeypatch,
    tmp_path,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter

    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        PdfIngestionAdapter,
        "extract_candidate_facts",
        lambda self, **kwargs: {
            "document_metadata": {
                "language": "zh",
                "cash_health_missing_status": {"restricted_cash": "not_surfaced"},
            },
            "candidate_facts": [
                {
                    "fact_id": "candidate-1",
                    "metric_id": "revenue",
                    "metric_label_raw": "Revenue",
                    "statement_type": "income_statement",
                    "entity_scope": "consolidated",
                    "period_id": "2025FY",
                    "currency": "CNY",
                    "raw_value": "100",
                    "numeric_value": 100.0,
                    "raw_unit": "yuan",
                    "normalized_unit": "currency_amount",
                    "confidence": 0.99,
                    "evidence_bundle_id": "bundle-1",
                }
            ],
        },
    )

    client = TestClient(create_app(storage_db_path=tmp_path / "storage.db"))
    extract_response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(pdf_path),
            "market": "CN",
            "min_confidence": 0.8,
            "persist_to_storage": True,
            "issuer_id": "CN_601919",
            "stock_code": "601919",
            "fiscal_year": 2025,
            "report_type": "annual",
            "company_name": "COSCO SHIPPING Holdings",
            "report_language": "zh",
        },
    )
    assert extract_response.status_code == 200
    storage = extract_response.json()["storage"]

    artifact_response = client.get(storage["artifact_lookup_path"])
    report_response = client.get(storage["report_lookup_path"])
    issuer_response = client.get("/issuers/CN_601919/reports")

    assert artifact_response.status_code == 200
    artifact_payload = artifact_response.json()
    assert artifact_payload["artifact_id"] == "CN_601919_2025"
    assert artifact_payload["manifest_entry"]["issuer_id"] == "CN_601919"
    assert artifact_payload["quality_gate"] in {"pass", "review", "fail"}
    assert artifact_payload["missing_status"]["cash_health_missing_status"] == {
        "restricted_cash": "not_surfaced"
    }

    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["report_registered"] is True
    assert report_payload["extracted_artifact_available"] is True
    assert report_payload["extracted_artifact_ids"] == ["CN_601919_2025"]

    assert issuer_response.status_code == 200
    assert issuer_response.json()["reports"][0]["fiscal_year"] == 2025
```

- [x] **Step 2: Run test to verify it passes or exposes a wiring gap**

Run:

```bash
uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_persisted_result_is_readable_by_storage_get_routes -q -o addopts=
```

Expected: PASS. If it fails, fix only the persistence/readback wiring needed for this contract.

- [x] **Step 3: Run focused storage API regression**

Run:

```bash
uv run pytest tests/integration/test_api_storage_runtime.py tests/unit/test_api_storage_runtime.py -q -o addopts=
```

Expected: PASS.

- [x] **Step 4: Commit**

```bash
git add financial-report-analysis/tests/integration/test_analysis_api.py financial-report-analysis/src/financial_report_analysis/api/routes.py financial-report-analysis/src/financial_report_analysis/api/extract_write_service.py
git commit -m "test: verify db backed extract readback"
```

## Task 6: Close Out Verification And Plan Status

**Files:**
- Modify: `docs/superpowers/plans/2026-04-24-financial-report-analysis-db-backed-extract-persistence-and-lookup-slice-implementation-plan.md`

- [x] **Step 1: Run focused unit tests**

Run:

```bash
uv run pytest tests/unit/test_extract_write_service.py tests/unit/test_p5_extraction.py tests/unit/test_api_storage_runtime.py tests/unit/test_storage_repository.py tests/unit/test_document_ledger_repository.py -q -o addopts=
```

Expected: PASS.

- [x] **Step 2: Run focused integration tests**

Run:

```bash
uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_requires_identity_when_persistence_is_requested tests/integration/test_analysis_api.py::test_extract_endpoint_rejects_non_annual_persisted_report_type tests/integration/test_analysis_api.py::test_extract_endpoint_returns_503_when_persistence_requested_without_storage tests/integration/test_analysis_api.py::test_extract_endpoint_persists_to_storage_when_requested tests/integration/test_analysis_api.py::test_extract_endpoint_persisted_result_is_readable_by_storage_get_routes tests/integration/test_api_storage_runtime.py -q -o addopts=
```

Expected: PASS.

- [x] **Step 3: Run Ruff**

Run:

```bash
uv run ruff check src tests
```

Expected: PASS.

- [x] **Step 4: Add closeout note**

At the top of this plan, below the header, add:

```markdown
> **Closeout status:** Completed. Focused unit, focused integration, and Ruff verification passed. This phase intentionally persists only the extracted artifact and lookup metadata; dataset/Turtle orchestration remains a later phase.
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-04-24-financial-report-analysis-db-backed-extract-persistence-and-lookup-slice-implementation-plan.md
git commit -m "docs: close db backed extract persistence plan"
```

## Self-Review

- Spec coverage:
  - Opt-in DB-backed write path: Task 1, Task 3, Task 4.
  - Explicit report identity: Task 1 and Task 3.
  - Reuse existing extract result without a second PDF read: Task 2.
  - Report/document/extraction-run registration: Task 3.
  - Persist extracted artifact and review surface: Task 3.
  - Return stable lookup identifiers: Task 3 and Task 4.
  - Verify existing GET endpoints can read persisted objects: Task 5.
  - Keep dataset/Turtle orchestration out of scope: file responsibilities and Task 6 closeout note.
- Placeholder scan:
  - No placeholder markers or open-ended test instructions remain.
- Type consistency:
  - `AnalysisStorageResult` response fields match `AnalysisExtractStorageResult.to_response_dict()`.
  - `persist_analysis_extract_result()` accepts `AnalysisExtractRequest`, `ApiRuntime`, `document`, `extracted_payload`, and `pipeline_result`, matching the route wiring in Task 4.
  - `build_extracted_artifact_from_result()` reuses existing P5 artifact fields and does not introduce a second artifact shape.
