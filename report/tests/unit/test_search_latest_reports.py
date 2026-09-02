import pytest

from src.handlers.pdf_handler import PDFHandler

CN_REPORT: dict[str, object] = {
    "stock_code": "600519",
    "announcement_title": "贵州茅台2025年年度报告",
    "pdf_url": "https://static.cninfo.com.cn/finalpage/report.pdf",
    "report_type": "annual",
    "year": 2025,
    "announcement_time": "1774916100000",
    "announcement_date": "2026-03-31",
}

HK_REPORT: dict[str, object] = {
    "stock_code": "00700",
    "title": "Tencent 2025 Annual Report",
    "pdf_url": "https://www1.hkexnews.hk/listedco/report.pdf",
    "report_type": "annual",
    "year": 2025,
    "language": "en",
    "release_time": "18/03/2026 16:42",
}


class StubDownloader:
    def __init__(self, reports: list[dict[str, object]]) -> None:
        self.reports = reports

    async def search_reports(self, **_: object) -> list[dict[str, object]]:
        return [dict(report) for report in self.reports]


def handler_with_reports(
    market: str, reports: list[dict[str, object]]
) -> PDFHandler:
    handler = PDFHandler.__new__(PDFHandler)
    handler.cache = {}
    handler.cn_downloader = StubDownloader(reports if market == "CN" else [])
    handler.hk_downloader = StubDownloader(reports if market == "HK" else [])
    return handler


@pytest.mark.asyncio
async def test_cn_search_returns_canonical_report_with_aware_announcement_time():
    handler = handler_with_reports("CN", [CN_REPORT])

    result = await handler.search_latest_reports(
        stock_code="600519",
        market="CN",
        report_types=["annual"],
    )

    assert result["success"] is True
    cn_report = result["data"][0]
    assert cn_report == {
        "stock_code": "600519",
        "market": "CN",
        "report_type": "annual",
        "report_year": 2025,
        "title": "贵州茅台2025年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/report.pdf",
        "language": "zh",
        "announcement_at": "2026-03-31T08:15:00+08:00",
        "announcement_date": "2026-03-31",
    }


@pytest.mark.asyncio
async def test_cn_search_preserves_date_without_synthesizing_timestamp():
    source_report = {
        **CN_REPORT,
        "announcement_time": "",
        "announcement_date": "2026-03-31",
    }
    handler = handler_with_reports("CN", [source_report])

    result = await handler.search_latest_reports(
        stock_code="600519",
        market="CN",
        report_types=["annual"],
    )

    assert result["data"][0] == {
        "stock_code": "600519",
        "market": "CN",
        "report_type": "annual",
        "report_year": 2025,
        "title": "贵州茅台2025年年度报告",
        "url": "https://static.cninfo.com.cn/finalpage/report.pdf",
        "language": "zh",
        "announcement_at": None,
        "announcement_date": "2026-03-31",
    }


@pytest.mark.asyncio
async def test_hk_search_returns_canonical_report_with_aware_release_time():
    handler = handler_with_reports("HK", [HK_REPORT])

    result = await handler.search_latest_reports(
        stock_code="00700",
        market="HK",
        report_types=["annual"],
    )

    assert result["data"][0] == {
        "stock_code": "00700",
        "market": "HK",
        "report_type": "annual",
        "report_year": 2025,
        "title": "Tencent 2025 Annual Report",
        "url": "https://www1.hkexnews.hk/listedco/report.pdf",
        "language": "en",
        "announcement_at": "2026-03-18T16:42:00+08:00",
        "announcement_date": "2026-03-18",
    }


@pytest.mark.asyncio
async def test_hk_search_preserves_date_without_synthesizing_timestamp():
    source_report = {**HK_REPORT, "release_time": "18/03/2026"}
    handler = handler_with_reports("HK", [source_report])

    result = await handler.search_latest_reports(
        stock_code="00700",
        market="HK",
        report_types=["annual"],
    )

    hk_date_only = result["data"][0]
    assert hk_date_only == {
        "stock_code": "00700",
        "market": "HK",
        "report_type": "annual",
        "report_year": 2025,
        "title": "Tencent 2025 Annual Report",
        "url": "https://www1.hkexnews.hk/listedco/report.pdf",
        "language": "en",
        "announcement_at": None,
        "announcement_date": "2026-03-18",
    }
    assert hk_date_only["announcement_at"] is None
    assert hk_date_only["announcement_date"] == "2026-03-18"


@pytest.mark.parametrize(
    ("override", "expected_error"),
    [
        pytest.param(
            {"stock_code": "600000"},
            "报告证券代码与请求不匹配",
            id="stock-code",
        ),
        pytest.param(
            {"report_type": "semi_annual"},
            "报告类型与请求不匹配",
            id="report-type",
        ),
    ],
)
@pytest.mark.asyncio
async def test_search_fails_when_report_identity_does_not_match_request(
    override: dict[str, object], expected_error: str
):
    handler = handler_with_reports("CN", [{**CN_REPORT, **override}])

    result = await handler.search_latest_reports(
        stock_code="600519",
        market="CN",
        report_types=["annual"],
    )

    assert result == {"success": False, "error": expected_error}


@pytest.mark.parametrize(
    ("override", "expected_error"),
    [
        pytest.param({"title": ""}, "报告标题不能为空", id="title"),
        pytest.param({"year": None}, "报告年份无效", id="year"),
        pytest.param({"language": "tc"}, "报告语言无效", id="language"),
        pytest.param(
            {"pdf_url": "http://www1.hkexnews.hk/listedco/report.pdf"},
            "报告URL必须使用HTTPS",
            id="https",
        ),
        pytest.param(
            {"pdf_url": "https://www1.hkexnews.hk.evil.test/report.pdf"},
            "报告URL不是官方来源",
            id="official-host",
        ),
    ],
)
@pytest.mark.asyncio
async def test_search_fails_when_hk_report_identity_is_malformed(
    override: dict[str, object], expected_error: str
):
    handler = handler_with_reports("HK", [{**HK_REPORT, **override}])

    result = await handler.search_latest_reports(
        stock_code="00700",
        market="HK",
        report_types=["annual"],
    )

    assert result == {"success": False, "error": expected_error}


@pytest.mark.parametrize(
    ("market", "stock_code", "source_report", "expected_error"),
    [
        pytest.param(
            "CN",
            "600519",
            {
                **CN_REPORT,
                "announcement_time": "",
                "announcement_date": "2026-02-30",
            },
            "报告公告日期无效",
            id="cn-announcement-date",
        ),
        pytest.param(
            "HK",
            "00700",
            {**HK_REPORT, "release_time": "30/02/2026"},
            "报告公告时间无效",
            id="hk-release-time",
        ),
        pytest.param(
            "HK",
            "00700",
            {**HK_REPORT, "release_time": "3/2/2026"},
            "报告公告时间无效",
            id="hk-noncanonical-date",
        ),
    ],
)
@pytest.mark.asyncio
async def test_search_fails_when_source_announcement_value_is_malformed(
    market: str,
    stock_code: str,
    source_report: dict[str, object],
    expected_error: str,
):
    handler = handler_with_reports(market, [source_report])

    result = await handler.search_latest_reports(
        stock_code=stock_code,
        market=market,
        report_types=["annual"],
    )

    assert result == {"success": False, "error": expected_error}


@pytest.mark.parametrize(
    ("market", "stock_code", "source_report"),
    [
        pytest.param(
            "CN",
            "600519",
            {
                key: value
                for key, value in CN_REPORT.items()
                if key not in {"announcement_time", "announcement_date"}
            },
            id="cn",
        ),
        pytest.param(
            "HK",
            "00700",
            {key: value for key, value in HK_REPORT.items() if key != "release_time"},
            id="hk",
        ),
    ],
)
@pytest.mark.asyncio
async def test_search_accepts_missing_source_announcement_value(
    market: str, stock_code: str, source_report: dict[str, object]
):
    handler = handler_with_reports(market, [source_report])

    result = await handler.search_latest_reports(
        stock_code=stock_code,
        market=market,
        report_types=["annual"],
    )

    assert result["success"] is True
    assert result["data"][0]["announcement_at"] is None
    assert result["data"][0]["announcement_date"] is None
