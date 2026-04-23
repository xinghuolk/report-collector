from __future__ import annotations

from dataclasses import asdict

from financial_report_analysis.p5.models import (
    P5DatasetArtifact,
    P5DatasetReviewSurface,
    P5ExtractedArtifact,
    P5ExtractedReviewSurface,
    P5TurtleExport,
    P5TurtleExportReviewSurface,
)


def build_extracted_review_surface(
    artifact: P5ExtractedArtifact,
) -> P5ExtractedReviewSurface:
    issues = tuple(artifact.validation_report.get("issues", ()))
    issue_codes = tuple(
        str(issue.get("code", "")).strip()
        for issue in issues
        if isinstance(issue, dict) and str(issue.get("code", "")).strip()
    )
    packet_signals = tuple(
        f"{packet.get('metric_id', 'unknown')}:{packet.get('conflict_state', packet.get('status', 'review_required'))}"
        for packet in artifact.review_packets
        if isinstance(packet, dict)
        and str(packet.get("conflict_state", packet.get("status", ""))).strip()
    )
    review_required_signals = tuple(
        sorted(
            {
                *issue_codes,
                *packet_signals,
            }
        )
    )
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
        review_required_signals=review_required_signals,
        duplicate_conflict_count=sum(
            1 for code in issue_codes if "duplicate" in code.lower()
        ),
        scope_mismatch_count=sum(
            1 for code in issue_codes if "scope" in code.lower()
        ),
    )


def build_dataset_review_surface(
    dataset: P5DatasetArtifact,
    *,
    extracted_artifacts: tuple[P5ExtractedArtifact, ...],
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
        pipeline_versions=tuple(
            sorted({artifact.pipeline_version for artifact in extracted_artifacts})
        ),
        source_artifact_ids=dataset.source_artifacts,
        present_row_count=int(quality_summary.get("present_row_count", 0)),
        missing_row_count=int(quality_summary.get("missing_row_count", 0)),
        review_required_artifact_ids=review_required_artifact_ids,
        duplicate_conflict_count=len(
            tuple(quality_summary.get("duplicate_fact_conflicts", ()))
        ),
        scope_mismatch_count=len(
            tuple(quality_summary.get("scope_mismatch_warnings", ()))
        ),
        unknown_count=int(quality_summary.get("unknown_count", 0)),
    )


def build_turtle_export_review_surface(
    turtle_export: P5TurtleExport,
    *,
    dataset: P5DatasetArtifact | None = None,
) -> P5TurtleExportReviewSurface:
    present_row_count = sum(
        1
        for row in turtle_export.rows
        if isinstance(row, dict) and row.get("missing_status") == "present"
    )
    missing_row_count = sum(
        1
        for row in turtle_export.rows
        if isinstance(row, dict) and row.get("missing_status") != "present"
    )
    source_artifact_ids: tuple[str, ...] = ()
    review_required_artifact_ids: tuple[str, ...] = ()
    duplicate_conflict_count = 0
    scope_mismatch_count = 0
    if dataset is not None:
        source_artifact_ids = dataset.source_artifacts
        review_required_artifact_ids = tuple(
            dataset.quality_summary.get("review_required_artifacts", ())
        )
        duplicate_conflict_count = len(
            tuple(dataset.quality_summary.get("duplicate_fact_conflicts", ()))
        )
        scope_mismatch_count = len(
            tuple(dataset.quality_summary.get("scope_mismatch_warnings", ()))
        )
    return P5TurtleExportReviewSurface(
        dataset_id=turtle_export.dataset_id,
        dataset_version=turtle_export.dataset_version,
        source_artifact_ids=source_artifact_ids,
        row_count=len(turtle_export.rows),
        present_row_count=present_row_count,
        missing_row_count=missing_row_count,
        alias_count=len(turtle_export.alias_map),
        review_required_artifact_ids=review_required_artifact_ids,
        duplicate_conflict_count=duplicate_conflict_count,
        scope_mismatch_count=scope_mismatch_count,
    )


def extracted_review_surface_to_payload(
    surface: P5ExtractedReviewSurface,
) -> dict[str, object]:
    return asdict(surface)


def extracted_review_surface_from_payload(
    payload: dict[str, object],
) -> P5ExtractedReviewSurface:
    return P5ExtractedReviewSurface(
        artifact_id=str(payload["artifact_id"]),
        artifact_version=str(payload["artifact_version"]),
        pipeline_version=str(payload["pipeline_version"]),
        source_pdf_path=str(payload["source_pdf_path"]),
        manifest_entry_key=tuple(payload["manifest_entry_key"]),  # type: ignore[arg-type]
        quality_gate=str(payload["quality_gate"]),
        review_issue_count=int(payload["review_issue_count"]),
        missing_status_groups=tuple(payload.get("missing_status_groups", ())),  # type: ignore[arg-type]
        review_required_signals=tuple(payload.get("review_required_signals", ())),  # type: ignore[arg-type]
        duplicate_conflict_count=int(payload.get("duplicate_conflict_count", 0)),
        scope_mismatch_count=int(payload.get("scope_mismatch_count", 0)),
    )


def dataset_review_surface_to_payload(
    surface: P5DatasetReviewSurface,
) -> dict[str, object]:
    return asdict(surface)


def dataset_review_surface_from_payload(
    payload: dict[str, object],
) -> P5DatasetReviewSurface:
    return P5DatasetReviewSurface(
        dataset_id=str(payload["dataset_id"]),
        dataset_version=str(payload["dataset_version"]),
        issuer_count=int(payload["issuer_count"]),
        period_count=int(payload["period_count"]),
        pipeline_versions=tuple(payload.get("pipeline_versions", ())),  # type: ignore[arg-type]
        source_artifact_ids=tuple(payload.get("source_artifact_ids", ())),  # type: ignore[arg-type]
        present_row_count=int(payload["present_row_count"]),
        missing_row_count=int(payload["missing_row_count"]),
        review_required_artifact_ids=tuple(
            payload.get("review_required_artifact_ids", ())
        ),  # type: ignore[arg-type]
        duplicate_conflict_count=int(payload.get("duplicate_conflict_count", 0)),
        scope_mismatch_count=int(payload.get("scope_mismatch_count", 0)),
        unknown_count=int(payload.get("unknown_count", 0)),
    )


def turtle_export_review_surface_to_payload(
    surface: P5TurtleExportReviewSurface,
) -> dict[str, object]:
    return asdict(surface)


def turtle_export_review_surface_from_payload(
    payload: dict[str, object],
) -> P5TurtleExportReviewSurface:
    return P5TurtleExportReviewSurface(
        dataset_id=str(payload["dataset_id"]),
        dataset_version=str(payload["dataset_version"]),
        source_artifact_ids=tuple(payload.get("source_artifact_ids", ())),  # type: ignore[arg-type]
        row_count=int(payload["row_count"]),
        present_row_count=int(payload["present_row_count"]),
        missing_row_count=int(payload["missing_row_count"]),
        alias_count=int(payload["alias_count"]),
        review_required_artifact_ids=tuple(
            payload.get("review_required_artifact_ids", ())
        ),  # type: ignore[arg-type]
        duplicate_conflict_count=int(payload.get("duplicate_conflict_count", 0)),
        scope_mismatch_count=int(payload.get("scope_mismatch_count", 0)),
    )
