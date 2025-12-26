"""
搜索API路由
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_pdf_handler
from ..schemas.common import APIResponse
from ...handlers.pdf_handler import PDFHandler

router = APIRouter()


@router.get("/reports/cn/search", response_model=APIResponse[Dict[str, Any]])
async def search_cn_reports(
    stock_code: str = Query(..., description="6位股票代码", pattern=r"^[0-9]{6}$"),
    report_type: str = Query(
        default="annual",
        description="报告类型: annual(年报), semi_annual(半年报), quarterly(季报), all(全部)",
    ),
    max_count: int = Query(default=10, ge=1, le=50, description="最大返回数量"),
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    搜索中国A股上市公司财报

    - **stock_code**: 6位数字股票代码 (如: 000001, 600519)
    - **report_type**: 报告类型
    - **max_count**: 最大返回数量 (1-50)

    数据源: 巨潮资讯网
    """
    result = await handler.search_available_reports(
        stock_code=stock_code,
        market="CN",
        report_type=report_type,
        max_count=max_count,
    )

    if result.get("success"):
        data = {
            "reports": result.get("data", []),
            "count": result.get("count", 0),
        }
        return APIResponse(success=True, data=data, message=f"找到 {result.get('count', 0)} 条记录")
    else:
        return APIResponse(success=False, error=result.get("error"))


@router.get("/reports/hk/search", response_model=APIResponse[Dict[str, Any]])
async def search_hk_reports(
    stock_code: str = Query(..., description="5位股票代码", pattern=r"^[0-9]{5}$"),
    report_type: str = Query(
        default="annual",
        description="报告类型: annual(年报), semi_annual(中期报告), quarterly(季报)",
    ),
    max_count: int = Query(default=10, ge=1, le=50, description="最大返回数量"),
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    搜索港股上市公司财报

    - **stock_code**: 5位数字股票代码 (如: 00700, 01810)
    - **report_type**: 报告类型
    - **max_count**: 最大返回数量 (1-50)

    数据源: 港交所披露易
    """
    result = await handler.search_available_reports(
        stock_code=stock_code,
        market="HK",
        report_type=report_type,
        max_count=max_count,
    )

    if result.get("success"):
        data = {
            "reports": result.get("data", []),
            "count": result.get("count", 0),
        }
        return APIResponse(success=True, data=data, message=f"找到 {result.get('count', 0)} 条记录")
    else:
        return APIResponse(success=False, error=result.get("error"))
