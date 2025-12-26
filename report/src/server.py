"""
统一服务入口
支持MCP和HTTP两种运行模式
"""
import argparse
import asyncio
import sys

from loguru import logger


def run_mcp_server() -> None:
    """运行MCP服务器"""
    from .main import main as mcp_main

    asyncio.run(mcp_main())


def run_http_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """运行HTTP服务器"""
    import uvicorn

    from .api.app import app

    logger.info(f"启动HTTP服务器: http://{host}:{port}")
    logger.info(f"API文档: http://{host}:{port}/docs")
    logger.info(f"ReDoc: http://{host}:{port}/redoc")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


def main() -> None:
    """主入口"""
    parser = argparse.ArgumentParser(
        description="财报收集服务器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # MCP模式 (默认)
  python -m src.server --mode mcp

  # HTTP模式
  python -m src.server --mode http --host 0.0.0.0 --port 8000

  # 仅指定端口
  python -m src.server --mode http --port 9000
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["mcp", "http"],
        default="mcp",
        help="运行模式: mcp (MCP服务器) 或 http (HTTP API服务器)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="HTTP服务器主机地址 (默认: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="HTTP服务器端口 (默认: 8000)",
    )

    args = parser.parse_args()

    if args.mode == "mcp":
        logger.info("启动MCP服务器模式...")
        run_mcp_server()
    else:
        logger.info("启动HTTP API服务器模式...")
        run_http_server(args.host, args.port)


if __name__ == "__main__":
    main()
