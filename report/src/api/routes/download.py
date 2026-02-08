"""
下载API路由
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Body

from ..dependencies import get_pdf_handler
from ..schemas.common import APIResponse
from ..schemas.download import BatchDownloadRequest
from ...handlers.pdf_handler import PDFHandler

router = APIRouter()


@router.post("/reports/cn/download", response_model=APIResponse[Dict[str, Any]])
async def download_cn_report(
    stock_code: str = Body(..., description="股票代码"),
    url: str = Body(..., description="下载URL"),
    title: Optional[str] = Body(default=None, description="文件标题"),
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    下载单个A股财报PDF

    - **stock_code**: 6位股票代码
    - **url**: 从搜索API获取的下载URL
    - **title**: 可选的文件标题
    """
    result = await handler.download_report(
        stock_code=stock_code,
        market="CN",
        report_url=url,
        report_title=title or "",
    )

    return APIResponse(
        success=result.get("success", False),
        data=result.get("data") if result.get("success") else None,
        error=result.get("error"),
        message="下载成功" if result.get("success") else None,
    )


@router.post("/reports/cn/batch-download", response_model=APIResponse[Dict[str, Any]])
async def batch_download_cn_reports(
    request: BatchDownloadRequest,
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    批量下载A股财报PDF

    自动搜索并下载指定股票的财报
    """
    result = await handler.download_stock_reports(
        stock_code=request.stock_code,
        market="CN",
        report_type=request.report_type,
        max_count=request.max_count,
    )

    return APIResponse(
        success=result.get("success", False),
        data=result.get("data") if result.get("success") else None,
        error=result.get("error"),
        message=f"下载了 {result.get('data', {}).get('downloaded_count', 0)} 个文件" if result.get("success") else None,
    )


@router.post("/reports/hk/batch-download", response_model=APIResponse[Dict[str, Any]])
async def batch_download_hk_reports(
    request: BatchDownloadRequest,
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    批量下载港股财报PDF

    自动搜索并下载指定股票的财报
    """
    result = await handler.download_stock_reports(
        stock_code=request.stock_code,
        market="HK",
        report_type=request.report_type,
        max_count=request.max_count,
    )

    return APIResponse(
        success=result.get("success", False),
        data=result.get("data") if result.get("success") else None,
        error=result.get("error"),
        message=f"下载了 {result.get('data', {}).get('downloaded_count', 0)} 个文件" if result.get("success") else None,
    )


@router.get("/pdfs", response_model=APIResponse[Dict[str, Any]])
async def list_downloaded_pdfs(
    stock_code: Optional[str] = Query(default=None, description="股票代码筛选"),
    market: Optional[str] = Query(default=None, description="市场筛选 (CN/HK/US)"),
    report_type: Optional[str] = Query(default=None, description="报告类型筛选"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
    sort_by: str = Query(
        default="download_time",
        description="排序字段: download_time/announcement_date/report_year",
    ),
    sort_order: str = Query(
        default="desc",
        description="排序方向: desc/asc",
    ),
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    列出已下载的PDF文件

    支持按股票代码、市场、报告类型筛选
    """
    result = await handler.list_downloaded_pdfs(
        stock_code=stock_code,
        market=market,
        report_type=report_type,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    if result.get("success"):
        data = {
            "pdfs": result.get("data", []),
            "count": result.get("count", 0),
        }
        return APIResponse(success=True, data=data, message=f"共 {result.get('count', 0)} 条记录")
    else:
        return APIResponse(success=False, error=result.get("error"))
