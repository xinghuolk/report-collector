"""
下载相关Schema
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class DownloadRequest(BaseModel):
    """下载请求"""

    stock_code: str = Field(..., description="股票代码")
    url: str = Field(..., description="下载URL")
    title: Optional[str] = Field(default=None, description="文件标题")


class BatchDownloadRequest(BaseModel):
    """批量下载请求"""

    stock_code: str = Field(..., description="股票代码")
    report_type: str = Field(
        default="annual",
        pattern=r"^(annual|semi_annual|quarterly|all)$",
        description="报告类型",
    )
    years: Optional[List[int]] = Field(default=None, description="年份列表")
    max_count: int = Field(default=5, ge=1, le=20, description="最大下载数量")


class DownloadResult(BaseModel):
    """下载结果"""

    success: bool = Field(description="是否成功")
    file_path: Optional[str] = Field(default=None, description="文件路径")
    file_name: Optional[str] = Field(default=None, description="文件名")
    file_size: Optional[int] = Field(default=None, description="文件大小(字节)")
    error: Optional[str] = Field(default=None, description="错误信息")


class PDFInfo(BaseModel):
    """PDF信息"""

    id: int = Field(description="ID")
    stock_code: str = Field(description="股票代码")
    stock_name: Optional[str] = Field(default=None, description="股票名称")
    market: str = Field(description="市场")
    report_type: Optional[str] = Field(default=None, description="报告类型")
    report_year: Optional[int] = Field(default=None, description="报告年份")
    file_path: str = Field(description="文件路径")
    file_name: str = Field(description="文件名")
    file_size: Optional[int] = Field(default=None, description="文件大小")
    download_time: Optional[str] = Field(default=None, description="下载时间")


class ListPDFsResponse(BaseModel):
    """PDF列表响应"""

    pdfs: List[PDFInfo] = Field(default_factory=list, description="PDF列表")
    count: int = Field(description="总数")
