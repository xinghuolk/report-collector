from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

from financial_report_analysis.p5.models import P5ExtractedArtifact

if TYPE_CHECKING:
    from financial_report_analysis.storage.repositories import ReportCoverage

YearAvailabilityStatus = Literal[
    "covered",
    "missing_report",
    "missing_extracted_artifact",
    "unknown",
]
ReportStatus = Literal["covered", "missing_report", "unknown"]
ArtifactStatus = Literal[
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


@dataclass(frozen=True, slots=True)
class MultiYearAvailabilityRequest:
    issuer_id: str
    start_year: int
    end_year: int
    metric_profile: str
    required_metric_ids: tuple[str, ...]
    report_type: str = "annual"

    def __post_init__(self) -> None:
        if not self.issuer_id.strip():
            raise ValueError("issuer_id must not be blank")
        if not self.metric_profile.strip():
            raise ValueError("metric_profile must not be blank")
        if self.start_year > self.end_year:
            raise ValueError("start_year must be <= end_year")
        if self.report_type != "annual":
            raise ValueError("report_type must be annual")


@dataclass(frozen=True, slots=True)
class AvailabilityMetric:
    metric_id: str
    status: MetricAvailabilityStatus
    value: int | float | None = None
    currency: str | None = None
    unit: str | None = None
    quality_status: str | None = None
    source_artifact_id: str | None = None
    source_fact_id: str | None = None
    evidence_bundle_id: str | None = None


@dataclass(frozen=True, slots=True)
class AvailabilityYear:
    fiscal_year: int
    report_status: ReportStatus
    artifact_status: ArtifactStatus
    report_id: int | None = None
    pdf_path: str | None = None
    source_artifact_ids: tuple[str, ...] = ()
    metrics: tuple[AvailabilityMetric, ...] = ()


@dataclass(frozen=True, slots=True)
class MultiYearAvailabilityView:
    issuer_id: str
    start_year: int
    end_year: int
    metric_profile: str
    report_type: str
    years: tuple[AvailabilityYear, ...]
    coverage_summary: dict[str, int]
    recommended_next_actions: tuple[str, ...] = ()


class AvailabilityReadRepository(Protocol):
    def get_report_coverage(
        self,
        issuer_id: str,
        fiscal_year: int,
        report_type: str,
    ) -> ReportCoverage: ...

    def load_extracted_artifact(self, artifact_id: str) -> P5ExtractedArtifact: ...


def build_multi_year_availability_view(
    *,
    repository: AvailabilityReadRepository,
    request: MultiYearAvailabilityRequest,
) -> MultiYearAvailabilityView:
    years: list[AvailabilityYear] = []

    for fiscal_year in range(request.start_year, request.end_year + 1):
        coverage = repository.get_report_coverage(
            request.issuer_id,
            fiscal_year,
            request.report_type,
        )
        if not coverage.report_registered:
            years.append(
                AvailabilityYear(
                    fiscal_year=fiscal_year,
                    report_status="missing_report",
                    artifact_status="missing_report",
                )
            )
            continue

        if not coverage.extracted_artifact_ids:
            years.append(
                AvailabilityYear(
                    fiscal_year=fiscal_year,
                    report_status="covered",
                    artifact_status="missing_extracted_artifact",
                    report_id=coverage.report_id,
                    pdf_path=coverage.pdf_path,
                )
            )
            continue

        artifacts = tuple(
            repository.load_extracted_artifact(artifact_id)
            for artifact_id in coverage.extracted_artifact_ids
        )
        years.append(
            AvailabilityYear(
                fiscal_year=fiscal_year,
                report_status="covered",
                artifact_status="covered",
                report_id=coverage.report_id,
                pdf_path=coverage.pdf_path,
                source_artifact_ids=coverage.extracted_artifact_ids,
                metrics=_availability_metrics(artifacts, request.required_metric_ids),
            )
        )

    return MultiYearAvailabilityView(
        issuer_id=request.issuer_id,
        start_year=request.start_year,
        end_year=request.end_year,
        metric_profile=request.metric_profile,
        report_type=request.report_type,
        years=tuple(years),
        coverage_summary=_coverage_summary(years),
        recommended_next_actions=_recommended_next_actions(years),
    )


def _availability_metrics(
    artifacts: tuple[P5ExtractedArtifact, ...],
    required_metric_ids: tuple[str, ...],
) -> tuple[AvailabilityMetric, ...]:
    metrics_by_id: dict[str, AvailabilityMetric] = {}
    required_metric_id_set = set(required_metric_ids)

    for artifact in artifacts:
        for fact in artifact.canonical_facts:
            metric_id = fact.get("metric_id")
            if (
                not isinstance(metric_id, str)
                or metric_id not in required_metric_id_set
                or metric_id in metrics_by_id
            ):
                continue
            metrics_by_id[metric_id] = _present_metric(artifact.artifact_id, fact)

    for metric_id in required_metric_ids:
        if metric_id in metrics_by_id:
            continue
        metrics_by_id[metric_id] = AvailabilityMetric(
            metric_id=metric_id,
            status=_missing_metric_status(metric_id, artifacts),
        )

    return tuple(metrics_by_id[metric_id] for metric_id in required_metric_ids)


def _present_metric(artifact_id: str, fact: dict[str, Any]) -> AvailabilityMetric:
    value = fact.get("numeric_value")
    if not isinstance(value, (int, float)):
        value = None
    return AvailabilityMetric(
        metric_id=str(fact["metric_id"]),
        status="present",
        value=value,
        currency=_optional_str(fact.get("currency")),
        unit=_optional_str(fact.get("normalized_unit"))
        or _optional_str(fact.get("raw_unit")),
        quality_status=_optional_str(fact.get("quality_status")),
        source_artifact_id=artifact_id,
        source_fact_id=_optional_str(fact.get("fact_id")),
        evidence_bundle_id=_optional_str(fact.get("evidence_bundle_id")),
    )


def _missing_metric_status(
    metric_id: str,
    artifacts: tuple[P5ExtractedArtifact, ...],
) -> MetricAvailabilityStatus:
    has_missing_status_entry = False
    for artifact in artifacts:
        for missing_group in artifact.missing_status.values():
            status = missing_group.get(metric_id)
            if status == "out_of_scope":
                return "out_of_scope"
            if status is not None:
                has_missing_status_entry = True
    if has_missing_status_entry:
        return "unknown"
    return "missing_metric"


def _optional_str(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _coverage_summary(years: list[AvailabilityYear]) -> dict[str, int]:
    present_metric_count = sum(
        1 for year in years for metric in year.metrics if metric.status == "present"
    )
    missing_metric_count = sum(
        1 for year in years for metric in year.metrics if metric.status == "missing_metric"
    )
    return {
        "year_count": len(years),
        "covered_year_count": sum(
            1 for year in years if year.artifact_status == "covered"
        ),
        "missing_report_count": sum(
            1 for year in years if year.report_status == "missing_report"
        ),
        "missing_extracted_artifact_count": sum(
            1
            for year in years
            if year.artifact_status == "missing_extracted_artifact"
        ),
        "present_metric_count": present_metric_count,
        "missing_metric_count": missing_metric_count,
    }


def _recommended_next_actions(
    years: list[AvailabilityYear],
) -> tuple[str, ...]:
    actions: list[str] = []
    if any(year.report_status == "missing_report" for year in years):
        actions.append("register_missing_reports")
    if any(year.artifact_status == "missing_extracted_artifact" for year in years):
        actions.append("run_existing_report_extraction")
    if any(metric.status == "missing_metric" for year in years for metric in year.metrics):
        actions.append("review_required_metric_coverage")
    return tuple(actions)
