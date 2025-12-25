"""
测试样本数据
包含各种测试场景的数据
"""
from datetime import datetime

# ==================== 股票代码样本 ====================

# 有效的 A 股代码
VALID_CN_STOCK_CODES = [
    "000001",  # 平安银行
    "600519",  # 贵州茅台
    "000858",  # 五粮液
    "601318",  # 中国平安
    "000002",  # 万科A
]

# 无效的 A 股代码
INVALID_CN_STOCK_CODES = [
    "00001",    # 5位
    "6005190",  # 7位
    "abcdef",   # 非数字
    "00000a",   # 包含字母
    "",         # 空字符串
    None,       # None
]

# 有效的港股代码
VALID_HK_STOCK_CODES = [
    "00700",  # 腾讯
    "01810",  # 小米
    "09988",  # 阿里巴巴
    "00005",  # 汇丰
    "02318",  # 中国平安
]

# 无效的港股代码
INVALID_HK_STOCK_CODES = [
    "0700",    # 4位
    "007000",  # 6位
    "ABCDE",   # 字母
    "0070a",   # 包含字母
]

# 有效的美股代码
VALID_US_STOCK_CODES = [
    "AAPL",   # 苹果
    "MSFT",   # 微软
    "GOOGL",  # 谷歌
    "AMZN",   # 亚马逊
    "TSLA",   # 特斯拉
]

# 无效的美股代码
INVALID_US_STOCK_CODES = [
    "AAAAAA",  # 6位
    "12345",   # 数字
    "aaa",     # 小写（验证器应该接受并转大写）
    "",        # 空字符串
]


# ==================== 市场代码样本 ====================

VALID_MARKETS = ["CN", "HK", "US", "cn", "hk", "us"]
INVALID_MARKETS = ["JP", "UK", "EU", "", None, "CHINA", "HONGKONG"]


# ==================== 报告类型样本 ====================

VALID_REPORT_TYPES = [
    "annual",
    "semi_annual",
    "quarterly",
    "balance_sheet",
    "income_statement",
    "cash_flow",
]

INVALID_REPORT_TYPES = [
    "monthly",
    "daily",
    "weekly",
    "",
    None,
    "年报",
]


# ==================== 日期样本 ====================

VALID_DATE_RANGES = [
    ("2020-01-01", "2020-12-31"),
    ("2023-01-01", "2023-06-30"),
    ("2019-01-01", "2024-12-31"),
]

INVALID_DATE_RANGES = [
    ("2020-12-31", "2020-01-01"),  # 开始晚于结束
    ("2020-13-01", "2020-12-31"),  # 无效月份
    ("2020-01-32", "2020-12-31"),  # 无效日期
    ("2010-01-01", "2025-12-31"),  # 范围超过10年
]

VALID_YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
INVALID_YEARS = [1985, 1989, 2030, 2050, "2023", None]


# ==================== 搜索关键词样本 ====================

VALID_KEYWORDS = [
    "年报",
    "半年报",
    "季度报告",
    "财务报表",
    "annual report",
]

INVALID_KEYWORDS = [
    "",
    "   ",
    "a" * 51,  # 超过50字符
    "test<script>",  # 包含危险字符
    "select; drop",  # 包含分号
    "echo $HOME",    # 包含$
]


# ==================== 财务数据样本 ====================

SAMPLE_INCOME_STATEMENT = {
    "revenue": 150000000000,
    "revenue_yoy": 5.2,
    "operating_cost": 80000000000,
    "gross_profit": 70000000000,
    "gross_margin": 46.67,
    "net_profit": 10000000000,
    "net_profit_yoy": 3.5,
    "net_profit_after_deduction": 9500000000,
    "rd_expense": 5000000000,
    "rd_expense_ratio": 3.33,
}

SAMPLE_BALANCE_SHEET = {
    "total_assets": 500000000000,
    "total_liabilities": 450000000000,
    "total_equity": 50000000000,
    "cash_and_equivalents": 20000000000,
    "accounts_receivable": 10000000000,
    "inventory": 5000000000,
    "goodwill": 3000000000,
    "intangible_assets": 2000000000,
}

SAMPLE_CASH_FLOW = {
    "operating_cash_flow": 15000000000,
    "investing_cash_flow": -8000000000,
    "financing_cash_flow": -5000000000,
    "net_cash_flow": 2000000000,
}

SAMPLE_FINANCIAL_METRICS = {
    "roe": 20.0,
    "roa": 2.0,
    "debt_ratio": 90.0,
    "eps": 5.5,
    "gross_margin": 46.67,
    "net_margin": 6.67,
}

SAMPLE_RELATED_PARTY_TRANSACTIONS = [
    {
        "party_name": "关联公司A",
        "transaction_type": "销售商品",
        "amount": 1000000000,
        "percentage": 0.67,
    },
    {
        "party_name": "关联公司B",
        "transaction_type": "采购商品",
        "amount": 500000000,
        "percentage": 0.33,
    },
]


# ==================== PDF 记录样本 ====================

def get_sample_pdf_info(
    stock_code: str = "000001",
    market: str = "CN",
    report_type: str = "annual",
    year: int = 2023
) -> dict:
    """生成样本PDF信息"""
    return {
        "stock_code": stock_code,
        "stock_name": STOCK_NAMES.get(stock_code, "测试公司"),
        "market": market,
        "report_type": report_type,
        "report_year": year,
        "report_quarter": None,
        "announcement_date": datetime(year + 1, 3, 15),
        "original_title": f"{STOCK_NAMES.get(stock_code, '测试公司')}{year}年{REPORT_TYPE_NAMES.get(report_type, '报告')}",
        "file_path": f"/tmp/test/{stock_code}/{report_type}/{year}_{report_type}.pdf",
        "file_name": f"{year}_{report_type}.pdf",
        "file_size": 1024000,
        "file_hash": f"hash_{stock_code}_{year}_{report_type}",
        "source_url": f"http://example.com/{stock_code}/{year}.pdf",
        "source_name": SOURCE_NAMES.get(market, "未知来源"),
        "metadata_json": None,
    }


STOCK_NAMES = {
    "000001": "平安银行",
    "600519": "贵州茅台",
    "000858": "五粮液",
    "00700": "腾讯控股",
    "01810": "小米集团",
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
}

REPORT_TYPE_NAMES = {
    "annual": "年度报告",
    "semi_annual": "半年度报告",
    "quarterly": "季度报告",
}

SOURCE_NAMES = {
    "CN": "巨潮资讯网",
    "HK": "港交所披露易",
    "US": "SEC EDGAR",
}


# ==================== API 响应样本 ====================

SAMPLE_CNINFO_RESPONSE = {
    "announcements": [
        {
            "id": "12345",
            "secCode": "000001",
            "secName": "平安银行",
            "announcementTitle": "平安银行股份有限公司2023年年度报告",
            "announcementTime": "2024-03-15 00:00:00",
            "adjunctUrl": "/finalpage/2024-03-15/12345.PDF",
            "announcementType": "年报",
        }
    ],
    "totalRecordNum": 1,
    "totalPages": 1,
    "hasMore": False,
}

SAMPLE_HKEX_RESPONSE = {
    "data": [
        {
            "stock_code": "00700",
            "stock_name": "騰訊控股",
            "title": "二零二三年年報",
            "year": 2023,
            "report_type": "annual",
            "language": "tc",
            "url": "https://www1.hkexnews.hk/listedco/listconews/sehk/2024/0320/12345.pdf",
            "announcement_date": "2024-03-20",
        }
    ]
}


# ==================== 数值解析样本 ====================

NUMBER_PARSING_SAMPLES = [
    # (输入, 期望输出)
    ("1,234,567", 1234567),
    ("1,234,567.89", 1234567.89),
    ("-1,234,567", -1234567),
    ("12.5%", 12.5),
    ("100万", 1000000),
    ("1.5亿", 150000000),
    ("10亿", 1000000000),
    ("100", 100),
    ("0", 0),
    ("-50.5", -50.5),
]

INVALID_NUMBER_SAMPLES = [
    "abc",
    "N/A",
    "-",
    "",
    None,
    "不适用",
]


# ==================== MCP 请求样本 ====================

SAMPLE_MCP_REQUESTS = {
    "search_cn_reports": {
        "method": "search_cn_reports",
        "params": {
            "stock_code": "000001",
            "report_type": "annual",
            "max_count": 10,
        },
    },
    "search_hk_reports": {
        "method": "search_hk_reports",
        "params": {
            "stock_code": "00700",
            "report_type": "annual",
            "max_count": 10,
        },
    },
    "download_cn_report": {
        "method": "download_cn_report",
        "params": {
            "stock_code": "000001",
            "report_type": "annual",
        },
    },
    "extract_pdf_content": {
        "method": "extract_pdf_content",
        "params": {
            "pdf_path": "/tmp/test.pdf",
        },
    },
}

INVALID_MCP_REQUESTS = {
    "missing_method": {
        "params": {"stock_code": "000001"},
    },
    "missing_params": {
        "method": "search_cn_reports",
    },
    "invalid_stock_code": {
        "method": "search_cn_reports",
        "params": {"stock_code": "abc", "market": "CN"},
    },
    "invalid_market": {
        "method": "get_report",
        "params": {"symbol": "000001", "market": "JP"},
    },
}
