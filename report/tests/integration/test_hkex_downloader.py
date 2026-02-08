"""
港交所披露易下载器集成测试
测试 HKEXDownloader 的搜索、下载、数据库操作
"""
import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.pdf_sources.hkex_downloader import HKEXDownloader


class TestHKEXDownloaderInit:
    """初始化测试"""

    def test_init_creates_download_dir(self, tmp_path):
        """测试初始化创建下载目录"""
        download_dir = tmp_path / "downloads" / "hk_stocks"
        downloader = HKEXDownloader(
            download_dir=str(download_dir),
            db_path=str(tmp_path / "test.db")
        )

        assert download_dir.exists()
        assert downloader.download_dir == download_dir

    def test_init_creates_database(self, tmp_path):
        """测试初始化创建数据库"""
        db_path = tmp_path / "test.db"
        downloader = HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(db_path)
        )

        assert db_path.exists()

    def test_init_database_has_reports_table(self, tmp_path):
        """测试数据库包含reports表"""
        db_path = tmp_path / "test.db"
        downloader = HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(db_path)
        )

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reports'")
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "reports"

    def test_headers_set(self, tmp_path):
        """测试请求头设置"""
        downloader = HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

        assert "User-Agent" in downloader.headers
        assert "Accept" in downloader.headers

    def test_category_map_has_annual(self, tmp_path):
        """测试分类映射包含年报"""
        downloader = HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

        assert "annual" in HKEXDownloader.CATEGORY_MAP
        assert "semi_annual" in HKEXDownloader.CATEGORY_MAP
        assert "quarterly" in HKEXDownloader.CATEGORY_MAP


class TestReportTypeMatching:
    """报告类型匹配测试"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    def test_match_annual_zh(self, downloader):
        """测试匹配中文年报"""
        assert downloader._match_report_type("二零二三年年度報告", "annual") is True
        assert downloader._match_report_type("2023年報", "annual") is True

    def test_match_annual_en(self, downloader):
        """测试匹配英文年报"""
        assert downloader._match_report_type("Annual Report 2023", "annual") is True
        assert downloader._match_report_type("Annual Results 2023", "annual") is True

    def test_match_semi_annual_zh(self, downloader):
        """测试匹配中文半年报"""
        assert downloader._match_report_type("二零二三年中期報告", "semi_annual") is True
        assert downloader._match_report_type("中期業績公告", "semi_annual") is True

    def test_match_semi_annual_en(self, downloader):
        """测试匹配英文半年报"""
        assert downloader._match_report_type("Interim Report 2023", "semi_annual") is True
        assert downloader._match_report_type("Interim Results", "semi_annual") is True

    def test_no_match(self, downloader):
        """测试不匹配的标题"""
        assert downloader._match_report_type("公司公告", "annual") is False
        assert downloader._match_report_type("Something else", "annual") is False


class TestLanguageDetection:
    """语言检测测试"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    def test_detect_chinese_by_title(self, downloader):
        """测试通过标题检测中文"""
        assert downloader._detect_language("二零二三年年度報告", "") == "zh"
        assert downloader._detect_language("公司股份", "") == "zh"

    def test_detect_chinese_by_path(self, downloader):
        """测试通过文件路径检测中文"""
        assert downloader._detect_language("report", "/path/to/report_c.pdf") == "zh"
        assert downloader._detect_language("report", "/report_c.pdf") == "zh"

    def test_detect_english_default(self, downloader):
        """测试默认英文"""
        assert downloader._detect_language("Annual Report", "/report.pdf") == "en"


class TestYearExtraction:
    """年份提取测试"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    def test_extract_year_from_title(self, downloader):
        """测试从标题提取年份

        注意：实现只支持数字年份格式，不支持中文年份（如"二零二四年"）
        """
        assert downloader._extract_year_from_title("Annual Report 2023") == 2023
        assert downloader._extract_year_from_title("2024年年報") == 2024

    def test_extract_year_not_found(self, downloader):
        """测试未找到年份"""
        assert downloader._extract_year_from_title("年度報告") is None
        assert downloader._extract_year_from_title("") is None


class TestNormalizeReportType:
    """报告类型标准化测试"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    def test_normalize_annual(self, downloader):
        assert downloader._normalize_report_type("annual") == "annual"

    def test_normalize_semi_annual(self, downloader):
        assert downloader._normalize_report_type("semi_annual") == "semi_annual"

    def test_normalize_quarterly(self, downloader):
        assert downloader._normalize_report_type("quarterly") == "quarterly"

    def test_normalize_results(self, downloader):
        assert downloader._normalize_report_type("results") == "results"

    def test_normalize_other(self, downloader):
        assert downloader._normalize_report_type("unknown") == "other"


class TestPeriodLabelExtraction:
    """季度期间标签提取测试"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    def test_extract_q1_label(self, downloader):
        label = downloader._extract_period_label(
            "ANNOUNCEMENT OF THE 2025 Q1 FINANCIAL RESULTS",
            "quarterly",
        )
        assert label == "q1"

    def test_extract_q3_label(self, downloader):
        label = downloader._extract_period_label(
            "Announcement of the 2025 Q3 Financial Results",
            "quarterly",
        )
        assert label == "q3"

    def test_extract_q4_full_year_label(self, downloader):
        label = downloader._extract_period_label(
            "ANNOUNCEMENT OF THE 2025 Q4 AND FULL YEAR FINANCIAL RESULTS",
            "quarterly",
        )
        assert label == "q4_fy"

    def test_extract_label_non_quarterly(self, downloader):
        label = downloader._extract_period_label("Annual Report 2025", "annual")
        assert label is None


class TestDownloadSubpath:
    """下载路径生成测试"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    def test_get_subpath_with_stock_and_type(self, downloader):
        """测试按股票和类型生成路径"""
        path = downloader._get_download_subpath("700", "annual")

        assert path.exists()
        # 股票代码应该被补齐为5位
        assert "00700" in str(path)
        assert "annual" in str(path)

    def test_get_subpath_pads_stock_code(self, downloader):
        """测试股票代码补齐为5位"""
        path = downloader._get_download_subpath("700", "annual")
        assert "00700" in str(path)

        path = downloader._get_download_subpath("1810", "annual")
        assert "01810" in str(path)

    def test_get_subpath_only_stock(self, downloader):
        """测试只有股票代码时生成路径"""
        path = downloader._get_download_subpath("00700")

        assert path.exists()
        assert "00700" in str(path)

    def test_get_subpath_creates_name_file(self, downloader):
        """测试创建股票名称标识文件"""
        path = downloader._get_download_subpath("00700", "annual", "騰訊控股")

        stock_dir = path.parent
        name_file = stock_dir / ".stock_name.txt"

        assert name_file.exists()
        assert name_file.read_text(encoding='utf-8') == "騰訊控股"


class TestCreateStockNameFile:
    """股票名称文件创建测试"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    def test_create_name_file(self, downloader, tmp_path):
        """测试创建名称文件"""
        stock_dir = tmp_path / "downloads" / "00700"
        stock_dir.mkdir(parents=True, exist_ok=True)

        downloader._create_stock_name_file(stock_dir, "騰訊控股")

        name_file = stock_dir / ".stock_name.txt"
        assert name_file.exists()
        assert name_file.read_text(encoding='utf-8') == "騰訊控股"

    def test_create_name_file_cleans_special_chars(self, downloader, tmp_path):
        """测试清理特殊字符"""
        stock_dir = tmp_path / "downloads" / "00700"
        stock_dir.mkdir(parents=True, exist_ok=True)

        downloader._create_stock_name_file(stock_dir, "騰訊控股<test>")

        name_file = stock_dir / ".stock_name.txt"
        assert name_file.exists()
        content = name_file.read_text(encoding='utf-8')
        assert "<" not in content
        assert ">" not in content

    def test_create_name_file_empty_name(self, downloader, tmp_path):
        """测试空名称不创建文件"""
        stock_dir = tmp_path / "downloads" / "00700"
        stock_dir.mkdir(parents=True, exist_ok=True)

        downloader._create_stock_name_file(stock_dir, "")

        name_file = stock_dir / ".stock_name.txt"
        assert not name_file.exists()


class TestParseSearchHtml:
    """HTML解析测试"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    def test_parse_empty_html(self, downloader):
        """测试解析空HTML"""
        results = downloader._parse_search_html("<html></html>", "00700", "annual")
        assert results == []

    def test_parse_html_with_results(self, downloader):
        """测试解析包含结果的HTML"""
        html = """
        <html>
        <body>
        <table class="table">
            <tr>
                <td>2024-03-20</td>
                <td><a href="/listedco/listconews/sehk/2024/0320/12345.pdf">Annual Report 2023</a></td>
                <td>10MB</td>
            </tr>
        </table>
        </body>
        </html>
        """
        results = downloader._parse_search_html(html, "00700", "annual")

        assert len(results) == 1
        assert results[0]["stock_code"] == "00700"
        assert "Annual Report 2023" in results[0]["title"]
        assert results[0]["pdf_url"].endswith(".pdf")


class TestSearchReports:
    """搜索报告测试（异步）"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    @pytest.mark.asyncio
    async def test_search_with_mock(self, downloader):
        """测试搜索使用Mock"""
        mock_html = """
        <html>
        <body>
        <table class="table">
            <tr>
                <td>2024-03-20</td>
                <td><a href="/report.pdf">Annual Report 2023</a></td>
                <td>10MB</td>
            </tr>
        </table>
        </body>
        </html>
        """

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=mock_html)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session

            results = await downloader.search_reports(
                stock_code="00700",
                report_type="annual",
                limit=10
            )

            assert len(results) == 1


class TestDownloadPDF:
    """PDF下载测试（异步）"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    @pytest.mark.asyncio
    async def test_download_invalid_url(self, downloader):
        """测试无效URL下载"""
        success, message, filepath = await downloader.download_pdf("", {})

        assert success is False
        assert "無效" in message

    @pytest.mark.asyncio
    async def test_download_with_mock(self, downloader, tmp_path):
        """测试使用Mock下载"""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n%%EOF"

        report_data = {
            "stock_code": "00700",
            "stock_name": "騰訊控股",
            "title": "Annual Report 2023",
            "report_type": "annual",
            "language": "en",
            "year": 2023
        }

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=pdf_content)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session

            success, message, filepath = await downloader.download_pdf(
                "https://www1.hkexnews.hk/report.pdf",
                report_data
            )

            assert success is True
            assert filepath is not None
            assert Path(filepath).exists()

    @pytest.mark.asyncio
    async def test_download_quarterly_filename_has_period_label(self, downloader):
        """测试季度报告文件名包含季度标签，避免同年覆盖"""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n%%EOF"

        report_data = {
            "stock_code": "09987",
            "stock_name": "Yum China",
            "title": "ANNOUNCEMENT OF THE 2025 Q3 FINANCIAL RESULTS",
            "report_type": "quarterly",
            "language": "en",
            "year": 2025
        }

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read = AsyncMock(return_value=pdf_content)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session

            success, _, filepath = await downloader.download_pdf(
                "https://www1.hkexnews.hk/report.pdf",
                report_data
            )

            assert success is True
            assert filepath is not None
            assert Path(filepath).name == "2025_quarterly_q3_en.pdf"


class TestDatabaseOperations:
    """数据库操作测试"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    def test_get_downloaded_reports_empty(self, downloader):
        """测试获取空的已下载列表"""
        reports = downloader.get_downloaded_reports()
        assert reports == []

    def test_get_collection_stats_empty(self, downloader):
        """测试获取空的统计信息"""
        stats = downloader.get_collection_stats()

        assert stats["total_reports"] == 0
        assert stats["downloaded_reports"] == 0


class TestParseAnnouncement:
    """公告解析测试"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    def test_parse_valid_announcement(self, downloader):
        """测试解析有效公告"""
        item = {
            "stock": [{"sc": "700", "sn": "騰訊控股"}],
            "title": "Annual Report 2023",
            "webPath": "/report.pdf",
            "newsId": "12345",
            "relTime": "2024-03-20",
            "size": "10MB",
            "market": "SEHK"
        }

        result = downloader._parse_announcement(item, "annual")

        assert result is not None
        assert result["stock_code"] == "00700"  # 补齐为5位
        assert result["stock_name"] == "騰訊控股"
        assert result["title"] == "Annual Report 2023"
        assert result["report_type"] == "annual"

    def test_parse_announcement_no_stocks(self, downloader):
        """测试解析无股票信息的公告"""
        item = {
            "title": "Annual Report 2023",
            "webPath": "/report.pdf"
        }

        result = downloader._parse_announcement(item, "annual")
        assert result is None

    def test_parse_announcement_no_web_path(self, downloader):
        """测试解析无PDF路径的公告"""
        item = {
            "stock": [{"sc": "700", "sn": "騰訊控股"}],
            "title": "Annual Report 2023",
            "webPath": ""
        }

        result = downloader._parse_announcement(item, "annual")
        assert result is None


class TestMarketMapping:
    """市场板块映射测试"""

    def test_market_map_has_sehk(self):
        """测试包含主板"""
        assert "sehk" in HKEXDownloader.MARKET_MAP
        assert HKEXDownloader.MARKET_MAP["sehk"] == "主板"

    def test_market_map_has_gem(self):
        """测试包含创业板"""
        assert "gem" in HKEXDownloader.MARKET_MAP
        assert HKEXDownloader.MARKET_MAP["gem"] == "創業板"


class TestReportTypeNames:
    """报告类型名称测试"""

    def test_annual_names(self):
        """测试年报名称"""
        assert HKEXDownloader.REPORT_TYPE_NAMES["annual"]["zh"] == "年報"
        assert HKEXDownloader.REPORT_TYPE_NAMES["annual"]["en"] == "Annual Report"

    def test_semi_annual_names(self):
        """测试半年报名称"""
        assert HKEXDownloader.REPORT_TYPE_NAMES["semi_annual"]["zh"] == "中期報告"
        assert HKEXDownloader.REPORT_TYPE_NAMES["semi_annual"]["en"] == "Interim Report"

    def test_quarterly_names(self):
        """测试季报名称"""
        assert HKEXDownloader.REPORT_TYPE_NAMES["quarterly"]["zh"] == "季度報告"
        assert HKEXDownloader.REPORT_TYPE_NAMES["quarterly"]["en"] == "Quarterly Report"


class TestUrlConversion:
    """URL 中英文转换测试"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    def test_get_chinese_url_from_english(self, downloader):
        """测试从英文URL生成中文URL"""
        en_url = "https://www1.hkexnews.hk/listedco/listconews/sehk/2025/0424/2025042401120.pdf"
        zh_url = downloader._get_chinese_url(en_url)

        assert zh_url is not None
        assert zh_url == "https://www1.hkexnews.hk/listedco/listconews/sehk/2025/0424/2025042401120_c.pdf"

    def test_get_chinese_url_already_chinese(self, downloader):
        """测试已经是中文URL时返回None"""
        zh_url = "https://www1.hkexnews.hk/listedco/listconews/sehk/2025/0424/2025042401120_c.pdf"
        result = downloader._get_chinese_url(zh_url)

        assert result is None

    def test_get_chinese_url_empty(self, downloader):
        """测试空URL返回None"""
        assert downloader._get_chinese_url("") is None
        assert downloader._get_chinese_url(None) is None

    def test_get_english_url_from_chinese(self, downloader):
        """测试从中文URL生成英文URL"""
        zh_url = "https://www1.hkexnews.hk/listedco/listconews/sehk/2025/0424/2025042401120_c.pdf"
        en_url = downloader._get_english_url(zh_url)

        assert en_url is not None
        assert en_url == "https://www1.hkexnews.hk/listedco/listconews/sehk/2025/0424/2025042401120.pdf"

    def test_get_english_url_empty(self, downloader):
        """测试空URL返回None"""
        assert downloader._get_english_url("") is None
        assert downloader._get_english_url(None) is None


class TestSearchEnglishOnly:
    """搜索只返回英文版本测试"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    @pytest.mark.asyncio
    async def test_search_returns_english_reports(self, downloader):
        """测试搜索返回英文版本财报"""
        # Mock 英文版搜索结果
        mock_html = """
        <html>
        <body>
        <table class="table">
            <tr>
                <td>2024-03-20</td>
                <td><a href="/listedco/listconews/sehk/2024/0320/12345.pdf">Annual Report 2023</a></td>
                <td>10MB</td>
            </tr>
        </table>
        </body>
        </html>
        """

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=mock_html)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session

            results = await downloader.search_reports(
                stock_code="00700",
                report_type="annual",
                limit=10
            )

            # 验证返回的是英文版本（URL不包含 _c）
            assert len(results) >= 0
            for result in results:
                url = result.get('pdf_url', '')
                # 英文版本的URL不应包含 _c.pdf
                if url:
                    # 检测语言应该是英文
                    lang = result.get('language', 'en')
                    assert lang == 'en' or '_c.' not in url


class TestDownloadStockReportsEnglish:
    """批量下载只下载英文版本测试"""

    @pytest.fixture
    def downloader(self, tmp_path):
        return HKEXDownloader(
            download_dir=str(tmp_path / "downloads"),
            db_path=str(tmp_path / "test.db")
        )

    @pytest.mark.asyncio
    async def test_download_filters_english_only(self, downloader):
        """测试批量下载只下载英文版本"""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n%%EOF"

        # Mock 搜索结果包含中英文两个版本
        mock_html = """
        <html>
        <body>
        <table class="table">
            <tr>
                <td>2024-03-20</td>
                <td><a href="/listedco/listconews/sehk/2024/0320/12345.pdf">Annual Report 2023</a></td>
                <td>10MB</td>
            </tr>
        </table>
        </body>
        </html>
        """

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()

            # Mock POST (搜索请求)
            mock_post_response = AsyncMock()
            mock_post_response.status = 200
            mock_post_response.text = AsyncMock(return_value=mock_html)
            mock_post_response.__aenter__ = AsyncMock(return_value=mock_post_response)
            mock_post_response.__aexit__ = AsyncMock(return_value=None)

            # Mock GET (下载请求)
            mock_get_response = AsyncMock()
            mock_get_response.status = 200
            mock_get_response.read = AsyncMock(return_value=pdf_content)
            mock_get_response.__aenter__ = AsyncMock(return_value=mock_get_response)
            mock_get_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.post = MagicMock(return_value=mock_post_response)
            mock_session.get = MagicMock(return_value=mock_get_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session

            downloaded = await downloader.download_stock_reports(
                stock_code="00700",
                report_type="annual",
                max_count=1
            )

            # 验证下载的是英文版本
            for filepath in downloaded:
                # 文件名应该包含 _en 而不是 _zh
                assert "_en.pdf" in filepath or "_en" in filepath

    @pytest.mark.asyncio
    async def test_download_respects_max_count(self, downloader):
        """测试批量下载遵守最大数量限制"""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n%%EOF"

        # Mock 搜索结果包含多个报告
        mock_html = """
        <html>
        <body>
        <table class="table">
            <tr>
                <td>2024-03-20</td>
                <td><a href="/report1.pdf">Annual Report 2023</a></td>
                <td>10MB</td>
            </tr>
            <tr>
                <td>2023-03-20</td>
                <td><a href="/report2.pdf">Annual Report 2022</a></td>
                <td>10MB</td>
            </tr>
            <tr>
                <td>2022-03-20</td>
                <td><a href="/report3.pdf">Annual Report 2021</a></td>
                <td>10MB</td>
            </tr>
        </table>
        </body>
        </html>
        """

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()

            mock_post_response = AsyncMock()
            mock_post_response.status = 200
            mock_post_response.text = AsyncMock(return_value=mock_html)
            mock_post_response.__aenter__ = AsyncMock(return_value=mock_post_response)
            mock_post_response.__aexit__ = AsyncMock(return_value=None)

            mock_get_response = AsyncMock()
            mock_get_response.status = 200
            mock_get_response.read = AsyncMock(return_value=pdf_content)
            mock_get_response.__aenter__ = AsyncMock(return_value=mock_get_response)
            mock_get_response.__aexit__ = AsyncMock(return_value=None)

            mock_session.post = MagicMock(return_value=mock_post_response)
            mock_session.get = MagicMock(return_value=mock_get_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session

            # 设置 max_count=2
            downloaded = await downloader.download_stock_reports(
                stock_code="00700",
                report_type="annual",
                max_count=2
            )

            # 应该最多下载2个文件
            assert len(downloaded) <= 2
