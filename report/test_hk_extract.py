"""测试港股财报内容提取"""
import asyncio
from pathlib import Path
import aiohttp

# 添加src到路径
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pdf_parser.content_extractor import PDFContentExtractor


async def download_pdf(url: str, save_path: Path) -> bool:
    """下载PDF文件"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    save_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(save_path, 'wb') as f:
                        f.write(content)
                    print(f"下载成功: {save_path} ({len(content) / 1024 / 1024:.2f} MB)")
                    return True
                else:
                    print(f"下载失败: {resp.status}")
                    return False
    except Exception as e:
        print(f"下载异常: {e}")
        return False


async def test_extract():
    """测试小米2024年报提取"""
    # 小米2024年报 - 英文版
    pdf_url = "https://www.hkexnews.hk/listedco/listconews/sehk/2025/0424/2025042401119.pdf"
    pdf_path = Path("/tmp/hk_extract_test/01810/2024_annual_en.pdf")

    # 下载
    print("=" * 60)
    print("下载小米2024年报(英文版)...")
    print(f"URL: {pdf_url}")
    print("=" * 60)

    if not pdf_path.exists():
        success = await download_pdf(pdf_url, pdf_path)
        if not success:
            return
    else:
        print(f"文件已存在: {pdf_path}")

    # 提取内容
    print("\n" + "=" * 60)
    print("提取财务数据...")
    print("=" * 60)

    extractor = PDFContentExtractor()
    result = extractor.extract(str(pdf_path))

    if not result.get("success"):
        print(f"提取失败: {result.get('error')}")
        return

    # 打印提取结果
    print("\n【元数据】")
    metadata = result.get("metadata", {})
    print(f"  股票代码: {metadata.get('stock_code')}")
    print(f"  股票名称: {metadata.get('stock_name')}")
    print(f"  报告类型: {metadata.get('report_type')}")
    print(f"  报告期间: {metadata.get('report_period')}")
    print(f"  总页数: {metadata.get('total_pages')}")

    print("\n【利润表】")
    income = result.get("income_statement", {})
    for key, value in income.items():
        if value is not None:
            if isinstance(value, float) and abs(value) > 1000:
                print(f"  {key}: {value:,.0f}")
            else:
                print(f"  {key}: {value}")

    print("\n【资产负债表】")
    balance = result.get("balance_sheet", {})
    for key, value in balance.items():
        if value is not None:
            if isinstance(value, float) and abs(value) > 1000:
                print(f"  {key}: {value:,.0f}")
            else:
                print(f"  {key}: {value}")

    print("\n【现金流量表】")
    cashflow = result.get("cash_flow_statement", {})
    for key, value in cashflow.items():
        if value is not None:
            if isinstance(value, float) and abs(value) > 1000:
                print(f"  {key}: {value:,.0f}")
            else:
                print(f"  {key}: {value}")

    print("\n【财务指标】")
    metrics = result.get("financial_metrics", {})
    for key, value in metrics.items():
        if value is not None:
            print(f"  {key}: {value}")

    print("\n【提取摘要】")
    summary = result.get("extraction_summary", {})
    print(f"  表格数: {summary.get('total_tables_found')}")
    print(f"  文本长度: {summary.get('text_length')}")
    print(f"  提取字段数: {summary.get('fields_extracted')}")

    # 保存完整结果
    import json
    output_file = Path("/tmp/hk_extract_test/01810_extract_result.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n完整结果已保存: {output_file}")


if __name__ == "__main__":
    asyncio.run(test_extract())
