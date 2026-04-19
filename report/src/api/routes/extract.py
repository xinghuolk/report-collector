"""
内容提取 API 路由。
"""
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, status

from ...handlers.pdf_handler import PDFHandler
from ..dependencies import get_pdf_handler
from ..schemas.common import APIResponse
from ..schemas.extract import AnalysisProxyRequest

router = APIRouter()


def _resolve_schema_version(
    schema: str | None,
    header_schema: str | None,
    accept_header: str | None,
) -> str:
    """解析 schema 版本，优先级为 query > header > accept。"""
    if schema in {"v1", "v2"}:
        return schema

    if header_schema in {"v1", "v2"}:
        return header_schema

    accept = (accept_header or "").lower()
    if "application/vnd.financial-reports.v1+json" in accept:
        return "v1"
    if "application/vnd.financial-reports.v2+json" in accept:
        return "v2"

    return "v2"


@router.post("/extract/content", response_model=APIResponse[dict[str, Any]])
async def extract_pdf_content(
    pdf_path: str | None = Body(default=None, description="PDF 文件路径"),
    pdf_id: int | None = Body(default=None, description="PDF 记录 ID"),
    force_refresh: bool = Body(default=False, description="强制重新提取，忽略缓存"),
    min_confidence: float | None = Body(
        default=None,
        ge=0.0,
        le=1.0,
        description="仅返回置信度不低于该值的 facts，仅 v2 生效",
    ),
    schema: str | None = Query(
        default=None,
        pattern=r"^(v1|v2)$",
        description="响应结构版本，query 兼容入口",
    ),
    x_schema_version: str | None = Header(
        default=None,
        alias="X-Schema-Version",
        description="响应结构版本，header 优先级低于 query",
    ),
    accept_header: str | None = Header(
        default=None,
        alias="Accept",
        description="支持 vendor MIME 版本协商",
    ),
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[dict[str, Any]]:
    """提取 PDF 中的结构化财务数据。"""
    if not pdf_path and not pdf_id:
        return APIResponse(success=False, error="请提供 pdf_path 或 pdf_id 参数")

    schema_version = _resolve_schema_version(schema, x_schema_version, accept_header)
    result = await handler.extract_pdf_content(
        pdf_path=pdf_path,
        pdf_id=pdf_id,
        force_refresh=force_refresh,
        schema_version=schema_version,
        min_confidence=min_confidence,
    )

    if result.get("success"):
        data = {k: v for k, v in result.items() if k not in ("success", "error")}
        return APIResponse(success=True, data=data, error=None)
    return APIResponse(success=False, data=None, error=result.get("error"))


@router.post("/extract/tables", response_model=APIResponse[dict[str, Any]])
async def extract_pdf_tables(
    pdf_path: str | None = Body(default=None, description="PDF 文件路径"),
    pdf_id: int | None = Body(default=None, description="PDF 记录 ID"),
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[dict[str, Any]]:
    """提取 PDF 中的表格数据。"""
    if not pdf_path and not pdf_id:
        return APIResponse(success=False, error="请提供 pdf_path 或 pdf_id 参数")

    result = await handler.extract_tables(pdf_path=pdf_path, pdf_id=pdf_id)
    return APIResponse(
        success=result.get("success", False),
        data=result.get("data") if result.get("success") else None,
        error=result.get("error"),
    )


@router.post("/extract/text", response_model=APIResponse[dict[str, Any]])
async def extract_pdf_text(
    pdf_path: str | None = Body(default=None, description="PDF 文件路径"),
    pdf_id: int | None = Body(default=None, description="PDF 记录 ID"),
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[dict[str, Any]]:
    """提取 PDF 全部文本。"""
    if not pdf_path and not pdf_id:
        return APIResponse(success=False, error="请提供 pdf_path 或 pdf_id 参数")

    result = await handler.extract_text(pdf_path=pdf_path, pdf_id=pdf_id)
    return APIResponse(
        success=result.get("success", False),
        data=result.get("data") if result.get("success") else None,
        error=result.get("error"),
    )


@router.post("/extract/analysis", response_model=APIResponse[dict[str, Any]])
async def extract_financial_report_analysis(
    request: AnalysisProxyRequest,
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[dict[str, Any]]:
    """转发 financial-report-analysis 独立 analysis service。"""
    try:
        result = await handler.extract_financial_report_analysis(request.model_dump())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return APIResponse(success=True, data=result, error=None)


@router.get("/cache/stats", response_model=APIResponse[dict[str, Any]])
async def get_extraction_cache_stats(
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[dict[str, Any]]:
    """获取提取结果缓存统计。"""
    result = await handler.get_cache_stats()
    return APIResponse(
        success=result.get("success", False),
        data=result.get("data") if result.get("success") else None,
        error=result.get("error"),
    )
