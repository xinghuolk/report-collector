from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from financial_report_analysis.p5.artifact_repository import P5JsonArtifactRepository
from financial_report_analysis.p5.lineage import build_dataset_lineage
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
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


TESTS_ROOT = Path(__file__).resolve().parents[1]


def _load_seed_manifest() -> dict[str, object]:
    manifest_path = TESTS_ROOT / "fixtures" / "p5_seed_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _latest_entry_per_issuer(entries: list[object]) -> list[dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    for entry in entries:
        assert isinstance(entry, dict)
        issuer_id = str(entry["issuer_id"])
        current = latest.get(issuer_id)
        if current is None or int(entry["fiscal_year"]) > int(current["fiscal_year"]):
            latest[issuer_id] = entry
    return [latest[issuer_id] for issuer_id in sorted(latest)]


def _entry_from_seed(raw_entry: dict[str, object], tmp_path: Path) -> P5ManifestEntry:
    issuer_id = str(raw_entry["issuer_id"])
    fiscal_year = int(raw_entry["fiscal_year"])
    pdf_path = tmp_path / "pdfs" / f"{issuer_id}_{fiscal_year}.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4\n")
    return P5ManifestEntry(
        issuer_id=issuer_id,
        market=raw_entry["market"],
        stock_code=str(raw_entry["stock_code"]),
        fiscal_year=fiscal_year,
        report_type=raw_entry["report_type"],
        pdf_path=pdf_path,
        source=str(raw_entry["source"]),
        company_name=str(raw_entry["company_name"]),
        report_language=str(raw_entry["report_language"]),
    )


def _artifact(entry: P5ManifestEntry) -> P5ExtractedArtifact:
    canonical_facts: tuple[dict[str, Any], ...]
    missing_status: dict[str, dict[str, str]]
    if entry.issuer_id == "CN_601919":
        canonical_facts = (
            {
                "fact_id": f"{entry.artifact_id}:revenue",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "numeric_value": float(entry.fiscal_year),
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": f"{entry.artifact_id}:revenue:evidence",
                "extensions": {"period_scope": "duration"},
            },
        )
        missing_status = {}
    else:
        canonical_facts = ()
        missing_status = {
            "working_capital_missing_status": {"accounts_receiv": "not_surfaced"},
            "cash_health_missing_status": {"restricted_cash": "unknown"},
        }

    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={
            "document_id": str(entry.pdf_path),
            "pdf_path": str(entry.pdf_path),
        },
        document_metadata={},
        candidate_facts=(),
        canonical_facts=canonical_facts,
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass" if canonical_facts else "review",
        missing_status=missing_status,
        created_at="2026-04-23T00:00:00",
    )


def test_p5_recompute_review_flow_uses_persisted_artifacts(
    tmp_path: Path,
) -> None:
    payload = _load_seed_manifest()
    entries = payload["entries"]
    assert isinstance(entries, list)
    focused_entries = tuple(
        _entry_from_seed(raw_entry, tmp_path)
        for raw_entry in _latest_entry_per_issuer(entries)
    )

    manifest_path = tmp_path / "p5_recompute_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "p5_seed_3_issuers_latest_years",
                "dataset_id": "p5_seed_review_flow",
                "manifest_version": payload["manifest_version"],
                "entries": [
                    {
                        "issuer_id": entry.issuer_id,
                        "market": entry.market,
                        "stock_code": entry.stock_code,
                        "company_name": entry.company_name,
                        "fiscal_year": entry.fiscal_year,
                        "report_type": entry.report_type,
                        "pdf_path": str(entry.pdf_path),
                        "source": entry.source,
                        "report_language": entry.report_language,
                    }
                    for entry in focused_entries
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    repository = P5JsonArtifactRepository(tmp_path / "p5")
    for entry in focused_entries:
        repository.save_extracted_artifact(_artifact(entry))

    def fail_if_pdf_extraction_is_called(entry: P5ManifestEntry) -> P5ExtractedArtifact:
        raise AssertionError(f"unexpected PDF extraction for {entry.artifact_id}")

    initial = run_p5_dataset_build(
        manifest_path=manifest_path,
        artifact_root=tmp_path / "p5",
        dataset_id="p5_seed_review_flow",
        required_metric_ids=("revenue", "cash", "operating_cash_flow"),
        build_artifact_func=fail_if_pdf_extraction_is_called,
        now_func=lambda: "2026-04-23T00:00:00",
    )
    plan = build_recompute_plan(
        manifest_id="p5_seed_3_issuers_latest_years",
        dataset_id="p5_seed_review_flow",
        extracted_artifact_ids=initial.extracted_artifact_ids,
        reason="manual_review_check",
    )
    recomputed = execute_recompute_plan(
        plan=plan,
        manifest_path=manifest_path,
        artifact_root=tmp_path / "p5",
        pdf_root=None,
    )

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
