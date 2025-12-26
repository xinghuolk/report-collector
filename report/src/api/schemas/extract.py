"""
内容提取相关Schema
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    """提取请求"""

    stock_code: str = Field(..., description="股票代码")
    market: str = Field(default="CN", pattern=r"^(CN|HK|US)$", description="市场")
    report_type: str = Field(default="annual", description="报告类型")
    year: Optional[int] = Field(default=None, description="年份")
    use_cache: bool = Field(default=True, description="是否使用缓存")


class ExtractByPathRequest(BaseModel):
    """按路径提取请求"""

    file_path: str = Field(..., description="PDF文件路径")
    use_cache: bool = Field(default=True, description="是否使用缓存")


class IncomeStatement(BaseModel):
    """利润表"""

    revenue: Optional[float] = Field(default=None, description="营业收入")
    operating_cost: Optional[float] = Field(default=None, description="营业成本")
    gross_profit: Optional[float] = Field(default=None, description="毛利润")
    operating_profit: Optional[float] = Field(default=None, description="营业利润")
    net_profit: Optional[float] = Field(default=None, description="净利润")
    net_profit_deducted: Optional[float] = Field(default=None, description="扣非净利润")
    rd_expense: Optional[float] = Field(default=None, description="研发费用")
    gross_margin: Optional[float] = Field(default=None, description="毛利率%")
    net_margin: Optional[float] = Field(default=None, description="净利率%")


class BalanceSheet(BaseModel):
    """资产负债表"""

    total_assets: Optional[float] = Field(default=None, description="总资产")
    total_liabilities: Optional[float] = Field(default=None, description="总负债")
    total_equity: Optional[float] = Field(default=None, description="所有者权益")
    current_assets: Optional[float] = Field(default=None, description="流动资产")
    current_liabilities: Optional[float] = Field(default=None, description="流动负债")
    cash_and_equivalents: Optional[float] = Field(default=None, description="货币资金")
    accounts_receivable: Optional[float] = Field(default=None, description="应收账款")
    inventory: Optional[float] = Field(default=None, description="存货")


class CashFlowStatement(BaseModel):
    """现金流量表"""

    operating_cash_flow: Optional[float] = Field(
        default=None, description="经营活动现金流"
    )
    investing_cash_flow: Optional[float] = Field(
        default=None, description="投资活动现金流"
    )
    financing_cash_flow: Optional[float] = Field(
        default=None, description="筹资活动现金流"
    )
    free_cash_flow: Optional[float] = Field(default=None, description="自由现金流")


class FinancialMetrics(BaseModel):
    """财务指标"""

    eps: Optional[float] = Field(default=None, description="每股收益")
    bps: Optional[float] = Field(default=None, description="每股净资产")
    roe: Optional[float] = Field(default=None, description="净资产收益率%")
    roa: Optional[float] = Field(default=None, description="总资产收益率%")
    debt_ratio: Optional[float] = Field(default=None, description="资产负债率%")


class ExtractContentResponse(BaseModel):
    """提取内容响应"""

    income_statement: Optional[IncomeStatement] = None
    balance_sheet: Optional[BalanceSheet] = None
    cash_flow_statement: Optional[CashFlowStatement] = None
    financial_metrics: Optional[FinancialMetrics] = None
    metadata: Optional[Dict[str, Any]] = None
    cache_info: Optional[Dict[str, Any]] = None


class ExtractTablesResponse(BaseModel):
    """提取表格响应"""

    tables: List[Dict[str, Any]] = Field(default_factory=list, description="表格列表")
    count: int = Field(description="表格数量")


class ExtractTextResponse(BaseModel):
    """提取文本响应"""

    text: str = Field(description="提取的文本")
    page_count: int = Field(description="页数")
    char_count: int = Field(description="字符数")


class CacheStatsResponse(BaseModel):
    """缓存统计响应"""

    total_cached: int = Field(description="缓存总数")
    cache_size_mb: float = Field(description="缓存大小(MB)")
    oldest_entry: Optional[str] = Field(default=None, description="最旧条目时间")
    newest_entry: Optional[str] = Field(default=None, description="最新条目时间")


class WarmCacheRequest(BaseModel):
    """预热缓存请求"""

    stock_code: Optional[str] = Field(default=None, description="股票代码")
    market: Optional[str] = Field(default=None, description="市场")
    max_files: int = Field(default=10, ge=1, le=50, description="最大文件数")
