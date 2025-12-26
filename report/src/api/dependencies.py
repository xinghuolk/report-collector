"""
FastAPI 依赖注入
"""
from typing import Optional
from loguru import logger

from ..handlers.pdf_handler import PDFHandler


class PDFHandlerSingleton:
    """PDFHandler 单例管理"""

    _instance: Optional[PDFHandler] = None
    _initialized: bool = False

    @classmethod
    async def get_instance(cls) -> PDFHandler:
        """获取 PDFHandler 单例实例"""
        if cls._instance is None:
            cls._instance = PDFHandler()
        if not cls._initialized:
            await cls._instance.initialize()
            cls._initialized = True
            logger.info("PDFHandler 单例初始化完成")
        return cls._instance

    @classmethod
    async def shutdown(cls) -> None:
        """关闭并清理资源"""
        if cls._instance is not None:
            cls._initialized = False
            cls._instance = None
            logger.info("PDFHandler 单例已清理")


async def get_pdf_handler() -> PDFHandler:
    """FastAPI 依赖注入函数"""
    return await PDFHandlerSingleton.get_instance()
