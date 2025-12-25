"""
测试共享 fixtures
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


# ==================== 事件循环配置 ====================

@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环用于整个测试会话"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==================== 临时目录和文件 ====================

@pytest.fixture
def temp_downloads(tmp_path):
    """临时下载目录"""
    downloads = tmp_path / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    cn_dir = downloads / "cn_stocks"
    hk_dir = downloads / "hk_stocks"
    us_dir = downloads / "us_stocks"
    cn_dir.mkdir(parents=True, exist_ok=True)
    hk_dir.mkdir(parents=True, exist_ok=True)
    us_dir.mkdir(parents=True, exist_ok=True)
    return downloads


@pytest.fixture
def temp_pdf_file(tmp_path):
    """创建最小有效PDF用于测试"""
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
196
%%EOF
"""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def temp_stock_pdf(tmp_path, temp_pdf_file):
    """创建带有股票信息的测试PDF结构"""
    stock_dir = tmp_path / "downloads" / "cn_stocks" / "000001" / "annual"
    stock_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = stock_dir / "2023_annual_report.pdf"
    pdf_path.write_bytes(temp_pdf_file.read_bytes())

    # 创建股票名称文件
    name_file = stock_dir.parent / ".stock_name.txt"
    name_file.write_text("平安银行")

    return pdf_path


# ==================== 数据库 fixtures ====================

@pytest_asyncio.fixture
async def pdf_manager(tmp_path):
    """使用临时数据库的 PDFManager"""
    from src.config import Config
    from src.pdf_manager import PDFManager

    # 创建临时数据库
    db_path = tmp_path / "test_reports.db"
    original_db_url = Config.DATABASE_URL
    Config.DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"

    manager = PDFManager()
    await manager.initialize()

    yield manager

    # 恢复原始配置
    Config.DATABASE_URL = original_db_url


@pytest_asyncio.fixture
async def pdf_handler(tmp_path, temp_downloads):
    """使用临时目录的 PDFHandler"""
    from src.config import Config
    from src.handlers.pdf_handler import PDFHandler

    # 保存原始配置
    original_downloads = Config.DOWNLOADS_DIR
    original_cn_dir = Config.CN_DOWNLOADS_DIR
    original_hk_dir = Config.HK_DOWNLOADS_DIR
    original_us_dir = Config.US_DOWNLOADS_DIR
    original_db_url = Config.DATABASE_URL

    # 设置临时配置
    db_path = tmp_path / "test_reports.db"
    Config.DOWNLOADS_DIR = temp_downloads
    Config.CN_DOWNLOADS_DIR = temp_downloads / "cn_stocks"
    Config.HK_DOWNLOADS_DIR = temp_downloads / "hk_stocks"
    Config.US_DOWNLOADS_DIR = temp_downloads / "us_stocks"
    Config.DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"

    handler = PDFHandler()
    await handler.initialize()

    yield handler

    # 恢复原始配置
    Config.DOWNLOADS_DIR = original_downloads
    Config.CN_DOWNLOADS_DIR = original_cn_dir
    Config.HK_DOWNLOADS_DIR = original_hk_dir
    Config.US_DOWNLOADS_DIR = original_us_dir
    Config.DATABASE_URL = original_db_url


# ==================== 样本数据 fixtures ====================

@pytest.fixture
def sample_pdf_info():
    """标准PDF记录字典"""
    return {
        "stock_code": "000001",
        "stock_name": "平安银行",
        "market": "CN",
        "report_type": "annual",
        "report_year": 2023,
        "report_quarter": None,
        "announcement_date": datetime(2024, 3, 15),
        "original_title": "平安银行股份有限公司2023年年度报告",
        "file_path": "/tmp/test/000001/annual/2023_annual.pdf",
        "file_name": "2023_annual.pdf",
        "file_size": 1024000,
        "file_hash": "abc123def456",
        "source_url": "http://example.com/report.pdf",
        "source_name": "巨潮资讯网",
        "metadata_json": None
    }


@pytest.fixture
def sample_hk_pdf_info():
    """港股PDF记录字典"""
    return {
        "stock_code": "00700",
        "stock_name": "騰訊控股",
        "market": "HK",
        "report_type": "annual",
        "report_year": 2023,
        "report_quarter": None,
        "announcement_date": datetime(2024, 3, 20),
        "original_title": "騰訊控股有限公司2023年年度報告",
        "file_path": "/tmp/test/00700/annual/2023_annual_tc.pdf",
        "file_name": "2023_annual_tc.pdf",
        "file_size": 2048000,
        "file_hash": "hk123abc456",
        "source_url": "https://www1.hkexnews.hk/report.pdf",
        "source_name": "港交所披露易",
        "metadata_json": None
    }


@pytest.fixture
def mock_extraction_result():
    """完整的提取结果样例"""
    return {
        "success": True,
        "income_statement": {
            "revenue": 1500000000000,
            "revenue_yoy": 5.2,
            "operating_cost": 800000000000,
            "gross_profit": 700000000000,
            "net_profit": 100000000000,
            "net_profit_after_deduction": 95000000000,
            "rd_expense": 50000000000
        },
        "balance_sheet": {
            "total_assets": 5000000000000,
            "total_liabilities": 4500000000000,
            "total_equity": 500000000000,
            "cash_and_equivalents": 200000000000,
            "accounts_receivable": 100000000000,
            "inventory": 50000000000,
            "goodwill": 30000000000,
            "intangible_assets": 20000000000
        },
        "cash_flow_statement": {
            "operating_cash_flow": 150000000000,
            "investing_cash_flow": -80000000000,
            "financing_cash_flow": -50000000000,
            "net_cash_flow": 20000000000
        },
        "financial_metrics": {
            "roe": 20.0,
            "roa": 2.0,
            "debt_ratio": 90.0,
            "eps": 5.5,
            "gross_margin": 46.67,
            "net_margin": 6.67
        },
        "related_party_transactions": [
            {
                "party_name": "关联公司A",
                "transaction_type": "销售商品",
                "amount": 1000000000,
                "percentage": 0.07
            }
        ],
        "metadata": {
            "stock_code": "000001",
            "stock_name": "平安银行",
            "report_type": "annual",
            "report_year": 2023,
            "language": "zh"
        },
        "extraction_summary": {
            "total_pages": 300,
            "tables_extracted": 50,
            "fields_extracted": 25
        }
    }


@pytest.fixture
def mock_cninfo_search_results():
    """巨潮资讯网搜索结果样例"""
    return {
        "announcements": [
            {
                "id": "12345",
                "secCode": "000001",
                "secName": "平安银行",
                "announcementTitle": "平安银行股份有限公司2023年年度报告",
                "announcementTime": "2024-03-15 00:00:00",
                "adjunctUrl": "/finalpage/2024-03-15/12345.PDF",
                "announcementType": "年报"
            },
            {
                "id": "12346",
                "secCode": "000001",
                "secName": "平安银行",
                "announcementTitle": "平安银行股份有限公司2022年年度报告",
                "announcementTime": "2023-03-18 00:00:00",
                "adjunctUrl": "/finalpage/2023-03-18/12346.PDF",
                "announcementType": "年报"
            }
        ],
        "totalRecordNum": 2,
        "totalPages": 1
    }


@pytest.fixture
def mock_hkex_search_results():
    """港交所搜索结果样例"""
    return [
        {
            "stock_code": "00700",
            "stock_name": "騰訊控股",
            "title": "二零二三年年報",
            "year": 2023,
            "report_type": "annual",
            "language": "tc",
            "url": "https://www1.hkexnews.hk/listedco/listconews/sehk/2024/0320/12345.pdf",
            "announcement_date": "2024-03-20"
        },
        {
            "stock_code": "00700",
            "stock_name": "Tencent Holdings",
            "title": "Annual Report 2023",
            "year": 2023,
            "report_type": "annual",
            "language": "en",
            "url": "https://www1.hkexnews.hk/listedco/listconews/sehk/2024/0320/12346.pdf",
            "announcement_date": "2024-03-20"
        }
    ]


# ==================== Mock fixtures ====================

@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp.ClientSession"""
    mock_session = MagicMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={})
    mock_response.read = AsyncMock(return_value=b"PDF content")
    mock_response.headers = {"Content-Type": "application/pdf"}
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


@pytest.fixture
def mock_cninfo_api(mocker, mock_cninfo_search_results, temp_pdf_file):
    """Mock 巨潮资讯网 API"""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_cninfo_search_results)
    mock_response.read = AsyncMock(return_value=temp_pdf_file.read_bytes())
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mocker.patch('aiohttp.ClientSession', return_value=mock_session)


@pytest.fixture
def mock_hkex_api(mocker, mock_hkex_search_results, temp_pdf_file):
    """Mock 港交所 API"""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"data": mock_hkex_search_results})
    mock_response.read = AsyncMock(return_value=temp_pdf_file.read_bytes())
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mocker.patch('aiohttp.ClientSession', return_value=mock_session)


@pytest.fixture
def mock_pdf_extractor(mocker, mock_extraction_result):
    """Mock PDF内容提取器"""
    return mocker.patch(
        'src.pdf_parser.content_extractor.FinancialReportExtractor.extract',
        new_callable=AsyncMock,
        return_value=mock_extraction_result
    )


# ==================== 配置相关 fixtures ====================

@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    """临时配置"""
    from src.config import Config

    # 保存原始值
    original_base_dir = Config.BASE_DIR
    original_downloads_dir = Config.DOWNLOADS_DIR

    # 设置临时值
    downloads = tmp_path / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(Config, 'DOWNLOADS_DIR', downloads)
    monkeypatch.setattr(Config, 'CN_DOWNLOADS_DIR', downloads / "cn_stocks")
    monkeypatch.setattr(Config, 'HK_DOWNLOADS_DIR', downloads / "hk_stocks")
    monkeypatch.setattr(Config, 'US_DOWNLOADS_DIR', downloads / "us_stocks")

    yield Config

    # 恢复原始值（monkeypatch 会自动恢复）


# ==================== 辅助函数 ====================

@pytest.fixture
def create_temp_pdf():
    """工厂fixture：创建临时PDF文件（每个文件内容不同）"""
    counter = [0]  # 使用列表以便在闭包中修改

    def _create_pdf(directory: Path, filename: str = "test.pdf") -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        counter[0] += 1
        # 每个PDF文件内容不同，确保哈希不同
        pdf_content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Unique ID: {counter[0]}) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000200 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
300
%%EOF
""".encode()
        pdf_path = directory / filename
        pdf_path.write_bytes(pdf_content)
        return pdf_path

    return _create_pdf
