"""
通用响应模型
"""
from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一API响应格式"""

    success: bool = Field(description="操作是否成功")
    data: Optional[T] = Field(default=None, description="返回数据")
    error: Optional[str] = Field(default=None, description="错误信息")
    message: Optional[str] = Field(default=None, description="提示信息")


class PaginationParams(BaseModel):
    """分页参数"""

    limit: int = Field(default=20, ge=1, le=100, description="每页数量")
    offset: int = Field(default=0, ge=0, description="偏移量")


class StockCodeParam(BaseModel):
    """股票代码参数"""

    stock_code: str = Field(..., description="股票代码")
    market: str = Field(default="CN", pattern=r"^(CN|HK|US)$", description="市场")


class ReportTypeParam(BaseModel):
    """报告类型参数"""

    report_type: str = Field(
        default="annual",
        pattern=r"^(annual|semi_annual|quarterly|all)$",
        description="报告类型",
    )


class YearParam(BaseModel):
    """年份参数"""

    year: Optional[int] = Field(default=None, ge=1990, le=2030, description="年份")
