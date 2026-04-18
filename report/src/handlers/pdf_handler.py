"""
PDF财报处理器
整合所有PDF下载、管理和内容提取功能
"""
import asyncio
import json
import re
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

    @staticmethod
    def _parse_hk_release_time(release_time: Optional[str]) -> Optional[datetime]:
        """解析港股披露易发布时间"""
        if not release_time:
            return None

        cleaned = release_time.replace("Release Time:", "").strip()
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_cn_announcement_time(report: Dict[str, Any]) -> Optional[datetime]:
        """解析A股公告发布时间"""
        raw_ts = report.get("announcement_time")
        if raw_ts:
            try:
                return datetime.fromtimestamp(int(raw_ts) / 1000)
            except (ValueError, TypeError):
                pass

        date_text = report.get("announcement_date")
        if date_text:
            try:
                return datetime.strptime(date_text, "%Y-%m-%d")
            except ValueError:
                return None

        return None

    @staticmethod
    def _normalize_schema_version(schema_version: Optional[str]) -> str:
        if schema_version in {"v1", "v2"}:
            return schema_version
        return "v2"

    @staticmethod
    def _to_v1_response(result: Dict[str, Any]) -> Dict[str, Any]:
        """将 V2 结果转换为 V1 兼容响应"""
        return {
            "success": bool(result.get("success")),
            "income_statement": result.get("income_statement", {}),
            "balance_sheet": result.get("balance_sheet", {}),
            "cash_flow_statement": result.get("cash_flow_statement", {}),
            "financial_metrics": result.get("financial_metrics", {}),
            "related_party_transactions": result.get("related_party_transactions", []),
            "metadata": result.get("metadata", {}),
            "extraction_summary": result.get("extraction_summary", {}),
            "_cache_info": result.get("_cache_info", {}),
            "file_path": result.get("file_path"),
        }

    @staticmethod
    def _build_hk_period_hint(
        report_type: str,
        title: Optional[str],
        year: Optional[int],
    ) -> Optional[str]:
        if not title:
            return f"{year}_{report_type}" if year else None

        title_lower = title.lower()
        if report_type == "annual":
            return f"{year}_fy" if year else "fy"
        if report_type == "semi_annual":
            return f"{year}_h1_ytd" if year else "h1_ytd"
        if report_type != "quarterly":
            return f"{year}_{report_type}" if year else report_type

        quarter_patterns = [
            ("q1", [r"\bq1\b", r"first quarter"]),
            ("q2", [r"\bq2\b", r"second quarter", r"six months", r"interim"]),
            ("q3", [r"\bq3\b", r"third quarter", r"nine months"]),
            ("q4", [r"\bq4\b", r"fourth quarter"]),
        ]
        for label, patterns in quarter_patterns:
            if any(re.search(pattern, title_lower, re.IGNORECASE) for pattern in patterns):
                if label == "q4" and ("full year" in title_lower or "year ended" in title_lower):
                    return f"{year}_q4_fy" if year else "q4_fy"
                return f"{year}_{label}" if year else label
        return f"{year}_quarterly" if year else "quarterly"

    def _build_hk_metadata_json(
        self, matched_report: Optional[Dict[str, Any]], report_type: str
    ) -> Optional[str]:
        if not matched_report:
            return None

        metadata = {
            "title": matched_report.get("title"),
            "release_time": matched_report.get("release_time"),
            "web_path": matched_report.get("web_path"),
            "period_hint": matched_report.get("period_hint")
            or self._build_hk_period_hint(
                report_type=report_type,
                title=matched_report.get("title"),
                year=matched_report.get("year"),
            ),
        }
        return json.dumps(metadata, ensure_ascii=False)

    @staticmethod
    def _normalize_report_types(
        report_types: Optional[List[str]], market: str
    ) -> List[str]:
        """标准化报告类型列表"""
        if not report_types:
            return ["annual", "semi_annual", "quarterly"]

        normalized: List[str] = []
        for report_type in report_types:
            if not report_type:
                continue
            if report_type == "all":
                return ["annual", "semi_annual", "quarterly"]
            normalized.append(report_type)

        return normalized or ["annual", "semi_annual", "quarterly"]

    @staticmethod
    def _report_identity(report: Dict[str, Any], market: str) -> str:
        """生成报告去重标识"""
        if market == "CN":
            return (
                report.get("adjunct_url")
                or report.get("announcement_id")
                or report.get("pdf_url")
                or report.get("announcement_title")
                or ""
            )
        return (
            report.get("web_path")
            or report.get("news_id")
            or report.get("pdf_url")
            or report.get("title")
            or ""
        )

    def _with_publish_time(self, report: Dict[str, Any], market: str) -> Dict[str, Any]:
        """补充统一的发布时间字段"""
        if market == "CN":
            publish_dt = self._parse_cn_announcement_time(report)
        else:
            publish_dt = self._parse_hk_release_time(report.get("release_time"))

        if publish_dt:
            report["publish_time"] = publish_dt.isoformat()
            report["publish_timestamp"] = int(publish_dt.timestamp())
        else:
            report["publish_time"] = None
            report["publish_timestamp"] = 0

        return report

    async def search_latest_reports(
        self,
        stock_code: str,
        market: str,
        report_types: Optional[List[str]] = None,
        max_count: int = 10,
    ) -> Dict[str, Any]:
        """跨类型检索并按发布时间排序的最新报告"""
        is_valid, error = DataValidator.validate_stock_symbol(stock_code, market)
        if not is_valid:
            return {"success": False, "error": error}

        is_valid, error = DataValidator.validate_market(market)
        if not is_valid:
            return {"success": False, "error": error}

        normalized_types = self._normalize_report_types(report_types, market)

        invalid_types = [
            report_type
            for report_type in normalized_types
            if report_type not in ("annual", "semi_annual", "quarterly")
        ]
        if invalid_types:
            return {"success": False, "error": f"不支持的报告类型: {', '.join(invalid_types)}"}

        cache_key = f"latest_{market}_{stock_code}_{'_'.join(normalized_types)}_{max_count}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            if market == "CN":
                tasks = [
                    self.cn_downloader.search_reports(
                        stock_code=stock_code,
                        report_type=report_type,
                        limit=max_count * 2,
                    )
                    for report_type in normalized_types
                ]
            elif market == "HK":
                tasks = [
                    self.hk_downloader.search_reports(
                        stock_code=stock_code,
                        report_type=report_type,
                        limit=max_count * 2,
                    )
                    for report_type in normalized_types
                ]
            else:
                return {"success": False, "error": f"不支持的市场: {market}"}

            results = await asyncio.gather(*tasks)
            merged: Dict[str, Dict[str, Any]] = {}

            for report_list in results:
                for report in report_list:
                    enriched = self._with_publish_time(report, market)
                    identity = self._report_identity(enriched, market)
                    if not identity:
                        identity = f"{enriched.get('title')}_{enriched.get('publish_time')}"
                    merged[identity] = enriched

            sorted_reports = sorted(
                merged.values(),
                key=lambda item: item.get("publish_timestamp", 0),
                reverse=True,
            )

            final_reports = sorted_reports[:max_count]
            result = {
                "success": True,
                "data": final_reports,
                "count": len(final_reports),
                "stock_code": stock_code,
                "market": market,
                "report_types": normalized_types,
                "sorted_by": "publish_time_desc",
            }

            self.cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"最新报告检索失败: {e}")
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
            
    async def download_stock_reports(
        self,
        stock_code: str,
        market: str = "CN",
        report_type: str = "annual",
        max_count: int = 3,
    ) -> Dict[str, Any]:
        """批量下载股票财报"""
        try:
            if market == "CN":
                # 下载中国A股财报
                downloaded_files = await self.cn_downloader.download_stock_reports(
                    stock_code, report_type, max_count
                )

                # 获取对应的报告信息用于补充元数据（顺序与下载一致）
                reports = await self.cn_downloader.search_reports(
                    stock_code=stock_code,
                    report_type=report_type,
                    limit=max_count,
                )
                
                # 批量添加到数据库
                pdf_ids = []
                for idx, file_path in enumerate(downloaded_files):
                    matched_report = reports[idx] if idx < len(reports) else None

                    announcement_date = (
                        self._parse_cn_announcement_time(matched_report)
                        if matched_report
                        else None
                    )
                    pdf_info = {
                        "stock_code": stock_code,
                        "market": market,
                        "report_type": report_type,
                        "report_year": matched_report.get("year") if matched_report else None,
                        "announcement_date": announcement_date,
                        "original_title": (
                            matched_report.get("announcement_title")
                            if matched_report
                            else Path(file_path).stem
                        ),
                        "file_path": file_path,
                        "file_name": Path(file_path).name,
                        "source_url": matched_report.get("pdf_url") if matched_report else None,
                        "source_name": "巨潮资讯网",
                        "metadata_json": None,
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
                # 下载港股财报（英文+繁体中文）
                download_results = await self.hk_downloader.download_stock_reports(
                    stock_code, report_type, max_count
                )

                # 批量添加到数据库
                pdf_ids = []
                downloaded_files = []
                for file_path, matched_report in download_results:
                    downloaded_files.append(file_path)
                    announcement_date = (
                        self._parse_hk_release_time(matched_report.get("release_time"))
                        if matched_report
                        else None
                    )
                    pdf_info = {
                        "stock_code": stock_code,
                        "market": market,
                        "report_type": report_type,
                        "report_year": matched_report.get("year") if matched_report else None,
                        "announcement_date": announcement_date,
                        "original_title": (
                            matched_report.get("title")
                            if matched_report
                            else Path(file_path).stem
                        ),
                        "file_path": file_path,
                        "file_name": Path(file_path).name,
                        "source_url": matched_report.get("pdf_url") if matched_report else None,
                        "source_name": "港交所披露易",
                        "metadata_json": self._build_hk_metadata_json(
                            matched_report, report_type
                        ),
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
            
    async def list_downloaded_pdfs(
        self,
        stock_code: str = None,
        market: str = None,
        report_type: str = None,
        limit: int = 20,
        sort_by: str = "download_time",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """列出已下载的PDF"""
        try:
            pdfs = await self.pdf_manager.search_pdfs(
                stock_code=stock_code,
                market=market,
                report_type=report_type,
                limit=limit,
                sort_by=sort_by,
                sort_order=sort_order,
            )

            valid_pdfs: List[Dict[str, Any]] = []
            missing_ids: List[int] = []
            for pdf in pdfs:
                if Path(pdf["file_path"]).exists():
                    valid_pdfs.append(pdf)
                else:
                    missing_ids.append(int(pdf["id"]))

            cleaned_missing = 0
            if missing_ids:
                cleaned_missing = await self.pdf_manager.mark_pdfs_unavailable(missing_ids)
                logger.warning(
                    f"检测到 {len(missing_ids)} 条孤儿PDF记录，已标记不可用 {cleaned_missing} 条"
                )

            return {
                "success": True,
                "data": valid_pdfs,
                "count": len(valid_pdfs),
                "missing_file_records_cleaned": cleaned_missing,
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

    async def _resolve_input_file_path(
        self, pdf_path: Optional[str], pdf_id: Optional[int]
    ) -> tuple[Optional[Path], Optional[str]]:
        """统一解析提取入口的 PDF 路径，并自动清理孤儿记录"""
        if pdf_path:
            file_path = Path(pdf_path)
            if not file_path.exists():
                return None, f"PDF文件不存在: {file_path}"
            return file_path, None

        if pdf_id:
            pdf_info = await self.pdf_manager.get_pdf_by_id(pdf_id)
            if not pdf_info:
                return None, f"未找到ID为{pdf_id}的PDF记录"

            file_path = Path(pdf_info["file_path"])
            if not file_path.exists():
                await self.pdf_manager.mark_pdfs_unavailable([pdf_id])
                return (
                    None,
                    f"PDF文件不存在: {file_path}；该记录已标记为不可用，请重新下载后再提取",
                )
            return file_path, None

        return None, "请提供pdf_path或pdf_id参数"

    @staticmethod
    def _apply_pdf_identity_context(
        result: Dict[str, Any],
        pdf_info: Optional[Dict[str, Any]],
    ) -> None:
        """用 PDF 记录上下文纠正提取结果身份字段（特别是 stock_code）。"""
        if not result.get("success") or not pdf_info:
            return

        stock_code = pdf_info.get("stock_code")
        stock_name = pdf_info.get("stock_name")
        market = pdf_info.get("market")

        metadata = result.get("metadata")
        if isinstance(metadata, dict):
            if stock_code:
                metadata["stock_code"] = stock_code
            if stock_name and not metadata.get("stock_name"):
                metadata["stock_name"] = stock_name
            if market and not metadata.get("market"):
                metadata["market"] = market

        document = result.get("document")
        if isinstance(document, dict):
            if stock_code:
                document["stock_code"] = stock_code
            if stock_name and not document.get("stock_name"):
                document["stock_name"] = stock_name
            if market and not document.get("market"):
                document["market"] = market

    async def extract_pdf_content(self, pdf_path: str = None,
                                  pdf_id: int = None,
                                  force_refresh: bool = False,
                                  schema_version: str = "v2",
                                  min_confidence: Optional[float] = None) -> Dict[str, Any]:
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
            schema_version = self._normalize_schema_version(schema_version)
            pdf_info: Optional[Dict[str, Any]] = None
            if pdf_id:
                pdf_info = await self.pdf_manager.get_pdf_by_id(pdf_id)
            file_path, resolve_error = await self._resolve_input_file_path(pdf_path, pdf_id)
            if resolve_error:
                return {"success": False, "error": resolve_error}
            assert file_path is not None

            # 计算文件哈希
            file_hash = await self.pdf_manager.calculate_file_hash(file_path)

            # 检查缓存（除非强制刷新）
            if not force_refresh:
                cached_result = await self.pdf_manager.get_cached_extraction(
                    file_hash,
                    schema_version=schema_version,
                )
                if cached_result:
                    logger.info(f"缓存命中: {file_path.name}")
                    self._apply_pdf_identity_context(cached_result, pdf_info)
                    cached_result['file_path'] = str(file_path)
                    return self._apply_min_confidence_filter(cached_result, min_confidence)

            # 缓存未命中，执行提取
            logger.info(f"缓存未命中，开始提取: {file_path.name}")
            start_time = time.time()

            result = self.content_extractor.extract(str(file_path))

            extraction_duration_ms = int((time.time() - start_time) * 1000)

            if result.get("success"):
                self._apply_pdf_identity_context(result, pdf_info)
                # V2 始终写缓存（主结构）
                await self.pdf_manager.save_extraction_cache(
                    file_hash=file_hash,
                    result=result,
                    extraction_duration_ms=extraction_duration_ms,
                    schema_version="v2",
                )

                # 添加缓存信息
                result['_cache_info'] = {
                    'from_cache': False,
                    'schema_version': "v2",
                    'extracted_at': datetime.now().isoformat(),
                    'extraction_duration_ms': extraction_duration_ms,
                    'file_hash': file_hash
                }
                result['file_path'] = str(file_path)

                if schema_version == "v1":
                    v1_result = self._to_v1_response(result)
                    cache_info = dict(result.get("_cache_info", {}))
                    cache_info["schema_version"] = "v1"
                    v1_result["_cache_info"] = cache_info
                    await self.pdf_manager.save_extraction_cache(
                        file_hash=file_hash,
                        result=v1_result,
                        extraction_duration_ms=extraction_duration_ms,
                        schema_version="v1",
                    )
                    return v1_result

                return self._apply_min_confidence_filter(result, min_confidence)
            else:
                return result

        except Exception as e:
            logger.error(f"提取PDF内容失败: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _apply_min_confidence_filter(
        result: Dict[str, Any], min_confidence: Optional[float]
    ) -> Dict[str, Any]:
        if min_confidence is None:
            return result
        if not result.get("success"):
            return result
        if result.get("schema_version") != "v2":
            return result

        facts = result.get("facts")
        if not isinstance(facts, list):
            return result

        kept_facts = []
        removed_fact_refs = []
        for fact in facts:
            confidence = fact.get("confidence")
            if isinstance(confidence, (int, float)) and confidence >= min_confidence:
                kept_facts.append(fact)
            else:
                removed_fact_refs.append(
                    f"{fact.get('statement')}.{fact.get('metric')}@{fact.get('period_id')}"
                )

        if len(kept_facts) == len(facts):
            return result

        result["facts"] = kept_facts
        quality = result.get("quality")
        if not isinstance(quality, dict):
            quality = {"status": "partial", "issues": []}
            result["quality"] = quality
        issues = quality.get("issues")
        if not isinstance(issues, list):
            issues = []
            quality["issues"] = issues

        issues.append(
            {
                "type": "confidence_filtered",
                "severity": "warning",
                "message": f"已按 min_confidence={min_confidence} 过滤低置信度事实。",
                "affected_facts": removed_fact_refs,
            }
        )
        if quality.get("status") == "ok":
            quality["status"] = "partial"

        return result

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
            file_path, resolve_error = await self._resolve_input_file_path(pdf_path, pdf_id)
            if resolve_error:
                return {"success": False, "error": resolve_error}
            assert file_path is not None

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
            file_path, resolve_error = await self._resolve_input_file_path(pdf_path, pdf_id)
            if resolve_error:
                return {"success": False, "error": resolve_error}
            assert file_path is not None

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
                limit=limit,
                schema_version="v2",
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
