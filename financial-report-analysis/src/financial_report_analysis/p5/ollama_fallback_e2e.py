from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True, slots=True)
class OllamaFallbackE2ECase:
    market: str
    stock_code: str
    fiscal_year: int
    report_type: str
    filename: str
    expected_metric_ids: tuple[str, ...] = ()
    expected_fallback_metric_ids: tuple[str, ...] = ()

    @property
    def relative_pdf_parts(self) -> tuple[str, str, str, str]:
        market_dir = "cn_stocks" if self.market == "CN" else "hk_stocks"
        return (market_dir, self.stock_code, self.report_type, self.filename)

    @property
    def issuer_id(self) -> str:
        return f"{self.market}_{self.stock_code}"


DEFAULT_OLLAMA_FALLBACK_E2E_CASE = OllamaFallbackE2ECase(
    market="HK",
    stock_code="09987",
    fiscal_year=2025,
    report_type="quarterly",
    filename="2025_quarterly_q3_en.pdf",
)


def selected_ollama_fallback_e2e_case() -> OllamaFallbackE2ECase:
    stock_code = os.getenv("FRA_OLLAMA_FALLBACK_E2E_STOCK_CODE")
    if not stock_code:
        return DEFAULT_OLLAMA_FALLBACK_E2E_CASE

    market = os.getenv("FRA_OLLAMA_FALLBACK_E2E_MARKET", "HK").upper()
    report_type = os.getenv("FRA_OLLAMA_FALLBACK_E2E_REPORT_TYPE", "annual")
    fiscal_year = int(os.getenv("FRA_OLLAMA_FALLBACK_E2E_FISCAL_YEAR", "2025"))
    filename = os.getenv("FRA_OLLAMA_FALLBACK_E2E_FILENAME")
    if filename is None:
        filename = (
            f"{fiscal_year}_年度报告.pdf"
            if market == "CN"
            else f"{fiscal_year}_annual_en.pdf"
        )

    return OllamaFallbackE2ECase(
        market=market,
        stock_code=stock_code,
        fiscal_year=fiscal_year,
        report_type=report_type,
        filename=filename,
        expected_metric_ids=_csv_env("FRA_OLLAMA_FALLBACK_E2E_EXPECTED_METRIC_IDS"),
        expected_fallback_metric_ids=_csv_env(
            "FRA_OLLAMA_FALLBACK_E2E_EXPECTED_FALLBACK_METRIC_IDS"
        ),
    )


def _csv_env(name: str) -> tuple[str, ...]:
    raw_value = os.getenv(name)
    if raw_value is None:
        return ()
    return tuple(
        item.strip()
        for item in raw_value.split(",")
        if item.strip()
    )
