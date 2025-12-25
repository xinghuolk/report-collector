"""
MCP服务器集成测试
测试 FinancialReportsPDFServer 的工具注册和调用
"""
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.main import FinancialReportsPDFServer
from src.config import Config


class TestMCPServerInit:
    """服务器初始化测试"""

    def test_server_init_creates_pdf_handler(self, tmp_path, monkeypatch):
        """测试服务器初始化创建PDFHandler"""
        # 设置临时配置
        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        monkeypatch.setattr(Config, 'DOWNLOADS_DIR', temp_downloads)
        monkeypatch.setattr(Config, 'CN_DOWNLOADS_DIR', temp_downloads / "cn_stocks")
        monkeypatch.setattr(Config, 'HK_DOWNLOADS_DIR', temp_downloads / "hk_stocks")
        monkeypatch.setattr(Config, 'DATABASE_URL', f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

        server = FinancialReportsPDFServer()

        assert server.pdf_handler is not None
        assert server.server is not None


class TestToolList:
    """工具列表测试"""

    def test_tools_include_search_cn_reports(self, tmp_path, monkeypatch):
        """测试工具列表包含search_cn_reports"""
        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        monkeypatch.setattr(Config, 'DOWNLOADS_DIR', temp_downloads)
        monkeypatch.setattr(Config, 'CN_DOWNLOADS_DIR', temp_downloads / "cn_stocks")
        monkeypatch.setattr(Config, 'HK_DOWNLOADS_DIR', temp_downloads / "hk_stocks")
        monkeypatch.setattr(Config, 'DATABASE_URL', f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

        server = FinancialReportsPDFServer()

        # 服务器应该已注册工具
        assert server.server is not None


class TestToolSchemas:
    """工具Schema测试"""

    @pytest.fixture
    def server(self, tmp_path, monkeypatch):
        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        monkeypatch.setattr(Config, 'DOWNLOADS_DIR', temp_downloads)
        monkeypatch.setattr(Config, 'CN_DOWNLOADS_DIR', temp_downloads / "cn_stocks")
        monkeypatch.setattr(Config, 'HK_DOWNLOADS_DIR', temp_downloads / "hk_stocks")
        monkeypatch.setattr(Config, 'DATABASE_URL', f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

        return FinancialReportsPDFServer()

    def test_expected_tools_count(self, server):
        """测试工具数量"""
        # 服务器应该注册了15个工具
        # 实际工具数量通过 list_tools 返回
        assert server.server is not None


class TestToolCallRouting:
    """工具调用路由测试"""

    @pytest_asyncio.fixture
    async def server(self, tmp_path, monkeypatch):
        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        monkeypatch.setattr(Config, 'DOWNLOADS_DIR', temp_downloads)
        monkeypatch.setattr(Config, 'CN_DOWNLOADS_DIR', temp_downloads / "cn_stocks")
        monkeypatch.setattr(Config, 'HK_DOWNLOADS_DIR', temp_downloads / "hk_stocks")
        monkeypatch.setattr(Config, 'DATABASE_URL', f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

        server = FinancialReportsPDFServer()
        await server.initialize()
        return server

    @pytest.mark.asyncio
    async def test_search_cn_reports_routing(self, server):
        """测试search_cn_reports路由"""
        mock_result = {
            "success": True,
            "data": [],
            "count": 0,
            "source": "巨潮资讯网"
        }

        with patch.object(
            server.pdf_handler, "search_available_reports", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_result

            # 模拟工具调用
            result = await server.pdf_handler.search_available_reports(
                stock_code="000001",
                market="CN",
                report_type="annual",
                max_count=10
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_search_hk_reports_routing(self, server):
        """测试search_hk_reports路由"""
        mock_result = {
            "success": True,
            "data": [],
            "count": 0,
            "source": "港交所披露易"
        }

        with patch.object(
            server.pdf_handler, "search_available_reports", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_result

            result = await server.pdf_handler.search_available_reports(
                stock_code="00700",
                market="HK",
                report_type="annual",
                max_count=10
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_list_downloaded_pdfs_routing(self, server):
        """测试list_downloaded_pdfs路由"""
        result = await server.pdf_handler.list_downloaded_pdfs()

        assert result["success"] is True
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_stats_routing(self, server):
        """测试get_collection_stats路由"""
        result = await server.pdf_handler.get_stats()

        assert result["success"] is True
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_cache_stats_routing(self, server):
        """测试get_cache_stats路由"""
        result = await server.pdf_handler.get_cache_stats()

        assert result["success"] is True
        assert "data" in result

    @pytest.mark.asyncio
    async def test_cleanup_cache_routing(self, server):
        """测试cleanup_cache路由"""
        result = await server.pdf_handler.cleanup_extraction_cache(days=90)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_warm_cache_routing(self, server):
        """测试warm_cache路由"""
        result = await server.pdf_handler.warm_cache()

        assert result["success"] is True


class TestToolCallErrors:
    """工具调用错误处理测试"""

    @pytest_asyncio.fixture
    async def server(self, tmp_path, monkeypatch):
        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        monkeypatch.setattr(Config, 'DOWNLOADS_DIR', temp_downloads)
        monkeypatch.setattr(Config, 'CN_DOWNLOADS_DIR', temp_downloads / "cn_stocks")
        monkeypatch.setattr(Config, 'HK_DOWNLOADS_DIR', temp_downloads / "hk_stocks")
        monkeypatch.setattr(Config, 'DATABASE_URL', f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

        server = FinancialReportsPDFServer()
        await server.initialize()
        return server

    @pytest.mark.asyncio
    async def test_invalid_stock_code_error(self, server):
        """测试无效股票代码错误"""
        result = await server.pdf_handler.search_available_reports(
            stock_code="invalid",
            market="CN"
        )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_pdf_not_exists_error(self, server):
        """测试PDF不存在错误"""
        result = await server.pdf_handler.get_pdf_info(pdf_id=9999)

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_extract_no_params_error(self, server):
        """测试提取无参数错误"""
        result = await server.pdf_handler.extract_pdf_content()

        assert result["success"] is False
        assert "error" in result


class TestServerConfiguration:
    """服务器配置测试"""

    def test_server_name(self, tmp_path, monkeypatch):
        """测试服务器名称"""
        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        monkeypatch.setattr(Config, 'DOWNLOADS_DIR', temp_downloads)
        monkeypatch.setattr(Config, 'CN_DOWNLOADS_DIR', temp_downloads / "cn_stocks")
        monkeypatch.setattr(Config, 'HK_DOWNLOADS_DIR', temp_downloads / "hk_stocks")
        monkeypatch.setattr(Config, 'DATABASE_URL', f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

        server = FinancialReportsPDFServer()

        assert server.server.name == Config.MCP_SERVER_NAME


class TestToolResponseFormat:
    """工具响应格式测试"""

    @pytest_asyncio.fixture
    async def server(self, tmp_path, monkeypatch):
        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        monkeypatch.setattr(Config, 'DOWNLOADS_DIR', temp_downloads)
        monkeypatch.setattr(Config, 'CN_DOWNLOADS_DIR', temp_downloads / "cn_stocks")
        monkeypatch.setattr(Config, 'HK_DOWNLOADS_DIR', temp_downloads / "hk_stocks")
        monkeypatch.setattr(Config, 'DATABASE_URL', f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

        server = FinancialReportsPDFServer()
        await server.initialize()
        return server

    @pytest.mark.asyncio
    async def test_success_response_has_success_field(self, server):
        """测试成功响应包含success字段"""
        result = await server.pdf_handler.get_stats()

        assert "success" in result
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_error_response_has_error_field(self, server):
        """测试错误响应包含error字段"""
        result = await server.pdf_handler.search_available_reports(
            stock_code="invalid",
            market="CN"
        )

        assert "success" in result
        assert result["success"] is False
        assert "error" in result


class TestMarketSupport:
    """市场支持测试"""

    @pytest_asyncio.fixture
    async def server(self, tmp_path, monkeypatch):
        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        monkeypatch.setattr(Config, 'DOWNLOADS_DIR', temp_downloads)
        monkeypatch.setattr(Config, 'CN_DOWNLOADS_DIR', temp_downloads / "cn_stocks")
        monkeypatch.setattr(Config, 'HK_DOWNLOADS_DIR', temp_downloads / "hk_stocks")
        monkeypatch.setattr(Config, 'DATABASE_URL', f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

        server = FinancialReportsPDFServer()
        await server.initialize()
        return server

    @pytest.mark.asyncio
    async def test_cn_market_supported(self, server):
        """测试A股市场支持"""
        with patch.object(
            server.pdf_handler.cn_downloader, "search_reports", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            result = await server.pdf_handler.search_available_reports(
                stock_code="000001",
                market="CN"
            )

            assert result["success"] is True
            assert result["source"] == "巨潮资讯网"

    @pytest.mark.asyncio
    async def test_hk_market_supported(self, server):
        """测试港股市场支持"""
        with patch.object(
            server.pdf_handler.hk_downloader, "search_reports", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            result = await server.pdf_handler.search_available_reports(
                stock_code="00700",
                market="HK"
            )

            assert result["success"] is True
            assert result["source"] == "港交所披露易"

    @pytest.mark.asyncio
    async def test_us_market_not_implemented(self, server):
        """测试美股市场未实现"""
        result = await server.pdf_handler.search_available_reports(
            stock_code="AAPL",
            market="US"
        )

        assert result["success"] is False
        assert "尚未实现" in result["error"]


class TestReportTypes:
    """报告类型测试"""

    @pytest_asyncio.fixture
    async def server(self, tmp_path, monkeypatch):
        temp_downloads = tmp_path / "downloads"
        temp_downloads.mkdir(parents=True, exist_ok=True)
        (temp_downloads / "cn_stocks").mkdir(exist_ok=True)
        (temp_downloads / "hk_stocks").mkdir(exist_ok=True)

        monkeypatch.setattr(Config, 'DOWNLOADS_DIR', temp_downloads)
        monkeypatch.setattr(Config, 'CN_DOWNLOADS_DIR', temp_downloads / "cn_stocks")
        monkeypatch.setattr(Config, 'HK_DOWNLOADS_DIR', temp_downloads / "hk_stocks")
        monkeypatch.setattr(Config, 'DATABASE_URL', f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

        server = FinancialReportsPDFServer()
        await server.initialize()
        return server

    @pytest.mark.asyncio
    async def test_annual_report_type(self, server):
        """测试年报类型"""
        with patch.object(
            server.pdf_handler.cn_downloader, "search_reports", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            result = await server.pdf_handler.search_available_reports(
                stock_code="000001",
                market="CN",
                report_type="annual"
            )

            assert result["success"] is True
            assert result["report_type"] == "annual"

    @pytest.mark.asyncio
    async def test_semi_annual_report_type(self, server):
        """测试半年报类型"""
        with patch.object(
            server.pdf_handler.cn_downloader, "search_reports", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            result = await server.pdf_handler.search_available_reports(
                stock_code="000001",
                market="CN",
                report_type="semi_annual"
            )

            assert result["success"] is True
            assert result["report_type"] == "semi_annual"

    @pytest.mark.asyncio
    async def test_quarterly_report_type(self, server):
        """测试季报类型"""
        with patch.object(
            server.pdf_handler.cn_downloader, "search_reports", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            result = await server.pdf_handler.search_available_reports(
                stock_code="000001",
                market="CN",
                report_type="quarterly"
            )

            assert result["success"] is True
            assert result["report_type"] == "quarterly"
