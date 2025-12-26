"""
缓存管理API路由
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Body

from ..dependencies import get_pdf_handler
from ..schemas.common import APIResponse
from ..schemas.extract import WarmCacheRequest
from ...handlers.pdf_handler import PDFHandler

router = APIRouter()


@router.get("/cache/stats", response_model=APIResponse[Dict[str, Any]])
async def get_cache_stats(
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    获取缓存统计信息

    返回缓存条目数量、大小、版本等信息
    """
    result = await handler.get_cache_stats()

    return APIResponse(
        success=result.get("success", False),
        data=result.get("data") if result.get("success") else None,
        error=result.get("error"),
    )


@router.delete("/cache/cleanup", response_model=APIResponse[Dict[str, Any]])
async def cleanup_cache(
    days: int = Query(
        default=90, ge=1, le=365, description="清理多少天前的缓存"
    ),
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    清理过期缓存

    删除指定天数之前的提取结果缓存
    """
    result = await handler.cleanup_extraction_cache(days=days)

    return APIResponse(
        success=result.get("success", False),
        data=result.get("data") if result.get("success") else None,
        error=result.get("error"),
        message=result.get("message") if result.get("success") else None,
    )


@router.post("/cache/warm", response_model=APIResponse[Dict[str, Any]])
async def warm_cache(
    request: WarmCacheRequest,
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    预热缓存

    对未缓存的PDF提前进行内容提取并缓存结果

    - **stock_code**: 可选，限定股票代码
    - **market**: 可选，限定市场
    - **max_files**: 最大处理文件数
    """
    result = await handler.warm_cache(
        stock_code=request.stock_code,
        market=request.market,
        limit=request.max_files,
    )

    return APIResponse(
        success=result.get("success", False),
        data=result.get("data") if result.get("success") else None,
        error=result.get("error"),
        message=result.get("message") if result.get("success") else None,
    )
