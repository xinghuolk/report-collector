"""
备用PDF下载器
提供备用的财报下载功能
"""
import asyncio
import aiohttp
import aiofiles
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger


class BackupDownloader:
    """备用PDF下载器"""
    
    def __init__(self, download_dir: str = "downloads/backup"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
    async def search_reports(self, stock_code: str, report_type: str = 'annual', 
                           limit: int = 20) -> List[Dict[str, Any]]:
        """搜索财报 - 备用方案，返回模拟数据"""
        logger.info(f"备用搜索 {stock_code} 的 {report_type} 报告")
        
        # 返回示例数据结构，实际使用时可以替换为其他数据源
        mock_reports = [
            {
                'announcement_id': f'mock_{stock_code}_001',
                'announcement_title': f'{stock_code} 2023年年度报告',
                'stock_code': stock_code,
                'stock_name': '测试公司',
                'announcement_time': '2024-04-30',
                'pdf_url': '',  # 暂时为空
                'file_size': 0,
                'report_type': report_type,
                'year': 2023,
                'source': '备用数据源'
            }
        ]
        
        return mock_reports
        
    async def download_pdf(self, pdf_url: str, stock_code: str, 
                          announcement_title: str = "") -> Optional[str]:
        """下载PDF文件"""
        if not pdf_url:
            logger.warning("没有提供PDF URL")
            return None
            
        try:
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_title = re.sub(r'[^\w\s-]', '', announcement_title)[:50]
            filename = f"{stock_code}_{safe_title}_{timestamp}.pdf"
            filepath = self.download_dir / filename
            
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(pdf_url, timeout=30) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        if len(content) > 0:
                            async with aiofiles.open(filepath, 'wb') as f:
                                await f.write(content)
                                
                            logger.info(f"PDF下载成功: {filename}")
                            return str(filepath)
                        else:
                            logger.error("下载的文件为空")
                            return None
                    else:
                        logger.error(f"PDF下载失败: HTTP {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"下载PDF异常: {e}")
            return None
            
    async def get_latest_annual_report(self, stock_code: str) -> Optional[str]:
        """获取最新年报PDF - 备用方案"""
        logger.info(f"备用方案：尝试获取 {stock_code} 最新年报")
        
        # 对于测试，我们可以创建一个示例PDF文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{stock_code}_latest_annual_{timestamp}.txt"
        filepath = self.download_dir / filename
        
        try:
            # 创建一个文本文件作为示例
            content = f"""
这是 {stock_code} 的模拟年报文件
生成时间: {datetime.now()}
说明: 这是MCP服务器测试用的模拟文件

实际使用时，此处应该包含：
1. 真实的PDF下载逻辑
2. 多个数据源的聚合
3. 错误处理和重试机制
""".encode('utf-8')
            
            async with aiofiles.open(filepath, 'wb') as f:
                await f.write(content)
            
            logger.info(f"创建模拟报告文件: {filename}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"创建模拟文件失败: {e}")
            return None
            
    def list_downloaded_files(self, stock_code: str = None) -> List[Path]:
        """列出已下载的文件"""
        if stock_code:
            pattern = f"{stock_code}_*"
        else:
            pattern = "*"
            
        return list(self.download_dir.glob(pattern))


# 测试函数
async def main():
    downloader = BackupDownloader()
    
    # 测试搜索
    reports = await downloader.search_reports("000001", "annual")
    print(f"搜索结果: {len(reports)} 个报告")
    
    # 测试下载
    file_path = await downloader.get_latest_annual_report("000001")
    if file_path:
        print(f"生成文件: {file_path}")
    

if __name__ == "__main__":
    asyncio.run(main())