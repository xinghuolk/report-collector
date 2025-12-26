"""
查询API路由
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Path, Query

from ..dependencies import get_pdf_handler
from ..schemas.common import APIResponse
from ...handlers.pdf_handler import PDFHandler

router = APIRouter()


@router.get("/pdfs/{pdf_id}", response_model=APIResponse[Dict[str, Any]])
async def get_pdf_info(
    pdf_id: int = Path(..., description="PDF记录ID"),
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    获取单个PDF详细信息

    - **pdf_id**: PDF记录ID (从列表API获取)
    """
    result = await handler.get_pdf_info(pdf_id=pdf_id)

    return APIResponse(
        success=result.get("success", False),
        data=result.get("data") if result.get("success") else None,
        error=result.get("error"),
    )


@router.get("/stats", response_model=APIResponse[Dict[str, Any]])
async def get_collection_stats(
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    获取收集统计信息

    返回各市场PDF数量、总文件大小等统计
    """
    result = await handler.get_stats()

    return APIResponse(
        success=result.get("success", False),
        data=result.get("data") if result.get("success") else None,
        error=result.get("error"),
    )


@router.delete("/pdfs/cleanup", response_model=APIResponse[Dict[str, Any]])
async def cleanup_old_pdfs(
    days: int = Query(default=90, ge=1, le=365, description="清理多少天前的文件"),
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    清理旧PDF文件

    - **days**: 清理多少天前下载的文件
    """
    result = await handler.cleanup_old_files(days=days)

    return APIResponse(
        success=result.get("success", False),
        data=None,
        error=result.get("error"),
        message=result.get("message") if result.get("success") else None,
    )
