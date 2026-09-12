# Financial Report Analysis 3-5Y Persisted Dataset Availability View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only 3-5Y persisted dataset availability view that returns facts, missing states, and lineage from already persisted financial-report artifacts.

**Architecture:** Add a focused P5 availability service that reads existing storage coverage and extracted artifacts, then expose it through a read-only FastAPI route. Real PDFs for `01810`, `09987`, and `601919` remain seed/smoke inputs only; the availability query path must never trigger PDF extraction, recompute, dataset build, Turtle export build, or writes.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy-backed `SqlAlchemyP5ArtifactRepository`, pytest.

---

## Source Spec

- `docs/superpowers/specs/active/2026-04-24-financial-report-analysis-3-5y-persisted-dataset-availability-view-design.md`
- `docs/superpowers/specs/active/2026-04-22-financial-report-analysis-unified-roadmap.md`
- `docs/architecture-analysis/2026-04-24-http-to-db-to-turtle-workflow-gap-analysis.md`

## File Structure

- Create `financial-report-analysis/src/financial_report_analysis/p5/availability.py`
  - Owns dataclasses and read-only assembly logic for multi-year availability.
  - Depends on repository read methods only.
  - Does not depend on PDF ingestion, semantic fallback, P5 runner, recompute, or Turtle export.

- Modify `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
  - Adds Pydantic response models for the availability endpoint.

- Modify `financial-report-analysis/src/financial_report_analysis/api/routes.py`
  - Adds `GET /issuers/{issuer_id}/dataset-availability`.
  - Translates service output to API response.

- Modify `financial-report-analysis/src/financial_report_analysis/p5/__init__.py`
  - Exposes availability service models only if this package already exports P5 public API from this file.

- Create `financial-report-analysis/tests/unit/test_p5_availability.py`
  - Unit-tests service behavior with a fake read-only repository.

- Modify `financial-report-analysis/tests/integration/test_api_storage_runtime.py`
  - Adds API integration coverage using SQLite-backed seeded data.

- Create `financial-report-analysis/tests/integration/test_p5_availability_real_pdf_seed_contract.py`
  - Adds a cheap fixture-path/contract test proving `01810`, `09987`, and `601919` seed PDFs are discoverable.
  - Does not run extraction by default.

- Modify `docs/AGENTS_HANDOFF_PROMPT.md` only if this file exists and currently tracks next-step guidance.
  - Mention that availability closeout should use seeded DB tests first, with real PDF seed smoke only when requested.

---

### Task 1: Availability Domain Models And Service

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/p5/availability.py`
- Test: `financial-report-analysis/tests/unit/test_p5_availability.py`

- [x] **Step 1: Write failing unit tests**

Create `financial-report-analysis/tests/unit/test_p5_availability.py` with these tests:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from financial_report_analysis.p5.availability import (
    MultiYearAvailabilityRequest,
    build_multi_year_availability_view,
)
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.storage.artifacts import ReportCoverage


@dataclass
class FakeReadRepository:
    coverages: dict[tuple[str, int, str], ReportCoverage]
    artifacts: dict[str, P5ExtractedArtifact]
    loaded_artifact_ids: list[str]

    def get_report_coverage(
        self,
        issuer_id: str,
        fiscal_year: int,
        report_type: str,
    ) -> ReportCoverage:
        return self.coverages.get(
            (issuer_id, fiscal_year, report_type),
            ReportCoverage(
                issuer_id=issuer_id,
                fiscal_year=fiscal_year,
                report_type=report_type,
                report_registered=False,
            ),
        )

    def load_extracted_artifact(self, artifact_id: str) -> P5ExtractedArtifact:
        self.loaded_artifact_ids.append(artifact_id)
        return self.artifacts[artifact_id]


def _entry(*, fiscal_year: int) -> P5ManifestEntry:
    return P5ManifestEntry(
        issuer_id="HK_09987",
        market="HK",
        stock_code="09987",
        fiscal_year=fiscal_year,
        report_type="annual",
        pdf_path=Path(f"09987_{fiscal_year}.pdf"),
        source="test",
        company_name="Yum China",
        report_language="en",
    )


def _artifact(
    *,
    fiscal_year: int,
    metric_id: str = "revenue",
    numeric_value: float = 100.0,
    missing_status: dict[str, dict[str, str]] | None = None,
) -> P5ExtractedArtifact:
    entry = _entry(fiscal_year=fiscal_year)
    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="test-pipeline",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={"document_id": str(entry.pdf_path), "pdf_path": str(entry.pdf_path)},
        document_metadata={"language": "en"},
        candidate_facts=(),
        canonical_facts=(
            {
                "fact_id": f"fact-{metric_id}-{fiscal_year}",
                "metric_id": metric_id,
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "numeric_value": numeric_value,
                "currency": "USD",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": f"bundle-{metric_id}-{fiscal_year}",
                "extensions": {"period_scope": "fy"},
            },
        ),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status=missing_status or {},
        created_at="2026-04-24T00:00:00+00:00",
    )


def _coverage(
    *,
    issuer_id: str = "HK_09987",
    fiscal_year: int,
    artifact_ids: tuple[str, ...],
) -> ReportCoverage:
    return ReportCoverage(
        issuer_id=issuer_id,
        fiscal_year=fiscal_year,
        report_type="annual",
        report_registered=True,
        report_id=fiscal_year,
        pdf_path=f"/reports/{issuer_id}/{fiscal_year}.pdf",
        extracted_artifact_ids=artifact_ids,
        extracted_artifact_available=bool(artifact_ids),
    )


def test_availability_returns_present_and_missing_years() -> None:
    artifact_2024 = _artifact(fiscal_year=2024)
    repository = FakeReadRepository(
        coverages={
            ("HK_09987", 2023, "annual"): _coverage(
                fiscal_year=2023,
                artifact_ids=(),
            ),
            ("HK_09987", 2024, "annual"): _coverage(
                fiscal_year=2024,
                artifact_ids=("HK_09987_2024",),
            ),
        },
        artifacts={"HK_09987_2024": artifact_2024},
        loaded_artifact_ids=[],
    )

    view = build_multi_year_availability_view(
        repository=repository,
        request=MultiYearAvailabilityRequest(
            issuer_id="HK_09987",
            start_year=2022,
            end_year=2024,
            metric_profile="turtle_core",
            required_metric_ids=("revenue", "cash"),
        ),
    )

    assert view.issuer_id == "HK_09987"
    assert view.start_year == 2022
    assert view.end_year == 2024
    assert [year.fiscal_year for year in view.years] == [2022, 2023, 2024]
    assert [year.report_status for year in view.years] == [
        "missing_report",
        "covered",
        "covered",
    ]
    assert [year.artifact_status for year in view.years] == [
        "missing_report",
        "missing_extracted_artifact",
        "covered",
    ]
    year_2024 = view.years[2]
    assert {metric.metric_id: metric.status for metric in year_2024.metrics} == {
        "cash": "missing_metric",
        "revenue": "present",
    }
    revenue = next(metric for metric in year_2024.metrics if metric.metric_id == "revenue")
    assert revenue.value == 100.0
    assert revenue.source_artifact_id == "HK_09987_2024"
    assert revenue.source_fact_id == "fact-revenue-2024"
    assert revenue.evidence_bundle_id == "bundle-revenue-2024"
    assert view.coverage_summary["year_count"] == 3
    assert view.coverage_summary["covered_year_count"] == 1
    assert view.coverage_summary["missing_report_count"] == 1
    assert view.coverage_summary["missing_extracted_artifact_count"] == 1
    assert view.coverage_summary["present_metric_count"] == 1
    assert view.coverage_summary["missing_metric_count"] == 1
    assert repository.loaded_artifact_ids == ["HK_09987_2024"]


def test_availability_uses_missing_status_from_artifact() -> None:
    artifact = _artifact(
        fiscal_year=2025,
        missing_status={"debt_missing_status": {"st_borr": "out_of_scope"}},
    )
    repository = FakeReadRepository(
        coverages={
            ("HK_09987", 2025, "annual"): _coverage(
                fiscal_year=2025,
                artifact_ids=("HK_09987_2025",),
            )
        },
        artifacts={"HK_09987_2025": artifact},
        loaded_artifact_ids=[],
    )

    view = build_multi_year_availability_view(
        repository=repository,
        request=MultiYearAvailabilityRequest(
            issuer_id="HK_09987",
            start_year=2025,
            end_year=2025,
            metric_profile="turtle_core",
            required_metric_ids=("revenue", "st_borr"),
        ),
    )

    statuses = {
        metric.metric_id: metric.status
        for metric in view.years[0].metrics
    }
    assert statuses == {"revenue": "present", "st_borr": "out_of_scope"}


def test_availability_rejects_invalid_ranges() -> None:
    with pytest.raises(ValueError, match="start_year must be <= end_year"):
        MultiYearAvailabilityRequest(
            issuer_id="HK_09987",
            start_year=2025,
            end_year=2024,
            metric_profile="turtle_core",
            required_metric_ids=("revenue",),
        )
```

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_p5_availability.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'financial_report_analysis.p5.availability'`.

- [x] **Step 3: Implement service and dataclasses**

Create `financial-report-analysis/src/financial_report_analysis/p5/availability.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from financial_report_analysis.p5.models import P5ExtractedArtifact
from financial_report_analysis.storage.artifacts import ReportCoverage

YearAvailabilityStatus = Literal[
    "covered",
    "missing_report",
    "missing_extracted_artifact",
    "unknown",
]
MetricAvailabilityStatus = Literal[
    "present",
    "missing_metric",
    "out_of_scope",
    "unknown",
]

_MISSING_STATUS_GROUPS = (
    "working_capital_missing_status",
    "debt_missing_status",
    "asset_missing_status",
    "cash_health_missing_status",
)


class AvailabilityReadRepository(Protocol):
    def get_report_coverage(
        self,
        issuer_id: str,
        fiscal_year: int,
        report_type: str,
    ) -> ReportCoverage: ...

    def load_extracted_artifact(self, artifact_id: str) -> P5ExtractedArtifact: ...


@dataclass(frozen=True, slots=True)
class MultiYearAvailabilityRequest:
    issuer_id: str
    start_year: int
    end_year: int
    metric_profile: str
    required_metric_ids: tuple[str, ...]
    report_type: str = "annual"

    def __post_init__(self) -> None:
        if self.start_year > self.end_year:
            raise ValueError("start_year must be <= end_year")
        if self.report_type != "annual":
            raise ValueError("availability view currently supports annual reports only")
        if not self.issuer_id.strip():
            raise ValueError("issuer_id is required")
        if not self.metric_profile.strip():
            raise ValueError("metric_profile is required")


@dataclass(frozen=True, slots=True)
class AvailabilityMetric:
    metric_id: str
    status: MetricAvailabilityStatus
    value: int | float | None
    currency: str | None
    unit: str | None
    quality_status: str | None
    source_artifact_id: str | None
    source_fact_id: str | None
    evidence_bundle_id: str | None


@dataclass(frozen=True, slots=True)
class AvailabilityYear:
    fiscal_year: int
    report_status: YearAvailabilityStatus
    artifact_status: YearAvailabilityStatus
    report_id: int | None
    pdf_path: str | None
    source_artifact_ids: tuple[str, ...]
    metrics: tuple[AvailabilityMetric, ...]


@dataclass(frozen=True, slots=True)
class MultiYearAvailabilityView:
    issuer_id: str
    report_type: str
    start_year: int
    end_year: int
    metric_profile: str
    years: tuple[AvailabilityYear, ...]
    coverage_summary: dict[str, int]
    recommended_next_actions: tuple[str, ...]


def build_multi_year_availability_view(
    *,
    repository: AvailabilityReadRepository,
    request: MultiYearAvailabilityRequest,
) -> MultiYearAvailabilityView:
    years = tuple(
        _availability_year(
            repository=repository,
            request=request,
            fiscal_year=fiscal_year,
        )
        for fiscal_year in range(request.start_year, request.end_year + 1)
    )
    return MultiYearAvailabilityView(
        issuer_id=request.issuer_id,
        report_type=request.report_type,
        start_year=request.start_year,
        end_year=request.end_year,
        metric_profile=request.metric_profile,
        years=years,
        coverage_summary=_coverage_summary(years),
        recommended_next_actions=_recommended_next_actions(years),
    )


def _availability_year(
    *,
    repository: AvailabilityReadRepository,
    request: MultiYearAvailabilityRequest,
    fiscal_year: int,
) -> AvailabilityYear:
    coverage = repository.get_report_coverage(
        request.issuer_id,
        fiscal_year,
        request.report_type,
    )
    if not coverage.report_registered:
        return AvailabilityYear(
            fiscal_year=fiscal_year,
            report_status="missing_report",
            artifact_status="missing_report",
            report_id=None,
            pdf_path=None,
            source_artifact_ids=(),
            metrics=(),
        )
    if not coverage.extracted_artifact_ids:
        return AvailabilityYear(
            fiscal_year=fiscal_year,
            report_status="covered",
            artifact_status="missing_extracted_artifact",
            report_id=coverage.report_id,
            pdf_path=coverage.pdf_path,
            source_artifact_ids=(),
            metrics=(),
        )

    artifacts = tuple(
        repository.load_extracted_artifact(artifact_id)
        for artifact_id in coverage.extracted_artifact_ids
    )
    metrics = _availability_metrics(
        artifacts=artifacts,
        required_metric_ids=request.required_metric_ids,
    )
    return AvailabilityYear(
        fiscal_year=fiscal_year,
        report_status="covered",
        artifact_status="covered",
        report_id=coverage.report_id,
        pdf_path=coverage.pdf_path,
        source_artifact_ids=coverage.extracted_artifact_ids,
        metrics=metrics,
    )


def _availability_metrics(
    *,
    artifacts: tuple[P5ExtractedArtifact, ...],
    required_metric_ids: tuple[str, ...],
) -> tuple[AvailabilityMetric, ...]:
    present = _present_metrics(artifacts)
    missing_status = _artifact_missing_status(artifacts)
    metric_ids = sorted(set(required_metric_ids) | set(present) | set(missing_status))
    metrics: list[AvailabilityMetric] = []
    for metric_id in metric_ids:
        present_metric = present.get(metric_id)
        if present_metric is not None:
            metrics.append(present_metric)
            continue
        status = missing_status.get(metric_id, "missing_metric")
        if status not in {"out_of_scope", "unknown"}:
            status = "missing_metric"
        metrics.append(
            AvailabilityMetric(
                metric_id=metric_id,
                status=status,
                value=None,
                currency=None,
                unit=None,
                quality_status=None,
                source_artifact_id=None,
                source_fact_id=None,
                evidence_bundle_id=None,
            )
        )
    return tuple(metrics)


def _present_metrics(
    artifacts: tuple[P5ExtractedArtifact, ...],
) -> dict[str, AvailabilityMetric]:
    metrics: dict[str, AvailabilityMetric] = {}
    for artifact in artifacts:
        for fact in artifact.canonical_facts:
            metric_id = _text(fact.get("metric_id"))
            if metric_id is None or metric_id in metrics:
                continue
            metrics[metric_id] = AvailabilityMetric(
                metric_id=metric_id,
                status="present",
                value=_numeric(fact.get("numeric_value")),
                currency=_text(fact.get("currency")),
                unit=_text(
                    fact.get("normalized_unit")
                    if fact.get("normalized_unit") is not None
                    else fact.get("raw_unit")
                ),
                quality_status=_text(fact.get("quality_status")),
                source_artifact_id=artifact.artifact_id,
                source_fact_id=_text(fact.get("fact_id")),
                evidence_bundle_id=_text(fact.get("evidence_bundle_id")),
            )
    return metrics


def _artifact_missing_status(
    artifacts: tuple[P5ExtractedArtifact, ...],
) -> dict[str, MetricAvailabilityStatus]:
    statuses: dict[str, MetricAvailabilityStatus] = {}
    for artifact in artifacts:
        for group_name in _MISSING_STATUS_GROUPS:
            group = artifact.missing_status.get(group_name, {})
            for metric_id, status in group.items():
                if metric_id in statuses:
                    continue
                statuses[metric_id] = "out_of_scope" if status == "out_of_scope" else "unknown"
    return statuses


def _coverage_summary(years: tuple[AvailabilityYear, ...]) -> dict[str, int]:
    present_metric_count = sum(
        1
        for year in years
        for metric in year.metrics
        if metric.status == "present"
    )
    missing_metric_count = sum(
        1
        for year in years
        for metric in year.metrics
        if metric.status == "missing_metric"
    )
    return {
        "year_count": len(years),
        "covered_year_count": sum(1 for year in years if year.artifact_status == "covered"),
        "missing_report_count": sum(
            1 for year in years if year.report_status == "missing_report"
        ),
        "missing_extracted_artifact_count": sum(
            1 for year in years if year.artifact_status == "missing_extracted_artifact"
        ),
        "present_metric_count": present_metric_count,
        "missing_metric_count": missing_metric_count,
    }


def _recommended_next_actions(
    years: tuple[AvailabilityYear, ...],
) -> tuple[str, ...]:
    actions: list[str] = []
    if any(year.report_status == "missing_report" for year in years):
        actions.append("register_missing_reports")
    if any(year.artifact_status == "missing_extracted_artifact" for year in years):
        actions.append("extract_missing_artifacts")
    if any(
        metric.status == "missing_metric"
        for year in years
        for metric in year.metrics
    ):
        actions.append("review_missing_metrics")
    return tuple(actions)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _numeric(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None
```

- [x] **Step 4: Run unit tests**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_p5_availability.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add financial-report-analysis/src/financial_report_analysis/p5/availability.py financial-report-analysis/tests/unit/test_p5_availability.py
git commit -m "feat: add multi-year availability service"
```

---

### Task 2: API Schema And Read-Only Route

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Test: `financial-report-analysis/tests/integration/test_api_storage_runtime.py`

- [x] **Step 1: Add failing API integration test**

Append this test to `financial-report-analysis/tests/integration/test_api_storage_runtime.py`:

```python
def test_dataset_availability_route_returns_read_only_multi_year_view(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(storage_db_path=tmp_path / "runtime.db"))
    _seed_runtime(client, tmp_path)

    response = client.get(
        "/issuers/CN_601919/dataset-availability",
        params={
            "start_year": 2024,
            "end_year": 2025,
            "profile": "turtle_core",
            "required_metric_id": ["revenue", "cash"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["issuer_id"] == "CN_601919"
    assert payload["start_year"] == 2024
    assert payload["end_year"] == 2025
    assert payload["metric_profile"] == "turtle_core"
    assert [year["fiscal_year"] for year in payload["years"]] == [2024, 2025]
    assert [year["artifact_status"] for year in payload["years"]] == [
        "missing_extracted_artifact",
        "covered",
    ]
    year_2025 = payload["years"][1]
    assert year_2025["source_artifact_ids"] == ["CN_601919_2025"]
    assert {metric["metric_id"]: metric["status"] for metric in year_2025["metrics"]} == {
        "cash": "missing_metric",
        "revenue": "present",
    }
    revenue = next(
        metric for metric in year_2025["metrics"] if metric["metric_id"] == "revenue"
    )
    assert revenue["source_artifact_id"] == "CN_601919_2025"
    assert revenue["source_fact_id"] == "canonical-CN_601919_2025"
    assert payload["coverage_summary"]["covered_year_count"] == 1
    assert payload["coverage_summary"]["missing_extracted_artifact_count"] == 1
    assert "extract_missing_artifacts" in payload["recommended_next_actions"]
```

Append this validation test to the same file:

```python
def test_dataset_availability_route_rejects_invalid_year_range(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(storage_db_path=tmp_path / "runtime.db"))

    response = client.get(
        "/issuers/CN_601919/dataset-availability",
        params={
            "start_year": 2025,
            "end_year": 2024,
            "profile": "turtle_core",
            "required_metric_id": ["revenue"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "start_year must be <= end_year"
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/integration/test_api_storage_runtime.py::test_dataset_availability_route_returns_read_only_multi_year_view tests/integration/test_api_storage_runtime.py::test_dataset_availability_route_rejects_invalid_year_range -q
```

Expected: FAIL with 404 because route does not exist.

- [x] **Step 3: Add Pydantic response models**

In `financial-report-analysis/src/financial_report_analysis/api/schemas.py`, add these models after `DatasetRowResponse`:

```python
class AvailabilityMetricResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    status: str
    value: int | float | None = None
    currency: str | None = None
    unit: str | None = None
    quality_status: str | None = None
    source_artifact_id: str | None = None
    source_fact_id: str | None = None
    evidence_bundle_id: str | None = None


class AvailabilityYearResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fiscal_year: int
    report_status: str
    artifact_status: str
    report_id: int | None = None
    pdf_path: str | None = None
    source_artifact_ids: tuple[str, ...] = ()
    metrics: list[AvailabilityMetricResponse] = []


class MultiYearAvailabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issuer_id: str
    report_type: str
    start_year: int
    end_year: int
    metric_profile: str
    years: list[AvailabilityYearResponse]
    coverage_summary: dict[str, int]
    recommended_next_actions: tuple[str, ...] = ()
```

- [x] **Step 4: Add route implementation**

In `financial-report-analysis/src/financial_report_analysis/api/routes.py`, update imports from schemas:

```python
from financial_report_analysis.api.schemas import (
    AnalysisExtractRequest,
    AnalysisExtractResponse,
    AvailabilityMetricResponse,
    AvailabilityYearResponse,
    DatasetArtifactResponse,
    DatasetAuditResponse,
    DatasetReviewSurfaceResponse,
    DatasetRowResponse,
    ExtractedArtifactResponse,
    ExtractedReviewSurfaceResponse,
    HealthResponse,
    IssuerReportsResponse,
    ManifestEntryResponse,
    MultiYearAvailabilityResponse,
    RecomputeDiffSummaryResponse,
    RecomputeResultResponse,
    ReportCoverageResponse,
    SourceArtifactAuditResponse,
    TurtleExportReviewSurfaceResponse,
)
```

Add import for service:

```python
from financial_report_analysis.p5.availability import (
    MultiYearAvailabilityRequest,
    MultiYearAvailabilityView,
    build_multi_year_availability_view,
)
```

Add this route after `get_report_coverage()`:

```python
@router.get(
    "/issuers/{issuer_id}/dataset-availability",
    response_model=MultiYearAvailabilityResponse,
)
def get_dataset_availability(
    issuer_id: str,
    start_year: int,
    end_year: int,
    profile: str,
    request: Request,
    required_metric_id: list[str] | None = None,
    report_type: str = "annual",
) -> MultiYearAvailabilityResponse:
    repository = _require_storage_repository(request)
    try:
        availability = build_multi_year_availability_view(
            repository=repository,
            request=MultiYearAvailabilityRequest(
                issuer_id=issuer_id,
                start_year=start_year,
                end_year=end_year,
                metric_profile=profile,
                required_metric_ids=tuple(required_metric_id or ()),
                report_type=report_type,
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _availability_to_response(availability)
```

Add this helper near existing response conversion helpers:

```python
def _availability_to_response(
    availability: MultiYearAvailabilityView,
) -> MultiYearAvailabilityResponse:
    return MultiYearAvailabilityResponse(
        issuer_id=availability.issuer_id,
        report_type=availability.report_type,
        start_year=availability.start_year,
        end_year=availability.end_year,
        metric_profile=availability.metric_profile,
        years=[
            AvailabilityYearResponse(
                fiscal_year=year.fiscal_year,
                report_status=year.report_status,
                artifact_status=year.artifact_status,
                report_id=year.report_id,
                pdf_path=year.pdf_path,
                source_artifact_ids=year.source_artifact_ids,
                metrics=[
                    AvailabilityMetricResponse(
                        metric_id=metric.metric_id,
                        status=metric.status,
                        value=metric.value,
                        currency=metric.currency,
                        unit=metric.unit,
                        quality_status=metric.quality_status,
                        source_artifact_id=metric.source_artifact_id,
                        source_fact_id=metric.source_fact_id,
                        evidence_bundle_id=metric.evidence_bundle_id,
                    )
                    for metric in year.metrics
                ],
            )
            for year in availability.years
        ],
        coverage_summary=availability.coverage_summary,
        recommended_next_actions=availability.recommended_next_actions,
    )
```

- [x] **Step 5: Run API tests**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/integration/test_api_storage_runtime.py::test_dataset_availability_route_returns_read_only_multi_year_view tests/integration/test_api_storage_runtime.py::test_dataset_availability_route_rejects_invalid_year_range -q
```

Expected: PASS.

- [x] **Step 6: Commit**

```powershell
git add financial-report-analysis/src/financial_report_analysis/api/schemas.py financial-report-analysis/src/financial_report_analysis/api/routes.py financial-report-analysis/tests/integration/test_api_storage_runtime.py
git commit -m "feat: expose persisted dataset availability view"
```

---

### Task 3: Read-Only Guardrails And Public Export Check

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/__init__.py`
- Test: `financial-report-analysis/tests/unit/test_public_exports.py`
- Test: `financial-report-analysis/tests/unit/test_p5_availability.py`

- [x] **Step 1: Add fake repository guardrail test**

Append this test to `financial-report-analysis/tests/unit/test_p5_availability.py`:

```python
def test_availability_service_does_not_require_write_build_or_extract_methods() -> None:
    artifact = _artifact(fiscal_year=2024)
    repository = FakeReadRepository(
        coverages={
            ("HK_09987", 2024, "annual"): _coverage(
                fiscal_year=2024,
                artifact_ids=("HK_09987_2024",),
            )
        },
        artifacts={"HK_09987_2024": artifact},
        loaded_artifact_ids=[],
    )

    view = build_multi_year_availability_view(
        repository=repository,
        request=MultiYearAvailabilityRequest(
            issuer_id="HK_09987",
            start_year=2024,
            end_year=2024,
            metric_profile="turtle_core",
            required_metric_ids=("revenue",),
        ),
    )

    assert view.coverage_summary["covered_year_count"] == 1
    assert repository.loaded_artifact_ids == ["HK_09987_2024"]
```

This test intentionally uses a fake repository with no save/build/extract methods. It proves the service only depends on read methods.

- [x] **Step 2: Add public export test**

If `financial-report-analysis/tests/unit/test_public_exports.py` already imports P5 symbols, add:

```python
def test_p5_availability_public_exports() -> None:
    from financial_report_analysis.p5.availability import (
        MultiYearAvailabilityRequest,
        build_multi_year_availability_view,
    )

    assert MultiYearAvailabilityRequest.__name__ == "MultiYearAvailabilityRequest"
    assert build_multi_year_availability_view.__name__ == "build_multi_year_availability_view"
```

- [x] **Step 3: Export symbols if project pattern requires it**

If `financial-report-analysis/src/financial_report_analysis/p5/__init__.py` already exports P5 classes/functions, add:

```python
from financial_report_analysis.p5.availability import (
    AvailabilityMetric,
    AvailabilityYear,
    MultiYearAvailabilityRequest,
    MultiYearAvailabilityView,
    build_multi_year_availability_view,
)
```

Also add these names to `__all__` if `__all__` exists in that file:

```python
    "AvailabilityMetric",
    "AvailabilityYear",
    "MultiYearAvailabilityRequest",
    "MultiYearAvailabilityView",
    "build_multi_year_availability_view",
```

If `p5/__init__.py` is intentionally empty and the project does not use package-root exports for P5, do not modify it; the direct module import test above is sufficient.

- [x] **Step 4: Run tests**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_p5_availability.py tests/unit/test_public_exports.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add financial-report-analysis/src/financial_report_analysis/p5/__init__.py financial-report-analysis/tests/unit/test_p5_availability.py financial-report-analysis/tests/unit/test_public_exports.py
git commit -m "test: lock availability read-only contract"
```

If `p5/__init__.py` was not changed, omit it from `git add`.

---

### Task 4: Real PDF Seed Contract For 01810, 09987, 601919

**Files:**
- Create: `financial-report-analysis/tests/integration/test_p5_availability_real_pdf_seed_contract.py`
- Optionally create: `financial-report-analysis/scripts/seed-availability-anchor-pdfs.ps1`

- [x] **Step 1: Add fixture path contract test**

Create `financial-report-analysis/tests/integration/test_p5_availability_real_pdf_seed_contract.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]

ANCHOR_PDF_GLOBS = {
    "HK_01810": "report/downloads/hk_stocks/01810/annual/*annual_en.pdf",
    "HK_09987": "report/downloads/hk_stocks/09987/annual/*annual_en.pdf",
    "CN_601919": "report/downloads/cn_stocks/601919/annual/*年度报告.pdf",
}


@pytest.mark.integration
def test_availability_anchor_pdf_fixtures_exist() -> None:
    missing: list[str] = []
    discovered: dict[str, list[Path]] = {}
    for issuer_id, pattern in ANCHOR_PDF_GLOBS.items():
        matches = sorted(REPO_ROOT.glob(pattern))
        discovered[issuer_id] = matches
        if not matches:
            missing.append(f"{issuer_id}: {pattern}")

    assert not missing, "missing anchor PDFs: " + ", ".join(missing)
    assert any(path.name.startswith("2024") for path in discovered["HK_01810"])
    assert any(path.name.startswith("2025") for path in discovered["HK_09987"])
    assert any(path.name.startswith("2024") for path in discovered["CN_601919"])
```

This test is intentionally cheap. It proves the seed inputs exist without extracting PDFs.

- [x] **Step 2: Run fixture contract test**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/integration/test_p5_availability_real_pdf_seed_contract.py -q
```

Expected: PASS.

- [x] **Step 3: Add optional seed script only if a similar script pattern exists**

If `financial-report-analysis/scripts/` already contains PowerShell utility scripts, create `financial-report-analysis/scripts/seed-availability-anchor-pdfs.ps1` with this content:

```powershell
param(
    [string]$StorageDbPath = "data/availability_anchor_seed.db"
)

$ErrorActionPreference = "Stop"

Write-Host "Seed anchor PDFs into storage DB: $StorageDbPath"
Write-Host "Anchors:"
Write-Host "  HK 01810 annual PDFs under report/downloads/hk_stocks/01810/annual"
Write-Host "  HK 09987 annual PDFs under report/downloads/hk_stocks/09987/annual"
Write-Host "  CN 601919 annual PDFs under report/downloads/cn_stocks/601919/annual"
Write-Host ""
Write-Host "This script is a documented entry point only. Use targeted API extract calls with persist_to_storage=true for selected anchor years."
Write-Host "Do not run this as part of default closeout."
```

If there is no PowerShell script pattern in the project, skip this optional script and keep the fixture-path test only.

- [x] **Step 4: Commit**

```powershell
git add financial-report-analysis/tests/integration/test_p5_availability_real_pdf_seed_contract.py
git commit -m "test: add availability anchor pdf seed contract"
```

If the optional script was created, include it in the same commit.

---

### Task 5: Focused Regression Suite And Documentation Closeout

**Files:**
- Modify: `docs/superpowers/specs/active/2026-04-24-financial-report-analysis-3-5y-persisted-dataset-availability-view-design.md`
- Modify: `docs/superpowers/specs/active/2026-04-22-financial-report-analysis-unified-roadmap.md` only if implementation names differ from the spec.
- Modify: `docs/architecture-analysis/2026-04-24-http-to-db-to-turtle-workflow-gap-analysis.md` only if implementation names differ from the spec.

- [x] **Step 1: Run targeted tests**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_p5_availability.py tests/unit/test_public_exports.py tests/integration/test_api_storage_runtime.py::test_dataset_availability_route_returns_read_only_multi_year_view tests/integration/test_api_storage_runtime.py::test_dataset_availability_route_rejects_invalid_year_range tests/integration/test_p5_availability_real_pdf_seed_contract.py -q
```

Expected: PASS.

- [x] **Step 2: Run adjacent storage/API tests**

Run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_db_assembly_service.py tests/unit/test_extract_write_service.py tests/integration/test_api_storage_runtime.py -q
```

Expected: PASS.

- [x] **Step 3: Run lint/format check if configured**

Run:

```powershell
cd financial-report-analysis
uv run ruff check src tests
```

Expected: PASS.

- [x] **Step 4: Document closeout evidence**

Append a short implementation note to the active spec under a new section `## 14. Implementation Closeout Notes`:

```markdown
## 14. Implementation Closeout Notes

Implementation should be considered complete only when:

- `MultiYearDatasetAvailabilityService` or equivalent read-only service exists.
- `GET /issuers/{issuer_id}/dataset-availability` returns persisted facts, missing states, and lineage.
- Tests prove missing report, missing artifact, present metric, and missing metric states.
- Tests prove the availability path does not trigger extract, recompute, dataset build, or Turtle build.
- Anchor seed fixture paths for `01810`, `09987`, and `601919` are checked by a cheap integration test.
```

- [x] **Step 5: Commit docs closeout**

```powershell
git add docs/superpowers/specs/active/2026-04-24-financial-report-analysis-3-5y-persisted-dataset-availability-view-design.md docs/superpowers/specs/active/2026-04-22-financial-report-analysis-unified-roadmap.md docs/architecture-analysis/2026-04-24-http-to-db-to-turtle-workflow-gap-analysis.md
git commit -m "docs: close availability view implementation plan"
```

Only include roadmap/gap docs if they changed during implementation.

---

## Verification Before Completion

Before claiming the plan is complete, run:

```powershell
cd financial-report-analysis
uv run pytest tests/unit/test_p5_availability.py tests/unit/test_public_exports.py tests/integration/test_api_storage_runtime.py tests/integration/test_p5_availability_real_pdf_seed_contract.py -q
uv run ruff check src tests
```

Expected:

- All selected tests pass.
- Ruff passes.
- No full real-PDF matrix is required for default closeout.
- No Ollama-backed tests are required for this plan.

## Self-Review

- Spec coverage: tasks cover service boundary, read-only API, status model, persisted-data-only query, 01810/09987/601919 seed fixtures, and focused verification.
- Placeholder scan: no `TBD`, `TODO`, or open-ended implementation steps are present.
- Type consistency: `MultiYearAvailabilityRequest`, `AvailabilityMetric`, `AvailabilityYear`, and `MultiYearAvailabilityView` are defined in Task 1 and reused consistently in later tasks.
- Scope check: plan does not implement PDF extraction, recompute, Turtle build, async workflow, approval workflow, or investment strategy orchestration.
