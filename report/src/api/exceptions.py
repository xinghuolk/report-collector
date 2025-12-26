"""
异常处理器
"""
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from loguru import logger


class APIException(Exception):
    """API异常基类"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundError(APIException):
    """资源未找到"""

    def __init__(self, message: str = "资源未找到", details: Optional[Dict] = None):
        super().__init__(
            message=message, error_code="NOT_FOUND", status_code=404, details=details
        )


class ValidationException(APIException):
    """验证错误"""

    def __init__(self, message: str = "参数验证失败", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class DownloadError(APIException):
    """下载错误"""

    def __init__(self, message: str = "下载失败", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="DOWNLOAD_ERROR",
            status_code=500,
            details=details,
        )


class ExtractionError(APIException):
    """内容提取错误"""

    def __init__(self, message: str = "内容提取失败", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="EXTRACTION_ERROR",
            status_code=500,
            details=details,
        )


def setup_exception_handlers(app: FastAPI) -> None:
    """注册异常处理器"""

    @app.exception_handler(APIException)
    async def api_exception_handler(
        request: Request, exc: APIException
    ) -> JSONResponse:
        logger.warning(f"API异常: {exc.message} | code={exc.error_code}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.message,
                "error_code": exc.error_code,
                "details": exc.details,
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        logger.warning(f"Pydantic验证错误: {exc.error_count()}个错误")
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": "请求参数验证失败",
                "error_code": "VALIDATION_ERROR",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(f"未处理的异常: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "服务器内部错误",
                "error_code": "INTERNAL_ERROR",
            },
        )
