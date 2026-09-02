import json
from datetime import datetime, timezone, tzinfo
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from src.pdf_manager import ReportPDF

HKEX_URL = "https://www1.hkexnews.hk/listedco/report.pdf"


class BrokenTimezone(tzinfo):
    def utcoffset(self, dt):
        raise RuntimeError("broken timezone")


@pytest.mark.asyncio
async def test_download_report_uses_exact_hk_url_and_persists_metadata(
    pdf_handler, tmp_path, monkeypatch
):
    downloaded = tmp_path / "2025_annual_en.pdf"
    downloaded.write_bytes(b"%PDF-1.4\nreport")
    download_pdf = AsyncMock(return_value=(True, "下载成功", str(downloaded)))
    extract_pdf_content = AsyncMock()
    monkeypatch.setattr(pdf_handler.hk_downloader, "download_pdf", download_pdf)
    monkeypatch.setattr(pdf_handler, "extract_pdf_content", extract_pdf_content)
    announced_at = datetime(2026, 3, 18, 16, 30, tzinfo=timezone.utc)

    result = await pdf_handler.download_report(
        stock_code="00700",
        market="HK",
        report_type="annual",
        report_url=HKEX_URL,
        report_title="Tencent 2025 Annual Report",
        auto_extract=True,
        report_year=2025,
        language="en",
        announcement_at=announced_at,
        announcement_date="2026-03-18",
    )

    assert result == {
        "success": True,
        "data": {
            "pdf_id": result["data"]["pdf_id"],
            "file_path": str(downloaded),
            "file_name": "2025_annual_en.pdf",
            "stock_code": "00700",
            "market": "HK",
            "report_year": 2025,
            "language": "en",
        },
    }
    assert result["data"]["pdf_id"] is not None
    download_pdf.assert_awaited_once_with(
        HKEX_URL,
        {
            "stock_code": "00700",
            "title": "Tencent 2025 Annual Report",
            "report_type": "annual",
            "year": 2025,
            "language": "en",
            "web_path": HKEX_URL,
            "release_time": "2026-03-18",
            "announcement_at": announced_at,
            "announcement_date": "2026-03-18",
            "market": "SEHK",
        },
    )
    extract_pdf_content.assert_not_awaited()

    async with pdf_handler.pdf_manager.async_session() as session:
        row = await session.scalar(select(ReportPDF))

    assert row is not None
    assert row.id == result["data"]["pdf_id"]
    assert row.stock_code == "00700"
    assert row.market == "HK"
    assert row.report_type == "annual"
    assert row.report_year == 2025
    assert row.original_title == "Tencent 2025 Annual Report"
    assert row.file_path == str(downloaded)
    assert row.file_name == "2025_annual_en.pdf"
    assert row.source_url == HKEX_URL
    assert row.source_name == "港交所披露易"
    metadata = json.loads(row.metadata_json)
    assert metadata == {
        "title": "Tencent 2025 Annual Report",
        "release_time": "2026-03-18",
        "announcement_at": "2026-03-18T16:30:00+00:00",
        "announcement_date": "2026-03-18",
        "web_path": HKEX_URL,
        "period_hint": "2025_fy",
        "language": "en",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "expected_error"),
    [
        ({"stock_code": "0700"}, "港股代码应为5位数字"),
        ({"report_url": None}, "港股报告URL不能为空"),
        (
            {"report_url": "http://www1.hkexnews.hk/listedco/report.pdf"},
            "港股报告URL必须使用HTTPS",
        ),
        (
            {"report_url": "https://www1.hkexnews.hk.evil.test/report.pdf"},
            "港股报告URL必须属于hkexnews.hk",
        ),
        ({"report_year": None}, "港股报告年份不能为空"),
        ({"language": "fr"}, "港股报告语言必须为en或zh"),
    ],
)
async def test_download_report_rejects_invalid_hk_selection(
    pdf_handler, monkeypatch, overrides, expected_error
):
    download_pdf = AsyncMock()
    monkeypatch.setattr(pdf_handler.hk_downloader, "download_pdf", download_pdf)
    arguments = {
        "stock_code": "00700",
        "market": "HK",
        "report_type": "annual",
        "report_url": HKEX_URL,
        "report_title": "Tencent 2025 Annual Report",
        "report_year": 2025,
        "language": "en",
    }
    arguments.update(overrides)

    result = await pdf_handler.download_report(**arguments)

    assert result == {"success": False, "error": expected_error}
    download_pdf.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_report_returns_hk_downloader_failure(
    pdf_handler, monkeypatch
):
    download_pdf = AsyncMock(return_value=(False, "HTTP错误: 503", None))
    monkeypatch.setattr(pdf_handler.hk_downloader, "download_pdf", download_pdf)

    result = await pdf_handler.download_report(
        stock_code="00700",
        market="HK",
        report_type="annual",
        report_url=HKEX_URL,
        report_title="Tencent 2025 Annual Report",
        report_year=2025,
        language="zh",
    )

    assert result == {"success": False, "error": "HTTP错误: 503"}
    async with pdf_handler.pdf_manager.async_session() as session:
        rows = (await session.scalars(select(ReportPDF))).all()
    assert rows == []


@pytest.mark.asyncio
async def test_download_report_does_not_invent_timestamp_from_announcement_date(
    pdf_handler, tmp_path, monkeypatch
):
    downloaded = tmp_path / "2025_annual_zh.pdf"
    downloaded.write_bytes(b"%PDF-1.4\nreport in Chinese")
    download_pdf = AsyncMock(return_value=(True, "下载成功", str(downloaded)))
    monkeypatch.setattr(pdf_handler.hk_downloader, "download_pdf", download_pdf)

    result = await pdf_handler.download_report(
        stock_code="00700",
        market="HK",
        report_type="annual",
        report_url=HKEX_URL,
        report_title="Tencent 2025 Annual Report",
        report_year=2025,
        language="zh",
        announcement_date="2026-03-18",
    )

    async with pdf_handler.pdf_manager.async_session() as session:
        row = await session.get(ReportPDF, result["data"]["pdf_id"])

    assert row is not None
    assert row.announcement_date is None
    metadata = json.loads(row.metadata_json)
    assert metadata["announcement_at"] is None
    assert metadata["announcement_date"] == "2026-03-18"
    report_data = download_pdf.await_args.args[1]
    assert report_data["announcement_at"] is None
    assert report_data["announcement_date"] == "2026-03-18"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "announcement_at",
    [
        pytest.param(datetime(2026, 3, 18, 16, 30), id="naive"),
        pytest.param(
            datetime(2026, 3, 18, 16, 30, tzinfo=BrokenTimezone()),
            id="broken-tzinfo",
        ),
    ],
)
async def test_download_report_rejects_announcement_at_without_valid_offset(
    pdf_handler, monkeypatch, announcement_at
):
    download_pdf = AsyncMock()
    monkeypatch.setattr(pdf_handler.hk_downloader, "download_pdf", download_pdf)

    result = await pdf_handler.download_report(
        stock_code="00700",
        market="HK",
        report_type="annual",
        report_url=HKEX_URL,
        report_title="Tencent 2025 Annual Report",
        report_year=2025,
        language="en",
        announcement_at=announcement_at,
    )

    assert result == {"success": False, "error": "港股公告时间必须包含时区"}
    download_pdf.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_report_fails_when_pdf_metadata_is_not_persisted(
    pdf_handler, tmp_path, monkeypatch
):
    missing_pdf = tmp_path / "missing.pdf"
    download_pdf = AsyncMock(return_value=(True, "下载成功", str(missing_pdf)))
    monkeypatch.setattr(pdf_handler.hk_downloader, "download_pdf", download_pdf)

    result = await pdf_handler.download_report(
        stock_code="00700",
        market="HK",
        report_type="annual",
        report_url=HKEX_URL,
        report_title="Tencent 2025 Annual Report",
        report_year=2025,
        language="en",
    )

    assert result == {"success": False, "error": "PDF元数据保存失败"}
    async with pdf_handler.pdf_manager.async_session() as session:
        rows = (await session.scalars(select(ReportPDF))).all()
    assert rows == []
