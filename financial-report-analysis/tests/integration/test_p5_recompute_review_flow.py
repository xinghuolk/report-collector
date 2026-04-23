from __future__ import annotations

import json
from pathlib import Path

import pytest

from financial_report_analysis.p5.artifact_repository import P5JsonArtifactRepository
from financial_report_analysis.p5.lineage import build_dataset_lineage
from financial_report_analysis.p5.recompute import (
    build_recompute_plan,
    execute_recompute_plan,
)
from financial_report_analysis.p5.review import (
    build_dataset_review_surface,
    build_extracted_review_surface,
)
from financial_report_analysis.p5.runner import run_p5_dataset_build
from financial_report_analysis.p5.turtle_export import build_turtle_export


pytestmark = [pytest.mark.real_pdf, pytest.mark.slow]


TESTS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TESTS_ROOT.parent.parent


def _load_seed_manifest() -> dict[str, object]:
    manifest_path = TESTS_ROOT / "fixtures" / "p5_seed_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _resolve_pdf_root(relative_paths: list[str]) -> Path | None:
    candidates = tuple({*Path(__file__).resolve().parents, REPO_ROOT})
    for root in candidates:
        if all((root / relative_paths[i]).exists() for i in range(len(relative_paths))):
            return root
    return None


def test_p5_recompute_review_flow_uses_persisted_artifacts(
    tmp_path: Path,
) -> None:
    payload = _load_seed_manifest()
    entries = payload["entries"]
    assert isinstance(entries, list)
    relative_paths = [str(entry["pdf_path"]) for entry in entries if isinstance(entry, dict)]
    pdf_root = _resolve_pdf_root(relative_paths)
    if pdf_root is None:
        pytest.skip("seed PDF sample(s) not available under a single pdf_root")

    manifest_path = TESTS_ROOT / "fixtures" / "p5_seed_manifest.json"
    initial = run_p5_dataset_build(
        manifest_path=manifest_path,
        artifact_root=tmp_path / "p5",
        dataset_id="p5_seed_review_flow",
        pdf_root=pdf_root,
        required_metric_ids=("revenue", "cash", "operating_cash_flow"),
        now_func=lambda: "2026-04-23T00:00:00",
    )
    plan = build_recompute_plan(
        manifest_id="p5_seed_3_issuers_2_years",
        dataset_id="p5_seed_review_flow",
        extracted_artifact_ids=initial.extracted_artifact_ids,
        reason="manual_review_check",
    )
    recomputed = execute_recompute_plan(
        plan=plan,
        manifest_path=manifest_path,
        artifact_root=tmp_path / "p5",
        pdf_root=pdf_root,
    )

    repository = P5JsonArtifactRepository(tmp_path / "p5")
    dataset = repository.load_dataset_artifact("p5_seed_review_flow")
    extracted_artifacts = tuple(
        repository.load_extracted_artifact(artifact_id)
        for artifact_id in initial.extracted_artifact_ids
    )

    extracted_surface = build_extracted_review_surface(extracted_artifacts[0])
    dataset_surface = build_dataset_review_surface(
        dataset,
        extracted_artifacts=extracted_artifacts,
    )
    lineage = build_dataset_lineage(
        dataset=dataset,
        extracted_artifacts=extracted_artifacts,
        turtle_export=build_turtle_export(dataset),
    )

    assert recomputed.dataset_path.exists()
    assert recomputed.turtle_export_path.exists()
    assert extracted_surface.artifact_id in initial.extracted_artifact_ids
    assert dataset_surface.dataset_id == "p5_seed_review_flow"
    assert lineage
