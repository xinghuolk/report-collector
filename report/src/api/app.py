"""
FastAPI 应用实例
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .dependencies import PDFHandlerSingleton
from .exceptions import setup_exception_handlers
from .routes import search, download, query, extract, cache
from ..config import Config


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("HTTP API服务器启动中...")
    Config.validate_config()
    await PDFHandlerSingleton.get_instance()
    logger.info("HTTP API服务器启动完成")

    yield

    # 关闭时清理
    logger.info("HTTP API服务器关闭中...")
    await PDFHandlerSingleton.shutdown()
    logger.info("HTTP API服务器已关闭")


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(
        title="财报收集API服务",
        description="""
中国A股、港股财报PDF收集与提取API

## 功能

* **搜索**: 搜索A股和港股上市公司财报
* **下载**: 下载单个或批量财报PDF
* **查询**: 查询已下载PDF信息和统计
* **提取**: 提取PDF中的财务数据、表格和文本
* **缓存**: 管理提取结果缓存

## 数据源

* A股: 巨潮资讯网 (cninfo.com.cn)
* 港股: 港交所披露易 (hkexnews.hk)
        """,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(search.router, prefix="/api/v1", tags=["搜索"])
    app.include_router(download.router, prefix="/api/v1", tags=["下载"])
    app.include_router(query.router, prefix="/api/v1", tags=["查询"])
    app.include_router(extract.router, prefix="/api/v1", tags=["提取"])
    app.include_router(cache.router, prefix="/api/v1", tags=["缓存"])

    # 异常处理
    setup_exception_handlers(app)

    # 健康检查
    @app.get("/health", tags=["系统"])
    async def health_check():
        """健康检查"""
        return {"status": "healthy", "service": "financial-reports-api"}

    @app.get("/", tags=["系统"])
    async def root():
        """根路径"""
        return {
            "service": "财报收集API服务",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
        }

    return app


# 应用实例
app = create_app()
