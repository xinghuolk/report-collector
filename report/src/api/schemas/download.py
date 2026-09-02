"""
下载相关Schema
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class DownloadRequest(BaseModel):
    """下载请求"""

    stock_code: str = Field(..., description="股票代码")
    url: str = Field(..., description="下载URL")
    title: str | None = Field(default=None, description="文件标题")


class HKSingleDownloadRequest(DownloadRequest):
    """港股单份报告下载请求"""

    stock_code: str = Field(pattern=r"^[0-9]{5}$", description="5位股票代码")
    report_type: str = Field(pattern=r"^(annual|semi_annual|quarterly)$")
    report_year: int = Field(ge=1990, le=2100)
    language: str = Field(pattern=r"^(en|zh)$")
    announcement_at: datetime | None = None
    announcement_date: str | None = None

    @field_validator("announcement_at")
    @classmethod
    def validate_announcement_at_timezone(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("announcement_at must include a timezone")
        return value


class BatchDownloadRequest(BaseModel):
    """批量下载请求"""

    stock_code: str = Field(..., description="股票代码")
    report_type: str = Field(
        default="annual",
        pattern=r"^(annual|semi_annual|quarterly|all)$",
        description="报告类型",
    )
    years: list[int] | None = Field(default=None, description="年份列表")
    max_count: int = Field(default=5, ge=1, le=20, description="最大下载数量")


class DownloadResult(BaseModel):
    """下载结果"""

    success: bool = Field(description="是否成功")
    file_path: str | None = Field(default=None, description="文件路径")
    file_name: str | None = Field(default=None, description="文件名")
    file_size: int | None = Field(default=None, description="文件大小(字节)")
    error: str | None = Field(default=None, description="错误信息")


class PDFInfo(BaseModel):
    """PDF信息"""

    id: int = Field(description="ID")
    stock_code: str = Field(description="股票代码")
    stock_name: str | None = Field(default=None, description="股票名称")
    market: str = Field(description="市场")
    report_type: str | None = Field(default=None, description="报告类型")
    report_year: int | None = Field(default=None, description="报告年份")
    file_path: str = Field(description="文件路径")
    file_name: str = Field(description="文件名")
    file_size: int | None = Field(default=None, description="文件大小")
    download_time: str | None = Field(default=None, description="下载时间")


class ListPDFsResponse(BaseModel):
    """PDF列表响应"""

    pdfs: list[PDFInfo] = Field(default_factory=list, description="PDF列表")
    count: int = Field(description="总数")
