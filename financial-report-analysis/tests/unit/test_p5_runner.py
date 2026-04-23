from __future__ import annotations

import json
from pathlib import Path

import pytest

from financial_report_analysis.p5.artifact_repository import (
    P5ArtifactRepositoryError,
    P5JsonArtifactRepository,
)
from financial_report_analysis.p5.models import (
    P5ExtractedArtifact,
    P5ManifestEntry,
    P5TurtleExport,
)
from financial_report_analysis.p5.runner import main, run_p5_dataset_build


def _entry(tmp_path: Path, *, fiscal_year: int = 2025) -> P5ManifestEntry:
    pdf_path = tmp_path / f"report_{fiscal_year}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    return P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=fiscal_year,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
        company_name="中远海控",
        report_language="zh",
    )


def _artifact(entry: P5ManifestEntry) -> P5ExtractedArtifact:
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
        canonical_facts=(
            {
                "fact_id": f"{entry.artifact_id}-revenue",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "numeric_value": 100.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-1",
                "extensions": {"period_scope": "duration"},
            },
        ),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={},
        created_at="2026-04-23T00:00:00",
    )


def test_run_p5_dataset_build_reuses_existing_extracted_artifact_and_persists_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    entry = _entry(tmp_path)
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "p5_seed",
                "manifest_version": "1.0",
                "entries": [
                    {
                        "issuer_id": entry.issuer_id,
                        "market": entry.market,
                        "stock_code": entry.stock_code,
                        "fiscal_year": entry.fiscal_year,
                        "report_type": entry.report_type,
                        "pdf_path": str(entry.pdf_path),
                        "source": entry.source,
                        "company_name": entry.company_name,
                        "report_language": entry.report_language,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    repository = P5JsonArtifactRepository(tmp_path / "data" / "p5")
    repository.save_extracted_artifact(_artifact(entry))

    calls = {"build": 0, "write_json": []}
    original_write_json = P5JsonArtifactRepository._write_json

    def tracked_write_json(path: Path, payload: dict[str, object]) -> Path:
        calls["write_json"].append(path)
        return original_write_json(path, payload)

    def build_artifact_func(entry_arg: P5ManifestEntry) -> P5ExtractedArtifact:
        calls["build"] += 1
        return _artifact(entry_arg)

    monkeypatch.setattr(
        P5JsonArtifactRepository,
        "_write_json",
        staticmethod(tracked_write_json),
    )
    result = run_p5_dataset_build(
        manifest_path=manifest_path,
        artifact_root=tmp_path / "data" / "p5",
        dataset_id="p5_seed",
        build_artifact_func=build_artifact_func,
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert calls["build"] == 0
    assert [path.name for path in calls["write_json"]] == [
        "p5_seed.json",
        "p5_seed_turtle_export.json",
    ]
    assert result.manifest_id == "p5_seed"
    assert result.extracted_artifact_ids == (entry.artifact_id,)
    assert result.dataset_path.exists()
    assert result.turtle_export_path.exists()

    dataset_payload = json.loads(result.dataset_path.read_text(encoding="utf-8"))
    assert dataset_payload["dataset_id"] == "p5_seed"
    assert dataset_payload["issuer_count"] == 1
    assert dataset_payload["source_artifacts"] == [entry.artifact_id]

    turtle_payload = json.loads(result.turtle_export_path.read_text(encoding="utf-8"))
    assert turtle_payload["dataset_id"] == "p5_seed"
    assert turtle_payload["rows"][0]["canonical_metric_id"] == "revenue"
    assert turtle_payload["rows"][0]["turtle_field"] == "revenue"


def test_run_p5_dataset_build_builds_missing_extracted_artifact(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    entry = _entry(tmp_path)
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "p5_seed",
                "manifest_version": "1.0",
                "entries": [
                    {
                        "issuer_id": entry.issuer_id,
                        "market": entry.market,
                        "stock_code": entry.stock_code,
                        "fiscal_year": entry.fiscal_year,
                        "report_type": entry.report_type,
                        "pdf_path": str(entry.pdf_path),
                        "source": entry.source,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    calls = {"build": 0}

    def build_artifact_func(entry_arg: P5ManifestEntry) -> P5ExtractedArtifact:
        calls["build"] += 1
        return _artifact(entry_arg)

    result = run_p5_dataset_build(
        manifest_path=manifest_path,
        artifact_root=tmp_path / "data" / "p5",
        dataset_id="p5_seed",
        build_artifact_func=build_artifact_func,
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert calls["build"] == 1
    assert result.dataset_path.exists()
    assert result.turtle_export_path.exists()
    assert P5JsonArtifactRepository(tmp_path / "data" / "p5").extracted_artifact_exists(
        entry.artifact_id
    )


def test_run_p5_dataset_build_rebuilds_cached_artifact_when_manifest_pdf_changes(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    cached_entry = _entry(tmp_path)
    updated_pdf_path = tmp_path / "report_2025_updated.pdf"
    updated_pdf_path.write_bytes(b"%PDF-1.4\n")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "p5_seed",
                "manifest_version": "1.0",
                "entries": [
                    {
                        "issuer_id": cached_entry.issuer_id,
                        "market": cached_entry.market,
                        "stock_code": cached_entry.stock_code,
                        "fiscal_year": cached_entry.fiscal_year,
                        "report_type": cached_entry.report_type,
                        "pdf_path": str(updated_pdf_path),
                        "source": cached_entry.source,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    repository = P5JsonArtifactRepository(tmp_path / "data" / "p5")
    repository.save_extracted_artifact(_artifact(cached_entry))

    calls = {"build": 0}

    def build_artifact_func(entry_arg: P5ManifestEntry) -> P5ExtractedArtifact:
        calls["build"] += 1
        built = _artifact(entry_arg)
        return built

    result = run_p5_dataset_build(
        manifest_path=manifest_path,
        artifact_root=tmp_path / "data" / "p5",
        dataset_id="p5_seed",
        build_artifact_func=build_artifact_func,
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert calls["build"] == 1
    reloaded = repository.load_extracted_artifact(cached_entry.artifact_id)
    assert reloaded.source_pdf_path == updated_pdf_path
    assert reloaded.manifest_entry.pdf_path == updated_pdf_path
    assert result.extracted_artifact_ids == (cached_entry.artifact_id,)


def test_run_p5_dataset_build_rejects_unsafe_turtle_export_dataset_id(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    entry = _entry(tmp_path)
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "p5_seed",
                "manifest_version": "1.0",
                "entries": [
                    {
                        "issuer_id": entry.issuer_id,
                        "market": entry.market,
                        "stock_code": entry.stock_code,
                        "fiscal_year": entry.fiscal_year,
                        "report_type": entry.report_type,
                        "pdf_path": str(entry.pdf_path),
                        "source": entry.source,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def build_turtle_export_func(_dataset) -> P5TurtleExport:
        return P5TurtleExport(
            dataset_id="../outside",
            dataset_version="1.0",
            created_at="2026-04-23T00:00:00",
            rows=(),
            alias_map={},
        )

    with pytest.raises(P5ArtifactRepositoryError, match="unsafe dataset_id"):
        run_p5_dataset_build(
            manifest_path=manifest_path,
            artifact_root=tmp_path / "data" / "p5",
            dataset_id="p5_seed",
            build_artifact_func=_artifact,
            build_turtle_export_func=build_turtle_export_func,
            now_func=lambda: "2026-04-23T00:00:00",
        )


def test_main_wires_cli_arguments_and_prints_result(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    artifact_root = tmp_path / "data" / "p5"
    entry = _entry(tmp_path)
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "p5_seed",
                "manifest_version": "1.0",
                "entries": [
                    {
                        "issuer_id": entry.issuer_id,
                        "market": entry.market,
                        "stock_code": entry.stock_code,
                        "fiscal_year": entry.fiscal_year,
                        "report_type": entry.report_type,
                        "pdf_path": str(entry.pdf_path),
                        "source": entry.source,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def fake_run_p5_dataset_build(**kwargs):
        assert kwargs["manifest_path"] == manifest_path
        assert kwargs["artifact_root"] == artifact_root
        assert kwargs["dataset_id"] == "p5_seed"
        assert kwargs["pdf_root"] == tmp_path
        assert kwargs["required_metric_ids"] == ("revenue", "cash")
        return type(
            "Result",
            (),
            {
                "manifest_id": "p5_seed",
                "extracted_artifact_ids": (entry.artifact_id,),
                "dataset_path": artifact_root / "datasets" / "p5_seed.json",
                "turtle_export_path": artifact_root
                / "datasets"
                / "p5_seed_turtle_export.json",
            },
        )()

    monkeypatch.setattr(
        "financial_report_analysis.p5.runner.run_p5_dataset_build",
        fake_run_p5_dataset_build,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "financial-report-analysis-p5",
            "--manifest",
            str(manifest_path),
            "--dataset-id",
            "p5_seed",
            "--artifact-root",
            str(artifact_root),
            "--pdf-root",
            str(tmp_path),
            "--required-metric-id",
            "revenue",
            "--required-metric-id",
            "cash",
        ],
    )

    main()

    stdout = json.loads(capsys.readouterr().out)
    assert stdout["manifest_id"] == "p5_seed"
    assert stdout["extracted_artifact_ids"] == [entry.artifact_id]
