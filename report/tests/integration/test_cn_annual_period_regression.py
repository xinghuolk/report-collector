import os
from pathlib import Path

import pytest

from src.pdf_parser.content_extractor import PDFContentExtractor


def _resolve_report_root() -> Path:
    worktree_root = Path(__file__).resolve().parents[2]
    if (worktree_root / "downloads").exists():
        return worktree_root

    repo_root = worktree_root.parent.parent.parent
    return repo_root / "report"


def _resolve_cn_annual_pdf() -> Path:
    env_path = os.getenv("CN_ANNUAL_SAMPLE_PDF")
    if env_path:
        return Path(env_path)

    root_dir = _resolve_report_root()
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

    extractor = PDFContentExtractor()
    result = extractor.extract(str(sample_pdf))
    assert result.get("success") is True
    assert extractor.is_english_report is False

    metadata = result.get("metadata", {})
    periods = result.get("periods", [])
    assert metadata.get("report_type") in {"annual", "semi_annual", "quarterly"}
    if metadata.get("report_type") == "annual":
        assert any(period.get("scope") == "full_year" for period in periods)
        assert metadata.get("primary_period_id", "").endswith("FY")
