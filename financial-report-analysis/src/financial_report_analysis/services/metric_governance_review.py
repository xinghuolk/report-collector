from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from financial_report_analysis.models.governance import (
    MetricGovernanceDecision,
    MetricGovernanceDecisionAnnotation,
    MetricGovernanceReviewItem,
)
from financial_report_analysis.p5.models import P5ExtractedArtifact


class MetricGovernanceReviewRepository(Protocol):
    def list_extracted_artifact_ids(
        self,
        issuer_id: str | None = None,
        fiscal_year: int | None = None,
    ) -> tuple[str, ...]: ...

    def load_extracted_artifact(self, artifact_id: str) -> P5ExtractedArtifact: ...

    def load_latest_metric_governance_decision(
        self,
        review_item_id: str,
    ) -> MetricGovernanceDecision | None: ...


class MetricGovernanceReviewService:
    def __init__(self, repository: MetricGovernanceReviewRepository) -> None:
        self._repository = repository

    def list_review_items(
        self,
        *,
        issuer_id: str | None = None,
        fiscal_year: int | None = None,
    ) -> list[MetricGovernanceReviewItem]:
        items: list[MetricGovernanceReviewItem] = []
        for artifact_id in self._repository.list_extracted_artifact_ids(
            issuer_id=issuer_id,
            fiscal_year=fiscal_year,
        ):
            artifact = self._repository.load_extracted_artifact(artifact_id)
            items.extend(self._review_items_from_artifact(artifact))
        return items

    def get_review_item(self, review_item_id: str) -> MetricGovernanceReviewItem | None:
        artifact_id, separator, _candidate_id = review_item_id.partition(":")
        if not separator:
            return None
        artifact = self._repository.load_extracted_artifact(artifact_id)
        for item in self._review_items_from_artifact(artifact):
            if item.review_item_id == review_item_id:
                return item
        return None

    def _review_items_from_artifact(
        self,
        artifact: P5ExtractedArtifact,
    ) -> list[MetricGovernanceReviewItem]:
        items: list[MetricGovernanceReviewItem] = []
        for candidate in artifact.candidate_facts:
            extensions = _extensions(candidate)
            governance = _governance(extensions)
            if governance.get("registry_status") != "provisional":
                continue

            fact_id = str(candidate.get("fact_id", ""))
            review_item_id = f"{artifact.artifact_id}:{fact_id}"
            latest = self._repository.load_latest_metric_governance_decision(
                review_item_id,
            )
            items.append(
                MetricGovernanceReviewItem(
                    review_item_id=review_item_id,
                    artifact_id=artifact.artifact_id,
                    issuer_id=artifact.manifest_entry.issuer_id,
                    fiscal_year=artifact.manifest_entry.fiscal_year,
                    report_type=artifact.manifest_entry.report_type,
                    metric_id=str(candidate.get("metric_id", "")),
                    raw_label=str(
                        candidate.get("raw_label")
                        or candidate.get("metric_label_raw")
                        or ""
                    ),
                    normalized_label=_optional_text(
                        candidate.get("normalized_label"),
                    ),
                    statement_type=str(candidate.get("statement_type", "")),
                    candidate_value=_optional_number(candidate.get("value")),
                    period_label=_optional_text(extensions.get("period_label")),
                    source_page=_optional_int(extensions.get("page_number")),
                    source_table_id=_optional_text(extensions.get("table_id")),
                    evidence_bundle_id=_optional_text(
                        candidate.get("evidence_bundle_id"),
                    ),
                    metric_governance=governance,
                    latest_decision=(
                        MetricGovernanceDecisionAnnotation.from_decision(latest)
                        if latest is not None
                        else None
                    ),
                )
            )
        return items


def _extensions(candidate: Mapping[str, object]) -> dict[str, object]:
    raw = candidate.get("extensions")
    return dict(raw) if isinstance(raw, dict) else {}


def _governance(extensions: Mapping[str, object]) -> dict[str, object]:
    raw = extensions.get("metric_governance")
    return dict(raw) if isinstance(raw, dict) else {}


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _optional_number(value: object) -> float | int | None:
    return value if isinstance(value, (float, int)) else None
