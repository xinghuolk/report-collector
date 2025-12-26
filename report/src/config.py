"""
财报PDF收集MCP服务器配置文件
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """配置管理类"""
    
    # MCP服务器配置
    MCP_SERVER_NAME = "financial-reports-pdf-server"
    MCP_SERVER_VERSION = "1.0.0"
    MCP_SERVER_DESCRIPTION = "财报PDF收集服务器 - 从官方网站下载上市公司财报PDF文件"
    
    # 文件存储配置
    BASE_DIR = Path(__file__).parent
    PROJECT_ROOT = BASE_DIR.parent  # 项目根目录
    DOWNLOADS_DIR = PROJECT_ROOT / "downloads"  # 下载到项目根目录/downloads
    DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR}/reports.db"
    
    # 下载目录结构
    CN_DOWNLOADS_DIR = DOWNLOADS_DIR / "cn_stocks"      # 中国A股
    HK_DOWNLOADS_DIR = DOWNLOADS_DIR / "hk_stocks"      # 港股
    US_DOWNLOADS_DIR = DOWNLOADS_DIR / "us_stocks"      # 美股
    
    # 请求配置
    REQUEST_DELAY = 2.0  # 请求间隔2秒，避免过于频繁
    MAX_RETRIES = 3
    REQUEST_TIMEOUT = 30
    
    # 缓存配置
    CACHE_TTL = 3600  # 缓存1小时
    MAX_CACHE_SIZE = 1000
    
    # 支持的市场
    SUPPORTED_MARKETS = ["CN", "HK", "US"]
    
    # 支持的报表类型
    SUPPORTED_REPORT_TYPES = [
        "annual",           # 年报
        "semi_annual",      # 半年报
        "quarterly",        # 季报
        "all"               # 所有类型
    ]
    
    # 数据源配置
    DATA_SOURCES = {
        "CN": {
            "name": "巨潮资讯网",
            "base_url": "http://www.cninfo.com.cn",
            "api_url": "http://www.cninfo.com.cn/new/hisAnnouncement/query",
            "enabled": True
        },
        "HK": {
            "name": "港交所披露易",
            "base_url": "https://www1.hkexnews.hk",
            "api_url": "https://www1.hkexnews.hk/ncms/json/eds/lcisehk1relsdc_{page}.json",
            "enabled": True
        },
        "US": {
            "name": "SEC EDGAR",
            "base_url": "https://www.sec.gov/edgar",
            "enabled": True
        }
    }
    
    # 文件管理配置
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS = ['.pdf']
    AUTO_CLEANUP_DAYS = 90  # 自动清理90天前的文件
    
    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = BASE_DIR / "financial_reports_pdf.log"

    # 搜索配置
    DEFAULT_SEARCH_LIMIT = 20
    MAX_SEARCH_LIMIT = 100

    # HTTP API服务器配置
    HTTP_HOST = os.getenv("HTTP_HOST", "0.0.0.0")
    HTTP_PORT = int(os.getenv("HTTP_PORT", "8000"))
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    API_PREFIX = "/api/v1"
    
    @classmethod
    def setup_directories(cls):
        """创建必要的目录"""
        directories = [
            cls.DOWNLOADS_DIR,
            cls.CN_DOWNLOADS_DIR,
            cls.HK_DOWNLOADS_DIR,
            cls.US_DOWNLOADS_DIR
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            
    @classmethod
    def validate_config(cls) -> bool:
        """验证配置"""
        try:
            # 创建目录
            cls.setup_directories()
            
            # 检查磁盘空间（可选）
            # 检查网络连接（可选）
            
            print("✅ PDF收集服务器配置验证完成")
            return True
            
        except Exception as e:
            print(f"❌ 配置验证失败: {e}")
            return False