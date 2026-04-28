from __future__ import annotations

from pathlib import Path

import pytest

from financial_report_analysis.models import (
    MetricLifecycleRecomputeAudit,
    MetricLifecycleRecomputeAuditItem,
    MetricLifecycleRecomputeAuditSummary,
)
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.p5.recompute import (
    build_recompute_plan,
    execute_recompute_plan,
    metric_lifecycle_recompute_audit_from_payload,
    metric_lifecycle_recompute_audit_to_payload,
)
from financial_report_analysis.services.metric_governance_review import (
    build_review_item_id,
)


def test_build_recompute_plan_marks_dataset_and_export_rebuild_when_pipeline_changes() -> None:
    plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=("CN_600519_2025", "CN_601919_2025"),
        reason="pipeline_version_changed",
    )

    assert plan.target_artifact_ids == ("CN_600519_2025", "CN_601919_2025")
    assert plan.rebuild_dataset is True
    assert plan.rebuild_turtle_export is True


def test_build_recompute_plan_can_select_export_only_rebuild() -> None:
    plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=(),
        reason="export_alias_changed",
    )

    assert plan.rebuild_dataset is False
    assert plan.rebuild_turtle_export is True


def test_build_recompute_plan_explicitly_maps_dataset_contract_changes() -> None:
    plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=("CN_600519_2025",),
        reason="dataset_assembly_contract_changed",
    )

    assert plan.rebuild_dataset is True
    assert plan.rebuild_turtle_export is True


def test_build_recompute_plan_maps_lifecycle_decision_changes_to_full_rebuild() -> None:
    plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=("CN_601919_2025", "CN_600519_2025"),
        reason="metric_lifecycle_decision_changed",
    )

    assert plan.target_artifact_ids == ("CN_600519_2025", "CN_601919_2025")
    assert plan.rebuild_dataset is True
    assert plan.rebuild_turtle_export is True


def test_execute_recompute_plan_reuses_runner_entry_point(tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    def fake_run_p5_dataset_build(**kwargs):
        calls.update(kwargs)
        return type(
            "Result",
            (),
            {
                "manifest_id": "p5_seed",
                "extracted_artifact_ids": ("CN_600519_2025",),
                "dataset_path": tmp_path / "p5_seed.json",
                "turtle_export_path": tmp_path / "p5_seed_turtle_export.json",
            },
        )()

    plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=("CN_600519_2025",),
        reason="pipeline_version_changed",
    )

    result = execute_recompute_plan(
        plan=plan,
        manifest_path=tmp_path / "manifest.json",
        artifact_root=tmp_path / "data" / "p5",
        pdf_root=tmp_path,
        run_p5_dataset_build_func=fake_run_p5_dataset_build,
    )

    assert calls["dataset_id"] == "p5_seed"
    assert calls["force_rebuild_artifact_ids"] == ("CN_600519_2025",)
    assert result.dataset_path.name == "p5_seed.json"
    assert result.diff_summary.rebuilt_dataset is True


def test_execute_recompute_plan_reuses_persisted_artifacts_for_review_recompute(
    tmp_path: Path,
) -> None:
    calls: dict[str, object] = {}

    def fake_run_p5_dataset_build(**kwargs):
        calls.update(kwargs)
        return type(
            "Result",
            (),
            {
                "manifest_id": "p5_seed",
                "extracted_artifact_ids": ("CN_601919_2025",),
                "dataset_path": tmp_path / "p5_seed.json",
                "turtle_export_path": tmp_path / "p5_seed_turtle_export.json",
            },
        )()

    plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=("CN_601919_2025",),
        reason="manual_review_check",
    )

    execute_recompute_plan(
        plan=plan,
        manifest_path=tmp_path / "manifest.json",
        artifact_root=tmp_path / "data" / "p5",
        pdf_root=tmp_path,
        run_p5_dataset_build_func=fake_run_p5_dataset_build,
    )

    assert calls["force_rebuild_artifact_ids"] == ()


def test_execute_recompute_plan_passes_lifecycle_transform_only_for_lifecycle_reason(
    tmp_path: Path,
) -> None:
    lifecycle_calls: dict[str, object] = {}
    normal_calls: dict[str, object] = {}
    audit = _lifecycle_audit()

    def fake_lifecycle_run_p5_dataset_build(**kwargs):
        lifecycle_calls.update(kwargs)
        transform = kwargs["artifact_transform_func"]
        transformed = transform(_artifact(tmp_path))
        assert transformed.canonical_facts[0]["metric_id"] == "accounts_receiv"
        return type(
            "Result",
            (),
            {
                "manifest_id": "p5_seed",
                "extracted_artifact_ids": ("CN_601919_2025",),
                "dataset_path": tmp_path / "p5_seed.json",
                "turtle_export_path": tmp_path / "p5_seed_turtle_export.json",
            },
        )()

    lifecycle_plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=("CN_601919_2025",),
        reason="metric_lifecycle_decision_changed",
    )

    execute_recompute_plan(
        plan=lifecycle_plan,
        manifest_path=tmp_path / "manifest.json",
        artifact_root=tmp_path / "data" / "p5",
        pdf_root=tmp_path,
        lifecycle_consumption_audit=audit,
        run_p5_dataset_build_func=fake_lifecycle_run_p5_dataset_build,
    )

    def fake_normal_run_p5_dataset_build(**kwargs):
        normal_calls.update(kwargs)
        return type(
            "Result",
            (),
            {
                "manifest_id": "p5_seed",
                "extracted_artifact_ids": ("CN_601919_2025",),
                "dataset_path": tmp_path / "p5_seed.json",
                "turtle_export_path": tmp_path / "p5_seed_turtle_export.json",
            },
        )()

    normal_plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=("CN_601919_2025",),
        reason="manual_review_check",
    )

    execute_recompute_plan(
        plan=normal_plan,
        manifest_path=tmp_path / "manifest.json",
        artifact_root=tmp_path / "data" / "p5",
        pdf_root=tmp_path,
        lifecycle_consumption_audit=audit,
        run_p5_dataset_build_func=fake_normal_run_p5_dataset_build,
    )

    assert callable(lifecycle_calls["artifact_transform_func"])
    assert "artifact_transform_func" not in normal_calls


def test_execute_recompute_plan_requires_audit_for_lifecycle_reason(
    tmp_path: Path,
) -> None:
    plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=("CN_601919_2025",),
        reason="metric_lifecycle_decision_changed",
    )

    with pytest.raises(
        ValueError,
        match="lifecycle_consumption_audit is required for lifecycle recompute",
    ):
        execute_recompute_plan(
            plan=plan,
            manifest_path=tmp_path / "manifest.json",
            artifact_root=tmp_path / "data" / "p5",
            pdf_root=tmp_path,
        )


def test_execute_recompute_plan_can_rebuild_only_turtle_export(tmp_path: Path) -> None:
    from financial_report_analysis.p5.artifact_repository import P5JsonArtifactRepository
    from financial_report_analysis.p5.models import P5DatasetArtifact, P5TurtleExport
    from financial_report_analysis.p5.runner import _save_turtle_export

    repository = P5JsonArtifactRepository(tmp_path / "data" / "p5")
    dataset = P5DatasetArtifact(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00",
        issuer_count=0,
        periods=(),
        metrics=(),
        rows=(),
        quality_summary={},
        source_artifacts=(),
    )
    repository.save_dataset_artifact(dataset)
    _save_turtle_export(
        repository,
        P5TurtleExport(
            dataset_id="p5_seed",
            dataset_version="1.0",
            created_at="2026-04-23T00:00:00",
            rows=(),
            alias_map={},
        ),
    )
    plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=(),
        reason="export_alias_changed",
    )

    result = execute_recompute_plan(
        plan=plan,
        manifest_path=tmp_path / "manifest.json",
        artifact_root=tmp_path / "data" / "p5",
        pdf_root=tmp_path,
    )

    assert result.dataset_path.name == "p5_seed.json"
    assert result.turtle_export_path.name == "p5_seed_turtle_export.json"
    assert result.diff_summary.rebuilt_dataset is False
    assert result.diff_summary.rebuilt_turtle_export is True


def test_execute_recompute_plan_ignores_created_at_only_diff(tmp_path: Path) -> None:
    from financial_report_analysis.p5.artifact_repository import P5JsonArtifactRepository
    from financial_report_analysis.p5.models import P5DatasetArtifact, P5TurtleExport
    from financial_report_analysis.p5.runner import _save_turtle_export

    repository = P5JsonArtifactRepository(tmp_path / "data" / "p5")
    original_dataset = P5DatasetArtifact(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00",
        issuer_count=0,
        periods=(),
        metrics=(),
        rows=(),
        quality_summary={},
        source_artifacts=(),
    )
    repository.save_dataset_artifact(original_dataset)
    _save_turtle_export(
        repository,
        P5TurtleExport(
            dataset_id="p5_seed",
            dataset_version="1.0",
            created_at="2026-04-23T00:00:00",
            rows=(),
            alias_map={},
        ),
    )

    def fake_run_p5_dataset_build(**_kwargs):
        updated_dataset = P5DatasetArtifact(
            dataset_id="p5_seed",
            dataset_version="1.0",
            created_at="2026-04-24T00:00:00",
            issuer_count=0,
            periods=(),
            metrics=(),
            rows=(),
            quality_summary={},
            source_artifacts=(),
        )
        dataset_path = repository.save_dataset_artifact(updated_dataset)
        turtle_path = _save_turtle_export(
            repository,
            P5TurtleExport(
                dataset_id="p5_seed",
                dataset_version="1.0",
                created_at="2026-04-24T00:00:00",
                rows=(),
                alias_map={},
            ),
        )
        return type(
            "Result",
            (),
            {
                "manifest_id": "p5_seed",
                "extracted_artifact_ids": (),
                "dataset_path": dataset_path,
                "turtle_export_path": turtle_path,
            },
        )()

    plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=(),
        reason="pipeline_version_changed",
    )

    result = execute_recompute_plan(
        plan=plan,
        manifest_path=tmp_path / "manifest.json",
        artifact_root=tmp_path / "data" / "p5",
        pdf_root=tmp_path,
        run_p5_dataset_build_func=fake_run_p5_dataset_build,
    )

    assert result.diff_summary.dataset_changed is False
    assert result.diff_summary.turtle_export_changed is False


def test_metric_lifecycle_recompute_audit_payload_round_trips() -> None:
    audit = _lifecycle_audit()

    payload = metric_lifecycle_recompute_audit_to_payload(audit)
    restored = metric_lifecycle_recompute_audit_from_payload(payload)

    assert restored == audit
    assert payload["summary"] == {
        "review_item_count": 1,
        "artifact_count": 1,
        "recompute_needed_count": 1,
        "dry_run_conflict_count": 0,
    }
    assert payload["items"][0]["latest_decision_action"] == "map_to_standard"
    assert payload["items"][0]["current_status"] == "mapped_to_standard"


def _lifecycle_audit() -> MetricLifecycleRecomputeAudit:
    item = MetricLifecycleRecomputeAuditItem(
        review_item_id=build_review_item_id("CN_601919_2025", "candidate-1"),
        artifact_id="CN_601919_2025",
        issuer_id="CN_601919",
        fiscal_year=2025,
        report_type="annual",
        candidate_metric_id="custom::cn::general::income-statement::root::receivables",
        raw_label="Receivables",
        lifecycle_entry_id="metric-lifecycle:1",
        current_status="mapped_to_standard",
        latest_decision_id="metric-lifecycle-decision:1",
        latest_decision_action="map_to_standard",
        target_metric_id="accounts_receiv",
        recompute_needed=True,
        consumption_action="map_to_standard",
        conflict_state="none",
        reason="lifecycle decision affects automatic outputs",
    )
    return MetricLifecycleRecomputeAudit(
        items=(item,),
        summary=MetricLifecycleRecomputeAuditSummary(
            review_item_count=1,
            artifact_count=1,
            recompute_needed_count=1,
            dry_run_conflict_count=0,
        ),
    )


def _artifact(tmp_path: Path) -> P5ExtractedArtifact:
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
    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={"document_id": str(pdf_path), "pdf_path": str(pdf_path)},
        document_metadata={},
        candidate_facts=(
            {
                "fact_id": "candidate-1",
                "metric_id": "custom::cn::general::income-statement::root::receivables",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "numeric_value": 12.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "evidence_bundle_id": "bundle-1",
                "extensions": {"period_scope": "duration"},
            },
        ),
        canonical_facts=(),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={},
        created_at="2026-04-23T00:00:00",
    )
