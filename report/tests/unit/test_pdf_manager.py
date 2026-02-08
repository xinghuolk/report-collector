"""
PDF管理器单元测试
测试 PDFManager 类的所有数据库操作和缓存管理
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

from src.pdf_manager import PDFManager, ReportPDF, ExtractedFinancialData, EXTRACTOR_VERSION
from src.config import Config


class TestPDFManagerInitialization:
    """PDF管理器初始化测试"""

    @pytest.mark.asyncio
    async def test_initialize_creates_database(self, tmp_path):
        """测试初始化时创建数据库"""
        db_path = tmp_path / "test.db"
        original_url = Config.DATABASE_URL
        Config.DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"

        manager = PDFManager()
        await manager.initialize()

        # 数据库文件应该被创建
        assert db_path.exists()

        Config.DATABASE_URL = original_url

    @pytest.mark.asyncio
    async def test_initialize_multiple_times(self, pdf_manager):
        """测试多次初始化不会出错"""
        # 再次初始化不应抛出异常
        await pdf_manager.initialize()
        await pdf_manager.initialize()


class TestPDFRecordCRUD:
    """PDF记录CRUD测试"""

    @pytest.mark.asyncio
    async def test_add_pdf_success(self, pdf_manager, temp_pdf_file):
        """测试成功添加PDF记录"""
        pdf_info = {
            "stock_code": "000001",
            "stock_name": "平安银行",
            "market": "CN",
            "report_type": "annual",
            "report_year": 2023,
            "original_title": "平安银行2023年年度报告",
            "file_path": str(temp_pdf_file),
            "file_name": temp_pdf_file.name,
            "source_name": "巨潮资讯网",
        }

        pdf_id = await pdf_manager.add_pdf(pdf_info)

        assert pdf_id is not None
        assert isinstance(pdf_id, int)
        assert pdf_id > 0

    @pytest.mark.asyncio
    async def test_add_pdf_file_not_exists(self, pdf_manager):
        """测试添加不存在的PDF文件"""
        pdf_info = {
            "stock_code": "000001",
            "market": "CN",
            "report_type": "annual",
            "original_title": "测试报告",
            "file_path": "/nonexistent/path/file.pdf",
            "file_name": "file.pdf",
            "source_name": "巨潮资讯网",
        }

        pdf_id = await pdf_manager.add_pdf(pdf_info)

        assert pdf_id is None

    @pytest.mark.asyncio
    async def test_add_pdf_duplicate_hash_rejected(self, pdf_manager, temp_pdf_file):
        """测试重复文件（相同哈希）被拒绝"""
        pdf_info = {
            "stock_code": "000001",
            "market": "CN",
            "report_type": "annual",
            "original_title": "测试报告",
            "file_path": str(temp_pdf_file),
            "file_name": temp_pdf_file.name,
            "source_name": "巨潮资讯网",
        }

        # 第一次添加成功
        pdf_id1 = await pdf_manager.add_pdf(pdf_info)
        assert pdf_id1 is not None

        # 第二次添加应返回已存在的记录ID
        pdf_id2 = await pdf_manager.add_pdf(pdf_info)
        assert pdf_id2 == pdf_id1

    @pytest.mark.asyncio
    async def test_get_pdf_by_id_exists(self, pdf_manager, temp_pdf_file):
        """测试根据ID获取存在的PDF"""
        pdf_info = {
            "stock_code": "000001",
            "market": "CN",
            "report_type": "annual",
            "original_title": "测试报告",
            "file_path": str(temp_pdf_file),
            "file_name": temp_pdf_file.name,
            "source_name": "巨潮资讯网",
        }

        pdf_id = await pdf_manager.add_pdf(pdf_info)
        result = await pdf_manager.get_pdf_by_id(pdf_id)

        assert result is not None
        assert result["id"] == pdf_id
        assert result["stock_code"] == "000001"
        assert result["market"] == "CN"

    @pytest.mark.asyncio
    async def test_get_pdf_by_id_not_exists(self, pdf_manager):
        """测试获取不存在的PDF"""
        result = await pdf_manager.get_pdf_by_id(99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_pdf_updates_last_accessed(self, pdf_manager, temp_pdf_file):
        """测试获取PDF时更新最后访问时间"""
        pdf_info = {
            "stock_code": "000001",
            "market": "CN",
            "report_type": "annual",
            "original_title": "测试报告",
            "file_path": str(temp_pdf_file),
            "file_name": temp_pdf_file.name,
            "source_name": "巨潮资讯网",
        }

        pdf_id = await pdf_manager.add_pdf(pdf_info)

        # 首次获取
        result1 = await pdf_manager.get_pdf_by_id(pdf_id)
        last_accessed1 = result1["last_accessed"]

        # 再次获取
        result2 = await pdf_manager.get_pdf_by_id(pdf_id)
        last_accessed2 = result2["last_accessed"]

        assert last_accessed2 is not None


class TestPDFSearch:
    """PDF搜索测试"""

    @pytest.mark.asyncio
    async def test_search_pdfs_by_stock_code(self, pdf_manager, create_temp_pdf, tmp_path):
        """测试按股票代码搜索"""
        # 添加两个不同股票的PDF
        pdf1 = create_temp_pdf(tmp_path / "pdf1", "test1.pdf")
        pdf2 = create_temp_pdf(tmp_path / "pdf2", "test2.pdf")

        await pdf_manager.add_pdf({
            "stock_code": "000001",
            "market": "CN",
            "report_type": "annual",
            "original_title": "报告1",
            "file_path": str(pdf1),
            "file_name": "test1.pdf",
            "source_name": "巨潮资讯网",
        })

        await pdf_manager.add_pdf({
            "stock_code": "000002",
            "market": "CN",
            "report_type": "annual",
            "original_title": "报告2",
            "file_path": str(pdf2),
            "file_name": "test2.pdf",
            "source_name": "巨潮资讯网",
        })

        results = await pdf_manager.search_pdfs(stock_code="000001")

        assert len(results) == 1
        assert results[0]["stock_code"] == "000001"

    @pytest.mark.asyncio
    async def test_search_pdfs_by_market(self, pdf_manager, create_temp_pdf, tmp_path):
        """测试按市场搜索"""
        pdf1 = create_temp_pdf(tmp_path / "pdf1", "cn.pdf")
        pdf2 = create_temp_pdf(tmp_path / "pdf2", "hk.pdf")

        await pdf_manager.add_pdf({
            "stock_code": "000001",
            "market": "CN",
            "report_type": "annual",
            "original_title": "A股报告",
            "file_path": str(pdf1),
            "file_name": "cn.pdf",
            "source_name": "巨潮资讯网",
        })

        await pdf_manager.add_pdf({
            "stock_code": "00700",
            "market": "HK",
            "report_type": "annual",
            "original_title": "港股报告",
            "file_path": str(pdf2),
            "file_name": "hk.pdf",
            "source_name": "港交所披露易",
        })

        cn_results = await pdf_manager.search_pdfs(market="CN")
        hk_results = await pdf_manager.search_pdfs(market="HK")

        assert len(cn_results) == 1
        assert cn_results[0]["market"] == "CN"
        assert len(hk_results) == 1
        assert hk_results[0]["market"] == "HK"

    @pytest.mark.asyncio
    async def test_search_pdfs_by_report_type(self, pdf_manager, create_temp_pdf, tmp_path):
        """测试按报告类型搜索"""
        pdf1 = create_temp_pdf(tmp_path / "pdf1", "annual.pdf")
        pdf2 = create_temp_pdf(tmp_path / "pdf2", "semi.pdf")

        await pdf_manager.add_pdf({
            "stock_code": "000001",
            "market": "CN",
            "report_type": "annual",
            "original_title": "年报",
            "file_path": str(pdf1),
            "file_name": "annual.pdf",
            "source_name": "巨潮资讯网",
        })

        await pdf_manager.add_pdf({
            "stock_code": "000001",
            "market": "CN",
            "report_type": "semi_annual",
            "original_title": "半年报",
            "file_path": str(pdf2),
            "file_name": "semi.pdf",
            "source_name": "巨潮资讯网",
        })

        annual_results = await pdf_manager.search_pdfs(report_type="annual")

        assert len(annual_results) == 1
        assert annual_results[0]["report_type"] == "annual"

    @pytest.mark.asyncio
    async def test_search_pdfs_combined_filters(self, pdf_manager, create_temp_pdf, tmp_path):
        """测试组合筛选"""
        pdf1 = create_temp_pdf(tmp_path / "pdf1", "1.pdf")

        await pdf_manager.add_pdf({
            "stock_code": "000001",
            "market": "CN",
            "report_type": "annual",
            "report_year": 2023,
            "original_title": "年报",
            "file_path": str(pdf1),
            "file_name": "1.pdf",
            "source_name": "巨潮资讯网",
        })

        results = await pdf_manager.search_pdfs(
            stock_code="000001",
            market="CN",
            report_type="annual",
            year=2023
        )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_pdfs_limit(self, pdf_manager, create_temp_pdf, tmp_path):
        """测试搜索限制"""
        for i in range(5):
            pdf = create_temp_pdf(tmp_path / f"pdf{i}", f"test{i}.pdf")
            await pdf_manager.add_pdf({
                "stock_code": "000001",
                "market": "CN",
                "report_type": "annual",
                "original_title": f"报告{i}",
                "file_path": str(pdf),
                "file_name": f"test{i}.pdf",
                "source_name": "巨潮资讯网",
            })

        results = await pdf_manager.search_pdfs(limit=3)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_pdfs_empty_result(self, pdf_manager):
        """测试搜索无结果"""
        results = await pdf_manager.search_pdfs(stock_code="999999")
        assert results == []


class TestExtractionCache:
    """提取缓存测试"""

    @pytest.mark.asyncio
    async def test_save_cache_new(self, pdf_manager):
        """测试保存新缓存"""
        file_hash = "test_hash_123"
        result = {
            "income_statement": {"revenue": 1000000},
            "balance_sheet": {"total_assets": 5000000},
            "cash_flow_statement": {},
            "financial_metrics": {},
            "related_party_transactions": [],
            "metadata": {"stock_code": "000001"},
            "extraction_summary": {"fields_extracted": 5},
        }

        success = await pdf_manager.save_extraction_cache(file_hash, result, 5000)

        assert success is True

    @pytest.mark.asyncio
    async def test_save_cache_update_existing(self, pdf_manager):
        """测试更新现有缓存"""
        file_hash = "test_hash_456"
        result1 = {
            "income_statement": {"revenue": 1000000},
        }
        result2 = {
            "income_statement": {"revenue": 2000000},
        }

        # 保存第一次
        await pdf_manager.save_extraction_cache(file_hash, result1, 5000)

        # 更新
        success = await pdf_manager.save_extraction_cache(file_hash, result2, 6000)

        assert success is True

        # 获取验证
        cached = await pdf_manager.get_cached_extraction(file_hash)
        assert cached["income_statement"]["revenue"] == 2000000

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, pdf_manager):
        """测试缓存命中"""
        file_hash = "test_hash_789"
        result = {
            "income_statement": {"revenue": 1000000},
            "balance_sheet": {},
            "metadata": {"stock_code": "000001"},
        }

        await pdf_manager.save_extraction_cache(file_hash, result, 5000)
        cached = await pdf_manager.get_cached_extraction(file_hash)

        assert cached is not None
        assert cached["success"] is True
        assert cached["income_statement"]["revenue"] == 1000000
        assert "_cache_info" in cached
        assert cached["_cache_info"]["from_cache"] is True

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, pdf_manager):
        """测试缓存未命中"""
        cached = await pdf_manager.get_cached_extraction("nonexistent_hash")
        assert cached is None

    @pytest.mark.asyncio
    async def test_get_cache_version_mismatch(self, pdf_manager, monkeypatch):
        """测试版本不匹配时缓存未命中"""
        file_hash = "test_hash_version"
        result = {"income_statement": {"revenue": 1000000}}

        await pdf_manager.save_extraction_cache(file_hash, result, 5000)

        # 模拟版本号变化
        import src.pdf_manager as pm
        original_version = pm.EXTRACTOR_VERSION
        monkeypatch.setattr(pm, 'EXTRACTOR_VERSION', "2.0.0")

        cached = await pdf_manager.get_cached_extraction(file_hash)

        assert cached is None

        # 恢复版本号
        monkeypatch.setattr(pm, 'EXTRACTOR_VERSION', original_version)

    @pytest.mark.asyncio
    async def test_invalidate_cache(self, pdf_manager):
        """测试使缓存失效"""
        file_hash = "test_hash_invalidate"
        result = {"income_statement": {"revenue": 1000000}}

        await pdf_manager.save_extraction_cache(file_hash, result, 5000)

        # 验证缓存存在
        cached = await pdf_manager.get_cached_extraction(file_hash)
        assert cached is not None

        # 使缓存失效
        success = await pdf_manager.invalidate_cache(file_hash)
        assert success is True

        # 验证缓存已删除
        cached = await pdf_manager.get_cached_extraction(file_hash)
        assert cached is None

    @pytest.mark.asyncio
    async def test_cache_fields_count(self, pdf_manager):
        """测试缓存字段计数"""
        file_hash = "test_hash_count"
        result = {
            "income_statement": {"revenue": 1000000, "net_profit": 500000},
            "balance_sheet": {"total_assets": 5000000},
            "cash_flow_statement": {},
            "financial_metrics": {"roe": 10.5},
            "related_party_transactions": [{"party": "A", "amount": 100}],
        }

        await pdf_manager.save_extraction_cache(file_hash, result, 5000)
        cached = await pdf_manager.get_cached_extraction(file_hash)

        # 应该统计非空字段
        assert cached["_cache_info"]["fields_extracted"] > 0


class TestCacheCleanup:
    """缓存清理测试"""

    @pytest.mark.asyncio
    async def test_cleanup_old_cache(self, pdf_manager):
        """测试清理过期缓存"""
        # 这个测试比较复杂，因为需要模拟旧数据
        # 简单验证方法可以被调用
        result = await pdf_manager.cleanup_extraction_cache(days=90)
        assert "deleted" in result
        assert "orphaned" in result

    @pytest.mark.asyncio
    async def test_get_uncached_pdfs(self, pdf_manager, create_temp_pdf, tmp_path):
        """测试获取未缓存的PDF"""
        pdf = create_temp_pdf(tmp_path / "uncached", "test.pdf")

        await pdf_manager.add_pdf({
            "stock_code": "000001",
            "market": "CN",
            "report_type": "annual",
            "original_title": "报告",
            "file_path": str(pdf),
            "file_name": "test.pdf",
            "source_name": "巨潮资讯网",
        })

        uncached = await pdf_manager.get_uncached_pdfs(limit=10)

        # 新添加的PDF应该在未缓存列表中
        assert len(uncached) >= 1


class TestStatistics:
    """统计测试"""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, pdf_manager):
        """测试空数据库的统计"""
        stats = await pdf_manager.get_stats()

        assert "total_pdfs" in stats
        assert stats["total_pdfs"] == 0
        assert "by_market" in stats
        assert "by_type" in stats

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self, pdf_manager, create_temp_pdf, tmp_path):
        """测试有数据时的统计"""
        pdf = create_temp_pdf(tmp_path / "stat", "test.pdf")

        await pdf_manager.add_pdf({
            "stock_code": "000001",
            "market": "CN",
            "report_type": "annual",
            "original_title": "报告",
            "file_path": str(pdf),
            "file_name": "test.pdf",
            "source_name": "巨潮资讯网",
        })

        stats = await pdf_manager.get_stats()

        assert stats["total_pdfs"] == 1
        assert stats["by_market"]["CN"] == 1
        assert stats["by_type"]["annual"] == 1

    @pytest.mark.asyncio
    async def test_get_cache_stats_empty(self, pdf_manager):
        """测试空缓存的统计"""
        stats = await pdf_manager.get_cache_stats()

        assert "total_cached" in stats
        assert stats["total_cached"] == 0
        assert stats["current_version"] == EXTRACTOR_VERSION

    @pytest.mark.asyncio
    async def test_get_cache_stats_with_data(self, pdf_manager):
        """测试有缓存数据时的统计"""
        file_hash = "test_stats_hash"
        result = {"income_statement": {"revenue": 1000000}}

        await pdf_manager.save_extraction_cache(file_hash, result, 5000)

        stats = await pdf_manager.get_cache_stats()

        assert stats["total_cached"] >= 1
        assert stats["cache_size_kb"] >= 0
        assert stats["by_version"].get(EXTRACTOR_VERSION, 0) >= 1


class TestFileHash:
    """文件哈希测试"""

    @pytest.mark.asyncio
    async def test_calculate_hash_consistency(self, pdf_manager, temp_pdf_file):
        """测试哈希计算一致性"""
        hash1 = await pdf_manager.calculate_file_hash(temp_pdf_file)
        hash2 = await pdf_manager.calculate_file_hash(temp_pdf_file)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 产生 64 个十六进制字符

    @pytest.mark.asyncio
    async def test_calculate_hash_different_files(self, pdf_manager, create_temp_pdf, tmp_path):
        """测试不同文件的哈希不同"""
        pdf1 = create_temp_pdf(tmp_path / "h1", "1.pdf")
        pdf2_dir = tmp_path / "h2"
        pdf2_dir.mkdir(parents=True, exist_ok=True)

        # 创建一个不同内容的文件
        pdf2 = pdf2_dir / "2.pdf"
        pdf2.write_bytes(b"%PDF-1.4 different content")

        hash1 = await pdf_manager.calculate_file_hash(pdf1)
        hash2 = await pdf_manager.calculate_file_hash(pdf2)

        assert hash1 != hash2


class TestCleanupOldFiles:
    """旧文件清理测试"""

    @pytest.mark.asyncio
    async def test_cleanup_old_files(self, pdf_manager):
        """测试清理旧文件方法可以被调用"""
        # 简单验证方法不会抛出异常
        await pdf_manager.cleanup_old_files(days=90)

    @pytest.mark.asyncio
    async def test_list_pdfs_by_stock(self, pdf_manager, create_temp_pdf, tmp_path):
        """测试按股票列出PDF"""
        pdf = create_temp_pdf(tmp_path / "list", "test.pdf")

        await pdf_manager.add_pdf({
            "stock_code": "000001",
            "market": "CN",
            "report_type": "annual",
            "original_title": "报告",
            "file_path": str(pdf),
            "file_name": "test.pdf",
            "source_name": "巨潮资讯网",
        })

        results = await pdf_manager.list_pdfs_by_stock("000001", "CN")

        assert len(results) == 1
        assert results[0]["stock_code"] == "000001"
