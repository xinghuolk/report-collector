"""
PDF文件管理系统
负责PDF文件的元数据管理、存储和检索
"""
import asyncio
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    Text,
    Boolean,
    Float,
    select,
    and_,
    or_,
    UniqueConstraint,
)
from loguru import logger

from .config import Config


class Base(DeclarativeBase):
    pass


# 提取器版本 - 更新此版本号会使所有旧缓存失效
EXTRACTOR_VERSION = "1.0.0"


class ExtractedFinancialData(Base):
    """财务数据提取缓存模型"""
    __tablename__ = "extracted_financial_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # 缓存键 - 基于文件哈希
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # 财务数据 (JSON格式存储)
    income_statement: Mapped[Optional[str]] = mapped_column(Text)
    balance_sheet: Mapped[Optional[str]] = mapped_column(Text)
    cash_flow_statement: Mapped[Optional[str]] = mapped_column(Text)
    financial_metrics: Mapped[Optional[str]] = mapped_column(Text)
    related_party_transactions: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)
    extraction_summary: Mapped[Optional[str]] = mapped_column(Text)

    # 缓存管理
    extracted_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now)
    extractor_version: Mapped[str] = mapped_column(String(20), nullable=False)
    extraction_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    fields_extracted: Mapped[int] = mapped_column(Integer, default=0)


class ExtractedFinancialDataV2(Base):
    """财务数据提取缓存模型（V2结构）"""
    __tablename__ = "extracted_financial_data_v2"
    __table_args__ = (
        UniqueConstraint("file_hash", "schema_version", name="uq_extracted_financial_data_v2_hash_schema"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v2")

    # V2 主结构
    document_json: Mapped[Optional[str]] = mapped_column(Text)
    periods_json: Mapped[Optional[str]] = mapped_column(Text)
    facts_json: Mapped[Optional[str]] = mapped_column(Text)
    evidence_json: Mapped[Optional[str]] = mapped_column(Text)
    quality_json: Mapped[Optional[str]] = mapped_column(Text)

    # 兼容层字段（V1 payload）
    compat_payload_json: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)
    extraction_summary: Mapped[Optional[str]] = mapped_column(Text)

    # 缓存管理
    extracted_at: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now)
    extractor_version: Mapped[str] = mapped_column(String(20), nullable=False)
    extraction_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    fields_extracted: Mapped[int] = mapped_column(Integer, default=0)


class ReportPDF(Base):
    """财报PDF文件模型"""
    __tablename__ = "report_pdfs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 股票信息
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stock_name: Mapped[Optional[str]] = mapped_column(String(100))
    market: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # CN, HK, US
    
    # 报告信息
    report_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # annual, semi_annual, quarterly
    report_year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    report_quarter: Mapped[Optional[int]] = mapped_column(Integer)  # 1,2,3,4 或 NULL
    announcement_date: Mapped[Optional[DateTime]] = mapped_column(DateTime)
    
    # 文件信息
    original_title: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64))  # SHA256
    
    # 下载信息
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(50), nullable=False)  # 巨潮资讯网, 香港交易所, SEC EDGAR
    download_time: Mapped[DateTime] = mapped_column(DateTime, default=datetime.now)
    
    # 状态信息
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    last_accessed: Mapped[Optional[DateTime]] = mapped_column(DateTime)
    
    # 元数据
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON格式的额外元数据


class PDFManager:
    """PDF文件管理器"""
    
    def __init__(self):
        self.engine = create_async_engine(Config.DATABASE_URL, echo=False)
        self.async_session = async_sessionmaker(
            self.engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )
        
    async def initialize(self):
        """初始化数据库"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("PDF管理器数据库初始化完成")
        
    async def add_pdf(self, pdf_info: Dict[str, Any]) -> Optional[int]:
        """添加PDF记录"""
        try:
            # 计算文件哈希
            file_path = Path(pdf_info['file_path'])
            if file_path.exists():
                file_hash = await self._calculate_file_hash(file_path)
                file_size = file_path.stat().st_size
            else:
                logger.warning(f"PDF文件不存在: {file_path}")
                return None
                
            # 检查是否已存在相同文件
            async with self.async_session() as session:
                existing = await session.execute(
                    select(ReportPDF).where(ReportPDF.file_hash == file_hash)
                )
                existing_record = existing.scalar_one_or_none()
                if existing_record:
                    updated = False
                    for field in [
                        "source_url",
                        "announcement_date",
                        "report_year",
                        "report_quarter",
                        "stock_name",
                        "metadata_json",
                    ]:
                        incoming = pdf_info.get(field)
                        if incoming is not None and getattr(existing_record, field) in (None, ""):
                            setattr(existing_record, field, incoming)
                            updated = True

                    if updated:
                        await session.commit()
                        logger.info(f"PDF记录已更新: {pdf_info['file_name']}")
                    else:
                        logger.info(f"PDF文件已存在: {pdf_info['file_name']}")
                    return existing_record.id
                    
                # 创建新记录
                pdf_record = ReportPDF(
                    stock_code=pdf_info['stock_code'],
                    stock_name=pdf_info.get('stock_name'),
                    market=pdf_info['market'],
                    report_type=pdf_info['report_type'],
                    report_year=pdf_info.get('report_year'),
                    report_quarter=pdf_info.get('report_quarter'),
                    announcement_date=pdf_info.get('announcement_date'),
                    original_title=pdf_info['original_title'],
                    file_path=str(file_path),
                    file_name=pdf_info['file_name'],
                    file_size=file_size,
                    file_hash=file_hash,
                    source_url=pdf_info.get('source_url'),
                    source_name=pdf_info['source_name'],
                    download_time=datetime.now(),
                    metadata_json=pdf_info.get('metadata_json')
                )
                
                session.add(pdf_record)
                await session.commit()
                await session.refresh(pdf_record)
                
                logger.info(f"PDF记录添加成功: {pdf_info['file_name']}")
                return pdf_record.id
                
        except Exception as e:
            logger.error(f"添加PDF记录失败: {e}")
            return None
            
    async def search_pdfs(
        self,
        stock_code: Optional[str] = None,
        market: Optional[str] = None,
        report_type: Optional[str] = None,
        year: Optional[int] = None,
        limit: int = 20,
        sort_by: str = "download_time",
        sort_order: str = "desc",
    ) -> List[Dict[str, Any]]:
        """搜索PDF文件"""
        try:
            async with self.async_session() as session:
                query = select(ReportPDF).where(ReportPDF.is_available == True)
                
                if stock_code:
                    query = query.where(ReportPDF.stock_code == stock_code)
                if market:
                    query = query.where(ReportPDF.market == market)
                if report_type and report_type != 'all':
                    query = query.where(ReportPDF.report_type == report_type)
                if year:
                    query = query.where(ReportPDF.report_year == year)
                    
                sort_fields = {
                    "download_time": ReportPDF.download_time,
                    "announcement_date": ReportPDF.announcement_date,
                    "report_year": ReportPDF.report_year,
                }
                sort_field = sort_fields.get(sort_by, ReportPDF.download_time)
                order_func = sort_field.desc if sort_order.lower() == "desc" else sort_field.asc
                query = query.order_by(order_func()).limit(limit)
                
                result = await session.execute(query)
                pdfs = result.scalars().all()
                
                return [self._pdf_to_dict(pdf) for pdf in pdfs]
                
        except Exception as e:
            logger.error(f"搜索PDF失败: {e}")
            return []
            
    async def get_pdf_by_id(self, pdf_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取PDF信息"""
        try:
            async with self.async_session() as session:
                result = await session.execute(
                    select(ReportPDF).where(ReportPDF.id == pdf_id)
                )
                pdf = result.scalar_one_or_none()
                
                if pdf:
                    # 更新最后访问时间
                    pdf.last_accessed = datetime.now()
                    await session.commit()
                    return self._pdf_to_dict(pdf)
                    
                return None
                
        except Exception as e:
            logger.error(f"获取PDF信息失败: {e}")
            return None
            
    async def list_pdfs_by_stock(self, stock_code: str, market: str) -> List[Dict[str, Any]]:
        """获取指定股票的所有PDF"""
        return await self.search_pdfs(stock_code=stock_code, market=market, limit=100)
        
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            async with self.async_session() as session:
                # 总数统计
                total_result = await session.execute(
                    select(ReportPDF.id).where(ReportPDF.is_available == True)
                )
                total_count = len(total_result.scalars().all())
                
                # 按市场统计
                market_stats = {}
                for market in Config.SUPPORTED_MARKETS:
                    market_result = await session.execute(
                        select(ReportPDF.id).where(
                            and_(ReportPDF.market == market, ReportPDF.is_available == True)
                        )
                    )
                    market_stats[market] = len(market_result.scalars().all())
                    
                # 按类型统计  
                type_stats = {}
                for report_type in ['annual', 'semi_annual', 'quarterly']:
                    type_result = await session.execute(
                        select(ReportPDF.id).where(
                            and_(ReportPDF.report_type == report_type, ReportPDF.is_available == True)
                        )
                    )
                    type_stats[report_type] = len(type_result.scalars().all())
                    
                return {
                    'total_pdfs': total_count,
                    'by_market': market_stats,
                    'by_type': type_stats,
                    'last_updated': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
            
    async def cleanup_old_files(self, days: int = 90):
        """清理旧文件"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        try:
            async with self.async_session() as session:
                # 查找旧记录
                result = await session.execute(
                    select(ReportPDF).where(ReportPDF.download_time < cutoff_time)
                )
                old_pdfs = result.scalars().all()
                
                for pdf in old_pdfs:
                    # 删除物理文件
                    file_path = Path(pdf.file_path)
                    if file_path.exists():
                        file_path.unlink()
                        logger.info(f"删除旧文件: {file_path}")
                        
                    # 标记为不可用
                    pdf.is_available = False
                    
                await session.commit()
                logger.info(f"清理了 {len(old_pdfs)} 个旧文件")
                
        except Exception as e:
            logger.error(f"清理旧文件失败: {e}")
            
    async def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件SHA256哈希"""
        hash_sha256 = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
                
        return hash_sha256.hexdigest()
        
    def _pdf_to_dict(self, pdf: ReportPDF) -> Dict[str, Any]:
        """将PDF模型转换为字典"""
        return {
            'id': pdf.id,
            'stock_code': pdf.stock_code,
            'stock_name': pdf.stock_name,
            'market': pdf.market,
            'report_type': pdf.report_type,
            'report_year': pdf.report_year,
            'report_quarter': pdf.report_quarter,
            'announcement_date': pdf.announcement_date.isoformat() if pdf.announcement_date else None,
            'original_title': pdf.original_title,
            'file_path': pdf.file_path,
            'file_name': pdf.file_name,
            'file_size': pdf.file_size,
            'file_hash': pdf.file_hash,
            'source_url': pdf.source_url,
            'source_name': pdf.source_name,
            'download_time': pdf.download_time.isoformat(),
            'is_available': pdf.is_available,
            'last_accessed': pdf.last_accessed.isoformat() if pdf.last_accessed else None
        }

    # ==================== 财务数据提取缓存管理 ====================

    async def get_cached_extraction(
        self, file_hash: str, schema_version: str = "v1"
    ) -> Optional[Dict[str, Any]]:
        """
        根据文件哈希获取缓存的提取结果

        Returns:
            缓存的提取结果字典，如果不存在或版本不匹配则返回 None
        """
        try:
            import json

            async with self.async_session() as session:
                if schema_version == "v2":
                    result = await session.execute(
                        select(ExtractedFinancialDataV2).where(
                            and_(
                                ExtractedFinancialDataV2.file_hash == file_hash,
                                ExtractedFinancialDataV2.schema_version == "v2",
                                ExtractedFinancialDataV2.extractor_version == EXTRACTOR_VERSION,
                            )
                        )
                    )
                    cache_v2 = result.scalar_one_or_none()
                    if not cache_v2:
                        return None

                    payload = json.loads(cache_v2.compat_payload_json) if cache_v2.compat_payload_json else {}
                    response = {
                        "success": True,
                        "schema_version": "v2",
                        "compat_mode": payload.get("compat_mode", True),
                        "document": json.loads(cache_v2.document_json) if cache_v2.document_json else {},
                        "periods": json.loads(cache_v2.periods_json) if cache_v2.periods_json else [],
                        "facts": json.loads(cache_v2.facts_json) if cache_v2.facts_json else [],
                        "evidence": json.loads(cache_v2.evidence_json) if cache_v2.evidence_json else [],
                        "quality": json.loads(cache_v2.quality_json) if cache_v2.quality_json else {
                            "status": "partial",
                            "issues": [],
                        },
                        "income_statement": payload.get("income_statement", {}),
                        "balance_sheet": payload.get("balance_sheet", {}),
                        "cash_flow_statement": payload.get("cash_flow_statement", {}),
                        "financial_metrics": payload.get("financial_metrics", {}),
                        "related_party_transactions": payload.get("related_party_transactions", []),
                        "metadata": json.loads(cache_v2.metadata_json) if cache_v2.metadata_json else {},
                        "extraction_summary": json.loads(cache_v2.extraction_summary) if cache_v2.extraction_summary else {},
                        "_cache_info": {
                            "from_cache": True,
                            "schema_version": "v2",
                            "extracted_at": cache_v2.extracted_at.isoformat(),
                            "extraction_duration_ms": cache_v2.extraction_duration_ms,
                            "extractor_version": cache_v2.extractor_version,
                            "fields_extracted": cache_v2.fields_extracted,
                        },
                    }
                    return response

                result = await session.execute(
                    select(ExtractedFinancialData).where(
                        and_(
                            ExtractedFinancialData.file_hash == file_hash,
                            ExtractedFinancialData.extractor_version == EXTRACTOR_VERSION,
                        )
                    )
                )
                cache = result.scalar_one_or_none()
                if not cache:
                    return None

                return {
                    "success": True,
                    "income_statement": json.loads(cache.income_statement) if cache.income_statement else {},
                    "balance_sheet": json.loads(cache.balance_sheet) if cache.balance_sheet else {},
                    "cash_flow_statement": json.loads(cache.cash_flow_statement) if cache.cash_flow_statement else {},
                    "financial_metrics": json.loads(cache.financial_metrics) if cache.financial_metrics else {},
                    "related_party_transactions": json.loads(cache.related_party_transactions) if cache.related_party_transactions else [],
                    "metadata": json.loads(cache.metadata_json) if cache.metadata_json else {},
                    "extraction_summary": json.loads(cache.extraction_summary) if cache.extraction_summary else {},
                    "_cache_info": {
                        "from_cache": True,
                        "schema_version": "v1",
                        "extracted_at": cache.extracted_at.isoformat(),
                        "extraction_duration_ms": cache.extraction_duration_ms,
                        "extractor_version": cache.extractor_version,
                        "fields_extracted": cache.fields_extracted,
                    },
                }

        except Exception as e:
            logger.error(f"获取缓存失败: {e}")
            return None

    async def save_extraction_cache(
        self,
        file_hash: str,
        result: Dict[str, Any],
        extraction_duration_ms: int = 0,
        schema_version: Optional[str] = None,
    ) -> bool:
        """
        保存提取结果到缓存

        Args:
            file_hash: 文件SHA256哈希
            result: 提取结果字典
            extraction_duration_ms: 提取耗时(毫秒)

        Returns:
            是否保存成功
        """
        try:
            import json

            target_schema = schema_version or result.get("schema_version", "v1")

            # 计算提取的字段数
            fields_count = 0
            for key in [
                "income_statement",
                "balance_sheet",
                "cash_flow_statement",
                "financial_metrics",
                "related_party_transactions",
            ]:
                data = result.get(key, {})
                if isinstance(data, dict):
                    fields_count += sum(1 for v in data.values() if v is not None)
                elif isinstance(data, list):
                    fields_count += len(data)
            if target_schema == "v2":
                fields_count += len(result.get("facts", []))

            async with self.async_session() as session:
                if target_schema == "v2":
                    existing = await session.execute(
                        select(ExtractedFinancialDataV2).where(
                            and_(
                                ExtractedFinancialDataV2.file_hash == file_hash,
                                ExtractedFinancialDataV2.schema_version == "v2",
                            )
                        )
                    )
                    cache_v2 = existing.scalar_one_or_none()
                    compat_payload = {
                        "compat_mode": result.get("compat_mode", True),
                        "income_statement": result.get("income_statement", {}),
                        "balance_sheet": result.get("balance_sheet", {}),
                        "cash_flow_statement": result.get("cash_flow_statement", {}),
                        "financial_metrics": result.get("financial_metrics", {}),
                        "related_party_transactions": result.get("related_party_transactions", []),
                    }
                    if cache_v2:
                        cache_v2.document_json = json.dumps(result.get("document", {}), ensure_ascii=False)
                        cache_v2.periods_json = json.dumps(result.get("periods", []), ensure_ascii=False)
                        cache_v2.facts_json = json.dumps(result.get("facts", []), ensure_ascii=False)
                        cache_v2.evidence_json = json.dumps(result.get("evidence", []), ensure_ascii=False)
                        cache_v2.quality_json = json.dumps(
                            result.get("quality", {"status": "partial", "issues": []}),
                            ensure_ascii=False,
                        )
                        cache_v2.compat_payload_json = json.dumps(compat_payload, ensure_ascii=False)
                        cache_v2.metadata_json = json.dumps(result.get("metadata", {}), ensure_ascii=False)
                        cache_v2.extraction_summary = json.dumps(result.get("extraction_summary", {}), ensure_ascii=False)
                        cache_v2.extracted_at = datetime.now()
                        cache_v2.extractor_version = EXTRACTOR_VERSION
                        cache_v2.extraction_duration_ms = extraction_duration_ms
                        cache_v2.fields_extracted = fields_count
                    else:
                        cache_v2 = ExtractedFinancialDataV2(
                            file_hash=file_hash,
                            schema_version="v2",
                            document_json=json.dumps(result.get("document", {}), ensure_ascii=False),
                            periods_json=json.dumps(result.get("periods", []), ensure_ascii=False),
                            facts_json=json.dumps(result.get("facts", []), ensure_ascii=False),
                            evidence_json=json.dumps(result.get("evidence", []), ensure_ascii=False),
                            quality_json=json.dumps(
                                result.get("quality", {"status": "partial", "issues": []}),
                                ensure_ascii=False,
                            ),
                            compat_payload_json=json.dumps(compat_payload, ensure_ascii=False),
                            metadata_json=json.dumps(result.get("metadata", {}), ensure_ascii=False),
                            extraction_summary=json.dumps(result.get("extraction_summary", {}), ensure_ascii=False),
                            extracted_at=datetime.now(),
                            extractor_version=EXTRACTOR_VERSION,
                            extraction_duration_ms=extraction_duration_ms,
                            fields_extracted=fields_count,
                        )
                        session.add(cache_v2)
                else:
                    existing = await session.execute(
                        select(ExtractedFinancialData).where(
                            ExtractedFinancialData.file_hash == file_hash
                        )
                    )
                    cache = existing.scalar_one_or_none()
                    if cache:
                        cache.income_statement = json.dumps(result.get("income_statement", {}), ensure_ascii=False)
                        cache.balance_sheet = json.dumps(result.get("balance_sheet", {}), ensure_ascii=False)
                        cache.cash_flow_statement = json.dumps(result.get("cash_flow_statement", {}), ensure_ascii=False)
                        cache.financial_metrics = json.dumps(result.get("financial_metrics", {}), ensure_ascii=False)
                        cache.related_party_transactions = json.dumps(result.get("related_party_transactions", []), ensure_ascii=False)
                        cache.metadata_json = json.dumps(result.get("metadata", {}), ensure_ascii=False)
                        cache.extraction_summary = json.dumps(result.get("extraction_summary", {}), ensure_ascii=False)
                        cache.extracted_at = datetime.now()
                        cache.extractor_version = EXTRACTOR_VERSION
                        cache.extraction_duration_ms = extraction_duration_ms
                        cache.fields_extracted = fields_count
                    else:
                        cache = ExtractedFinancialData(
                            file_hash=file_hash,
                            income_statement=json.dumps(result.get("income_statement", {}), ensure_ascii=False),
                            balance_sheet=json.dumps(result.get("balance_sheet", {}), ensure_ascii=False),
                            cash_flow_statement=json.dumps(result.get("cash_flow_statement", {}), ensure_ascii=False),
                            financial_metrics=json.dumps(result.get("financial_metrics", {}), ensure_ascii=False),
                            related_party_transactions=json.dumps(result.get("related_party_transactions", []), ensure_ascii=False),
                            metadata_json=json.dumps(result.get("metadata", {}), ensure_ascii=False),
                            extraction_summary=json.dumps(result.get("extraction_summary", {}), ensure_ascii=False),
                            extracted_at=datetime.now(),
                            extractor_version=EXTRACTOR_VERSION,
                            extraction_duration_ms=extraction_duration_ms,
                            fields_extracted=fields_count,
                        )
                        session.add(cache)

                await session.commit()
                logger.info(
                    f"缓存保存成功: {file_hash[:16]}... ({fields_count} 字段, "
                    f"{extraction_duration_ms}ms, schema={target_schema})"
                )
                return True

        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
            return False

    async def invalidate_cache(
        self, file_hash: str, schema_version: Optional[str] = None
    ) -> bool:
        """
        使缓存失效

        Args:
            file_hash: 文件SHA256哈希

        Returns:
            是否成功删除
        """
        try:
            async with self.async_session() as session:
                deleted = False
                if schema_version in (None, "v1"):
                    result = await session.execute(
                        select(ExtractedFinancialData).where(
                            ExtractedFinancialData.file_hash == file_hash
                        )
                    )
                    cache = result.scalar_one_or_none()
                    if cache:
                        await session.delete(cache)
                        deleted = True

                if schema_version in (None, "v2"):
                    result_v2 = await session.execute(
                        select(ExtractedFinancialDataV2).where(
                            and_(
                                ExtractedFinancialDataV2.file_hash == file_hash,
                                ExtractedFinancialDataV2.schema_version == "v2",
                            )
                        )
                    )
                    cache_v2 = result_v2.scalar_one_or_none()
                    if cache_v2:
                        await session.delete(cache_v2)
                        deleted = True

                if deleted:
                    await session.commit()
                    logger.info(f"缓存已失效: {file_hash[:16]}..., schema={schema_version or 'all'}")
                return deleted

        except Exception as e:
            logger.error(f"使缓存失效失败: {e}")
            return False

    async def cleanup_extraction_cache(self, days: int = 90) -> Dict[str, int]:
        """
        清理旧的提取缓存

        Args:
            days: 清理超过多少天的缓存

        Returns:
            清理统计 {'deleted': n, 'orphaned': m}
        """
        cutoff_time = datetime.now() - timedelta(days=days)
        deleted_count = 0
        orphaned_count = 0

        try:
            async with self.async_session() as session:
                # 1. 删除旧版本/过期缓存（V1）
                old_v1_result = await session.execute(
                    select(ExtractedFinancialData).where(
                        or_(
                            ExtractedFinancialData.extractor_version != EXTRACTOR_VERSION,
                            ExtractedFinancialData.extracted_at < cutoff_time,
                        )
                    )
                )
                for cache in old_v1_result.scalars().all():
                    await session.delete(cache)
                    deleted_count += 1

                # 2. 删除旧版本/过期缓存（V2）
                old_v2_result = await session.execute(
                    select(ExtractedFinancialDataV2).where(
                        or_(
                            ExtractedFinancialDataV2.extractor_version != EXTRACTOR_VERSION,
                            ExtractedFinancialDataV2.extracted_at < cutoff_time,
                        )
                    )
                )
                for cache in old_v2_result.scalars().all():
                    await session.delete(cache)
                    deleted_count += 1

                all_pdf_hashes_result = await session.execute(
                    select(ReportPDF.file_hash).where(ReportPDF.is_available == True)
                )
                valid_hashes = set(h for h in all_pdf_hashes_result.scalars().all() if h)

                # 3. 删除孤立缓存（V1）
                all_v1_caches_result = await session.execute(select(ExtractedFinancialData))
                for cache in all_v1_caches_result.scalars().all():
                    if cache.file_hash not in valid_hashes:
                        await session.delete(cache)
                        orphaned_count += 1

                # 4. 删除孤立缓存（V2）
                all_v2_caches_result = await session.execute(select(ExtractedFinancialDataV2))
                for cache in all_v2_caches_result.scalars().all():
                    if cache.file_hash not in valid_hashes:
                        await session.delete(cache)
                        orphaned_count += 1

                await session.commit()
                logger.info(f"缓存清理完成: 删除 {deleted_count} 个过期缓存, {orphaned_count} 个孤立缓存")

                return {'deleted': deleted_count, 'orphaned': orphaned_count}

        except Exception as e:
            logger.error(f"清理缓存失败: {e}")
            return {'deleted': 0, 'orphaned': 0, 'error': str(e)}

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计字典
        """
        try:
            async with self.async_session() as session:
                # 总缓存数（V1 + V2）
                total_v1_result = await session.execute(select(ExtractedFinancialData))
                all_v1 = total_v1_result.scalars().all()
                total_v2_result = await session.execute(select(ExtractedFinancialDataV2))
                all_v2 = total_v2_result.scalars().all()
                all_caches = list(all_v1) + list(all_v2)

                if not all_caches:
                    return {
                        'total_cached': 0,
                        'cache_size_kb': 0,
                        'avg_extraction_time_ms': 0,
                        'avg_fields_extracted': 0,
                        'oldest_cache': None,
                        'newest_cache': None,
                        'by_version': {},
                        'current_version': EXTRACTOR_VERSION
                    }

                # 计算统计
                total_size = 0
                total_time = 0
                total_fields = 0
                time_count = 0
                version_stats = {}
                oldest = None
                newest = None

                for cache in all_caches:
                    # 大小统计（估算JSON大小，兼容 V1/V2）
                    fields = []
                    if isinstance(cache, ExtractedFinancialData):
                        fields = [
                            cache.income_statement,
                            cache.balance_sheet,
                            cache.cash_flow_statement,
                            cache.financial_metrics,
                            cache.related_party_transactions,
                            cache.metadata_json,
                            cache.extraction_summary,
                        ]
                    else:
                        fields = [
                            cache.document_json,
                            cache.periods_json,
                            cache.facts_json,
                            cache.evidence_json,
                            cache.quality_json,
                            cache.compat_payload_json,
                            cache.metadata_json,
                            cache.extraction_summary,
                        ]
                    for field in fields:
                        if field:
                            total_size += len(field.encode('utf-8'))

                    # 时间统计
                    if cache.extraction_duration_ms:
                        total_time += cache.extraction_duration_ms
                        time_count += 1

                    # 字段统计
                    total_fields += cache.fields_extracted

                    # 版本统计
                    version = cache.extractor_version
                    version_stats[version] = version_stats.get(version, 0) + 1

                    # 时间范围
                    if oldest is None or cache.extracted_at < oldest:
                        oldest = cache.extracted_at
                    if newest is None or cache.extracted_at > newest:
                        newest = cache.extracted_at

                return {
                    'total_cached': len(all_caches),
                    'cache_size_kb': round(total_size / 1024, 2),
                    'avg_extraction_time_ms': round(total_time / time_count) if time_count > 0 else 0,
                    'avg_fields_extracted': round(total_fields / len(all_caches), 1),
                    'oldest_cache': oldest.isoformat() if oldest else None,
                    'newest_cache': newest.isoformat() if newest else None,
                    'by_version': version_stats,
                    'current_version': EXTRACTOR_VERSION
                }

        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {'error': str(e)}

    async def get_uncached_pdfs(
        self,
        stock_code: Optional[str] = None,
        market: Optional[str] = None,
        limit: int = 100,
        schema_version: str = "v2",
    ) -> List[Dict[str, Any]]:
        """
        获取未缓存的PDF列表（用于缓存预热）

        Args:
            stock_code: 可选，指定股票代码
            market: 可选，指定市场
            limit: 返回数量限制

        Returns:
            未缓存的PDF信息列表
        """
        try:
            async with self.async_session() as session:
                # 获取所有已缓存的哈希
                if schema_version == "v2":
                    cached_result = await session.execute(
                        select(ExtractedFinancialDataV2.file_hash).where(
                            and_(
                                ExtractedFinancialDataV2.extractor_version == EXTRACTOR_VERSION,
                                ExtractedFinancialDataV2.schema_version == "v2",
                            )
                        )
                    )
                else:
                    cached_result = await session.execute(
                        select(ExtractedFinancialData.file_hash).where(
                            ExtractedFinancialData.extractor_version == EXTRACTOR_VERSION
                        )
                    )
                cached_hashes = set(cached_result.scalars().all())

                # 查询未缓存的PDF
                query = select(ReportPDF).where(
                    and_(
                        ReportPDF.is_available == True,
                        ReportPDF.file_hash.isnot(None)
                    )
                )

                if stock_code:
                    query = query.where(ReportPDF.stock_code == stock_code)
                if market:
                    query = query.where(ReportPDF.market == market)

                query = query.order_by(ReportPDF.download_time.desc()).limit(limit * 2)

                result = await session.execute(query)
                pdfs = result.scalars().all()

                uncached = []
                for pdf in pdfs:
                    if pdf.file_hash not in cached_hashes:
                        uncached.append(self._pdf_to_dict(pdf))
                        if len(uncached) >= limit:
                            break

                return uncached

        except Exception as e:
            logger.error(f"获取未缓存PDF失败: {e}")
            return []

    async def calculate_file_hash(self, file_path: Path) -> str:
        """计算文件SHA256哈希（公开方法）"""
        return await self._calculate_file_hash(file_path)
