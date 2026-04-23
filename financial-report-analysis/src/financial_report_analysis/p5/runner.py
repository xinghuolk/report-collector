from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from financial_report_analysis.p5.artifact_repository import P5JsonArtifactRepository
from financial_report_analysis.p5.dataset import assemble_dataset
from financial_report_analysis.p5.extraction import build_extracted_artifact
from financial_report_analysis.p5.manifest import load_manifest
from financial_report_analysis.p5.models import (
    P5DatasetArtifact,
    P5ExtractedArtifact,
    P5ManifestEntry,
    P5TurtleExport,
)
from financial_report_analysis.p5.turtle_export import build_turtle_export


@dataclass(frozen=True, slots=True)
class P5RunResult:
    manifest_id: str
    extracted_artifact_ids: tuple[str, ...]
    dataset_path: Path
    turtle_export_path: Path


def run_p5_dataset_build(
    *,
    manifest_path: str | Path,
    artifact_root: str | Path,
    dataset_id: str,
    pdf_root: str | Path | None = None,
    required_metric_ids: tuple[str, ...] = (),
    force_rebuild_artifact_ids: tuple[str, ...] = (),
    write_turtle_export: bool = True,
    build_artifact_func: Callable[
        [P5ManifestEntry],
        P5ExtractedArtifact,
    ] = build_extracted_artifact,
    assemble_dataset_func: Callable[..., P5DatasetArtifact] = assemble_dataset,
    build_turtle_export_func: Callable[[P5DatasetArtifact], P5TurtleExport] = build_turtle_export,
    now_func: Callable[[], str] | None = None,
) -> P5RunResult:
    manifest = load_manifest(manifest_path, pdf_root=pdf_root)
    repository = P5JsonArtifactRepository(artifact_root)
    forced_artifact_ids = set(force_rebuild_artifact_ids)

    extracted_artifacts: list[P5ExtractedArtifact] = []
    for entry in manifest.entries:
        artifact = _load_or_build_artifact(
            repository=repository,
            entry=entry,
            force_rebuild=entry.artifact_id in forced_artifact_ids,
            build_artifact_func=build_artifact_func,
        )
        extracted_artifacts.append(artifact)

    dataset = assemble_dataset_func(
        dataset_id=dataset_id,
        artifacts=tuple(extracted_artifacts),
        required_metric_ids=required_metric_ids,
        now_func=now_func,
    )
    repository.save_dataset_artifact(dataset)
    dataset_path = repository.dataset_artifact_path(dataset_id)
    turtle_export_path = repository.turtle_export_artifact_path(dataset_id)
    if write_turtle_export:
        turtle_export = build_turtle_export_func(dataset)
        turtle_export_path = _save_turtle_export(repository, turtle_export)

    return P5RunResult(
        manifest_id=manifest.manifest_id,
        extracted_artifact_ids=tuple(artifact.artifact_id for artifact in extracted_artifacts),
        dataset_path=dataset_path,
        turtle_export_path=turtle_export_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a P5 dataset and Turtle export from a manifest",
    )
    parser.add_argument("--manifest", required=True, help="Path to the P5 manifest JSON")
    parser.add_argument(
        "--artifact-root",
        default="data/p5",
        help="Root directory for persisted P5 artifacts",
    )
    parser.add_argument("--dataset-id", required=True, help="Dataset identifier to persist")
    parser.add_argument(
        "--pdf-root",
        default=None,
        help="Base directory for resolving relative manifest pdf_path values",
    )
    parser.add_argument(
        "--required-metric-id",
        dest="required_metric_ids",
        action="append",
        default=[],
        help="Metric ids to include as required missing rows",
    )
    args = parser.parse_args()

    result = run_p5_dataset_build(
        manifest_path=Path(args.manifest),
        artifact_root=Path(args.artifact_root),
        dataset_id=args.dataset_id,
        pdf_root=Path(args.pdf_root) if args.pdf_root is not None else None,
        required_metric_ids=tuple(args.required_metric_ids),
    )
    print(
        json.dumps(
            {
                "manifest_id": result.manifest_id,
                "extracted_artifact_ids": list(result.extracted_artifact_ids),
                "dataset_path": str(result.dataset_path),
                "turtle_export_path": str(result.turtle_export_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _build_and_persist_artifact(
    *,
    repository: P5JsonArtifactRepository,
    entry: P5ManifestEntry,
    build_artifact_func: Callable[[P5ManifestEntry], P5ExtractedArtifact],
) -> P5ExtractedArtifact:
    artifact = build_artifact_func(entry)
    repository.save_extracted_artifact(artifact)
    return artifact


def _load_or_build_artifact(
    *,
    repository: P5JsonArtifactRepository,
    entry: P5ManifestEntry,
    force_rebuild: bool,
    build_artifact_func: Callable[[P5ManifestEntry], P5ExtractedArtifact],
) -> P5ExtractedArtifact:
    if force_rebuild or not repository.extracted_artifact_exists(entry.artifact_id):
        return _build_and_persist_artifact(
            repository=repository,
            entry=entry,
            build_artifact_func=build_artifact_func,
        )

    artifact = repository.load_extracted_artifact(entry.artifact_id)
    if _artifact_matches_manifest_entry(artifact, entry):
        return artifact

    return _build_and_persist_artifact(
        repository=repository,
        entry=entry,
        build_artifact_func=build_artifact_func,
    )


def _artifact_matches_manifest_entry(
    artifact: P5ExtractedArtifact,
    entry: P5ManifestEntry,
) -> bool:
    return (
        artifact.manifest_entry == entry
        and artifact.source_pdf_path == entry.pdf_path
        and Path(str(artifact.document.get("pdf_path", ""))) == entry.pdf_path
        and str(artifact.document.get("document_id", "")) == str(entry.pdf_path)
    )


def _save_turtle_export(
    repository: P5JsonArtifactRepository,
    turtle_export: P5TurtleExport,
) -> Path:
    return repository.save_turtle_export(turtle_export)
