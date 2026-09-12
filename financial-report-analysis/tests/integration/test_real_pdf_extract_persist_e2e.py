from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from financial_report_analysis.api.app import create_app


REPO_ROOT = Path(__file__).resolve().parents[3]
MAIN_REPO_ROOT = REPO_ROOT.parent.parent


@dataclass(frozen=True, slots=True)
class AnnualPdfCase:
    market: str
    stock_code: str
    fiscal_year: int
    filename: str
    report_language: str

    @property
    def issuer_id(self) -> str:
        return f"{self.market}_{self.stock_code}"


DEFAULT_ANNUAL_PDF_CASES = (
    AnnualPdfCase(
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        filename="2025_年度报告.pdf",
        report_language="zh",
    ),
    AnnualPdfCase(
        market="HK",
        stock_code="02498",
        fiscal_year=2022,
        filename="2022_annual_en.pdf",
        report_language="en",
    ),
)


def _selected_cases() -> tuple[AnnualPdfCase, ...]:
    stock_code = os.getenv("FRA_REAL_PDF_E2E_STOCK_CODE")
    if not stock_code:
        return DEFAULT_ANNUAL_PDF_CASES

    market = os.getenv("FRA_REAL_PDF_E2E_MARKET", "CN").upper()
    fiscal_year = int(os.getenv("FRA_REAL_PDF_E2E_FISCAL_YEAR", "2025"))
    filename = os.getenv("FRA_REAL_PDF_E2E_FILENAME")
    if filename is None:
        filename = (
            f"{fiscal_year}_年度报告.pdf"
            if market == "CN"
            else f"{fiscal_year}_annual_en.pdf"
        )
    return (
        AnnualPdfCase(
            market=market,
            stock_code=stock_code,
            fiscal_year=fiscal_year,
            filename=filename,
            report_language="zh" if market == "CN" else "en",
        ),
    )


def _sample_pdf(case: AnnualPdfCase) -> Path | None:
    market_dir = "cn_stocks" if case.market == "CN" else "hk_stocks"
    relative_path = Path(
        "report",
        "downloads",
        market_dir,
        case.stock_code,
        "annual",
        case.filename,
    )
    for root in (REPO_ROOT, MAIN_REPO_ROOT):
        candidate = root / relative_path
        if candidate.exists():
            return candidate
    return None


@pytest.mark.real_pdf
@pytest.mark.slow
@pytest.mark.parametrize("case", _selected_cases(), ids=lambda case: case.issuer_id)
def test_real_pdf_extract_persist_and_readback_e2e(
    case: AnnualPdfCase,
    tmp_path: Path,
) -> None:
    sample_pdf = _sample_pdf(case)
    if sample_pdf is None:
        pytest.skip(
            "real PDF sample not found; set FRA_REAL_PDF_E2E_* to an existing sample"
        )

    client = TestClient(create_app(storage_db_path=tmp_path / "runtime.db"))
    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": str(sample_pdf),
            "market": case.market,
            "min_confidence": 0.8,
            "persist_to_storage": True,
            "issuer_id": case.issuer_id,
            "stock_code": case.stock_code,
            "fiscal_year": case.fiscal_year,
            "report_type": "annual",
            "report_language": case.report_language,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["pdf_path"] == str(sample_pdf)
    assert payload["quality_gate"] in {"pass", "review"}
    assert payload["key_facts"]

    storage = payload["storage"]
    assert storage["persisted"] is True
    assert storage["artifact_id"] == f"{case.issuer_id}_{case.fiscal_year}"

    artifact_response = client.get(storage["artifact_lookup_path"])
    assert artifact_response.status_code == 200
    artifact = artifact_response.json()
    assert artifact["artifact_id"] == storage["artifact_id"]
    assert artifact["manifest_entry"]["issuer_id"] == case.issuer_id
    assert artifact["manifest_entry"]["stock_code"] == case.stock_code
    assert artifact["manifest_entry"]["fiscal_year"] == case.fiscal_year
    assert artifact["canonical_facts"]

    report_response = client.get(storage["report_lookup_path"])
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["report_registered"] is True
    assert report["extracted_artifact_available"] is True
    assert storage["artifact_id"] in report["extracted_artifact_ids"]
