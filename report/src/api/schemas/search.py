"""
搜索相关Schema
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ReportInfo(BaseModel):
    """财报信息"""

    title: str = Field(description="财报标题")
    url: str = Field(description="下载URL")
    publish_date: Optional[str] = Field(default=None, description="发布日期")
    report_type: Optional[str] = Field(default=None, description="报告类型")
    file_size: Optional[str] = Field(default=None, description="文件大小")


class SearchReportsResponse(BaseModel):
    """搜索结果响应"""

    reports: List[ReportInfo] = Field(default_factory=list, description="财报列表")
    count: int = Field(description="结果数量")
    stock_code: str = Field(description="股票代码")
    market: str = Field(description="市场")
    report_type: str = Field(description="报告类型")
    source: str = Field(description="数据源")
