# DB-Backed Extract To P5/Turtle Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in `/api/v1/analysis/extract` wiring that persists extracted artifacts, optionally builds DB-backed P5 dataset/Turtle outputs, and returns stable lookup ids.

**Architecture:** Keep the route thin. Extend request/response schemas for opt-in build flags, add a DB-backed P5 assembly service that reads persisted artifacts and writes dataset/turtle/review/lineage records, then wire the route to call that service only after extract persistence succeeds.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy SQLite repository, pytest, Ruff.

---

## File Structure

- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
  - Add `build_dataset`, `build_turtle`, `dataset_id`, and `dataset_version` request fields.
  - Add a nested build result response model under `storage`.
  - Validate that build flags require `persist_to_storage=true`.
- Create: `financial-report-analysis/src/financial_report_analysis/p5/db_assembly_service.py`
  - Own DB-backed dataset/turtle build for one persisted extract artifact.
  - Read via `SqlAlchemyP5ArtifactRepository.load_extracted_artifact`.
  - Reuse `assemble_dataset`, `build_turtle_export`, review builders, and `build_dataset_lineage`.
  - Save dataset, turtle export, review surfaces, and lineage through repository methods.
- Modify: `financial-report-analysis/src/financial_report_analysis/api/extract_write_service.py`
  - Add build result dataclasses and `build_p5_outputs_for_persisted_extract(...)` orchestration helper.
  - Keep `persist_analysis_extract_result(...)` unchanged except for reusable identity fields if needed.
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
  - Validate storage when any build flag is set.
  - After persistence, call the build helper and attach build lookup data.
  - Convert build validation errors to 400 and unexpected build failures to 500.
- Test: `financial-report-analysis/tests/unit/test_api_schemas.py`
  - Cover build flag validation.
- Test: `financial-report-analysis/tests/unit/test_db_assembly_service.py`
  - Cover service-level dataset/turtle/review/lineage persistence.
- Test: `financial-report-analysis/tests/unit/test_extract_write_service.py`
  - Cover orchestration helper response shape.
- Test: `financial-report-analysis/tests/integration/test_analysis_api.py`
  - Cover HTTP opt-in build success and validation failures.

---

### Task 1: Schema Gate For Opt-In Build Flags

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Create: `financial-report-analysis/tests/unit/test_api_schemas.py`

- [x] **Step 1: Write failing schema validation tests**

Create `financial-report-analysis/tests/unit/test_api_schemas.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from financial_report_analysis.api.schemas import AnalysisExtractRequest


def test_build_dataset_requires_persist_to_storage() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AnalysisExtractRequest(
            pdf_path="/tmp/report.pdf",
            market="CN",
            build_dataset=True,
        )

    assert "build_dataset requires persist_to_storage=true" in str(exc_info.value)


def test_build_turtle_requires_persist_to_storage() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AnalysisExtractRequest(
            pdf_path="/tmp/report.pdf",
            market="CN",
            build_turtle=True,
        )

    assert "build_turtle requires persist_to_storage=true" in str(exc_info.value)


def test_build_turtle_is_accepted_without_repeating_build_dataset() -> None:
    request = AnalysisExtractRequest(
        pdf_path="/tmp/report.pdf",
        market="CN",
        persist_to_storage=True,
        build_turtle=True,
        issuer_id="CN_601919",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
    )

    assert request.build_dataset is False
    assert request.build_turtle is True
```

- [x] **Step 2: Run the new tests and verify they fail**

Run from `financial-report-analysis/`:

```bash
uv run pytest tests/unit/test_api_schemas.py -q -o addopts=
```

Expected: FAIL because `build_dataset`, `build_turtle`, `dataset_id`, and `dataset_version` are not yet schema fields.

- [x] **Step 3: Extend request and response schemas**

Modify `financial-report-analysis/src/financial_report_analysis/api/schemas.py`:

```python
class AnalysisExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pdf_path: str | None = None
    pdf_url: str | None = None
    market: str | None = None
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    persist_to_storage: bool = False
    build_dataset: bool = False
    build_turtle: bool = False
    dataset_id: str | None = None
    dataset_version: str | None = None
    issuer_id: str | None = None
    stock_code: str | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    report_type: str | None = None
    company_name: str | None = None
    report_language: str | None = None
    source: str = "api"

    @model_validator(mode="after")
    def validate_persistence_identity(self) -> "AnalysisExtractRequest":
        if (self.build_dataset or self.build_turtle) and not self.persist_to_storage:
            field_name = "build_turtle" if self.build_turtle else "build_dataset"
            raise ValueError(f"{field_name} requires persist_to_storage=true")
        if not self.persist_to_storage:
            return self

        missing_fields = [
            field_name
            for field_name in ("issuer_id", "stock_code", "fiscal_year", "report_type")
            if _is_missing_identity_value(getattr(self, field_name))
        ]
        if missing_fields:
            raise ValueError(
                "persist_to_storage requires explicit report identity fields: "
                + ", ".join(missing_fields)
            )
        if self.report_type != "annual":
            raise ValueError(
                "persist_to_storage currently supports report_type='annual' only"
            )
        return self
```

Add the nested response model before `AnalysisStorageResult`:

```python
class AnalysisBuildResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str | None = None
    dataset_version: str | None = None
    turtle_export_id: str | None = None
    dataset_lookup_path: str | None = None
    turtle_export_lookup_path: str | None = None
    source_artifact_ids: tuple[str, ...] = ()
    lineage_record_count: int = 0
    build_warnings: tuple[str, ...] = ()
```

Then add this field to `AnalysisStorageResult`:

```python
    build: AnalysisBuildResult | None = None
```

- [x] **Step 4: Run schema tests and existing persistence schema tests**

Run from `financial-report-analysis/`:

```bash
uv run pytest tests/unit/test_api_schemas.py tests/integration/test_analysis_api.py::test_extract_endpoint_requires_identity_when_persistence_is_requested tests/integration/test_analysis_api.py::test_extract_endpoint_rejects_non_annual_persisted_report_type -q -o addopts=
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/financial_report_analysis/api/schemas.py tests/unit/test_api_schemas.py
git commit -m "feat: add extract build request schema"
```

---

### Task 2: DB-Backed P5/Turtle Assembly Service

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/p5/db_assembly_service.py`
- Create: `financial-report-analysis/tests/unit/test_db_assembly_service.py`

- [x] **Step 1: Write failing service tests**

Create `financial-report-analysis/tests/unit/test_db_assembly_service.py`:

```python
from __future__ import annotations

from pathlib import Path

from financial_report_analysis.api.runtime import build_api_runtime
from financial_report_analysis.p5.db_assembly_service import (
    DbP5AssemblyRequest,
    build_db_p5_outputs_for_artifact,
)
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry


def _artifact(entry: P5ManifestEntry) -> P5ExtractedArtifact:
    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="test",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={"document_id": str(entry.pdf_path), "pdf_path": str(entry.pdf_path)},
        document_metadata={"language": "zh"},
        candidate_facts=(),
        canonical_facts=(
            {
                "fact_id": "fact-revenue",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "numeric_value": 100.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "evidence_bundle_id": "bundle-revenue",
                "extensions": {"period_scope": "fy"},
            },
        ),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={"cash_health_missing_status": {"restricted_cash": "not_surfaced"}},
        created_at="2026-04-24T00:00:00+00:00",
    )


def test_build_db_p5_outputs_for_artifact_persists_dataset_review_and_lineage(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    assert runtime.storage_repository is not None
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=tmp_path / "report.pdf",
        source="test",
    )
    runtime.storage_repository.save_extracted_artifact(_artifact(entry))

    result = build_db_p5_outputs_for_artifact(
        repository=runtime.storage_repository,
        request=DbP5AssemblyRequest(
            artifact_id="CN_601919_2025",
            dataset_id=None,
            dataset_version=None,
            build_turtle=False,
        ),
        now_func=lambda: "2026-04-24T00:00:00+00:00",
    )

    assert result.dataset_id == "single_report_CN_601919_2025_annual_CN_601919_2025"
    assert result.dataset_version == "1.0"
    assert result.turtle_export_id is None
    assert result.source_artifact_ids == ("CN_601919_2025",)
    assert result.lineage_record_count >= 1
    assert result.build_warnings == ()
    dataset = runtime.storage_repository.load_dataset_artifact(result.dataset_id)
    surface = runtime.storage_repository.load_dataset_review_surface(result.dataset_id)
    lineage = runtime.storage_repository.list_lineage_records(dataset_id=result.dataset_id)
    assert dataset.source_artifacts == ("CN_601919_2025",)
    assert surface.dataset_id == result.dataset_id
    assert tuple(record.source_artifact_id for record in lineage) == ("CN_601919_2025",)


def test_build_db_p5_outputs_for_artifact_persists_turtle_export(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    assert runtime.storage_repository is not None
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=tmp_path / "report.pdf",
        source="test",
    )
    runtime.storage_repository.save_extracted_artifact(_artifact(entry))

    result = build_db_p5_outputs_for_artifact(
        repository=runtime.storage_repository,
        request=DbP5AssemblyRequest(
            artifact_id="CN_601919_2025",
            dataset_id="custom_dataset",
            dataset_version="api-test",
            build_turtle=True,
        ),
        now_func=lambda: "2026-04-24T00:00:00+00:00",
    )

    assert result.dataset_id == "custom_dataset"
    assert result.dataset_version == "api-test"
    assert result.turtle_export_id == "custom_dataset"
    turtle = runtime.storage_repository.load_turtle_export("custom_dataset")
    turtle_surface = runtime.storage_repository.load_turtle_export_review_surface(
        "custom_dataset"
    )
    assert turtle.dataset_id == "custom_dataset"
    assert turtle_surface.dataset_id == "custom_dataset"
```

- [x] **Step 2: Run the service tests and verify they fail**

Run from `financial-report-analysis/`:

```bash
uv run pytest tests/unit/test_db_assembly_service.py -q -o addopts=
```

Expected: FAIL because `financial_report_analysis.p5.db_assembly_service` does not exist.

- [x] **Step 3: Implement the DB assembly service**

Create `financial-report-analysis/src/financial_report_analysis/p5/db_assembly_service.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from financial_report_analysis.p5.dataset import assemble_dataset
from financial_report_analysis.p5.lineage import build_dataset_lineage
from financial_report_analysis.p5.review import (
    build_dataset_review_surface,
    build_turtle_export_review_surface,
)
from financial_report_analysis.p5.turtle_export import build_turtle_export
from financial_report_analysis.storage.repositories import SqlAlchemyP5ArtifactRepository


@dataclass(frozen=True, slots=True)
class DbP5AssemblyRequest:
    artifact_id: str
    dataset_id: str | None
    dataset_version: str | None
    build_turtle: bool


@dataclass(frozen=True, slots=True)
class DbP5AssemblyResult:
    dataset_id: str
    dataset_version: str
    turtle_export_id: str | None
    source_artifact_ids: tuple[str, ...]
    lineage_record_count: int
    build_warnings: tuple[str, ...] = ()

    @property
    def dataset_lookup_path(self) -> str:
        return f"/datasets/{self.dataset_id}"

    @property
    def turtle_export_lookup_path(self) -> str | None:
        if self.turtle_export_id is None:
            return None
        return f"/datasets/{self.turtle_export_id}"


def build_db_p5_outputs_for_artifact(
    *,
    repository: SqlAlchemyP5ArtifactRepository,
    request: DbP5AssemblyRequest,
    now_func: Callable[[], str] | None = None,
) -> DbP5AssemblyResult:
    artifact = repository.load_extracted_artifact(request.artifact_id)
    dataset_id = request.dataset_id or _default_single_report_dataset_id(
        artifact_id=artifact.artifact_id,
        issuer_id=artifact.manifest_entry.issuer_id,
        fiscal_year=artifact.manifest_entry.fiscal_year,
        report_type=artifact.manifest_entry.report_type,
    )
    dataset = assemble_dataset(
        dataset_id=dataset_id,
        artifacts=(artifact,),
        now_func=now_func,
    )
    if request.dataset_version is not None:
        dataset = replace(dataset, dataset_version=request.dataset_version)
    repository.save_dataset_artifact(dataset)
    repository.save_dataset_review_surface(
        build_dataset_review_surface(dataset, extracted_artifacts=(artifact,))
    )

    turtle_export_id: str | None = None
    turtle_export = None
    if request.build_turtle:
        turtle_export = build_turtle_export(dataset)
        repository.save_turtle_export(turtle_export)
        repository.save_turtle_export_review_surface(
            build_turtle_export_review_surface(turtle_export, dataset=dataset)
        )
        turtle_export_id = turtle_export.dataset_id

    lineage_record_count = repository.save_lineage_records(
        build_dataset_lineage(
            dataset=dataset,
            extracted_artifacts=(artifact,),
            turtle_export=turtle_export,
        )
    )
    return DbP5AssemblyResult(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        turtle_export_id=turtle_export_id,
        source_artifact_ids=dataset.source_artifacts,
        lineage_record_count=lineage_record_count,
    )


def _default_single_report_dataset_id(
    *,
    issuer_id: str,
    fiscal_year: int,
    report_type: str,
    artifact_id: str,
) -> str:
    return f"single_report_{issuer_id}_{fiscal_year}_{report_type}_{artifact_id}"
```

- [x] **Step 4: Run service tests**

Run from `financial-report-analysis/`:

```bash
uv run pytest tests/unit/test_db_assembly_service.py -q -o addopts=
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/financial_report_analysis/p5/db_assembly_service.py tests/unit/test_db_assembly_service.py
git commit -m "feat: add db backed p5 assembly service"
```

---

### Task 3: Extract Write Orchestration Helper

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/extract_write_service.py`
- Modify: `financial-report-analysis/tests/unit/test_extract_write_service.py`

- [x] **Step 1: Write failing orchestration helper test**

Append to `financial-report-analysis/tests/unit/test_extract_write_service.py`:

```python
def test_build_p5_outputs_for_persisted_extract_returns_response_payload(
    tmp_path: Path,
) -> None:
    from financial_report_analysis.api.extract_write_service import (
        build_p5_outputs_for_persisted_extract,
    )

    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    runtime = build_api_runtime(tmp_path / "storage.db")
    request = AnalysisExtractRequest(
        pdf_path=str(pdf_path),
        market="CN",
        persist_to_storage=True,
        build_turtle=True,
        issuer_id="CN_601919",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
    )
    storage_result = persist_analysis_extract_result(
        runtime=runtime,
        request=request,
        document={"document_id": str(pdf_path), "pdf_path": str(pdf_path)},
        extracted_payload={
            "document_metadata": {},
            "candidate_facts": [
                {
                    "fact_id": "candidate-revenue",
                    "metric_id": "revenue",
                    "metric_label_raw": "Revenue",
                    "statement_type": "income_statement",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "CNY",
                    "raw_value": "100",
                    "numeric_value": 100.0,
                    "raw_unit": "yuan",
                    "normalized_unit": "currency_amount",
                    "precision": 0,
                    "confidence": 0.99,
                    "document_id": str(pdf_path),
                    "block_id": "block-1",
                    "page_index": 0,
                    "evidence_bundle_id": "bundle-1",
                }
            ],
        },
        pipeline_result={
            "canonical_facts": [
                {
                    "fact_id": "canonical-revenue",
                    "metric_id": "revenue",
                    "statement_type": "income_statement",
                    "entity_scope": "consolidated",
                    "numeric_value": 100.0,
                    "currency": "CNY",
                    "normalized_unit": "currency_amount",
                    "evidence_bundle_id": "bundle-1",
                    "extensions": {"period_scope": "fy"},
                }
            ],
            "derived_facts": [],
            "validation_report": {"overall_status": "ok", "issues": []},
            "review_packets": [],
            "quality_gate": "pass",
        },
        now_func=lambda: "2026-04-24T00:00:00+00:00",
    )

    build_result = build_p5_outputs_for_persisted_extract(
        runtime=runtime,
        request=request,
        storage_result=storage_result,
        now_func=lambda: "2026-04-24T00:00:00+00:00",
    )

    assert build_result is not None
    payload = build_result.to_response_dict()
    assert payload["dataset_id"] == "single_report_CN_601919_2025_annual_CN_601919_2025"
    assert payload["turtle_export_id"] == payload["dataset_id"]
    assert payload["dataset_lookup_path"] == f"/datasets/{payload['dataset_id']}"
    assert payload["turtle_export_lookup_path"] is None
    assert payload["source_artifact_ids"] == ("CN_601919_2025",)
    assert payload["lineage_record_count"] >= 1
```

- [x] **Step 2: Run the helper test and verify it fails**

Run from `financial-report-analysis/`:

```bash
uv run pytest tests/unit/test_extract_write_service.py::test_build_p5_outputs_for_persisted_extract_returns_response_payload -q -o addopts=
```

Expected: FAIL because `build_p5_outputs_for_persisted_extract` does not exist.

- [x] **Step 3: Add build result dataclass and helper**

Modify `financial-report-analysis/src/financial_report_analysis/api/extract_write_service.py` imports:

```python
from financial_report_analysis.p5.db_assembly_service import (
    DbP5AssemblyRequest,
    build_db_p5_outputs_for_artifact,
)
```

Add below `AnalysisExtractStorageResult`:

```python
@dataclass(frozen=True, slots=True)
class AnalysisExtractBuildResult:
    dataset_id: str
    dataset_version: str
    turtle_export_id: str | None
    dataset_lookup_path: str
    turtle_export_lookup_path: str | None
    source_artifact_ids: tuple[str, ...]
    lineage_record_count: int
    build_warnings: tuple[str, ...] = ()

    def to_response_dict(self) -> dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "turtle_export_id": self.turtle_export_id,
            "dataset_lookup_path": self.dataset_lookup_path,
            "turtle_export_lookup_path": self.turtle_export_lookup_path,
            "source_artifact_ids": self.source_artifact_ids,
            "lineage_record_count": self.lineage_record_count,
            "build_warnings": self.build_warnings,
        }
```

Add helper after `persist_analysis_extract_result(...)`:

```python
def build_p5_outputs_for_persisted_extract(
    *,
    runtime: ApiRuntime,
    request: AnalysisExtractRequest,
    storage_result: AnalysisExtractStorageResult,
    now_func: Callable[[], str] | None = None,
) -> AnalysisExtractBuildResult | None:
    if not request.build_dataset and not request.build_turtle:
        return None
    if runtime.storage_repository is None:
        raise RuntimeError("storage repository is not configured")

    assembly_result = build_db_p5_outputs_for_artifact(
        repository=runtime.storage_repository,
        request=DbP5AssemblyRequest(
            artifact_id=storage_result.artifact_id,
            dataset_id=_optional_text(request.dataset_id),
            dataset_version=_optional_text(request.dataset_version),
            build_turtle=request.build_turtle,
        ),
        now_func=now_func,
    )
    return AnalysisExtractBuildResult(
        dataset_id=assembly_result.dataset_id,
        dataset_version=assembly_result.dataset_version,
        turtle_export_id=assembly_result.turtle_export_id,
        dataset_lookup_path=assembly_result.dataset_lookup_path,
        turtle_export_lookup_path=assembly_result.turtle_export_lookup_path,
        source_artifact_ids=assembly_result.source_artifact_ids,
        lineage_record_count=assembly_result.lineage_record_count,
        build_warnings=assembly_result.build_warnings,
    )
```

- [x] **Step 4: Run helper and existing write service tests**

Run from `financial-report-analysis/`:

```bash
uv run pytest tests/unit/test_extract_write_service.py tests/unit/test_db_assembly_service.py -q -o addopts=
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/financial_report_analysis/api/extract_write_service.py tests/unit/test_extract_write_service.py
git commit -m "feat: add extract p5 build orchestration helper"
```

---

### Task 4: Wire HTTP Extract Route To Opt-In Build

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`

- [x] **Step 1: Write failing HTTP validation and success tests**

Append to `financial-report-analysis/tests/integration/test_analysis_api.py`:

```python
def test_extract_endpoint_rejects_build_dataset_without_persistence() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": "ignored.pdf",
            "market": "CN",
            "build_dataset": True,
        },
    )

    assert response.status_code == 422
    assert "build_dataset requires persist_to_storage=true" in response.text


def test_extract_endpoint_returns_503_when_build_requested_without_storage(
    monkeypatch,
    tmp_path,
) -> None:
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
            "build_dataset": True,
            "issuer_id": "CN_601919",
            "stock_code": "601919",
            "fiscal_year": 2025,
            "report_type": "annual",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "storage repository is not configured"


def test_extract_endpoint_persists_dataset_when_build_dataset_requested(
    monkeypatch,
    tmp_path,
) -> None:
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
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "CNY",
                    "raw_value": "100",
                    "numeric_value": 100.0,
                    "raw_unit": "yuan",
                    "normalized_unit": "currency_amount",
                    "precision": 0,
                    "confidence": 0.99,
                    "document_id": str(pdf_path),
                    "block_id": "block-1",
                    "page_index": 0,
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
            "build_dataset": True,
            "issuer_id": "CN_601919",
            "stock_code": "601919",
            "fiscal_year": 2025,
            "report_type": "annual",
        },
    )

    assert response.status_code == 200
    storage = response.json()["storage"]
    assert storage["artifact_id"] == "CN_601919_2025"
    assert storage["build"]["dataset_id"] == (
        "single_report_CN_601919_2025_annual_CN_601919_2025"
    )
    assert storage["build"]["turtle_export_id"] is None
    dataset_response = client.get(storage["build"]["dataset_lookup_path"])
    audit_response = client.get(
        f"{storage['build']['dataset_lookup_path']}/audit"
    )
    assert dataset_response.status_code == 200
    assert dataset_response.json()["source_artifacts"] == ["CN_601919_2025"]
    assert audit_response.status_code == 200
    assert audit_response.json()["source_artifact_ids"] == ["CN_601919_2025"]


def test_extract_endpoint_persists_turtle_when_build_turtle_requested(
    monkeypatch,
    tmp_path,
) -> None:
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
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "CNY",
                    "raw_value": "100",
                    "numeric_value": 100.0,
                    "raw_unit": "yuan",
                    "normalized_unit": "currency_amount",
                    "precision": 0,
                    "confidence": 0.99,
                    "document_id": str(pdf_path),
                    "block_id": "block-1",
                    "page_index": 0,
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
            "build_turtle": True,
            "dataset_id": "api_single_report_dataset",
            "dataset_version": "api-test",
            "issuer_id": "CN_601919",
            "stock_code": "601919",
            "fiscal_year": 2025,
            "report_type": "annual",
        },
    )

    assert response.status_code == 200
    build = response.json()["storage"]["build"]
    assert build["dataset_id"] == "api_single_report_dataset"
    assert build["dataset_version"] == "api-test"
    assert build["turtle_export_id"] == "api_single_report_dataset"
    assert build["turtle_export_lookup_path"] is None
    audit_response = client.get("/datasets/api_single_report_dataset/audit")
    assert audit_response.status_code == 200
    assert audit_response.json()["turtle_export_review_surface"] is not None
```

- [x] **Step 2: Run new API tests and verify route wiring failures**

Run from `financial-report-analysis/`:

```bash
uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_rejects_build_dataset_without_persistence tests/integration/test_analysis_api.py::test_extract_endpoint_returns_503_when_build_requested_without_storage tests/integration/test_analysis_api.py::test_extract_endpoint_persists_dataset_when_build_dataset_requested tests/integration/test_analysis_api.py::test_extract_endpoint_persists_turtle_when_build_turtle_requested -q -o addopts=
```

Expected: validation tests may pass after Task 1; success tests FAIL because route does not call build helper.

- [x] **Step 3: Wire route to helper**

Modify imports in `financial-report-analysis/src/financial_report_analysis/api/routes.py`:

```python
from financial_report_analysis.api.extract_write_service import (
    build_p5_outputs_for_persisted_extract,
    persist_analysis_extract_result,
)
```

Replace the `if request.persist_to_storage:` block in `extract_analysis(...)` with:

```python
    if request.persist_to_storage or request.build_dataset or request.build_turtle:
        if (
            runtime.storage_repository is None
            or runtime.historical_ingestion_service is None
        ):
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
            build_result = build_p5_outputs_for_persisted_extract(
                runtime=runtime,
                request=request,
                storage_result=storage_result,
            )
        except P5ArtifactRepositoryError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

        storage_payload = storage_result.to_response_dict()
        if build_result is not None:
            storage_payload["build"] = build_result.to_response_dict()
        analysis_result["storage"] = storage_payload
```

- [x] **Step 4: Run targeted API tests**

Run from `financial-report-analysis/`:

```bash
uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_returns_503_when_persistence_requested_without_storage tests/integration/test_analysis_api.py::test_extract_endpoint_persists_to_storage_when_requested tests/integration/test_analysis_api.py::test_extract_endpoint_persisted_result_is_readable_by_storage_get_routes tests/integration/test_analysis_api.py::test_extract_endpoint_rejects_build_dataset_without_persistence tests/integration/test_analysis_api.py::test_extract_endpoint_returns_503_when_build_requested_without_storage tests/integration/test_analysis_api.py::test_extract_endpoint_persists_dataset_when_build_dataset_requested tests/integration/test_analysis_api.py::test_extract_endpoint_persists_turtle_when_build_turtle_requested -q -o addopts=
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/financial_report_analysis/api/routes.py tests/integration/test_analysis_api.py
git commit -m "feat: wire extract route to db p5 build"
```

---

### Task 5: Final Verification And Plan Closeout

**Files:**
- Modify: `docs/superpowers/plans/2026-04-24-financial-report-analysis-db-backed-extract-to-p5-turtle-orchestration-implementation-plan.md`

- [x] **Step 1: Run the focused unit and integration suite**

Run from `financial-report-analysis/`:

```bash
uv run pytest tests/unit/test_api_schemas.py tests/unit/test_db_assembly_service.py tests/unit/test_extract_write_service.py tests/unit/test_storage_repository.py tests/unit/test_p5_runner.py tests/integration/test_analysis_api.py::test_extract_endpoint_requires_identity_when_persistence_is_requested tests/integration/test_analysis_api.py::test_extract_endpoint_rejects_non_annual_persisted_report_type tests/integration/test_analysis_api.py::test_extract_endpoint_returns_503_when_persistence_requested_without_storage tests/integration/test_analysis_api.py::test_extract_endpoint_persists_to_storage_when_requested tests/integration/test_analysis_api.py::test_extract_endpoint_persisted_result_is_readable_by_storage_get_routes tests/integration/test_analysis_api.py::test_extract_endpoint_rejects_build_dataset_without_persistence tests/integration/test_analysis_api.py::test_extract_endpoint_returns_503_when_build_requested_without_storage tests/integration/test_analysis_api.py::test_extract_endpoint_persists_dataset_when_build_dataset_requested tests/integration/test_analysis_api.py::test_extract_endpoint_persists_turtle_when_build_turtle_requested tests/integration/test_api_storage_runtime.py -q -o addopts=
```

Expected: PASS.

- [x] **Step 2: Run lint**

Run from `financial-report-analysis/`:

```bash
uv run ruff check src tests
```

Expected: `All checks passed!`

- [x] **Step 3: Mark all completed task checkboxes**

Edit this plan file and change every completed `- [ ]` to `- [x]`.

- [x] **Step 4: Commit closeout**

```bash
git add docs/superpowers/plans/2026-04-24-financial-report-analysis-db-backed-extract-to-p5-turtle-orchestration-implementation-plan.md
git commit -m "docs: close db backed extract to p5 turtle plan"
```

---

## Self-Review Notes

- Spec coverage:
  - Opt-in request fields and validation are covered by Task 1.
  - DB-backed assembly service is covered by Task 2.
  - Thin route orchestration is covered by Tasks 3 and 4.
  - Failure behavior for build-without-persistence and missing storage is covered by Tasks 1 and 4.
  - Dataset/turtle readback and audit verification are covered by Task 4.
  - Regression coverage for existing extract persistence and JSON runner is covered by Task 5.
- Placeholder scan:
  - The plan contains concrete tests, implementation snippets, commands, and expected outcomes for every task.
- Type consistency:
  - `AnalysisExtractBuildResult.to_response_dict()` produces the same keys as `AnalysisBuildResult`.
  - `build_turtle=True` is accepted without `build_dataset=True`; the service builds dataset automatically.
  - `turtle_export_id` uses the existing repository contract where turtle exports are keyed by `dataset_id`.
  - `turtle_export_lookup_path` intentionally returns `None` until a real turtle export read endpoint exists.
- Review follow-up:
  - Task 2 added atomic repository bundle persistence after review.
