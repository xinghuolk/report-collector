"""
PDF处理器集成测试
测试 PDFHandler 的搜索、下载、提取、缓存管理功能
"""
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.handlers.pdf_handler import PDFHandler
from src.config import Config


class TestPDFHandlerInit:
    """初始化测试"""

    @pytest_asyncio.fixture
    async def handler(self, tmp_path):
        """使用临时配置的PDFHandler"""
        # 保存原始配置
        original_downloads = Config.DOWNLOADS_DIR
        original_cn_dir = Config.CN_DOWNLOADS_DIR
        original_hk_dir = Config.HK_DOWNLOADS_DIR
        original_db_url = Config.DATABASE_URL

        # 设置临时配置
        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        Config.DOWNLOADS_DIR = temp_downloads
        Config.CN_DOWNLOADS_DIR = temp_downloads / "cn_stocks"
        Config.HK_DOWNLOADS_DIR = temp_downloads / "hk_stocks"
        Config.DATABASE_URL = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"

        handler = PDFHandler()
        await handler.initialize()

        yield handler

        # 恢复原始配置
        Config.DOWNLOADS_DIR = original_downloads
        Config.CN_DOWNLOADS_DIR = original_cn_dir
        Config.HK_DOWNLOADS_DIR = original_hk_dir
        Config.DATABASE_URL = original_db_url

    @pytest.mark.asyncio
    async def test_initialize(self, handler):
        """测试初始化"""
        assert handler.pdf_manager is not None
        assert handler.cn_downloader is not None
        assert handler.hk_downloader is not None
        assert handler.content_extractor is not None
        assert handler.cache is not None


class TestSearchAvailableReports:
    """搜索功能测试"""

    @pytest_asyncio.fixture
    async def handler(self, tmp_path):
        original_downloads = Config.DOWNLOADS_DIR
        original_cn_dir = Config.CN_DOWNLOADS_DIR
        original_hk_dir = Config.HK_DOWNLOADS_DIR
        original_db_url = Config.DATABASE_URL

        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        Config.DOWNLOADS_DIR = temp_downloads
        Config.CN_DOWNLOADS_DIR = temp_downloads / "cn_stocks"
        Config.HK_DOWNLOADS_DIR = temp_downloads / "hk_stocks"
        Config.DATABASE_URL = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"

        handler = PDFHandler()
        await handler.initialize()

        yield handler

        Config.DOWNLOADS_DIR = original_downloads
        Config.CN_DOWNLOADS_DIR = original_cn_dir
        Config.HK_DOWNLOADS_DIR = original_hk_dir
        Config.DATABASE_URL = original_db_url

    @pytest.mark.asyncio
    async def test_search_invalid_stock_code(self, handler):
        """测试无效股票代码"""
        result = await handler.search_available_reports("invalid", market="CN")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_invalid_market(self, handler):
        """测试无效市场"""
        result = await handler.search_available_reports("000001", market="INVALID")

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_invalid_report_type(self, handler):
        """测试无效报告类型"""
        result = await handler.search_available_reports(
            "000001", market="CN", report_type="invalid"
        )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_us_market_not_implemented(self, handler):
        """测试美股市场未实现"""
        result = await handler.search_available_reports("AAPL", market="US")

        assert result["success"] is False
        assert "尚未实现" in result["error"]

    @pytest.mark.asyncio
    async def test_search_cn_with_mock(self, handler):
        """测试A股搜索使用Mock"""
        mock_reports = [
            {
                "announcement_id": "12345",
                "announcement_title": "平安银行2023年年度报告",
                "stock_code": "000001",
                "stock_name": "平安银行",
            }
        ]

        with patch.object(
            handler.cn_downloader, "search_reports", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_reports

            result = await handler.search_available_reports("000001", market="CN")

            assert result["success"] is True
            assert result["count"] == 1
            assert result["source"] == "巨潮资讯网"

    @pytest.mark.asyncio
    async def test_search_hk_with_mock(self, handler):
        """测试港股搜索使用Mock"""
        mock_reports = [
            {
                "stock_code": "00700",
                "stock_name": "騰訊控股",
                "title": "Annual Report 2023",
            }
        ]

        with patch.object(
            handler.hk_downloader, "search_reports", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_reports

            result = await handler.search_available_reports("00700", market="HK")

            assert result["success"] is True
            assert result["count"] == 1
            assert result["source"] == "港交所披露易"

    @pytest.mark.asyncio
    async def test_search_uses_cache(self, handler):
        """测试搜索使用缓存"""
        mock_reports = [{"test": "data"}]

        with patch.object(
            handler.cn_downloader, "search_reports", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_reports

            # 第一次调用
            result1 = await handler.search_available_reports("000001", market="CN")

            # 第二次调用应该使用缓存
            result2 = await handler.search_available_reports("000001", market="CN")

            # 应该只调用一次
            assert mock_search.call_count == 1
            assert result1 == result2


class TestListDownloadedPdfs:
    """列出已下载PDF测试"""

    @pytest_asyncio.fixture
    async def handler(self, tmp_path):
        original_downloads = Config.DOWNLOADS_DIR
        original_cn_dir = Config.CN_DOWNLOADS_DIR
        original_hk_dir = Config.HK_DOWNLOADS_DIR
        original_db_url = Config.DATABASE_URL

        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        Config.DOWNLOADS_DIR = temp_downloads
        Config.CN_DOWNLOADS_DIR = temp_downloads / "cn_stocks"
        Config.HK_DOWNLOADS_DIR = temp_downloads / "hk_stocks"
        Config.DATABASE_URL = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"

        handler = PDFHandler()
        await handler.initialize()

        yield handler

        Config.DOWNLOADS_DIR = original_downloads
        Config.CN_DOWNLOADS_DIR = original_cn_dir
        Config.HK_DOWNLOADS_DIR = original_hk_dir
        Config.DATABASE_URL = original_db_url

    @pytest.mark.asyncio
    async def test_list_empty(self, handler):
        """测试列出空列表"""
        result = await handler.list_downloaded_pdfs()

        assert result["success"] is True
        assert result["count"] == 0
        assert result["data"] == []

    @pytest.mark.asyncio
    async def test_list_filters_missing_files_and_marks_unavailable(self, handler, tmp_path):
        """测试列表自动过滤并清理缺失文件记录"""
        valid_pdf = tmp_path / "downloads" / "cn_stocks" / "000001" / "annual" / "valid.pdf"
        valid_pdf.parent.mkdir(parents=True, exist_ok=True)
        valid_pdf.write_bytes(b"%PDF-1.4 valid")

        missing_pdf = (
            tmp_path / "downloads" / "cn_stocks" / "000001" / "annual" / "missing.pdf"
        )
        missing_pdf.parent.mkdir(parents=True, exist_ok=True)
        missing_pdf.write_bytes(b"%PDF-1.4 missing")

        valid_id = await handler.pdf_manager.add_pdf(
            {
                "stock_code": "000001",
                "stock_name": "平安银行",
                "market": "CN",
                "report_type": "annual",
                "report_year": 2024,
                "original_title": "2024年年度报告",
                "file_path": str(valid_pdf),
                "file_name": valid_pdf.name,
                "source_name": "巨潮资讯网",
            }
        )
        missing_id = await handler.pdf_manager.add_pdf(
            {
                "stock_code": "000001",
                "stock_name": "平安银行",
                "market": "CN",
                "report_type": "annual",
                "report_year": 2023,
                "original_title": "2023年年度报告",
                "file_path": str(missing_pdf),
                "file_name": missing_pdf.name,
                "source_name": "巨潮资讯网",
            }
        )
        assert valid_id is not None
        assert missing_id is not None

        missing_pdf.unlink()

        result = await handler.list_downloaded_pdfs(stock_code="000001", market="CN")
        assert result["success"] is True
        assert result["count"] == 1
        assert result["missing_file_records_cleaned"] == 1
        assert result["data"][0]["id"] == valid_id

        missing_info = await handler.pdf_manager.get_pdf_by_id(missing_id)
        assert missing_info is not None
        assert missing_info["is_available"] is False


class TestGetPdfInfo:
    """获取PDF信息测试"""

    @pytest_asyncio.fixture
    async def handler(self, tmp_path):
        original_downloads = Config.DOWNLOADS_DIR
        original_cn_dir = Config.CN_DOWNLOADS_DIR
        original_hk_dir = Config.HK_DOWNLOADS_DIR
        original_db_url = Config.DATABASE_URL

        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        Config.DOWNLOADS_DIR = temp_downloads
        Config.CN_DOWNLOADS_DIR = temp_downloads / "cn_stocks"
        Config.HK_DOWNLOADS_DIR = temp_downloads / "hk_stocks"
        Config.DATABASE_URL = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"

        handler = PDFHandler()
        await handler.initialize()

        yield handler

        Config.DOWNLOADS_DIR = original_downloads
        Config.CN_DOWNLOADS_DIR = original_cn_dir
        Config.HK_DOWNLOADS_DIR = original_hk_dir
        Config.DATABASE_URL = original_db_url

    @pytest.mark.asyncio
    async def test_get_pdf_info_not_exists(self, handler):
        """测试获取不存在的PDF信息"""
        result = await handler.get_pdf_info(9999)

        assert result["success"] is False
        assert "不存在" in result["error"]


class TestGetStats:
    """获取统计信息测试"""

    @pytest_asyncio.fixture
    async def handler(self, tmp_path):
        original_downloads = Config.DOWNLOADS_DIR
        original_cn_dir = Config.CN_DOWNLOADS_DIR
        original_hk_dir = Config.HK_DOWNLOADS_DIR
        original_db_url = Config.DATABASE_URL

        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        Config.DOWNLOADS_DIR = temp_downloads
        Config.CN_DOWNLOADS_DIR = temp_downloads / "cn_stocks"
        Config.HK_DOWNLOADS_DIR = temp_downloads / "hk_stocks"
        Config.DATABASE_URL = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"

        handler = PDFHandler()
        await handler.initialize()

        yield handler

        Config.DOWNLOADS_DIR = original_downloads
        Config.CN_DOWNLOADS_DIR = original_cn_dir
        Config.HK_DOWNLOADS_DIR = original_hk_dir
        Config.DATABASE_URL = original_db_url

    @pytest.mark.asyncio
    async def test_get_stats(self, handler):
        """测试获取统计信息"""
        result = await handler.get_stats()

        assert result["success"] is True
        assert "data" in result


class TestExtractPdfContent:
    """提取PDF内容测试"""

    @pytest_asyncio.fixture
    async def handler(self, tmp_path):
        original_downloads = Config.DOWNLOADS_DIR
        original_cn_dir = Config.CN_DOWNLOADS_DIR
        original_hk_dir = Config.HK_DOWNLOADS_DIR
        original_db_url = Config.DATABASE_URL

        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        Config.DOWNLOADS_DIR = temp_downloads
        Config.CN_DOWNLOADS_DIR = temp_downloads / "cn_stocks"
        Config.HK_DOWNLOADS_DIR = temp_downloads / "hk_stocks"
        Config.DATABASE_URL = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"

        handler = PDFHandler()
        await handler.initialize()

        yield handler

        Config.DOWNLOADS_DIR = original_downloads
        Config.CN_DOWNLOADS_DIR = original_cn_dir
        Config.HK_DOWNLOADS_DIR = original_hk_dir
        Config.DATABASE_URL = original_db_url

    @pytest.mark.asyncio
    async def test_extract_no_params(self, handler):
        """测试未提供参数"""
        result = await handler.extract_pdf_content()

        assert result["success"] is False
        assert "请提供" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_file_not_exists(self, handler):
        """测试文件不存在"""
        result = await handler.extract_pdf_content(pdf_path="/nonexistent/file.pdf")

        assert result["success"] is False
        assert "不存在" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_pdf_id_not_exists(self, handler):
        """测试PDF ID不存在"""
        result = await handler.extract_pdf_content(pdf_id=9999)

        assert result["success"] is False
        assert "未找到" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_by_pdf_id_marks_missing_record_unavailable(self, handler, tmp_path):
        """测试按ID提取遇到孤儿记录时自动标记不可用"""
        orphan_pdf = tmp_path / "downloads" / "hk_stocks" / "09987" / "quarterly" / "orphan.pdf"
        orphan_pdf.parent.mkdir(parents=True, exist_ok=True)
        orphan_pdf.write_bytes(b"%PDF-1.4 orphan")

        pdf_id = await handler.pdf_manager.add_pdf(
            {
                "stock_code": "09987",
                "stock_name": "XIAOMI-W",
                "market": "HK",
                "report_type": "quarterly",
                "report_year": 2025,
                "report_quarter": 3,
                "original_title": "Q3 Results",
                "file_path": str(orphan_pdf),
                "file_name": orphan_pdf.name,
                "source_name": "港交所披露易",
            }
        )
        assert pdf_id is not None

        orphan_pdf.unlink()
        result = await handler.extract_pdf_content(pdf_id=pdf_id)

        assert result["success"] is False
        assert "已标记为不可用" in result["error"]

        refreshed = await handler.pdf_manager.get_pdf_by_id(pdf_id)
        assert refreshed is not None
        assert refreshed["is_available"] is False


class TestExtractTables:
    """提取表格测试"""

    @pytest_asyncio.fixture
    async def handler(self, tmp_path):
        original_downloads = Config.DOWNLOADS_DIR
        original_cn_dir = Config.CN_DOWNLOADS_DIR
        original_hk_dir = Config.HK_DOWNLOADS_DIR
        original_db_url = Config.DATABASE_URL

        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        Config.DOWNLOADS_DIR = temp_downloads
        Config.CN_DOWNLOADS_DIR = temp_downloads / "cn_stocks"
        Config.HK_DOWNLOADS_DIR = temp_downloads / "hk_stocks"
        Config.DATABASE_URL = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"

        handler = PDFHandler()
        await handler.initialize()

        yield handler

        Config.DOWNLOADS_DIR = original_downloads
        Config.CN_DOWNLOADS_DIR = original_cn_dir
        Config.HK_DOWNLOADS_DIR = original_hk_dir
        Config.DATABASE_URL = original_db_url

    @pytest.mark.asyncio
    async def test_extract_tables_no_params(self, handler):
        """测试未提供参数"""
        result = await handler.extract_tables()

        assert result["success"] is False
        assert "请提供" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_tables_file_not_exists(self, handler):
        """测试文件不存在"""
        result = await handler.extract_tables(pdf_path="/nonexistent/file.pdf")

        assert result["success"] is False
        assert "不存在" in result["error"]


class TestExtractText:
    """提取文本测试"""

    @pytest_asyncio.fixture
    async def handler(self, tmp_path):
        original_downloads = Config.DOWNLOADS_DIR
        original_cn_dir = Config.CN_DOWNLOADS_DIR
        original_hk_dir = Config.HK_DOWNLOADS_DIR
        original_db_url = Config.DATABASE_URL

        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        Config.DOWNLOADS_DIR = temp_downloads
        Config.CN_DOWNLOADS_DIR = temp_downloads / "cn_stocks"
        Config.HK_DOWNLOADS_DIR = temp_downloads / "hk_stocks"
        Config.DATABASE_URL = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"

        handler = PDFHandler()
        await handler.initialize()

        yield handler

        Config.DOWNLOADS_DIR = original_downloads
        Config.CN_DOWNLOADS_DIR = original_cn_dir
        Config.HK_DOWNLOADS_DIR = original_hk_dir
        Config.DATABASE_URL = original_db_url

    @pytest.mark.asyncio
    async def test_extract_text_no_params(self, handler):
        """测试未提供参数"""
        result = await handler.extract_text()

        assert result["success"] is False
        assert "请提供" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_text_file_not_exists(self, handler):
        """测试文件不存在"""
        result = await handler.extract_text(pdf_path="/nonexistent/file.pdf")

        assert result["success"] is False
        assert "不存在" in result["error"]


class TestCacheManagement:
    """缓存管理测试"""

    @pytest_asyncio.fixture
    async def handler(self, tmp_path):
        original_downloads = Config.DOWNLOADS_DIR
        original_cn_dir = Config.CN_DOWNLOADS_DIR
        original_hk_dir = Config.HK_DOWNLOADS_DIR
        original_db_url = Config.DATABASE_URL

        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        Config.DOWNLOADS_DIR = temp_downloads
        Config.CN_DOWNLOADS_DIR = temp_downloads / "cn_stocks"
        Config.HK_DOWNLOADS_DIR = temp_downloads / "hk_stocks"
        Config.DATABASE_URL = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"

        handler = PDFHandler()
        await handler.initialize()

        yield handler

        Config.DOWNLOADS_DIR = original_downloads
        Config.CN_DOWNLOADS_DIR = original_cn_dir
        Config.HK_DOWNLOADS_DIR = original_hk_dir
        Config.DATABASE_URL = original_db_url

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, handler):
        """测试获取缓存统计"""
        result = await handler.get_cache_stats()

        assert result["success"] is True
        assert "data" in result

    @pytest.mark.asyncio
    async def test_cleanup_extraction_cache(self, handler):
        """测试清理提取缓存"""
        result = await handler.cleanup_extraction_cache(days=90)

        assert result["success"] is True
        assert "message" in result

    @pytest.mark.asyncio
    async def test_warm_cache_no_uncached(self, handler):
        """测试预热缓存 - 无未缓存PDF"""
        result = await handler.warm_cache()

        assert result["success"] is True
        assert result["data"]["processed"] == 0
        assert "所有PDF都已缓存" in result["message"]


class TestConfidenceFilter:
    """低置信度过滤测试"""

    def test_apply_min_confidence_filter_for_v2(self):
        result = {
            "success": True,
            "schema_version": "v2",
            "facts": [
                {
                    "statement": "income_statement",
                    "metric": "revenue",
                    "period_id": "2025FY",
                    "confidence": 0.96,
                },
                {
                    "statement": "income_statement",
                    "metric": "net_profit",
                    "period_id": "2025FY",
                    "confidence": 0.75,
                },
            ],
            "quality": {"status": "ok", "issues": []},
        }

        filtered = PDFHandler._apply_min_confidence_filter(result, 0.9)

        assert len(filtered["facts"]) == 1
        assert filtered["facts"][0]["metric"] == "revenue"
        assert filtered["quality"]["status"] == "partial"
        assert any(
            issue.get("type") == "confidence_filtered"
            for issue in filtered["quality"]["issues"]
        )

    def test_to_v1_response_keeps_legacy_fields(self):
        v2_result = {
            "success": True,
            "schema_version": "v2",
            "income_statement": {"revenue": 100},
            "balance_sheet": {"total_assets": 1000},
            "cash_flow_statement": {"operating_cash_flow": 200},
            "financial_metrics": {"eps": 1.2},
            "related_party_transactions": [],
            "metadata": {"stock_code": "09987"},
            "extraction_summary": {"fields_extracted": 4},
            "_cache_info": {"from_cache": False},
            "file_path": "/tmp/test.pdf",
        }

        v1_result = PDFHandler._to_v1_response(v2_result)
        assert v1_result["success"] is True
        assert "schema_version" not in v1_result
        assert v1_result["income_statement"]["revenue"] == 100
        assert v1_result["metadata"]["stock_code"] == "09987"

    def test_build_hk_metadata_json_includes_period_hint(self):
        handler = PDFHandler()
        metadata_json = handler._build_hk_metadata_json(
            matched_report={
                "title": "ANNOUNCEMENT OF THE 2025 Q4 AND FULL YEAR FINANCIAL RESULTS",
                "release_time": "04/02/2026 18:00",
                "web_path": "/listedco/listconews/sehk/2026/0204/xxx.pdf",
                "year": 2025,
            },
            report_type="quarterly",
        )
        assert metadata_json is not None
        assert "period_hint" in metadata_json
        assert "q4_fy" in metadata_json

    def test_apply_pdf_identity_context_overrides_stock_code(self):
        handler = PDFHandler()
        result = {
            "success": True,
            "metadata": {"stock_code": "1398"},
            "document": {"stock_code": "1398"},
        }
        pdf_info = {"stock_code": "09987", "stock_name": "YUM CHINA", "market": "HK"}

        handler._apply_pdf_identity_context(result, pdf_info)

        assert result["metadata"]["stock_code"] == "09987"
        assert result["document"]["stock_code"] == "09987"


class TestCleanupOldFiles:
    """清理旧文件测试"""

    @pytest_asyncio.fixture
    async def handler(self, tmp_path):
        original_downloads = Config.DOWNLOADS_DIR
        original_cn_dir = Config.CN_DOWNLOADS_DIR
        original_hk_dir = Config.HK_DOWNLOADS_DIR
        original_db_url = Config.DATABASE_URL

        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        Config.DOWNLOADS_DIR = temp_downloads
        Config.CN_DOWNLOADS_DIR = temp_downloads / "cn_stocks"
        Config.HK_DOWNLOADS_DIR = temp_downloads / "hk_stocks"
        Config.DATABASE_URL = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"

        handler = PDFHandler()
        await handler.initialize()

        yield handler

        Config.DOWNLOADS_DIR = original_downloads
        Config.CN_DOWNLOADS_DIR = original_cn_dir
        Config.HK_DOWNLOADS_DIR = original_hk_dir
        Config.DATABASE_URL = original_db_url

    @pytest.mark.asyncio
    async def test_cleanup_old_files(self, handler):
        """测试清理旧文件"""
        result = await handler.cleanup_old_files(days=90)

        assert result["success"] is True
        assert "message" in result


class TestDownloadStockReports:
    """批量下载测试"""

    @pytest_asyncio.fixture
    async def handler(self, tmp_path):
        original_downloads = Config.DOWNLOADS_DIR
        original_cn_dir = Config.CN_DOWNLOADS_DIR
        original_hk_dir = Config.HK_DOWNLOADS_DIR
        original_db_url = Config.DATABASE_URL

        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        Config.DOWNLOADS_DIR = temp_downloads
        Config.CN_DOWNLOADS_DIR = temp_downloads / "cn_stocks"
        Config.HK_DOWNLOADS_DIR = temp_downloads / "hk_stocks"
        Config.DATABASE_URL = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"

        handler = PDFHandler()
        await handler.initialize()

        yield handler

        Config.DOWNLOADS_DIR = original_downloads
        Config.CN_DOWNLOADS_DIR = original_cn_dir
        Config.HK_DOWNLOADS_DIR = original_hk_dir
        Config.DATABASE_URL = original_db_url

    @pytest.mark.asyncio
    async def test_download_cn_with_mock(self, handler, tmp_path):
        """测试A股批量下载使用Mock"""
        # 创建临时PDF文件
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%%EOF")

        with patch.object(
            handler.cn_downloader, "download_stock_reports", new_callable=AsyncMock
        ) as mock_download:
            mock_download.return_value = [str(pdf_file)]

            result = await handler.download_stock_reports(
                "000001", market="CN", max_count=1
            )

            assert result["success"] is True
            assert result["data"]["downloaded_count"] == 1

    @pytest.mark.asyncio
    async def test_download_hk_with_mock(self, handler, tmp_path):
        """测试港股批量下载使用Mock"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%%EOF")

        with patch.object(
            handler.hk_downloader, "download_stock_reports", new_callable=AsyncMock
        ) as mock_download:
            mock_download.return_value = [str(pdf_file)]

            result = await handler.download_stock_reports(
                "00700", market="HK", max_count=1
            )

            assert result["success"] is True
            assert result["data"]["downloaded_count"] == 1

    @pytest.mark.asyncio
    async def test_download_unsupported_market(self, handler):
        """测试不支持的市场"""
        result = await handler.download_stock_reports("AAPL", market="US")

        assert result["success"] is False
        assert "暂不支持" in result["error"]
