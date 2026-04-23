from financial_report_analysis.p5.models import (
    P5ArtifactLineage,
    P5DatasetArtifact,
    P5DatasetReviewSurface,
    P5ExtractedReviewSurface,
    P5RecomputePlan,
    P5TurtleExport,
    P5TurtleExportReviewSurface,
)
from financial_report_analysis.p5.review import (
    build_dataset_review_surface,
    build_extracted_review_surface,
    build_turtle_export_review_surface,
)


def test_post_p5_models_capture_minimum_contract() -> None:
    extracted = P5ExtractedReviewSurface(
        artifact_id="CN_601919_2025",
        artifact_version="1.0",
        pipeline_version="p5-v1",
        source_pdf_path="report/downloads/cn_stocks/601919/annual/2025_年度报告.pdf",
        manifest_entry_key=("CN_601919", 2025, "annual"),
        quality_gate="pass",
        review_issue_count=0,
        missing_status_groups=("working_capital_missing_status",),
    )
    dataset = P5DatasetReviewSurface(
        dataset_id="p5_seed",
        dataset_version="1.0",
        issuer_count=1,
        period_count=1,
        pipeline_versions=("p5-v1",),
        source_artifact_ids=("CN_601919_2025",),
        present_row_count=10,
        missing_row_count=2,
        review_required_artifact_ids=(),
    )
    lineage = P5ArtifactLineage(
        dataset_id="p5_seed",
        source_artifact_id="CN_601919_2025",
        source_pdf_path="report/downloads/cn_stocks/601919/annual/2025_年度报告.pdf",
        pipeline_version="p5-v1",
        source_fact_id="fact-1",
        evidence_bundle_id="bundle-1",
    )
    recompute_plan = P5RecomputePlan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        target_artifact_ids=("CN_601919_2025",),
        rebuild_dataset=True,
        rebuild_turtle_export=True,
        reason="pipeline_version_changed",
    )

    assert extracted.artifact_id == "CN_601919_2025"
    assert dataset.present_row_count == 10
    assert lineage.source_fact_id == "fact-1"
    assert recompute_plan.rebuild_dataset is True


def test_build_extracted_review_surface_counts_review_signals(tmp_path) -> None:
    from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry

    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
    )
    artifact = P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=pdf_path,
        document={"document_id": str(pdf_path), "pdf_path": str(pdf_path)},
        document_metadata={"working_capital_missing_status": {"notes_receiv": "absent"}},
        candidate_facts=(),
        canonical_facts=(),
        derived_facts=(),
        validation_report={"overall_status": "review", "issues": [{"code": "scope_conflict"}]},
        review_packets=({"metric_id": "cash", "conflict_state": "review_required"},),
        quality_gate="review",
        missing_status={"working_capital_missing_status": {"notes_receiv": "absent"}},
        created_at="2026-04-23T00:00:00",
    )

    surface = build_extracted_review_surface(artifact)

    assert surface.artifact_id == "CN_601919_2025"
    assert surface.review_issue_count == 1
    assert surface.quality_gate == "review"
    assert surface.missing_status_groups == ("working_capital_missing_status",)
    assert surface.review_required_signals == (
        "cash:review_required",
        "scope_conflict",
    )
    assert surface.scope_mismatch_count == 1


def test_build_dataset_review_surface_uses_quality_summary(tmp_path) -> None:
    from financial_report_analysis.p5.models import P5DatasetArtifact

    dataset = P5DatasetArtifact(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00",
        issuer_count=2,
        periods=(2024, 2025),
        metrics=("cash", "revenue"),
        rows=(),
        quality_summary={
            "present_row_count": 12,
            "missing_row_count": 3,
            "review_required_artifacts": ["CN_601919_2025"],
            "duplicate_fact_conflicts": [{"metric_id": "revenue"}],
            "scope_mismatch_warnings": [{"metric_id": "cash"}],
            "unknown_count": 1,
        },
        source_artifacts=("CN_600519_2025", "CN_601919_2025"),
    )
    extracted_artifacts = (
        _build_review_artifact(
            tmp_path,
            artifact_id="CN_600519_2025",
            pipeline_version="p5-v1",
        ),
        _build_review_artifact(
            tmp_path,
            artifact_id="CN_601919_2025",
            pipeline_version="p5-v2",
        ),
    )

    surface = build_dataset_review_surface(
        dataset,
        extracted_artifacts=extracted_artifacts,
    )

    assert surface.dataset_id == "p5_seed"
    assert surface.period_count == 2
    assert surface.present_row_count == 12
    assert surface.pipeline_versions == ("p5-v1", "p5-v2")
    assert surface.review_required_artifact_ids == ("CN_601919_2025",)
    assert surface.duplicate_conflict_count == 1
    assert surface.scope_mismatch_count == 1
    assert surface.unknown_count == 1


def test_build_turtle_export_review_surface_summarizes_rows() -> None:
    dataset = P5DatasetArtifact(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00",
        issuer_count=1,
        periods=(2025,),
        metrics=("cash", "revenue"),
        rows=(),
        quality_summary={
            "review_required_artifacts": ["CN_601919_2025"],
            "duplicate_fact_conflicts": [{"metric_id": "cash"}],
            "scope_mismatch_warnings": [{"metric_id": "cash"}],
        },
        source_artifacts=("CN_601919_2025",),
    )
    export = P5TurtleExport(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00",
        rows=(
            {"canonical_metric_id": "cash", "missing_status": "present"},
            {"canonical_metric_id": "revenue", "missing_status": "unknown"},
        ),
        alias_map={"cash": "money_cap"},
    )

    surface = build_turtle_export_review_surface(export, dataset=dataset)

    assert isinstance(surface, P5TurtleExportReviewSurface)
    assert surface.dataset_id == "p5_seed"
    assert surface.source_artifact_ids == ("CN_601919_2025",)
    assert surface.row_count == 2
    assert surface.present_row_count == 1
    assert surface.missing_row_count == 1
    assert surface.alias_count == 1
    assert surface.review_required_artifact_ids == ("CN_601919_2025",)
    assert surface.duplicate_conflict_count == 1
    assert surface.scope_mismatch_count == 1


def _build_review_artifact(
    tmp_path,
    *,
    artifact_id: str,
    pipeline_version: str,
):
    from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry

    market, stock_code, fiscal_year = artifact_id.split("_")
    pdf_path = tmp_path / f"{artifact_id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    entry = P5ManifestEntry(
        issuer_id=f"{market}_{stock_code}",
        market=market,
        stock_code=stock_code,
        fiscal_year=int(fiscal_year),
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
    )
    return P5ExtractedArtifact(
        artifact_id=artifact_id,
        artifact_version="1.0",
        pipeline_version=pipeline_version,
        manifest_entry=entry,
        source_pdf_path=pdf_path,
        document={"document_id": str(pdf_path), "pdf_path": str(pdf_path)},
        document_metadata={},
        candidate_facts=(),
        canonical_facts=(),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={},
        created_at="2026-04-23T00:00:00",
    )
