"""
搜索API路由
"""
from typing import Any, Dict, List, Optional

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


@router.get("/reports/search-latest", response_model=APIResponse[Dict[str, Any]])
async def search_latest_reports(
    market: str = Query(..., description="市场: CN/HK", pattern=r"^(CN|HK)$"),
    stock_code: str = Query(..., description="股票代码"),
    report_types: Optional[List[str]] = Query(
        default=None,
        description="报告类型列表，支持 annual/semi_annual/quarterly/all",
    ),
    max_count: int = Query(default=10, ge=1, le=50, description="最大返回数量"),
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    跨类型检索并按发布时间排序的最新报告列表

    - **market**: CN/HK
    - **stock_code**: 股票代码（CN 6位 / HK 5位）
    - **report_types**: 可重复参数或逗号分隔字符串
    - **max_count**: 最大返回数量 (1-50)
    """
    normalized_types: Optional[List[str]] = None
    if report_types:
        if len(report_types) == 1 and "," in report_types[0]:
            normalized_types = [t.strip() for t in report_types[0].split(",") if t.strip()]
        else:
            normalized_types = report_types

    result = await handler.search_latest_reports(
        stock_code=stock_code,
        market=market,
        report_types=normalized_types,
        max_count=max_count,
    )

    if result.get("success"):
        data = {
            "reports": result.get("data", []),
            "count": result.get("count", 0),
            "stock_code": result.get("stock_code"),
            "market": result.get("market"),
            "report_types": result.get("report_types", []),
            "sorted_by": result.get("sorted_by"),
        }
        return APIResponse(success=True, data=data, message=f"找到 {result.get('count', 0)} 条记录")
    else:
        return APIResponse(success=False, error=result.get("error"))
