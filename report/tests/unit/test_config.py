"""
配置单元测试
测试 Config 类的所有配置项和方法
"""
import os
from pathlib import Path

import pytest

from src.config import Config


class TestConfigDirectories:
    """配置目录测试"""

    def test_base_dir_is_path(self):
        """测试 BASE_DIR 是 Path 类型"""
        assert isinstance(Config.BASE_DIR, Path)

    def test_base_dir_exists(self):
        """测试 BASE_DIR 指向存在的目录"""
        assert Config.BASE_DIR.exists()

    def test_project_root_is_parent_of_base_dir(self):
        """测试 PROJECT_ROOT 是 BASE_DIR 的父目录"""
        assert Config.PROJECT_ROOT == Config.BASE_DIR.parent

    def test_downloads_dir_under_project_root(self):
        """测试下载目录在项目根目录下"""
        assert str(Config.DOWNLOADS_DIR).startswith(str(Config.PROJECT_ROOT))

    def test_cn_downloads_dir(self):
        """测试A股下载目录配置"""
        assert Config.CN_DOWNLOADS_DIR == Config.DOWNLOADS_DIR / "cn_stocks"

    def test_hk_downloads_dir(self):
        """测试港股下载目录配置"""
        assert Config.HK_DOWNLOADS_DIR == Config.DOWNLOADS_DIR / "hk_stocks"

    def test_us_downloads_dir(self):
        """测试美股下载目录配置"""
        assert Config.US_DOWNLOADS_DIR == Config.DOWNLOADS_DIR / "us_stocks"

    def test_database_url_format(self):
        """测试数据库URL格式"""
        assert Config.DATABASE_URL.startswith("sqlite+aiosqlite:///")
        assert Config.DATABASE_URL.endswith(".db")


class TestConfigValues:
    """配置值测试"""

    def test_mcp_server_name(self):
        """测试MCP服务器名称"""
        assert Config.MCP_SERVER_NAME == "financial-reports-pdf-server"

    def test_mcp_server_version(self):
        """测试MCP服务器版本"""
        assert Config.MCP_SERVER_VERSION == "1.0.0"

    def test_supported_markets(self):
        """测试支持的市场列表"""
        assert "CN" in Config.SUPPORTED_MARKETS
        assert "HK" in Config.SUPPORTED_MARKETS
        assert "US" in Config.SUPPORTED_MARKETS
        assert len(Config.SUPPORTED_MARKETS) == 3

    def test_supported_report_types(self):
        """测试支持的报表类型"""
        assert "annual" in Config.SUPPORTED_REPORT_TYPES
        assert "semi_annual" in Config.SUPPORTED_REPORT_TYPES
        assert "quarterly" in Config.SUPPORTED_REPORT_TYPES
        assert "all" in Config.SUPPORTED_REPORT_TYPES

    def test_request_delay(self):
        """测试请求延迟配置"""
        assert Config.REQUEST_DELAY == 2.0
        assert isinstance(Config.REQUEST_DELAY, float)

    def test_max_retries(self):
        """测试最大重试次数"""
        assert Config.MAX_RETRIES == 3
        assert isinstance(Config.MAX_RETRIES, int)

    def test_request_timeout(self):
        """测试请求超时配置"""
        assert Config.REQUEST_TIMEOUT == 30
        assert isinstance(Config.REQUEST_TIMEOUT, int)

    def test_cache_ttl(self):
        """测试缓存TTL配置"""
        assert Config.CACHE_TTL == 3600
        assert isinstance(Config.CACHE_TTL, int)

    def test_max_cache_size(self):
        """测试最大缓存大小"""
        assert Config.MAX_CACHE_SIZE == 1000
        assert isinstance(Config.MAX_CACHE_SIZE, int)

    def test_max_file_size(self):
        """测试最大文件大小配置"""
        assert Config.MAX_FILE_SIZE == 100 * 1024 * 1024  # 100MB
        assert isinstance(Config.MAX_FILE_SIZE, int)

    def test_allowed_extensions(self):
        """测试允许的文件扩展名"""
        assert ".pdf" in Config.ALLOWED_EXTENSIONS

    def test_auto_cleanup_days(self):
        """测试自动清理天数"""
        assert Config.AUTO_CLEANUP_DAYS == 90
        assert isinstance(Config.AUTO_CLEANUP_DAYS, int)

    def test_default_search_limit(self):
        """测试默认搜索限制"""
        assert Config.DEFAULT_SEARCH_LIMIT == 20
        assert isinstance(Config.DEFAULT_SEARCH_LIMIT, int)

    def test_max_search_limit(self):
        """测试最大搜索限制"""
        assert Config.MAX_SEARCH_LIMIT == 100
        assert isinstance(Config.MAX_SEARCH_LIMIT, int)


class TestDataSources:
    """数据源配置测试"""

    def test_data_sources_has_cn(self):
        """测试包含A股数据源"""
        assert "CN" in Config.DATA_SOURCES
        cn_source = Config.DATA_SOURCES["CN"]
        assert cn_source["name"] == "巨潮资讯网"
        assert "cninfo.com.cn" in cn_source["base_url"]
        assert cn_source["enabled"] is True

    def test_data_sources_has_hk(self):
        """测试包含港股数据源"""
        assert "HK" in Config.DATA_SOURCES
        hk_source = Config.DATA_SOURCES["HK"]
        assert hk_source["name"] == "港交所披露易"
        assert "hkexnews.hk" in hk_source["base_url"]
        assert hk_source["enabled"] is True

    def test_data_sources_has_us(self):
        """测试包含美股数据源"""
        assert "US" in Config.DATA_SOURCES
        us_source = Config.DATA_SOURCES["US"]
        assert us_source["name"] == "SEC EDGAR"
        assert "sec.gov" in us_source["base_url"]
        assert us_source["enabled"] is True

    def test_cn_source_api_url(self):
        """测试A股数据源API URL"""
        cn_source = Config.DATA_SOURCES["CN"]
        assert "api_url" in cn_source
        assert "hisAnnouncement" in cn_source["api_url"]

    def test_hk_source_api_url(self):
        """测试港股数据源API URL"""
        hk_source = Config.DATA_SOURCES["HK"]
        assert "api_url" in hk_source


class TestSetupDirectories:
    """目录创建测试"""

    def test_setup_directories_creates_dirs(self, tmp_path, monkeypatch):
        """测试 setup_directories 创建目录"""
        # 设置临时目录
        downloads = tmp_path / "downloads"
        monkeypatch.setattr(Config, 'DOWNLOADS_DIR', downloads)
        monkeypatch.setattr(Config, 'CN_DOWNLOADS_DIR', downloads / "cn_stocks")
        monkeypatch.setattr(Config, 'HK_DOWNLOADS_DIR', downloads / "hk_stocks")
        monkeypatch.setattr(Config, 'US_DOWNLOADS_DIR', downloads / "us_stocks")

        # 调用 setup_directories
        Config.setup_directories()

        # 验证目录已创建
        assert downloads.exists()
        assert (downloads / "cn_stocks").exists()
        assert (downloads / "hk_stocks").exists()
        assert (downloads / "us_stocks").exists()

    def test_setup_directories_idempotent(self, tmp_path, monkeypatch):
        """测试多次调用 setup_directories 不会出错"""
        downloads = tmp_path / "downloads"
        monkeypatch.setattr(Config, 'DOWNLOADS_DIR', downloads)
        monkeypatch.setattr(Config, 'CN_DOWNLOADS_DIR', downloads / "cn_stocks")
        monkeypatch.setattr(Config, 'HK_DOWNLOADS_DIR', downloads / "hk_stocks")
        monkeypatch.setattr(Config, 'US_DOWNLOADS_DIR', downloads / "us_stocks")

        # 多次调用不应出错
        Config.setup_directories()
        Config.setup_directories()
        Config.setup_directories()

        assert downloads.exists()


class TestValidateConfig:
    """配置验证测试"""

    def test_validate_config_success(self, tmp_path, monkeypatch, capsys):
        """测试配置验证成功"""
        downloads = tmp_path / "downloads"
        monkeypatch.setattr(Config, 'DOWNLOADS_DIR', downloads)
        monkeypatch.setattr(Config, 'CN_DOWNLOADS_DIR', downloads / "cn_stocks")
        monkeypatch.setattr(Config, 'HK_DOWNLOADS_DIR', downloads / "hk_stocks")
        monkeypatch.setattr(Config, 'US_DOWNLOADS_DIR', downloads / "us_stocks")

        result = Config.validate_config()

        assert result is True
        captured = capsys.readouterr()
        assert "验证完成" in captured.out


class TestLogConfig:
    """日志配置测试"""

    def test_log_level_default(self):
        """测试默认日志级别"""
        # 默认从环境变量读取，如果没有则为 INFO
        assert Config.LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR"]

    def test_log_file_path(self):
        """测试日志文件路径"""
        assert isinstance(Config.LOG_FILE, Path)
        assert Config.LOG_FILE.name.endswith(".log")
