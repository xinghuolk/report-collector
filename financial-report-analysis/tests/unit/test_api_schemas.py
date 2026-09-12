from __future__ import annotations

import pytest
from pydantic import ValidationError

from financial_report_analysis.api.schemas import AnalysisExtractRequest


def test_build_dataset_requires_persist_to_storage() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AnalysisExtractRequest(
            pdf_path="/tmp/report.pdf",
            market="CN",
            build_dataset=True,
        )

    assert "build_dataset requires persist_to_storage=true" in str(exc_info.value)


def test_build_turtle_requires_persist_to_storage() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AnalysisExtractRequest(
            pdf_path="/tmp/report.pdf",
            market="CN",
            build_turtle=True,
        )

    assert "build_turtle requires persist_to_storage=true" in str(exc_info.value)


def test_build_turtle_is_accepted_without_repeating_build_dataset() -> None:
    request = AnalysisExtractRequest(
        pdf_path="/tmp/report.pdf",
        market="CN",
        persist_to_storage=True,
        build_turtle=True,
        issuer_id="CN_601919",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
    )

    assert request.build_dataset is False
    assert request.build_turtle is True
