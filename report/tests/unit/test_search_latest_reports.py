from datetime import datetime

from src.handlers.pdf_handler import PDFHandler


def test_parse_hk_release_time_with_prefix():
    parsed = PDFHandler._parse_hk_release_time("Release Time:04/02/2026 19:21")
    assert parsed == datetime(2026, 2, 4, 19, 21)


def test_parse_hk_release_time_date_only():
    parsed = PDFHandler._parse_hk_release_time("04/02/2026")
    assert parsed == datetime(2026, 2, 4)


def test_parse_cn_announcement_time_from_timestamp():
    base = datetime(2025, 1, 1, 0, 0, 0)
    report = {"announcement_time": str(int(base.timestamp() * 1000))}
    parsed = PDFHandler._parse_cn_announcement_time(report)
    assert parsed == base


def test_with_publish_time_cn_fallback_date():
    handler = PDFHandler()
    report = {"announcement_date": "2025-12-31"}
    enriched = handler._with_publish_time(report, "CN")
    assert enriched["publish_time"].startswith("2025-12-31")
    assert enriched["publish_timestamp"] > 0
