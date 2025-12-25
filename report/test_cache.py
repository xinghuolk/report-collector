"""测试财务数据提取缓存机制"""
import asyncio
import time
from pathlib import Path

# 添加src到路径
import sys
sys.path.insert(0, str(Path(__file__).parent))

from src.pdf_manager import PDFManager, EXTRACTOR_VERSION
from src.handlers.pdf_handler import PDFHandler


async def test_cache():
    """测试缓存机制"""
    # 使用已下载的测试PDF
    test_pdf = Path("/tmp/hk_extract_test/01810/2024_annual_en.pdf")

    if not test_pdf.exists():
        print(f"测试文件不存在: {test_pdf}")
        print("请先运行 test_hk_extract.py 下载测试文件")
        return

    print("=" * 60)
    print("财务数据提取缓存机制测试")
    print(f"提取器版本: {EXTRACTOR_VERSION}")
    print("=" * 60)

    # 初始化
    handler = PDFHandler()
    await handler.initialize()

    # 获取初始缓存统计
    print("\n【初始缓存统计】")
    stats = await handler.get_cache_stats()
    print(f"  总缓存数: {stats['data'].get('total_cached', 0)}")
    print(f"  当前版本: {stats['data'].get('current_version')}")

    # 第一次提取（应该没有缓存）
    print("\n【第一次提取（无缓存）】")
    start = time.time()
    result1 = await handler.extract_pdf_content(pdf_path=str(test_pdf))
    duration1 = time.time() - start

    if result1.get("success"):
        cache_info = result1.get("_cache_info", {})
        print(f"  提取成功: {result1.get('success')}")
        print(f"  来自缓存: {cache_info.get('from_cache', False)}")
        print(f"  耗时: {duration1:.2f} 秒 ({cache_info.get('extraction_duration_ms', int(duration1*1000))} ms)")
        print(f"  收入: {result1.get('income_statement', {}).get('revenue')}")
    else:
        print(f"  提取失败: {result1.get('error')}")
        return

    # 第二次提取（应该命中缓存）
    print("\n【第二次提取（应命中缓存）】")
    start = time.time()
    result2 = await handler.extract_pdf_content(pdf_path=str(test_pdf))
    duration2 = time.time() - start

    if result2.get("success"):
        cache_info = result2.get("_cache_info", {})
        print(f"  提取成功: {result2.get('success')}")
        print(f"  来自缓存: {cache_info.get('from_cache', False)}")
        print(f"  耗时: {duration2:.3f} 秒")
        print(f"  原始提取耗时: {cache_info.get('extraction_duration_ms')} ms")
        print(f"  提取器版本: {cache_info.get('extractor_version')}")
    else:
        print(f"  提取失败: {result2.get('error')}")

    # 强制刷新
    print("\n【强制刷新（忽略缓存）】")
    start = time.time()
    result3 = await handler.extract_pdf_content(pdf_path=str(test_pdf), force_refresh=True)
    duration3 = time.time() - start

    if result3.get("success"):
        cache_info = result3.get("_cache_info", {})
        print(f"  提取成功: {result3.get('success')}")
        print(f"  来自缓存: {cache_info.get('from_cache', False)}")
        print(f"  耗时: {duration3:.2f} 秒")

    # 获取最终缓存统计
    print("\n【最终缓存统计】")
    stats = await handler.get_cache_stats()
    data = stats.get('data', {})
    print(f"  总缓存数: {data.get('total_cached', 0)}")
    print(f"  缓存大小: {data.get('cache_size_kb', 0)} KB")
    print(f"  平均提取时间: {data.get('avg_extraction_time_ms', 0)} ms")
    print(f"  平均字段数: {data.get('avg_fields_extracted', 0)}")
    print(f"  版本分布: {data.get('by_version', {})}")

    # 性能对比
    print("\n【性能对比】")
    print(f"  首次提取: {duration1:.2f} 秒")
    print(f"  缓存读取: {duration2:.3f} 秒")
    if duration2 > 0:
        speedup = duration1 / duration2
        print(f"  性能提升: {speedup:.0f}x")

    print("\n测试完成!")


if __name__ == "__main__":
    asyncio.run(test_cache())
