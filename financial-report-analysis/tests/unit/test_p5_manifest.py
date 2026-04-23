from __future__ import annotations

import json
from pathlib import Path

import pytest

from financial_report_analysis.p5.manifest import load_manifest
from financial_report_analysis.p5.models import P5ManifestValidationError


def test_load_manifest_accepts_three_issuer_seed(tmp_path: Path) -> None:
    pdf_a = tmp_path / "601919_2025.pdf"
    pdf_b = tmp_path / "02498_2022.pdf"
    pdf_c = tmp_path / "09987_2025.pdf"
    for path in (pdf_a, pdf_b, pdf_c):
        path.write_bytes(b"%PDF-1.4\n")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "p5_seed_3_issuers",
                "manifest_version": "1.0",
                "entries": [
                    {
                        "issuer_id": "CN_601919",
                        "market": "CN",
                        "stock_code": "601919",
                        "company_name": "中远海控",
                        "fiscal_year": 2025,
                        "report_type": "annual",
                        "pdf_path": str(pdf_a),
                        "source": "report",
                        "report_language": "zh",
                    },
                    {
                        "issuer_id": "HK_02498",
                        "market": "HK",
                        "stock_code": "02498",
                        "fiscal_year": 2022,
                        "report_type": "annual",
                        "pdf_path": str(pdf_b),
                        "source": "report",
                        "report_language": "en",
                    },
                    {
                        "issuer_id": "HK_09987",
                        "market": "HK",
                        "stock_code": "09987",
                        "fiscal_year": 2025,
                        "report_type": "annual",
                        "pdf_path": str(pdf_c),
                        "source": "report",
                        "report_language": "en",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manifest = load_manifest(manifest_path)

    assert manifest.manifest_id == "p5_seed_3_issuers"
    assert len(manifest.entries) == 3
    assert manifest.entries[0].artifact_id == "CN_601919_2025"
    assert manifest.entries[1].market == "HK"
    assert manifest.entries[2].pdf_path == pdf_c


def test_load_manifest_rejects_missing_pdf_path(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "bad",
                "manifest_version": "1.0",
                "entries": [
                    {
                        "issuer_id": "CN_601919",
                        "market": "CN",
                        "stock_code": "601919",
                        "fiscal_year": 2025,
                        "report_type": "annual",
                        "pdf_path": str(tmp_path / "missing.pdf"),
                        "source": "report",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(P5ManifestValidationError, match="pdf_path does not exist"):
        load_manifest(manifest_path)


def test_load_manifest_rejects_duplicate_entry_key(tmp_path: Path) -> None:
    pdf_path = tmp_path / "601919_2025.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    entry = {
        "issuer_id": "CN_601919",
        "market": "CN",
        "stock_code": "601919",
        "fiscal_year": 2025,
        "report_type": "annual",
        "pdf_path": str(pdf_path),
        "source": "report",
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "bad",
                "manifest_version": "1.0",
                "entries": [entry, dict(entry)],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(P5ManifestValidationError, match="duplicate manifest entry"):
        load_manifest(manifest_path)


def test_load_manifest_resolves_relative_pdf_path_from_pdf_root(
    tmp_path: Path,
) -> None:
    pdf_root = tmp_path / "repo"
    pdf_path = (
        pdf_root / "report" / "downloads" / "cn_stocks" / "601919" / "annual" / "2025.pdf"
    )
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4\n")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "relative",
                "manifest_version": "1.0",
                "entries": [
                    {
                        "issuer_id": "CN_601919",
                        "market": "CN",
                        "stock_code": "601919",
                        "fiscal_year": 2025,
                        "report_type": "annual",
                        "pdf_path": "report/downloads/cn_stocks/601919/annual/2025.pdf",
                        "source": "report",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = load_manifest(manifest_path, pdf_root=pdf_root)

    assert manifest.entries[0].pdf_path == pdf_path


def test_load_manifest_rejects_non_annual_report_type(tmp_path: Path) -> None:
    pdf_path = tmp_path / "601919_2025_q3.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "bad",
                "manifest_version": "1.0",
                "entries": [
                    {
                        "issuer_id": "CN_601919",
                        "market": "CN",
                        "stock_code": "601919",
                        "fiscal_year": 2025,
                        "report_type": "quarterly",
                        "pdf_path": str(pdf_path),
                        "source": "report",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(P5ManifestValidationError, match="unsupported report_type"):
        load_manifest(manifest_path)
