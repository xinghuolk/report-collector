from __future__ import annotations

from financial_report_analysis.p5.models import (
    P5DatasetArtifact,
    P5DatasetReviewSurface,
    P5ExtractedArtifact,
    P5ExtractedReviewSurface,
)


def build_extracted_review_surface(
    artifact: P5ExtractedArtifact,
) -> P5ExtractedReviewSurface:
    issues = artifact.validation_report.get("issues", ())
    missing_status_groups = tuple(artifact.missing_status.keys())
    return P5ExtractedReviewSurface(
        artifact_id=artifact.artifact_id,
        artifact_version=artifact.artifact_version,
        pipeline_version=artifact.pipeline_version,
        source_pdf_path=str(artifact.source_pdf_path),
        manifest_entry_key=artifact.manifest_entry.entry_key,
        quality_gate=artifact.quality_gate,
        review_issue_count=len(tuple(issues)),
        missing_status_groups=missing_status_groups,
    )


def build_dataset_review_surface(
    dataset: P5DatasetArtifact,
) -> P5DatasetReviewSurface:
    quality_summary = dataset.quality_summary
    review_required_artifact_ids = tuple(
        quality_summary.get("review_required_artifacts", ())
    )
    return P5DatasetReviewSurface(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        issuer_count=dataset.issuer_count,
        period_count=len(dataset.periods),
        source_artifact_ids=dataset.source_artifacts,
        present_row_count=int(quality_summary.get("present_row_count", 0)),
        missing_row_count=int(quality_summary.get("missing_row_count", 0)),
        review_required_artifact_ids=review_required_artifact_ids,
    )
