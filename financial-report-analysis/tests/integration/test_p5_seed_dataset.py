from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from financial_report_analysis.p5.runner import run_p5_dataset_build


pytestmark = [pytest.mark.real_pdf, pytest.mark.slow]


TESTS_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TESTS_ROOT.parent
REPO_ROOT = PROJECT_ROOT.parent


def _discover_pdf_root_candidates() -> tuple[Path, ...]:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for ancestor in Path(__file__).resolve().parents:
        if not (ancestor / "report" / "downloads").exists():
            continue
        if ancestor in seen:
            continue
        seen.add(ancestor)
        candidates.append(ancestor)
    if REPO_ROOT not in seen:
        candidates.append(REPO_ROOT)
    return tuple(candidates)


PDF_ROOT_CANDIDATES = _discover_pdf_root_candidates()


def _load_seed_manifest() -> dict[str, object]:
    manifest_path = TESTS_ROOT / "fixtures" / "p5_seed_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _missing_samples(relative_paths: list[str]) -> list[str]:
    missing: list[str] = []
    for relative_path in relative_paths:
        if not any((root / relative_path).exists() for root in PDF_ROOT_CANDIDATES):
            missing.append(relative_path)
    return missing


def _resolve_pdf_root(relative_paths: list[str]) -> Path | None:
    for root in PDF_ROOT_CANDIDATES:
        if all((root / relative_path).exists() for relative_path in relative_paths):
            return root
    return None


def test_p5_seed_dataset_builds_from_existing_real_pdf_samples(
    tmp_path: Path,
) -> None:
    payload = _load_seed_manifest()
    entries = payload["entries"]
    assert isinstance(entries, list)
    assert len(entries) == 6

    issuer_counts = Counter()
    years: set[int] = set()
    relative_paths: list[str] = []
    for entry in entries:
        assert isinstance(entry, dict)
        issuer_counts[str(entry["issuer_id"])] += 1
        years.add(int(entry["fiscal_year"]))
        relative_paths.append(str(entry["pdf_path"]))

    assert set(issuer_counts) == {"CN_600519", "CN_601919", "CN_688008"}
    assert all(count == 2 for count in issuer_counts.values())
    assert years == {2024, 2025}

    missing = _missing_samples(relative_paths)
    if missing:
        pytest.skip("seed PDF sample(s) not available: " + ", ".join(missing))

    pdf_root = _resolve_pdf_root(relative_paths)
    if pdf_root is None:
        pytest.skip(
            "seed PDF sample(s) are not available under a single pdf_root: "
            + ", ".join(str(root) for root in PDF_ROOT_CANDIDATES)
        )

    manifest_path = TESTS_ROOT / "fixtures" / "p5_seed_manifest.json"
    result = run_p5_dataset_build(
        manifest_path=manifest_path,
        artifact_root=tmp_path / "p5",
        dataset_id="p5_seed_3_issuers_2_years",
        pdf_root=pdf_root,
        required_metric_ids=("revenue", "cash", "operating_cash_flow"),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert result.dataset_path.exists()
    assert result.turtle_export_path.exists()

    dataset_payload = json.loads(result.dataset_path.read_text(encoding="utf-8"))
    assert dataset_payload["dataset_id"] == "p5_seed_3_issuers_2_years"
    assert dataset_payload["dataset_version"] == "1.0"
    assert dataset_payload["issuer_count"] == 3
    assert dataset_payload["periods"] == [2024, 2025]
    assert len(dataset_payload["source_artifacts"]) == 6
    assert dataset_payload["rows"]
    assert isinstance(dataset_payload["quality_summary"], dict)
    assert all(isinstance(row, dict) for row in dataset_payload["rows"])
    present_rows = [
        row for row in dataset_payload["rows"] if row["missing_status"] == "present"
    ]
    assert present_rows
    assert dataset_payload["quality_summary"]["present_row_count"] == len(present_rows)
    assert {row["issuer_id"] for row in present_rows} == {
        "CN_600519",
        "CN_601919",
        "CN_688008",
    }
    assert {"cash", "revenue"} <= {row["metric_id"] for row in present_rows}
    assert all(row.get("source_fact_id") for row in present_rows)

    turtle_payload = json.loads(result.turtle_export_path.read_text(encoding="utf-8"))
    assert turtle_payload["dataset_id"] == "p5_seed_3_issuers_2_years"
    assert turtle_payload["dataset_version"] == "1.0"
    assert turtle_payload["rows"]
    assert isinstance(turtle_payload["alias_map"], dict)
    first_row = turtle_payload["rows"][0]
    assert isinstance(first_row, dict)
    assert {"canonical_metric_id", "turtle_field"}.issubset(first_row)
    present_turtle_rows = [
        row for row in turtle_payload["rows"] if row.get("missing_status") == "present"
    ]
    assert present_turtle_rows
    assert {row["issuer_id"] for row in present_turtle_rows} == {
        "CN_600519",
        "CN_601919",
        "CN_688008",
    }
