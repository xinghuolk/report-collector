from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from financial_report_analysis.api.app import create_app


def test_health_endpoint_reports_ready() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_extract_endpoint_requires_pdf_source() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "pdf_path or pdf_url is required"


def test_extract_endpoint_rejects_whitespace_only_sources() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": "   ",
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "pdf_path or pdf_url is required"


def test_extract_endpoint_rejects_both_sources() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": "/tmp/report.pdf",
            "pdf_url": "https://example.com/report.pdf",
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "provide only one of pdf_path or pdf_url"


def test_extract_endpoint_rejects_missing_pdf_path() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": "/tmp/report.pdf",
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "pdf_path does not exist"


def test_extract_endpoint_runs_ingestion_path_for_pdf_input(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from financial_report_analysis.ingestion.pdf_ingestion import PdfIngestionAdapter

    pdf_path = tmp_path / "mock.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

    def fake_extract_text(
        self: PdfIngestionAdapter,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
    ) -> str:
        assert pdf_path == str(pdf_file)
        assert pdf_url is None
        return "2024 Annual Report\nRevenue 1,234 RMB'000\n"

    pdf_file = pdf_path
    monkeypatch.setattr(PdfIngestionAdapter, "_extract_text", fake_extract_text)

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(pdf_path),
            "market": "CN",
            "min_confidence": 0.8,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["quality_gate"] == "pass"
    assert payload["key_facts"]
    assert payload["key_facts"][0]["metric_id"] == "revenue"
    assert payload["key_facts"][0]["numeric_value"] == 1_234_000.0


def test_package_root_does_not_import_api_app_transitively() -> None:
    sys.modules.pop("financial_report_analysis", None)
    sys.modules.pop("financial_report_analysis.api", None)
    sys.modules.pop("financial_report_analysis.api.app", None)

    module = importlib.import_module("financial_report_analysis")

    assert "financial_report_analysis.api.app" not in sys.modules
    assert not hasattr(module, "create_app")
