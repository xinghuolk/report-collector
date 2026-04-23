from __future__ import annotations

from pathlib import Path

from financial_report_analysis.p5.recompute import (
    build_recompute_plan,
    execute_recompute_plan,
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
