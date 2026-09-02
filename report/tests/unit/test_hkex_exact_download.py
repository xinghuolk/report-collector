import json
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from src.pdf_manager import ReportPDF
from src.pdf_sources.hkex_downloader import HKEXDownloader

PDF_ONE = b"%PDF-1.4\nfirst report"
PDF_TWO = b"%PDF-1.7\nsecond report"


class StubResponse:
    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status = status
        self.body = body
        self.read_count = 0

    async def read(self) -> bytes:
        self.read_count += 1
        return self.body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class StubSession:
    def __init__(self, responses: list[StubResponse]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, dict[str, object]]] = []

    def get(self, url: str, **kwargs: object) -> StubResponse:
        self.requests.append((url, kwargs))
        return self.responses.pop(0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


@pytest.fixture
def downloader(tmp_path: Path) -> HKEXDownloader:
    return HKEXDownloader(
        download_dir=str(tmp_path / "downloads"),
        db_path=str(tmp_path / "hkex.db"),
    )


def report_data(url: str) -> dict[str, object]:
    return {
        "stock_code": "00700",
        "title": "Tencent 2025 Annual Report",
        "report_type": "annual",
        "year": 2025,
        "language": "en",
        "web_path": url,
        "market": "SEHK",
    }


def install_http_stub(
    monkeypatch: pytest.MonkeyPatch, responses: list[StubResponse]
) -> StubSession:
    session = StubSession(responses)
    monkeypatch.setattr(
        "src.pdf_sources.hkex_downloader.aiohttp.ClientSession",
        lambda **kwargs: session,
    )
    return session


@pytest.mark.asyncio
async def test_exact_download_disambiguates_same_filename_by_source_url(
    downloader: HKEXDownloader, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_url = "https://www1.hkexnews.hk/listedco/first.pdf"
    second_url = "https://www1.hkexnews.hk/listedco/second.pdf"
    session = install_http_stub(
        monkeypatch,
        [StubResponse(200, PDF_ONE), StubResponse(200, PDF_TWO)],
    )

    first = await downloader.download_pdf(first_url, report_data(first_url), exact=True)
    second = await downloader.download_pdf(
        second_url, report_data(second_url), exact=True
    )

    assert first[0] is True
    assert second[0] is True
    first_path = Path(first[2] or "")
    second_path = Path(second[2] or "")
    assert first_path.name == "2025_annual_en.pdf"
    assert second_path.name == "2025_annual_en_e8e97fbaf899.pdf"
    assert first_path != second_path
    assert first_path.read_bytes() == PDF_ONE
    assert second_path.read_bytes() == PDF_TWO
    assert [request[0] for request in session.requests] == [first_url, second_url]
    assert all(request[1]["allow_redirects"] is False for request in session.requests)

    rows = downloader.get_downloaded_reports(stock_code="00700")
    assert {(row["web_path"], row["_file_path"]) for row in rows} == {
        (first_url, str(first_path)),
        (second_url, str(second_path)),
    }


@pytest.mark.asyncio
async def test_exact_download_respects_stale_conventional_path_provenance(
    downloader: HKEXDownloader, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_url = "https://www1.hkexnews.hk/listedco/first.pdf"
    second_url = "https://www1.hkexnews.hk/listedco/second.pdf"
    install_http_stub(
        monkeypatch,
        [StubResponse(200, PDF_ONE), StubResponse(200, PDF_TWO)],
    )
    first = await downloader.download_pdf(first_url, report_data(first_url), exact=True)
    first_path = Path(first[2] or "")
    first_path.unlink()

    second = await downloader.download_pdf(
        second_url, report_data(second_url), exact=True
    )

    second_path = Path(second[2] or "")
    assert second_path.name == "2025_annual_en_e8e97fbaf899.pdf"
    assert second_path.read_bytes() == PDF_TWO
    rows = downloader.get_downloaded_reports(stock_code="00700")
    assert {(row["web_path"], row["_file_path"]) for row in rows} == {
        (first_url, str(first_path)),
        (second_url, str(second_path)),
    }


@pytest.mark.asyncio
async def test_exact_download_reuses_valid_pdf_for_same_url(
    downloader: HKEXDownloader, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://www1.hkexnews.hk/listedco/report.pdf"
    session = install_http_stub(monkeypatch, [StubResponse(200, PDF_ONE)])

    first = await downloader.download_pdf(url, report_data(url), exact=True)
    second = await downloader.download_pdf(url, report_data(url), exact=True)

    assert first[0] is True
    assert second == (True, "文件已存在", first[2])
    assert Path(first[2] or "").read_bytes() == PDF_ONE
    assert len(session.requests) == 1
    assert len(downloader.get_downloaded_reports(stock_code="00700")) == 1


@pytest.mark.asyncio
async def test_exact_download_rejects_redirect_without_following_it(
    downloader: HKEXDownloader, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://www1.hkexnews.hk/listedco/redirect.pdf"
    response = StubResponse(302)
    session = install_http_stub(monkeypatch, [response])

    result = await downloader.download_pdf(url, report_data(url), exact=True)

    assert result == (False, "HTTP錯誤: 302", None)
    assert session.requests == [(url, {"allow_redirects": False})]
    assert response.read_count == 0
    assert list(downloader.download_dir.rglob("*.pdf")) == []
    assert list(downloader.download_dir.rglob("*.tmp")) == []
    assert downloader.get_downloaded_reports() == []


@pytest.mark.asyncio
async def test_exact_download_rejects_non_pdf_body_without_artifacts(
    downloader: HKEXDownloader, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://www1.hkexnews.hk/listedco/report.pdf"
    install_http_stub(monkeypatch, [StubResponse(200, b"<html>not a PDF</html>")])

    result = await downloader.download_pdf(url, report_data(url), exact=True)

    assert result == (False, "響應內容不是PDF", None)
    assert list(downloader.download_dir.rglob("*.pdf")) == []
    assert list(downloader.download_dir.rglob("*.tmp")) == []
    assert downloader.get_downloaded_reports() == []


@pytest.mark.asyncio
async def test_default_download_preserves_legacy_http_200_body_behavior(
    downloader: HKEXDownloader, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://www1.hkexnews.hk/listedco/report.pdf"
    body = b"legacy downloader body"
    session = install_http_stub(monkeypatch, [StubResponse(200, body)])

    result = await downloader.download_pdf(url, report_data(url))

    assert result[0] is True
    assert Path(result[2] or "").read_bytes() == body
    assert session.requests == [(url, {})]
    assert len(downloader.get_downloaded_reports(stock_code="00700")) == 1


@pytest.mark.parametrize(
    ("raw_announcement_at", "expected_utc", "expected_operational"),
    [
        (
            "2026-03-18T16:30:00Z",
            "2026-03-18T16:30:00Z",
            datetime(2026, 3, 18, 16, 30),
        ),
        (
            "2026-03-18T16:30:00+08:00",
            "2026-03-18T08:30:00Z",
            datetime(2026, 3, 18, 8, 30),
        ),
    ],
    ids=["z", "positive-offset"],
)
@pytest.mark.asyncio
async def test_handler_preserves_raw_timestamp_and_stores_utc_operational_time(
    pdf_handler,
    monkeypatch: pytest.MonkeyPatch,
    raw_announcement_at: str,
    expected_utc: str,
    expected_operational: datetime,
) -> None:
    url = "https://www1.hkexnews.hk/listedco/report.pdf"
    session = install_http_stub(monkeypatch, [StubResponse(200, PDF_ONE)])

    result = await pdf_handler.download_report(
        stock_code="00700",
        market="HK",
        report_type="annual",
        report_url=url,
        report_title="Tencent 2025 Annual Report",
        report_year=2025,
        language="en",
        announcement_at=raw_announcement_at,
        announcement_date="2026-03-18",
    )

    assert result["success"] is True
    file_path = Path(result["data"]["file_path"])
    assert file_path.read_bytes() == PDF_ONE
    assert session.requests == [(url, {"allow_redirects": False})]
    assert pdf_handler.hk_downloader.get_downloaded_reports()[0]["web_path"] == url

    async with pdf_handler.pdf_manager.async_session() as database_session:
        row = await database_session.scalar(select(ReportPDF))

    assert row is not None
    assert row.announcement_date == expected_operational
    metadata = json.loads(row.metadata_json)
    assert metadata["announcement_at"] == raw_announcement_at
    assert metadata["announcement_at_utc"] == expected_utc
