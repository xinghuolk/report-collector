from __future__ import annotations

from io import BytesIO
import re
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader


class PdfIngestionInputError(ValueError):
    """Raised when ingestion input cannot be read as requested."""


class PdfIngestionAdapter:
    _REVENUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        (
            "Revenue",
            re.compile(
                r"\bRevenue\b[^\d\-()]*([0-9][0-9,]*(?:\.\d+)?)",
                re.IGNORECASE,
            ),
        ),
        (
            "Turnover",
            re.compile(
                r"\bTurnover\b[^\d\-()]*([0-9][0-9,]*(?:\.\d+)?)",
                re.IGNORECASE,
            ),
        ),
        (
            "\u8425\u4e1a\u6536\u5165",
            re.compile(
                r"\u8425\u4e1a\u603b?\u6536\u5165[^\d\-()]*([0-9][0-9,]*(?:\.\d+)?)"
            ),
        ),
    )

    def extract_candidate_facts(
        self,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
        market: str | None,
        min_confidence: float | None,
    ) -> dict[str, Any]:
        document_id = pdf_path or pdf_url or "unknown-document"
        text = self._extract_text(pdf_path=pdf_path, pdf_url=pdf_url)
        language = self._detect_language(text, market)
        period_id = self._detect_period_id(text)
        currency = self._detect_currency(text, market)
        raw_unit = self._detect_raw_unit(text)
        confidence = 0.9

        candidate_facts: list[dict[str, Any]] = []
        if period_id is None:
            return {
                "candidate_facts": candidate_facts,
                "document_metadata": {"language": language},
            }

        for index, (label, numeric_value) in enumerate(self._extract_revenue_facts(text), start=1):
            if min_confidence is not None and confidence < min_confidence:
                continue
            candidate_facts.append(
                {
                    "fact_id": f"{document_id}:candidate:{index}",
                    "fact_kind": "candidate",
                    "metric_id": "raw_revenue",
                    "metric_label_raw": label,
                    "statement_type": "income_statement",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": period_id,
                    "currency": currency,
                    "raw_value": str(numeric_value),
                    "numeric_value": numeric_value,
                    "raw_unit": raw_unit,
                    "normalized_unit": None,
                    "precision": self._precision(numeric_value),
                    "confidence": confidence,
                    "extensions": {
                        "market": market or "CN",
                        "accounting_standard": "OTHER",
                    },
                    "document_id": document_id,
                    "block_id": f"{document_id}:block:1",
                    "page_index": 0,
                    "evidence_bundle_id": f"{document_id}:bundle:{index}",
                    "table_coord": None,
                    "extraction_method": "pdf_text_regex",
                    "extraction_version": "v1",
                    "source_rank_hint": 1,
                }
            )

        return {
            "candidate_facts": candidate_facts,
            "document_metadata": {"language": language},
        }

    def _extract_text(self, *, pdf_path: str | None, pdf_url: str | None) -> str:
        if pdf_path:
            path = Path(pdf_path)
            if not path.exists():
                raise PdfIngestionInputError("pdf_path does not exist")
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)

        if pdf_url:
            response = httpx.get(pdf_url, timeout=30.0)
            response.raise_for_status()
            reader = PdfReader(BytesIO(response.content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)

        return ""

    def _extract_revenue_facts(self, text: str) -> list[tuple[str, float]]:
        facts: list[tuple[str, float]] = []
        for label, pattern in self._REVENUE_PATTERNS:
            match = pattern.search(text)
            if match is None:
                continue
            facts.append((label, self._parse_number(match.group(1))))
            break
        return facts

    @staticmethod
    def _detect_period_id(text: str) -> str | None:
        annual_match = re.search(r"\b(20\d{2})\s+Annual Report\b", text, re.IGNORECASE)
        if annual_match:
            return f"{annual_match.group(1)}FY"

        quarter_match = re.search(r"\b(20\d{2})\s*Q([1-4])\b", text, re.IGNORECASE)
        if quarter_match:
            return f"{quarter_match.group(1)}Q{quarter_match.group(2)}"

        chinese_annual = re.search(r"(20\d{2})\u5e74\u5e74\u5ea6\u62a5\u544a", text)
        if chinese_annual:
            return f"{chinese_annual.group(1)}FY"

        chinese_quarter = re.search(
            r"(20\d{2})\u5e74\u7b2c([\u4e00\u4e8c\u4e09\u56db])\u5b63\u5ea6\u62a5\u544a",
            text,
        )
        if chinese_quarter:
            quarter_map = {
                "\u4e00": "1",
                "\u4e8c": "2",
                "\u4e09": "3",
                "\u56db": "4",
            }
            return f"{chinese_quarter.group(1)}Q{quarter_map[chinese_quarter.group(2)]}"

        return None

    @staticmethod
    def _detect_language(text: str, market: str | None) -> str:
        if re.search(r"[\u4e00-\u9fff]", text):
            return "zh-Hant" if market == "HK" else "zh-Hans"
        return "en"

    @staticmethod
    def _detect_currency(text: str, market: str | None) -> str:
        upper_text = text.upper()
        if "HK$" in text or "HKD" in upper_text or "\u6e2f\u5143" in text:
            return "HKD"
        if "US$" in text or "USD" in upper_text or "\u7f8e\u5143" in text:
            return "USD"
        if "RMB" in upper_text or "CNY" in upper_text or "\u4eba\u6c11\u5e01" in text:
            return "CNY"
        if market == "HK":
            return "HKD"
        if market == "US":
            return "USD"
        return "CNY"

    @staticmethod
    def _detect_raw_unit(text: str) -> str | None:
        thousand_match = re.search(
            r"(RMB|CNY|USD|HKD|HK\$|US\$)\s*['` ]?0{3}",
            text,
            re.IGNORECASE,
        )
        if thousand_match:
            currency = thousand_match.group(1).upper().replace("$", "")
            return f"{currency}'000"
        if "\u4ebf\u5143" in text or "\u4ebf" in text:
            return "\u4ebf\u5143"
        if "\u767e\u4e07\u5143" in text or "\u767e\u4e07" in text:
            return "\u767e\u4e07\u5143"
        if "\u4e07\u5143" in text:
            return "\u4e07\u5143"
        return None

    @staticmethod
    def _parse_number(raw_number: str) -> float:
        return float(raw_number.replace(",", ""))

    @staticmethod
    def _precision(numeric_value: float) -> int:
        text = f"{numeric_value}"
        if "." not in text:
            return 0
        return len(text.split(".", maxsplit=1)[1].rstrip("0"))
