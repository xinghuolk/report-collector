"""
财报PDF收集MCP服务器主入口
"""
import asyncio
import sys
from typing import Dict, List, Optional, Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from loguru import logger

from .handlers.pdf_handler import PDFHandler
from .utils.validators import DataValidator
from .config import Config


class FinancialReportsPDFServer:
    """财报PDF收集MCP服务器"""
    
    def __init__(self):
        self.server = Server(Config.MCP_SERVER_NAME)
        self.pdf_handler = PDFHandler()
        
        # 配置日志
        logger.add(Config.LOG_FILE, level=Config.LOG_LEVEL, rotation="10 MB")
        logger.info("财报PDF收集MCP服务器初始化开始")
        
        # 验证配置并创建目录
        Config.validate_config()
        
        # 注册工具
        self._register_tools()
        
    def _register_tools(self):
        """注册MCP工具"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """列出所有可用工具"""
            return [
                Tool(
                    name="search_cn_reports",
                    description="搜索中国A股上市公司可用的财报PDF。默认只返回完整报告，自动过滤摘要版、英文版等。数据来源：巨潮资讯网。",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "stock_code": {
                                "type": "string",
                                "description": "股票代码（6位数字）"
                            },
                            "report_type": {
                                "type": "string",
                                "enum": ["annual", "semi_annual", "quarterly", "all"],
                                "description": "报告类型",
                                "default": "annual"
                            },
                            "max_count": {
                                "type": "integer",
                                "description": "最大搜索数量",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 50
                            }
                        },
                        "required": ["stock_code"]
                    }
                ),
                Tool(
                    name="search_hk_reports",
                    description="搜索香港上市公司可用的财报PDF。返回繁体中文和英文两个版本。数据来源：港交所披露易。",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "stock_code": {
                                "type": "string",
                                "description": "股票代码（5位数字，如00700）"
                            },
                            "report_type": {
                                "type": "string",
                                "enum": ["annual", "semi_annual", "quarterly"],
                                "description": "报告类型（注意：港股季报非强制披露）",
                                "default": "annual"
                            },
                            "max_count": {
                                "type": "integer",
                                "description": "最大搜索数量",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 50
                            }
                        },
                        "required": ["stock_code"]
                    }
                ),
                Tool(
                    name="download_cn_report",
                    description="下载中国A股公司财报PDF。文件按股票代码和报告类型组织存储，自动创建股票名称标识文件。",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "stock_code": {
                                "type": "string",
                                "description": "股票代码（6位数字）"
                            },
                            "report_url": {
                                "type": "string",
                                "description": "报告PDF下载URL（可选，不提供则下载最新年报）"
                            },
                            "report_title": {
                                "type": "string",
                                "description": "报告标题（可选）",
                                "default": ""
                            },
                            "report_type": {
                                "type": "string",
                                "enum": ["annual", "semi_annual", "quarterly"],
                                "description": "报告类型",
                                "default": "annual"
                            }
                        },
                        "required": ["stock_code"]
                    }
                ),
                Tool(
                    name="download_stock_reports",
                    description="批量下载A股股票的多个财报PDF",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "stock_code": {
                                "type": "string",
                                "description": "股票代码（6位数字）"
                            },
                            "report_type": {
                                "type": "string",
                                "enum": ["annual", "semi_annual", "quarterly"],
                                "description": "报告类型",
                                "default": "annual"
                            },
                            "max_count": {
                                "type": "integer",
                                "description": "最大下载数量",
                                "default": 3,
                                "minimum": 1,
                                "maximum": 10
                            }
                        },
                        "required": ["stock_code"]
                    }
                ),
                Tool(
                    name="download_hk_reports",
                    description="批量下载港股的财报PDF。同时下载繁体中文和英文两个版本。",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "stock_code": {
                                "type": "string",
                                "description": "股票代码（5位数字，如00700）"
                            },
                            "report_type": {
                                "type": "string",
                                "enum": ["annual", "semi_annual", "quarterly"],
                                "description": "报告类型",
                                "default": "annual"
                            },
                            "max_count": {
                                "type": "integer",
                                "description": "最大下载数量",
                                "default": 3,
                                "minimum": 1,
                                "maximum": 10
                            }
                        },
                        "required": ["stock_code"]
                    }
                ),
                Tool(
                    name="list_downloaded_pdfs",
                    description="列出已下载的财报PDF文件",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "stock_code": {
                                "type": "string",
                                "description": "股票代码（可选，筛选指定股票）"
                            },
                            "market": {
                                "type": "string",
                                "enum": ["CN", "HK", "US"],
                                "description": "市场（可选）"
                            },
                            "report_type": {
                                "type": "string",
                                "enum": ["annual", "semi_annual", "quarterly"],
                                "description": "报告类型（可选）"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回数量限制",
                                "default": 20,
                                "minimum": 1,
                                "maximum": 100
                            }
                        }
                    }
                ),
                Tool(
                    name="get_pdf_info",
                    description="获取PDF文件详细信息",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pdf_id": {
                                "type": "integer",
                                "description": "PDF文件ID"
                            }
                        },
                        "required": ["pdf_id"]
                    }
                ),
                Tool(
                    name="get_collection_stats",
                    description="获取PDF收集统计信息",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="cleanup_old_pdfs",
                    description="清理旧的PDF文件",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "清理多少天前的文件",
                                "default": 90,
                                "minimum": 1,
                                "maximum": 365
                            }
                        }
                    }
                ),
                Tool(
                    name="extract_pdf_content",
                    description="提取财报PDF的结构化财务数据（支持缓存，首次提取约20秒，后续秒级返回）。包括：利润表(营业收入、净利润、扣非净利润、研发费用等)、资产负债表(总资产、应收账款、存货、商誉、无形资产等)、现金流量表、关联交易明细。返回结果包含_cache_info字段标识缓存状态。",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pdf_path": {
                                "type": "string",
                                "description": "PDF文件的完整路径"
                            },
                            "pdf_id": {
                                "type": "integer",
                                "description": "PDF记录ID（从list_downloaded_pdfs获取）"
                            },
                            "force_refresh": {
                                "type": "boolean",
                                "description": "强制重新提取（忽略缓存）",
                                "default": False
                            }
                        }
                    }
                ),
                Tool(
                    name="extract_pdf_tables",
                    description="提取PDF中的所有表格数据",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pdf_path": {
                                "type": "string",
                                "description": "PDF文件的完整路径"
                            },
                            "pdf_id": {
                                "type": "integer",
                                "description": "PDF记录ID"
                            }
                        }
                    }
                ),
                Tool(
                    name="extract_pdf_text",
                    description="提取PDF的全部文本内容",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pdf_path": {
                                "type": "string",
                                "description": "PDF文件的完整路径"
                            },
                            "pdf_id": {
                                "type": "integer",
                                "description": "PDF记录ID"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_cache_stats",
                    description="获取财务数据提取缓存的统计信息。包括缓存数量、大小、平均提取时间、版本分布等。",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="cleanup_cache",
                    description="清理旧的财务数据提取缓存。删除过期缓存和孤立缓存（对应PDF已删除）。",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "清理多少天前的缓存",
                                "default": 90,
                                "minimum": 1,
                                "maximum": 365
                            }
                        }
                    }
                ),
                Tool(
                    name="warm_cache",
                    description="预热财务数据提取缓存。对未缓存的PDF执行提取操作，适合在下载新财报后批量预热。",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "stock_code": {
                                "type": "string",
                                "description": "股票代码（可选，指定则只预热该股票）"
                            },
                            "market": {
                                "type": "string",
                                "enum": ["CN", "HK", "US"],
                                "description": "市场（可选）"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "最多处理多少个PDF",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 50
                            }
                        }
                    }
                )
            ]
            
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """调用工具"""
            try:
                logger.info(f"调用工具: {name}, 参数: {arguments}")
                
                # 路由到对应的处理器方法
                if name == "search_cn_reports":
                    result = await self.pdf_handler.search_available_reports(
                        stock_code=arguments["stock_code"],
                        market="CN",
                        report_type=arguments.get("report_type", "annual"),
                        max_count=arguments.get("max_count", 10)
                    )
                elif name == "search_hk_reports":
                    result = await self.pdf_handler.search_available_reports(
                        stock_code=arguments["stock_code"],
                        market="HK",
                        report_type=arguments.get("report_type", "annual"),
                        max_count=arguments.get("max_count", 10)
                    )
                elif name == "download_cn_report":
                    result = await self.pdf_handler.download_report(
                        stock_code=arguments["stock_code"],
                        market="CN",
                        report_type=arguments.get("report_type", "annual"),
                        report_url=arguments.get("report_url"),
                        report_title=arguments.get("report_title", "")
                    )
                elif name == "download_stock_reports":
                    result = await self.pdf_handler.download_stock_reports(
                        stock_code=arguments["stock_code"],
                        market="CN",
                        report_type=arguments.get("report_type", "annual"),
                        max_count=arguments.get("max_count", 3)
                    )
                elif name == "download_hk_reports":
                    result = await self.pdf_handler.download_stock_reports(
                        stock_code=arguments["stock_code"],
                        market="HK",
                        report_type=arguments.get("report_type", "annual"),
                        max_count=arguments.get("max_count", 3)
                    )
                elif name == "list_downloaded_pdfs":
                    result = await self.pdf_handler.list_downloaded_pdfs(
                        stock_code=arguments.get("stock_code"),
                        market=arguments.get("market"),
                        report_type=arguments.get("report_type"),
                        limit=arguments.get("limit", 20)
                    )
                elif name == "get_pdf_info":
                    result = await self.pdf_handler.get_pdf_info(
                        pdf_id=arguments["pdf_id"]
                    )
                elif name == "get_collection_stats":
                    result = await self.pdf_handler.get_stats()
                elif name == "cleanup_old_pdfs":
                    result = await self.pdf_handler.cleanup_old_files(
                        days=arguments.get("days", 90)
                    )
                elif name == "extract_pdf_content":
                    result = await self.pdf_handler.extract_pdf_content(
                        pdf_path=arguments.get("pdf_path"),
                        pdf_id=arguments.get("pdf_id"),
                        force_refresh=arguments.get("force_refresh", False)
                    )
                elif name == "extract_pdf_tables":
                    result = await self.pdf_handler.extract_tables(
                        pdf_path=arguments.get("pdf_path"),
                        pdf_id=arguments.get("pdf_id")
                    )
                elif name == "extract_pdf_text":
                    result = await self.pdf_handler.extract_text(
                        pdf_path=arguments.get("pdf_path"),
                        pdf_id=arguments.get("pdf_id")
                    )
                elif name == "get_cache_stats":
                    result = await self.pdf_handler.get_cache_stats()
                elif name == "cleanup_cache":
                    result = await self.pdf_handler.cleanup_extraction_cache(
                        days=arguments.get("days", 90)
                    )
                elif name == "warm_cache":
                    result = await self.pdf_handler.warm_cache(
                        stock_code=arguments.get("stock_code"),
                        market=arguments.get("market"),
                        limit=arguments.get("limit", 10)
                    )
                else:
                    result = {"success": False, "error": f"未知工具: {name}"}
                    
                # 格式化返回结果
                if result.get("success"):
                    import json
                    return [TextContent(
                        type="text", 
                        text=json.dumps(result, ensure_ascii=False, indent=2)
                    )]
                else:
                    return [TextContent(
                        type="text",
                        text=f"错误: {result.get('error', '未知错误')}"
                    )]
                    
            except Exception as e:
                logger.error(f"工具调用失败 {name}: {e}")
                return [TextContent(
                    type="text",
                    text=f"服务器错误: {str(e)}"
                )]
                
    async def initialize(self):
        """初始化服务器"""
        await self.pdf_handler.initialize()
        logger.info("财报PDF收集MCP服务器初始化完成")
                
    async def run(self):
        """运行MCP服务器"""
        logger.info("启动财报PDF收集MCP服务器...")
        await self.initialize()
        # 使用stdio_server装饰器来正确运行MCP服务器
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, 
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """主函数"""
    # 创建并运行服务器
    server = FinancialReportsPDFServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())