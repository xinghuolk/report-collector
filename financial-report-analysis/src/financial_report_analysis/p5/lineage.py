from __future__ import annotations

from dataclasses import asdict

from financial_report_analysis.p5.models import (
    P5ArtifactLineage,
    P5DatasetArtifact,
    P5ExtractedArtifact,
    P5TurtleExport,
)


def build_dataset_lineage(
    *,
    dataset: P5DatasetArtifact,
    extracted_artifacts: tuple[P5ExtractedArtifact, ...],
    turtle_export: P5TurtleExport | None = None,
) -> tuple[P5ArtifactLineage, ...]:
    artifacts_by_id = {
        artifact.artifact_id: artifact
        for artifact in extracted_artifacts
    }
    export_index = _export_rows_by_key(turtle_export)
    lineage: list[P5ArtifactLineage] = []
    for row in dataset.rows:
        artifact = artifacts_by_id.get(row.source_artifact_id)
        if artifact is None:
            continue
        export_match = export_index.get(_row_key(row))
        lineage.append(
            P5ArtifactLineage(
                dataset_id=dataset.dataset_id,
                source_artifact_id=row.source_artifact_id,
                source_pdf_path=str(artifact.source_pdf_path),
                pipeline_version=artifact.pipeline_version,
                source_fact_id=row.source_fact_id,
                evidence_bundle_id=row.evidence_bundle_id,
                manifest_entry_key=artifact.manifest_entry.entry_key,
                export_row_index=export_match[0] if export_match is not None else None,
                turtle_field=export_match[1] if export_match is not None else None,
            )
        )
    return tuple(lineage)


def _export_rows_by_key(
    turtle_export: P5TurtleExport | None,
) -> dict[tuple[object, ...], tuple[int, str | None]]:
    if turtle_export is None:
        return {}
    index: dict[tuple[object, ...], tuple[int, str | None]] = {}
    for row_index, row in enumerate(turtle_export.rows):
        if not isinstance(row, dict):
            continue
        index[_export_row_key(row)] = (
            row_index,
            str(row.get("turtle_field")) if row.get("turtle_field") is not None else None,
        )
    return index


def _row_key(row: object) -> tuple[object, ...]:
    return (
        getattr(row, "issuer_id"),
        getattr(row, "fiscal_year"),
        getattr(row, "metric_id"),
        getattr(row, "entity_scope"),
        getattr(row, "period_scope"),
        getattr(row, "statement_type"),
        getattr(row, "source_artifact_id"),
        getattr(row, "source_fact_id"),
    )


def _export_row_key(row: dict[str, object]) -> tuple[object, ...]:
    return (
        row.get("issuer_id"),
        row.get("fiscal_year"),
        row.get("canonical_metric_id", row.get("metric_id")),
        row.get("entity_scope"),
        row.get("period_scope"),
        row.get("statement_type"),
        row.get("source_artifact_id"),
        row.get("source_fact_id"),
    )


def artifact_lineage_to_payload(lineage: P5ArtifactLineage) -> dict[str, object]:
    return asdict(lineage)


def artifact_lineage_from_payload(payload: dict[str, object]) -> P5ArtifactLineage:
    return P5ArtifactLineage(
        dataset_id=str(payload["dataset_id"]),
        source_artifact_id=str(payload["source_artifact_id"]),
        source_pdf_path=str(payload["source_pdf_path"]),
        pipeline_version=str(payload["pipeline_version"]),
        source_fact_id=str(payload["source_fact_id"]) if payload.get("source_fact_id") is not None else None,
        evidence_bundle_id=str(payload["evidence_bundle_id"]) if payload.get("evidence_bundle_id") is not None else None,
        manifest_entry_key=tuple(payload["manifest_entry_key"]) if payload.get("manifest_entry_key") is not None else None,  # type: ignore[arg-type]
        export_row_index=int(payload["export_row_index"]) if payload.get("export_row_index") is not None else None,
        turtle_field=str(payload["turtle_field"]) if payload.get("turtle_field") is not None else None,
    )
