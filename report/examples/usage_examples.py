"""
MCP财报服务器使用示例
"""
import asyncio
import json
from src.main import FinancialReportsServer


async def example_search_cn_stocks():
    """示例：搜索中国A股"""
    server = FinancialReportsServer()
    
    # 搜索平安银行
    result = await server.cn_handler.search_stocks("平安银行")
    print("搜索中国A股结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    

async def example_get_annual_reports():
    """示例：获取年报数据"""
    server = FinancialReportsServer()
    
    # 获取平安银行最近3年年报
    result = await server.cn_handler.get_annual_reports("000001", [2023, 2022, 2021])
    print("年报数据：")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:1000] + "...")


async def example_get_balance_sheet():
    """示例：获取资产负债表"""
    server = FinancialReportsServer()
    
    # 获取2023年资产负债表
    result = await server.cn_handler.get_balance_sheet("000001", 2023)
    print("资产负债表：")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:1000] + "...")


async def main():
    """运行示例"""
    print("=== 财报MCP服务器使用示例 ===\n")
    
    try:
        await example_search_cn_stocks()
        print("\n" + "="*50 + "\n")
        
        await example_get_balance_sheet()  
        print("\n" + "="*50 + "\n")
        
        await example_get_annual_reports()
        
    except Exception as e:
        print(f"示例运行失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())