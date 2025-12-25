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
from sqlalchemy import String, Integer, DateTime, Text, Boolean, Float, select, and_, or_
from loguru import logger

from .config import Config


class Base(DeclarativeBase):
    pass


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
                if existing.scalar_one_or_none():
                    logger.info(f"PDF文件已存在: {pdf_info['file_name']}")
                    return None
                    
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
            
    async def search_pdfs(self, stock_code: Optional[str] = None, 
                         market: Optional[str] = None,
                         report_type: Optional[str] = None,
                         year: Optional[int] = None,
                         limit: int = 20) -> List[Dict[str, Any]]:
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
                    
                query = query.order_by(ReportPDF.download_time.desc()).limit(limit)
                
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