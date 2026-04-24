from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from financial_report_analysis.p5.availability import (
    AvailabilityYear,
    MultiYearAvailabilityRequest,
    build_multi_year_availability_view,
)
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.storage.repositories import ReportCoverage


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
    normalized_unit: str | None = "currency_amount",
    raw_unit: str | None = None,
    missing_status: dict[str, dict[str, str]] | None = None,
) -> P5ExtractedArtifact:
    entry = _entry(fiscal_year=fiscal_year)
    canonical_fact = {
        "fact_id": f"fact-{metric_id}-{fiscal_year}",
        "metric_id": metric_id,
        "statement_type": "income_statement",
        "entity_scope": "consolidated",
        "numeric_value": numeric_value,
        "currency": "USD",
        "quality_status": "ok",
        "evidence_bundle_id": f"bundle-{metric_id}-{fiscal_year}",
        "extensions": {"period_scope": "fy"},
    }
    if normalized_unit is not None:
        canonical_fact["normalized_unit"] = normalized_unit
    if raw_unit is not None:
        canonical_fact["raw_unit"] = raw_unit
    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="test-pipeline",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={"document_id": str(entry.pdf_path), "pdf_path": str(entry.pdf_path)},
        document_metadata={"language": "en"},
        candidate_facts=(),
        canonical_facts=(canonical_fact,),
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
    assert view.report_type == "annual"
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
    assert [(year.report_id, year.pdf_path) for year in view.years] == [
        (None, None),
        (2023, "/reports/HK_09987/2023.pdf"),
        (2024, "/reports/HK_09987/2024.pdf"),
    ]
    assert [year.source_artifact_ids for year in view.years] == [
        (),
        (),
        ("HK_09987_2024",),
    ]
    year_2024 = view.years[2]
    assert {metric.metric_id: metric.status for metric in year_2024.metrics} == {
        "cash": "missing_metric",
        "revenue": "present",
    }
    revenue = next(metric for metric in year_2024.metrics if metric.metric_id == "revenue")
    assert revenue.value == 100.0
    assert revenue.currency == "USD"
    assert revenue.unit == "currency_amount"
    assert revenue.quality_status == "ok"
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


def test_availability_metric_unit_falls_back_to_raw_unit() -> None:
    artifact = _artifact(
        fiscal_year=2024,
        normalized_unit=None,
        raw_unit="RMB millions",
    )
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

    assert view.years[0].metrics[0].unit == "RMB millions"


def test_availability_only_returns_required_metric_projection() -> None:
    artifact = _artifact(fiscal_year=2024, metric_id="cash")
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

    assert {metric.metric_id: metric.status for metric in view.years[0].metrics} == {
        "revenue": "missing_metric",
    }


def test_availability_returns_no_metrics_when_projection_is_empty() -> None:
    artifact = _artifact(fiscal_year=2024, metric_id="cash")
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
            required_metric_ids=(),
        ),
    )

    assert view.years[0].metrics == ()


@pytest.mark.parametrize(
    "missing_status",
    [
        {
            "first_group": {"st_borr": "absent"},
            "second_group": {"st_borr": "out_of_scope"},
        },
        {
            "first_group": {"st_borr": "out_of_scope"},
            "second_group": {"st_borr": "not_surfaced"},
        },
    ],
)
def test_availability_missing_status_prefers_out_of_scope_over_unknown(
    missing_status: dict[str, dict[str, str]],
) -> None:
    artifact = _artifact(fiscal_year=2024, missing_status=missing_status)
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
            required_metric_ids=("st_borr",),
        ),
    )

    assert view.years[0].metrics[0].status == "out_of_scope"


def test_availability_uses_missing_status_from_artifact() -> None:
    artifact = _artifact(
        fiscal_year=2025,
        missing_status={
            "debt_missing_status": {
                "st_borr": "out_of_scope",
                "lt_borr": "absent",
                "lease_liab": "not_surfaced",
            }
        },
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
            required_metric_ids=("revenue", "st_borr", "lt_borr", "lease_liab", "cash"),
        ),
    )

    statuses = {
        metric.metric_id: metric.status
        for metric in view.years[0].metrics
    }
    assert statuses == {
        "cash": "missing_metric",
        "lease_liab": "unknown",
        "lt_borr": "unknown",
        "revenue": "present",
        "st_borr": "out_of_scope",
    }


def test_availability_models_reserve_unknown_year_status() -> None:
    year = AvailabilityYear(
        fiscal_year=2025,
        report_status="unknown",
        artifact_status="unknown",
    )

    assert year.report_status == "unknown"
    assert year.artifact_status == "unknown"


def test_availability_rejects_invalid_ranges() -> None:
    with pytest.raises(ValueError, match="start_year must be <= end_year"):
        MultiYearAvailabilityRequest(
            issuer_id="HK_09987",
            start_year=2025,
            end_year=2024,
            metric_profile="turtle_core",
            required_metric_ids=("revenue",),
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"issuer_id": " "}, "issuer_id must not be blank"),
        ({"metric_profile": ""}, "metric_profile must not be blank"),
        ({"report_type": "quarterly"}, "report_type must be annual"),
    ],
)
def test_availability_rejects_invalid_request_fields(
    kwargs: dict[str, str],
    message: str,
) -> None:
    request_kwargs = {
        "issuer_id": "HK_09987",
        "start_year": 2024,
        "end_year": 2024,
        "metric_profile": "turtle_core",
        "required_metric_ids": ("revenue",),
        **kwargs,
    }

    with pytest.raises(ValueError, match=message):
        MultiYearAvailabilityRequest(**request_kwargs)
