from __future__ import annotations

from financial_report_analysis.p5.lineage import build_dataset_lineage
from financial_report_analysis.p5.models import (
    P5DatasetArtifact,
    P5DatasetRow,
    P5ExtractedArtifact,
    P5ManifestEntry,
)
from financial_report_analysis.p5.turtle_export import build_turtle_export


def test_build_dataset_lineage_links_rows_back_to_artifacts(tmp_path) -> None:
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
    dataset = P5DatasetArtifact(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00",
        issuer_count=1,
        periods=(2025,),
        metrics=("revenue",),
        rows=(
            P5DatasetRow(
                issuer_id="CN_601919",
                market="CN",
                stock_code="601919",
                fiscal_year=2025,
                metric_id="revenue",
                entity_scope="consolidated",
                period_scope="duration",
                statement_type="income_statement",
                value=100.0,
                currency="CNY",
                unit="currency_amount",
                quality_status="ok",
                missing_status="present",
                source_fact_id="fact-1",
                source_artifact_id="CN_601919_2025",
                evidence_bundle_id="bundle-1",
            ),
        ),
        quality_summary={},
        source_artifacts=("CN_601919_2025",),
    )

    lineage = build_dataset_lineage(
        dataset=dataset,
        extracted_artifacts=(artifact,),
        turtle_export=build_turtle_export(dataset),
    )

    assert len(lineage) == 1
    assert lineage[0].dataset_id == "p5_seed"
    assert lineage[0].source_pdf_path == str(pdf_path)
    assert lineage[0].source_fact_id == "fact-1"
    assert lineage[0].manifest_entry_key == entry.entry_key
    assert lineage[0].turtle_field == "revenue"
