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
        return None


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
    dataset_review_surface = build_dataset_review_surface(
        dataset,
        extracted_artifacts=(artifact,),
    )

    turtle_export_id: str | None = None
    turtle_export = None
    turtle_export_review_surface = None
    if request.build_turtle:
        turtle_export = build_turtle_export(dataset)
        turtle_export_review_surface = build_turtle_export_review_surface(
            turtle_export,
            dataset=dataset,
        )
        turtle_export_id = turtle_export.dataset_id

    lineage_records = build_dataset_lineage(
        dataset=dataset,
        extracted_artifacts=(artifact,),
        turtle_export=turtle_export,
    )
    lineage_record_count = repository.save_p5_assembly_bundle(
        dataset=dataset,
        dataset_review_surface=dataset_review_surface,
        turtle_export=turtle_export,
        turtle_export_review_surface=turtle_export_review_surface,
        lineage_records=lineage_records,
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
