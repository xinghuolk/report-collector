from pathlib import Path
from unittest.mock import patch

from src.pdf_parser.content_extractor import PDFContentExtractor


class TestPeriodClassifier:
    def setup_method(self) -> None:
        self.extractor = PDFContentExtractor()

    def test_q4_full_year_results_builds_fy_and_comparison(self) -> None:
        self.extractor.full_text = (
            "ANNOUNCEMENT OF THE 2025 Q4 AND FULL YEAR FINANCIAL RESULTS "
            "year ended December 31, 2025"
        )
        self.extractor.is_english_report = True
        self.extractor.current_pdf_path = Path("/test/2026_quarterly_en.pdf")

        with patch.object(self.extractor, "current_pdf_path") as mock_path:
            mock_path.stat.return_value.st_size = 1024
            mock_path.name = "2026_quarterly_en.pdf"
            with patch("src.pdf_parser.content_extractor.PdfReader") as mock_reader:
                mock_reader.return_value.metadata = None
                mock_reader.return_value.pages = [1]
                metadata = self.extractor._extract_metadata()
                periods = self.extractor._build_periods(metadata)

        period_ids = {period["period_id"] for period in periods}
        assert metadata.report_type == "quarterly"
        assert metadata.primary_period_id == "2025FY"
        assert {"2025FY", "2024FY", "2025Q4_SINGLE"} <= period_ids
        assert "BS_2025-12-31" in period_ids

    def test_q3_results_builds_ytd_and_single(self) -> None:
        self.extractor.full_text = (
            "ANNOUNCEMENT OF THE 2025 Q3 FINANCIAL RESULTS "
            "and nine months ended September 30, 2025"
        )
        self.extractor.is_english_report = True
        self.extractor.current_pdf_path = Path("/test/2025_quarterly_q3_en.pdf")

        with patch.object(self.extractor, "current_pdf_path") as mock_path:
            mock_path.stat.return_value.st_size = 1024
            mock_path.name = "2025_quarterly_q3_en.pdf"
            with patch("src.pdf_parser.content_extractor.PdfReader") as mock_reader:
                mock_reader.return_value.metadata = None
                mock_reader.return_value.pages = [1]
                metadata = self.extractor._extract_metadata()
                periods = self.extractor._build_periods(metadata)

        period_ids = {period["period_id"] for period in periods}
        assert metadata.primary_period_id == "2025Q3_YTD"
        assert {"2025Q3_YTD", "2025Q3_SINGLE", "BS_2025-09-30"} <= period_ids
