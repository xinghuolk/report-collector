from financial_report_analysis.p5.models import (
    P5ArtifactLineage,
    P5DatasetReviewSurface,
    P5ExtractedReviewSurface,
    P5RecomputePlan,
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
