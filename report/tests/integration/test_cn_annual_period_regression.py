import os
from pathlib import Path

import pytest

from src.pdf_parser.content_extractor import PDFContentExtractor


def _resolve_cn_annual_pdf() -> Path:
    env_path = os.getenv("CN_ANNUAL_SAMPLE_PDF")
    if env_path:
        return Path(env_path)

    root_dir = Path(__file__).resolve().parents[2]
    candidates = sorted((root_dir / "downloads" / "cn_stocks").glob("*/annual/*.pdf"))
    if candidates:
        return candidates[0]
    return Path("__missing_cn_annual_sample__.pdf")


@pytest.mark.integration
def test_cn_annual_period_regression() -> None:
    sample_pdf = _resolve_cn_annual_pdf()
    if not sample_pdf or not sample_pdf.exists():
        pytest.skip(
            "No CN annual sample PDF found. "
            "Set CN_ANNUAL_SAMPLE_PDF or place one under downloads/cn_stocks/*/annual/"
        )

    result = PDFContentExtractor().extract(str(sample_pdf))
    assert result.get("success") is True

    metadata = result.get("metadata", {})
    periods = result.get("periods", [])
    assert metadata.get("report_type") in {"annual", "semi_annual", "quarterly"}
    if metadata.get("report_type") == "annual":
        assert any(period.get("scope") == "full_year" for period in periods)
