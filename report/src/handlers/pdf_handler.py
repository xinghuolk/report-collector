"""
PDF财报处理器
整合所有PDF下载、管理和内容提取功能
"""
import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger
from cachetools import TTLCache

from ..pdf_sources.cninfo_downloader import CninfoDownloader
from ..pdf_sources.hkex_downloader import HKEXDownloader
from ..pdf_manager import PDFManager
from ..pdf_parser import PDFContentExtractor
from ..utils.validators import DataValidator
from ..config import Config


class PDFHandler:
    """PDF财报处理器"""

    def __init__(self):
        self.pdf_manager = PDFManager()
        self.cn_downloader = CninfoDownloader(str(Config.CN_DOWNLOADS_DIR))
        self.hk_downloader = HKEXDownloader(str(Config.HK_DOWNLOADS_DIR))
        self.content_extractor = PDFContentExtractor()
        self.cache = TTLCache(maxsize=Config.MAX_CACHE_SIZE, ttl=Config.CACHE_TTL)
        
    async def initialize(self):
        """初始化处理器"""
        await self.pdf_manager.initialize()
        logger.info("PDF处理器初始化完成")
        
    async def search_available_reports(self, stock_code: str, market: str = "CN", 
                                     report_type: str = "annual", 
                                     max_count: int = 10) -> Dict[str, Any]:
        """搜索可用的财报"""
        # 验证输入
        is_valid, error = DataValidator.validate_stock_symbol(stock_code, market)
        if not is_valid:
            return {"success": False, "error": error}
            
        is_valid, error = DataValidator.validate_market(market)
        if not is_valid:
            return {"success": False, "error": error}
            
        is_valid, error = DataValidator.validate_report_type(report_type)
        if not is_valid:
            return {"success": False, "error": error}
            
        cache_key = f"search_{market}_{stock_code}_{report_type}_{max_count}"
        
        # 检查缓存
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        try:
            if market == "CN":
                # 使用巨潮资讯网（统一数据源，覆盖所有中国股票）
                reports = await self.cn_downloader.search_reports(
                    stock_code=stock_code, 
                    report_type=report_type, 
                    limit=max_count
                )
                
                result = {
                    "success": True,
                    "data": reports,
                    "count": len(reports),
                    "stock_code": stock_code,
                    "market": market,
                    "report_type": report_type,
                    "source": "巨潮资讯网"
                }
                
                # 缓存结果
                self.cache[cache_key] = result
                return result
                
            elif market == "HK":
                # 使用港交所披露易
                reports = await self.hk_downloader.search_reports(
                    stock_code=stock_code,
                    report_type=report_type,
                    limit=max_count
                )

                result = {
                    "success": True,
                    "data": reports,
                    "count": len(reports),
                    "stock_code": stock_code,
                    "market": market,
                    "report_type": report_type,
                    "source": "港交所披露易"
                }

                self.cache[cache_key] = result
                return result
                
            elif market == "US":
                # TODO: 实现美股搜索
                return {"success": False, "error": "美股搜索功能尚未实现"}
                
            else:
                return {"success": False, "error": f"不支持的市场: {market}"}
                
        except Exception as e:
            logger.error(f"搜索财报失败: {e}")
            return {"success": False, "error": str(e)}
            
    async def download_report(self, stock_code: str, market: str = "CN",
                            report_type: str = "annual", report_url: str = None,
                            report_title: str = "",
                            auto_extract: bool = False) -> Dict[str, Any]:
        """
        下载财报PDF

        Args:
            stock_code: 股票代码
            market: 市场（CN/HK/US）
            report_type: 报告类型
            report_url: 报告URL
            report_title: 报告标题
            auto_extract: 下载后是否自动提取并缓存财务数据

        Returns:
            下载结果字典
        """
        # 验证输入
        is_valid, error = DataValidator.validate_stock_symbol(stock_code, market)
        if not is_valid:
            return {"success": False, "error": error}

        try:
            if market == "CN":
                if report_url:
                    # 下载指定URL的报告
                    file_path = await self.cn_downloader.download_pdf(
                        report_url, stock_code, report_title
                    )
                else:
                    # 下载最新报告
                    file_path = await self.cn_downloader.get_latest_annual_report(stock_code)

                if file_path:
                    # 添加到数据库
                    pdf_info = {
                        'stock_code': stock_code,
                        'market': market,
                        'report_type': report_type,
                        'original_title': report_title,
                        'file_path': file_path,
                        'file_name': Path(file_path).name,
                        'source_url': report_url,
                        'source_name': '巨潮资讯网'
                    }

                    pdf_id = await self.pdf_manager.add_pdf(pdf_info)

                    result = {
                        "success": True,
                        "data": {
                            "pdf_id": pdf_id,
                            "file_path": file_path,
                            "file_name": Path(file_path).name,
                            "stock_code": stock_code,
                            "market": market
                        }
                    }

                    # 自动提取并缓存
                    if auto_extract:
                        logger.info(f"自动提取财务数据: {file_path}")
                        extract_result = await self.extract_pdf_content(pdf_path=file_path)
                        result["data"]["auto_extracted"] = extract_result.get("success", False)
                        if extract_result.get("_cache_info"):
                            result["data"]["extraction_duration_ms"] = extract_result["_cache_info"].get("extraction_duration_ms")

                    return result
                else:
                    return {"success": False, "error": "PDF下载失败"}

            else:
                return {"success": False, "error": f"暂不支持{market}市场的下载"}

        except Exception as e:
            logger.error(f"下载财报失败: {e}")
            return {"success": False, "error": str(e)}
            
    async def download_stock_reports(self, stock_code: str, market: str = "CN",
                                   report_type: str = "annual", 
                                   max_count: int = 3) -> Dict[str, Any]:
        """批量下载股票财报"""
        try:
            if market == "CN":
                # 下载中国A股财报
                downloaded_files = await self.cn_downloader.download_stock_reports(
                    stock_code, report_type, max_count
                )
                
                # 批量添加到数据库
                pdf_ids = []
                for file_path in downloaded_files:
                    pdf_info = {
                        'stock_code': stock_code,
                        'market': market,
                        'report_type': report_type,
                        'original_title': Path(file_path).stem,
                        'file_path': file_path,
                        'file_name': Path(file_path).name,
                        'source_name': '巨潮资讯网'
                    }
                    
                    pdf_id = await self.pdf_manager.add_pdf(pdf_info)
                    if pdf_id:
                        pdf_ids.append(pdf_id)
                        
                return {
                    "success": True,
                    "data": {
                        "downloaded_count": len(downloaded_files),
                        "pdf_ids": pdf_ids,
                        "files": downloaded_files,
                        "stock_code": stock_code,
                        "market": market
                    }
                }

            elif market == "HK":
                # 下载港股财报
                downloaded_files = await self.hk_downloader.download_stock_reports(
                    stock_code, report_type, max_count
                )

                # 批量添加到数据库
                pdf_ids = []
                for file_path in downloaded_files:
                    pdf_info = {
                        'stock_code': stock_code,
                        'market': market,
                        'report_type': report_type,
                        'original_title': Path(file_path).stem,
                        'file_path': file_path,
                        'file_name': Path(file_path).name,
                        'source_name': '港交所披露易'
                    }

                    pdf_id = await self.pdf_manager.add_pdf(pdf_info)
                    if pdf_id:
                        pdf_ids.append(pdf_id)

                return {
                    "success": True,
                    "data": {
                        "downloaded_count": len(downloaded_files),
                        "pdf_ids": pdf_ids,
                        "files": downloaded_files,
                        "stock_code": stock_code,
                        "market": market
                    }
                }

            else:
                return {"success": False, "error": f"暂不支持{market}市场的批量下载"}
                
        except Exception as e:
            logger.error(f"批量下载财报失败: {e}")
            return {"success": False, "error": str(e)}
            
    async def list_downloaded_pdfs(self, stock_code: str = None, market: str = None,
                                 report_type: str = None, limit: int = 20) -> Dict[str, Any]:
        """列出已下载的PDF"""
        try:
            pdfs = await self.pdf_manager.search_pdfs(
                stock_code=stock_code,
                market=market,
                report_type=report_type,
                limit=limit
            )
            
            return {
                "success": True,
                "data": pdfs,
                "count": len(pdfs)
            }
            
        except Exception as e:
            logger.error(f"列出PDF失败: {e}")
            return {"success": False, "error": str(e)}
            
    async def get_pdf_info(self, pdf_id: int) -> Dict[str, Any]:
        """获取PDF详细信息"""
        try:
            pdf_info = await self.pdf_manager.get_pdf_by_id(pdf_id)
            
            if pdf_info:
                return {"success": True, "data": pdf_info}
            else:
                return {"success": False, "error": "PDF不存在"}
                
        except Exception as e:
            logger.error(f"获取PDF信息失败: {e}")
            return {"success": False, "error": str(e)}
            
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            stats = await self.pdf_manager.get_stats()
            return {"success": True, "data": stats}
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"success": False, "error": str(e)}
            
    async def cleanup_old_files(self, days: int = 90) -> Dict[str, Any]:
        """清理旧文件"""
        try:
            await self.pdf_manager.cleanup_old_files(days)
            return {"success": True, "message": f"已清理{days}天前的旧文件"}

        except Exception as e:
            logger.error(f"清理旧文件失败: {e}")
            return {"success": False, "error": str(e)}

    async def extract_pdf_content(self, pdf_path: str = None,
                                  pdf_id: int = None,
                                  force_refresh: bool = False) -> Dict[str, Any]:
        """
        提取PDF财报内容（支持缓存）

        Args:
            pdf_path: PDF文件路径（优先使用）
            pdf_id: PDF记录ID（从数据库获取路径）
            force_refresh: 是否强制重新提取（忽略缓存）

        Returns:
            包含结构化财务数据的字典，包含 _cache_info 字段标识缓存状态
        """
        try:
            # 确定PDF路径
            if pdf_path:
                file_path = Path(pdf_path)
            elif pdf_id:
                pdf_info = await self.pdf_manager.get_pdf_by_id(pdf_id)
                if not pdf_info:
                    return {"success": False, "error": f"未找到ID为{pdf_id}的PDF记录"}
                file_path = Path(pdf_info['file_path'])
            else:
                return {"success": False, "error": "请提供pdf_path或pdf_id参数"}

            if not file_path.exists():
                return {"success": False, "error": f"PDF文件不存在: {file_path}"}

            # 计算文件哈希
            file_hash = await self.pdf_manager.calculate_file_hash(file_path)

            # 检查缓存（除非强制刷新）
            if not force_refresh:
                cached_result = await self.pdf_manager.get_cached_extraction(file_hash)
                if cached_result:
                    logger.info(f"缓存命中: {file_path.name}")
                    cached_result['file_path'] = str(file_path)
                    return cached_result

            # 缓存未命中，执行提取
            logger.info(f"缓存未命中，开始提取: {file_path.name}")
            start_time = time.time()

            result = self.content_extractor.extract(str(file_path))

            extraction_duration_ms = int((time.time() - start_time) * 1000)

            if result.get("success"):
                # 保存到缓存
                await self.pdf_manager.save_extraction_cache(
                    file_hash=file_hash,
                    result=result,
                    extraction_duration_ms=extraction_duration_ms
                )

                # 添加缓存信息
                result['_cache_info'] = {
                    'from_cache': False,
                    'extracted_at': datetime.now().isoformat(),
                    'extraction_duration_ms': extraction_duration_ms,
                    'file_hash': file_hash
                }
                result['file_path'] = str(file_path)

                return result
            else:
                return result

        except Exception as e:
            logger.error(f"提取PDF内容失败: {e}")
            return {"success": False, "error": str(e)}

    async def extract_tables(self, pdf_path: str = None,
                            pdf_id: int = None) -> Dict[str, Any]:
        """
        提取PDF中的所有表格

        Args:
            pdf_path: PDF文件路径
            pdf_id: PDF记录ID

        Returns:
            包含所有表格数据的字典
        """
        try:
            # 确定PDF路径
            if pdf_path:
                file_path = Path(pdf_path)
            elif pdf_id:
                pdf_info = await self.pdf_manager.get_pdf_by_id(pdf_id)
                if not pdf_info:
                    return {"success": False, "error": f"未找到ID为{pdf_id}的PDF记录"}
                file_path = Path(pdf_info['file_path'])
            else:
                return {"success": False, "error": "请提供pdf_path或pdf_id参数"}

            if not file_path.exists():
                return {"success": False, "error": f"PDF文件不存在: {file_path}"}

            # 提取表格
            tables = self.content_extractor.extract_tables_raw(str(file_path))

            return {
                "success": True,
                "data": {
                    "tables": tables,
                    "total_tables": len(tables)
                },
                "file_path": str(file_path)
            }

        except Exception as e:
            logger.error(f"提取表格失败: {e}")
            return {"success": False, "error": str(e)}

    async def extract_text(self, pdf_path: str = None,
                          pdf_id: int = None) -> Dict[str, Any]:
        """
        提取PDF全部文本

        Args:
            pdf_path: PDF文件路径
            pdf_id: PDF记录ID

        Returns:
            包含全部文本的字典
        """
        try:
            # 确定PDF路径
            if pdf_path:
                file_path = Path(pdf_path)
            elif pdf_id:
                pdf_info = await self.pdf_manager.get_pdf_by_id(pdf_id)
                if not pdf_info:
                    return {"success": False, "error": f"未找到ID为{pdf_id}的PDF记录"}
                file_path = Path(pdf_info['file_path'])
            else:
                return {"success": False, "error": "请提供pdf_path或pdf_id参数"}

            if not file_path.exists():
                return {"success": False, "error": f"PDF文件不存在: {file_path}"}

            # 提取文本
            text = self.content_extractor.extract_text_full(str(file_path))

            return {
                "success": True,
                "data": {
                    "text": text,
                    "length": len(text)
                },
                "file_path": str(file_path)
            }

        except Exception as e:
            logger.error(f"提取文本失败: {e}")
            return {"success": False, "error": str(e)}

    # ==================== 缓存管理功能 ====================

    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取提取缓存统计信息"""
        try:
            stats = await self.pdf_manager.get_cache_stats()
            return {"success": True, "data": stats}
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {"success": False, "error": str(e)}

    async def cleanup_extraction_cache(self, days: int = 90) -> Dict[str, Any]:
        """
        清理旧的提取缓存

        Args:
            days: 清理超过多少天的缓存

        Returns:
            清理统计结果
        """
        try:
            result = await self.pdf_manager.cleanup_extraction_cache(days)
            return {
                "success": True,
                "data": result,
                "message": f"清理了 {result.get('deleted', 0)} 个过期缓存, {result.get('orphaned', 0)} 个孤立缓存"
            }
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")
            return {"success": False, "error": str(e)}

    async def warm_cache(self, stock_code: str = None, market: str = None,
                        limit: int = 10) -> Dict[str, Any]:
        """
        预热缓存 - 对未缓存的PDF执行提取

        Args:
            stock_code: 可选，指定股票代码
            market: 可选，指定市场
            limit: 最多处理多少个PDF

        Returns:
            预热结果统计
        """
        try:
            # 获取未缓存的PDF
            uncached_pdfs = await self.pdf_manager.get_uncached_pdfs(
                stock_code=stock_code,
                market=market,
                limit=limit
            )

            if not uncached_pdfs:
                return {
                    "success": True,
                    "data": {
                        "processed": 0,
                        "succeeded": 0,
                        "failed": 0
                    },
                    "message": "所有PDF都已缓存"
                }

            succeeded = 0
            failed = 0
            total_duration_ms = 0

            for pdf in uncached_pdfs:
                result = await self.extract_pdf_content(pdf_path=pdf['file_path'])
                if result.get("success"):
                    succeeded += 1
                    if result.get("_cache_info"):
                        total_duration_ms += result["_cache_info"].get("extraction_duration_ms", 0)
                else:
                    failed += 1

            return {
                "success": True,
                "data": {
                    "processed": len(uncached_pdfs),
                    "succeeded": succeeded,
                    "failed": failed,
                    "total_duration_ms": total_duration_ms,
                    "avg_duration_ms": total_duration_ms // succeeded if succeeded > 0 else 0
                },
                "message": f"预热完成: 成功 {succeeded}, 失败 {failed}"
            }

        except Exception as e:
            logger.error(f"缓存预热失败: {e}")
            return {"success": False, "error": str(e)}