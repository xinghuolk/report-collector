from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from financial_report_analysis.p5.artifact_repository import P5JsonArtifactRepository
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.p5.runner import run_p5_dataset_build


TESTS_ROOT = Path(__file__).resolve().parents[1]


def _load_seed_entries(tmp_path: Path) -> tuple[P5ManifestEntry, ...]:
    payload = json.loads(
        (TESTS_ROOT / "fixtures" / "p5_seed_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    entries: list[P5ManifestEntry] = []
    for raw_entry in payload["entries"]:
        assert isinstance(raw_entry, dict)
        issuer_id = str(raw_entry["issuer_id"])
        fiscal_year = int(raw_entry["fiscal_year"])
        pdf_path = tmp_path / "pdfs" / f"{issuer_id}_{fiscal_year}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"%PDF-1.4\n")
        entries.append(
            P5ManifestEntry(
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
        )
    return tuple(entries)


def _write_manifest(path: Path, entries: tuple[P5ManifestEntry, ...]) -> None:
    path.write_text(
        json.dumps(
            {
                "manifest_id": "p5_seed_3_issuers_available_years",
                "dataset_id": "p5_seed_3_issuers_available_years",
                "manifest_version": "1.0",
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
                    for entry in entries
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
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
            {
                "fact_id": f"{entry.artifact_id}:cash",
                "metric_id": "cash",
                "statement_type": "balance_sheet",
                "entity_scope": "consolidated",
                "numeric_value": float(entry.fiscal_year * 10),
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": f"{entry.artifact_id}:cash:evidence",
                "extensions": {"period_scope": "point_in_time"},
            },
        )
        missing_status = {
            "cash_health_missing_status": {"restricted_cash": "not_surfaced"}
        }
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


def test_p5_seed_dataset_builds_from_persisted_extracted_artifacts(
    tmp_path: Path,
) -> None:
    entries = _load_seed_entries(tmp_path)
    manifest_path = tmp_path / "p5_seed_manifest.json"
    artifact_root = tmp_path / "p5"
    _write_manifest(manifest_path, entries)
    repository = P5JsonArtifactRepository(artifact_root)
    for entry in entries:
        repository.save_extracted_artifact(_artifact(entry))

    def fail_if_pdf_extraction_is_called(entry: P5ManifestEntry) -> P5ExtractedArtifact:
        raise AssertionError(f"unexpected PDF extraction for {entry.artifact_id}")

    result = run_p5_dataset_build(
        manifest_path=manifest_path,
        artifact_root=artifact_root,
        dataset_id="p5_seed_3_issuers_available_years",
        required_metric_ids=("revenue", "cash", "operating_cash_flow"),
        build_artifact_func=fail_if_pdf_extraction_is_called,
        now_func=lambda: "2026-04-23T00:00:00",
    )

    dataset = repository.load_dataset_artifact("p5_seed_3_issuers_available_years")
    turtle_export = repository.load_turtle_export("p5_seed_3_issuers_available_years")

    assert result.extracted_artifact_ids == tuple(entry.artifact_id for entry in entries)
    assert dataset.issuer_count == 3
    assert dataset.periods == (2020, 2021, 2022, 2023, 2024, 2025)
    assert len(dataset.source_artifacts) == 13
    assert {row.issuer_id for row in dataset.rows} == {
        "CN_601919",
        "HK_01810",
        "HK_09987",
    }
    assert dataset.quality_summary["present_row_count"] == 6
    assert dataset.quality_summary["missing_by_issuer"]["HK_01810"] > 0
    assert dataset.quality_summary["missing_by_issuer"]["HK_09987"] > 0
    assert all(
        row.source_fact_id
        for row in dataset.rows
        if row.missing_status == "present"
    )
    assert turtle_export.dataset_id == dataset.dataset_id
    assert len(turtle_export.rows) == len(dataset.rows)
