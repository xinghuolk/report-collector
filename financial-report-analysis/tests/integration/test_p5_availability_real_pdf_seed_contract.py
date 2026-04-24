from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]

ANCHOR_PDF_GLOBS = {
    "HK_01810": "report/downloads/hk_stocks/01810/annual/*annual_en.pdf",
    "HK_09987": "report/downloads/hk_stocks/09987/annual/*annual_en.pdf",
    "CN_601919": "report/downloads/cn_stocks/601919/annual/*年度报告.pdf",
}


@pytest.mark.real_pdf
def test_availability_anchor_pdf_fixtures_exist() -> None:
    missing: list[str] = []
    discovered: dict[str, list[Path]] = {}
    for issuer_id, pattern in ANCHOR_PDF_GLOBS.items():
        matches = sorted(REPO_ROOT.glob(pattern))
        discovered[issuer_id] = matches
        if not matches:
            missing.append(f"{issuer_id}: {pattern}")

    assert not missing, "missing anchor PDFs: " + ", ".join(missing)
    assert any(path.name.startswith("2024") for path in discovered["HK_01810"])
    assert any(path.name.startswith("2025") for path in discovered["HK_09987"])
    assert any(path.name.startswith("2024") for path in discovered["CN_601919"])
