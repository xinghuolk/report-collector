"""
内容提取API路由
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Body

from ..dependencies import get_pdf_handler
from ..schemas.common import APIResponse
from ...handlers.pdf_handler import PDFHandler

router = APIRouter()


@router.post("/extract/content", response_model=APIResponse[Dict[str, Any]])
async def extract_pdf_content(
    pdf_path: Optional[str] = Body(default=None, description="PDF文件路径"),
    pdf_id: Optional[int] = Body(default=None, description="PDF记录ID"),
    force_refresh: bool = Body(default=False, description="强制重新提取(忽略缓存)"),
    min_confidence: Optional[float] = Body(
        default=None, ge=0.0, le=1.0, description="仅返回置信度不低于该值的 facts（仅V2）"
    ),
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    提取PDF中的结构化财务数据

    提供 pdf_path 或 pdf_id 之一:
    - **pdf_path**: PDF文件绝对路径
    - **pdf_id**: 从列表API获取的PDF记录ID
    - **force_refresh**: 是否强制重新提取(忽略缓存)

    自动识别并提取:
    - 利润表 (营业收入、净利润等)
    - 资产负债表 (总资产、负债、权益等)
    - 现金流量表 (经营、投资、筹资现金流等)
    - 财务指标 (EPS、ROE、负债率等)

    支持缓存，重复提取将直接返回缓存结果
    """
    if not pdf_path and not pdf_id:
        return APIResponse(
            success=False,
            error="请提供 pdf_path 或 pdf_id 参数",
        )

    result = await handler.extract_pdf_content(
        pdf_path=pdf_path,
        pdf_id=pdf_id,
        force_refresh=force_refresh,
        min_confidence=min_confidence,
    )

    # extract_pdf_content 返回的是扁平结构，不需要取 data
    if result.get("success"):
        # 移除内部的 success 字段，避免重复
        data = {k: v for k, v in result.items() if k not in ("success", "error")}
        return APIResponse(success=True, data=data, error=None)
    else:
        return APIResponse(success=False, data=None, error=result.get("error"))


@router.post("/extract/tables", response_model=APIResponse[Dict[str, Any]])
async def extract_pdf_tables(
    pdf_path: Optional[str] = Body(default=None, description="PDF文件路径"),
    pdf_id: Optional[int] = Body(default=None, description="PDF记录ID"),
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    提取PDF中的表格数据

    提供 pdf_path 或 pdf_id 之一

    返回PDF中识别出的所有表格，以列表形式呈现
    """
    if not pdf_path and not pdf_id:
        return APIResponse(
            success=False,
            error="请提供 pdf_path 或 pdf_id 参数",
        )

    result = await handler.extract_tables(
        pdf_path=pdf_path,
        pdf_id=pdf_id,
    )

    return APIResponse(
        success=result.get("success", False),
        data=result.get("data") if result.get("success") else None,
        error=result.get("error"),
    )


@router.post("/extract/text", response_model=APIResponse[Dict[str, Any]])
async def extract_pdf_text(
    pdf_path: Optional[str] = Body(default=None, description="PDF文件路径"),
    pdf_id: Optional[int] = Body(default=None, description="PDF记录ID"),
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    提取PDF全部文本

    提供 pdf_path 或 pdf_id 之一

    返回PDF中的纯文本内容
    """
    if not pdf_path and not pdf_id:
        return APIResponse(
            success=False,
            error="请提供 pdf_path 或 pdf_id 参数",
        )

    result = await handler.extract_text(
        pdf_path=pdf_path,
        pdf_id=pdf_id,
    )

    return APIResponse(
        success=result.get("success", False),
        data=result.get("data") if result.get("success") else None,
        error=result.get("error"),
    )


@router.get("/cache/stats", response_model=APIResponse[Dict[str, Any]])
async def get_extraction_cache_stats(
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    """
    获取提取结果缓存统计

    返回缓存数量、大小、最近更新时间等
    """
    result = await handler.get_cache_stats()

    return APIResponse(
        success=result.get("success", False),
        data=result.get("data") if result.get("success") else None,
        error=result.get("error"),
    )
