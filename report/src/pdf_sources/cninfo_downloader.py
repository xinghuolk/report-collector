"""
巨潮资讯网PDF财报下载器 - 现代化MCP集成版本
中国A股官方信息披露平台 (www.cninfo.com.cn)

整合三个实现版本的优点：
1. 正确的API端点和参数结构
2. 标准化文件名格式：{YYYYMMDD}_{stock_code}_{announcement_id}_{title}.pdf  
3. 完整的SQLite元数据管理
4. 现代化异步编程和错误处理
5. 完整的报告分类系统
"""

import asyncio
import aiohttp
import aiofiles
import re
import sqlite3
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from urllib.parse import urljoin, quote
from loguru import logger
import json
from contextlib import asynccontextmanager


class CninfoDownloader:
    """巨潮资讯网财报下载器 - MCP专用版本"""
    
    # 巨潮资讯网报告分类映射（完整版本）
    CATEGORY_MAP = {
        # 定期报告
        'annual': 'category_ndbg_szsh',           # 年报
        'semi_annual': 'category_bndbg_szsh',     # 半年报  
        'quarterly_1': 'category_yjdbg_szsh',     # 一季报
        'quarterly_3': 'category_sjdbg_szsh',     # 三季报
        'quarterly': 'category_yjdbg_szsh;category_sjdbg_szsh',  # 所有季报
        'all_reports': 'category_ndbg_szsh;category_bndbg_szsh;category_yjdbg_szsh;category_sjdbg_szsh',
        
        # 公司治理
        'performance_forecast': 'category_yjygjxz_szsh',   # 业绩预告
        'equity_distribution': 'category_qyfpxzcs_szsh',   # 权益分派
        'board_meeting': 'category_dshgg_szsh',            # 董事会
        'supervisory_board': 'category_jshgg_szsh',        # 监事会
        'shareholders_meeting': 'category_gddh_szsh',      # 股东大会
        'daily_operation': 'category_rcjy_szsh',           # 日常经营
        'corporate_governance': 'category_gszl_szsh',      # 公司治理
        
        # 融资相关
        'ipo': 'category_sf_szsh',                         # 首发
        'additional_offering': 'category_zf_szsh',         # 增发
        'stock_incentive': 'category_gqjl_szsh',          # 股权激励
        'rights_issue': 'category_pg_szsh',               # 配股
        'unlock': 'category_jj_szsh',                     # 解禁
        'corporate_bonds': 'category_gszq_szsh',          # 公司债
        'convertible_bonds': 'category_kzzq_szsh',        # 可转债
        'other_financing': 'category_qtrz_szsh',          # 其他融资
        
        # 股权变动和风险
        'equity_change': 'category_gqbd_szsh',            # 股权变动
        'clarification': 'category_cqdq_szsh',            # 澄清致歉
        'risk_warning': 'category_fxts_szsh',             # 风险提示
        'special_treatment': 'category_tbclts_szsh',      # 特别处理和退市
        'delisting_period': 'category_tszlq_szsh',        # 退市整理期
    }
    
    # 交易所映射
    EXCHANGE_MAP = {
        'sz': 'sz',              # 深市
        'szmb': 'szmb',          # 深主板
        'szcy': 'szcy',          # 创业板
        'sh': 'sh',              # 沪市
        'shmb': 'shmb',          # 沪主板
        'shkcp': 'shkcp',        # 科创板
        'bj': 'bj',              # 北交所
        'all': ''                # 所有交易所
    }

    def __init__(self, download_dir: str = "downloads/cn_stocks", db_path: str = None):
        """初始化下载器"""
        self.base_url = "http://www.cninfo.com.cn"
        self.api_url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
        self.pdf_base_url = "https://static.cninfo.com.cn"  # PDF下载需要HTTPS
        
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # 数据库路径
        self.db_path = db_path or self.download_dir / "cninfo_reports.db"
        self.init_database()
        
        # API搜索请求头
        self.api_headers = {
            'Host': 'www.cninfo.com.cn',
            'Connection': 'keep-alive',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Origin': 'http://www.cninfo.com.cn',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Referer': 'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        
        # PDF下载请求头（简化版本）
        self.download_headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        
        # 文件组织：每个子目录最多1000个文件
        self.max_files_per_dir = 1000

    def init_database(self):
        """初始化SQLite数据库（基于cninfo_scraper的完整结构）"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # 创建报告元数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    _id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    _insert_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    _insert_location TEXT,
                    _insert_filename TEXT,
                    _file_path TEXT,
                    _file_size INTEGER,
                    _download_status TEXT DEFAULT 'pending',
                    _announcement_time_converted TIMESTAMP,
                    
                    -- 巨潮资讯网原始字段
                    adjunct_size TEXT,
                    adjunct_url TEXT UNIQUE,
                    announcement_content TEXT,
                    announcement_id TEXT,
                    announcement_time TEXT,
                    announcement_title TEXT,
                    announcement_type TEXT,
                    announcement_type_name TEXT,
                    associate_announcement TEXT,
                    batch_num TEXT,
                    column_id TEXT,
                    id TEXT,
                    important TEXT,
                    org_id TEXT,
                    org_name TEXT,
                    page_column TEXT,
                    sec_code TEXT,
                    sec_name TEXT,
                    storage_time TEXT,
                    
                    -- 索引字段
                    report_year INTEGER,
                    report_type TEXT,
                    exchange TEXT
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sec_code ON reports(sec_code)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_report_type ON reports(report_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_announcement_time ON reports(_announcement_time_converted)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_adjunct_url ON reports(adjunct_url)')
            
            conn.commit()
            conn.close()
            logger.info(f"数据库初始化完成: {self.db_path}")
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise

    def _get_download_subpath(self, stock_code: str = None, report_type: str = None,
                               stock_name: str = None) -> Path:
        """
        获取下载子目录（按股票代码和报告类型组织）

        目录结构: downloads/cn_stocks/{stock_code}/{report_type}/
        例如: downloads/cn_stocks/601318/annual/

        Args:
            stock_code: 股票代码
            report_type: 报告类型 (annual/semi_annual/quarterly)
            stock_name: 股票名称（用于创建标识文件）
        """
        if stock_code and report_type:
            # 新结构：按股票代码和报告类型分目录
            stock_dir = self.download_dir / stock_code
            stock_dir.mkdir(parents=True, exist_ok=True)

            # 创建股票名称标识文件
            if stock_name:
                self._create_stock_name_file(stock_dir, stock_name)

            report_type_dir = self._normalize_report_type(report_type)
            subpath = stock_dir / report_type_dir
            subpath.mkdir(parents=True, exist_ok=True)
            return subpath
        elif stock_code:
            # 只有股票代码，放在股票目录下
            subpath = self.download_dir / stock_code
            subpath.mkdir(parents=True, exist_ok=True)
            if stock_name:
                self._create_stock_name_file(subpath, stock_name)
            return subpath
        else:
            # 兼容旧逻辑：按数量分批
            subpath_list = [
                d for d in self.download_dir.iterdir()
                if d.is_dir() and d.name.isdigit()
            ]

            if subpath_list:
                latest_subpath = max(subpath_list, key=lambda x: int(x.name))
                pdf_files = list(latest_subpath.glob("*.pdf"))

                if len(pdf_files) < self.max_files_per_dir:
                    return latest_subpath

            next_num = len(subpath_list) + 1
            new_subpath = self.download_dir / f"{next_num:05d}"
            new_subpath.mkdir(exist_ok=True)
            return new_subpath

    def _create_stock_name_file(self, stock_dir: Path, stock_name: str):
        """在股票目录下创建名称标识文件"""
        # 清理股票名称
        clean_name = re.sub(r'<[^>]+>', '', stock_name)  # 去掉HTML标签
        clean_name = re.sub(r'[<>:"/\\|?*]', '', clean_name)  # 去掉非法字符
        clean_name = clean_name.strip()

        if not clean_name:
            return

        # 检查是否已有标识文件
        existing_files = list(stock_dir.glob("*.txt"))
        for f in existing_files:
            if f.stem == clean_name:
                return  # 已存在同名文件

        # 删除旧的标识文件（如果股票名称变了）
        for f in existing_files:
            if not f.name.startswith('_'):  # 保留其他txt文件
                f.unlink()

        # 创建新的标识文件
        name_file = stock_dir / f"{clean_name}.txt"
        name_file.touch()
        logger.debug(f"创建股票标识文件: {name_file}")

    def _normalize_report_type(self, report_type: str) -> str:
        """标准化报告类型目录名"""
        type_map = {
            'annual': 'annual',
            'semi_annual': 'semi_annual',
            'quarterly': 'quarterly',
            'quarterly_1': 'quarterly',
            'quarterly_3': 'quarterly',
            'other': 'other'
        }
        return type_map.get(report_type, 'other')

    def _generate_filename(self, report_data: Dict, include_stock_info: bool = False) -> str:
        """
        生成文件名

        新结构下文件名简化为: {年份}_{报告类型简称}.pdf
        例如: 2024_年度报告.pdf, 2024_Q1.pdf

        Args:
            report_data: 报告数据
            include_stock_info: 是否包含股票信息（兼容旧模式）
        """
        try:
            # 获取基础信息
            if 'stock_name' in report_data:
                company_name = report_data.get('stock_name', '')
                stock_code = report_data.get('stock_code', '')
                title = report_data.get('announcement_title', '')
                year = report_data.get('year', '')
            else:
                company_name = report_data.get('secName', '')
                stock_code = report_data.get('secCode', '')
                title = report_data.get('announcementTitle', '')
                year = self._extract_year_from_title(title)

            # 清理公司名称
            company_name = re.sub(r'<[^>]+>', '', company_name)
            company_name = re.sub(r'[\s\u3000]+', '', company_name)
            company_name = re.sub(r'[<>:"/\\|?*]', '', company_name)

            # 识别报告类型
            report_type = self._get_friendly_report_type(title)

            if include_stock_info:
                # 旧模式：包含完整信息
                if company_name and stock_code and year:
                    filename = f"{company_name}_{stock_code}_{report_type}_{year}.pdf"
                else:
                    timestamp = datetime.now().strftime('%Y%m%d')
                    filename = f"{stock_code}_{timestamp}_{report_type}.pdf"
            else:
                # 新模式：简化文件名（目录已包含股票代码和类型）
                if year:
                    filename = f"{year}_{report_type}.pdf"
                else:
                    timestamp = datetime.now().strftime('%Y%m%d')
                    filename = f"{timestamp}_{report_type}.pdf"

            # 确保文件名不会太长
            if len(filename) > 150:
                filename = filename[:150] + '.pdf'

            return filename

        except Exception as e:
            logger.warning(f"生成文件名失败: {e}")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            return f"{timestamp}.pdf"
    
    def _get_friendly_report_type(self, title: str) -> str:
        """从标题中识别友好的报告类型"""
        title = title.lower()
        
        if '年度报告摘要' in title or '年报摘要' in title:
            return '年度报告摘要'
        elif '年度报告' in title or '年报' in title:
            return '年度报告'
        elif '半年度报告摘要' in title or '中报摘要' in title:
            return '半年度报告摘要'
        elif '半年度报告' in title or '中报' in title:
            return '半年度报告'
        elif '第三季度报告' in title or '三季报' in title:
            return '第三季度报告'
        elif '第一季度报告' in title or '一季报' in title:
            return '第一季度报告'
        elif '季度报告' in title or '季报' in title:
            return '季度报告'
        elif '业绩预告' in title:
            return '业绩预告'
        elif '业绩快报' in title:
            return '业绩快报'
        elif '临时公告' in title:
            return '临时公告'
        else:
            return '其他公告'

    async def search_reports(self,
                           stock_code: str = "",
                           company_name: str = "",
                           report_type: str = 'annual',
                           start_date: str = None,
                           end_date: str = None,
                           exchange: str = 'all',
                           limit: int = 30,
                           page_num: int = 1,
                           exclude_summary: bool = True) -> List[Dict[str, Any]]:
        """搜索财报 - 支持股票代码和公司名称搜索

        Args:
            stock_code: 股票代码
            company_name: 公司名称
            report_type: 报告类型
            start_date: 开始日期
            end_date: 结束日期
            exchange: 交易所
            limit: 返回数量限制
            page_num: 页码
            exclude_summary: 是否排除摘要版本（默认True，只返回完整报告）
        """
        
        # 设置默认日期范围
        if not start_date:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=3*365)  # 默认3年
            start_date = start_dt.strftime('%Y-%m-%d')
            end_date = end_dt.strftime('%Y-%m-%d')
        elif not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        # 确定searchkey - 优先使用公司名称，其次股票代码
        search_key = ""
        if company_name:
            search_key = company_name
            logger.info(f"使用公司名称搜索: {company_name}")
        elif stock_code:
            search_key = stock_code
            logger.info(f"使用股票代码搜索: {stock_code}")
        
        # 自动检测交易所
        detected_exchange = exchange
        if exchange == 'all' and stock_code:
            if stock_code.startswith(('600', '601', '603', '605', '688')):
                detected_exchange = 'sse'  # 沪市
            elif stock_code.startswith(('000', '002', '300')):
                detected_exchange = 'szse'  # 深市
            elif stock_code.startswith(('43', '83', '87')):
                detected_exchange = 'bj'   # 北交所

        # 构建请求参数
        params = {
            "pageNum": str(page_num),
            "pageSize": str(limit),
            "column": detected_exchange if detected_exchange != 'all' else 'szse',
            "tabName": "fulltext",
            "searchkey": search_key,  # 关键！使用searchkey进行精确搜索
            "category": self.CATEGORY_MAP.get(report_type, self.CATEGORY_MAP['annual']),
            "seDate": f"{start_date}~{end_date}",
            "sortName": "time",
            "sortType": "desc",
            "isHLtitle": "true"
        }

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(headers=self.api_headers, timeout=timeout) as session:
                async with session.post(self.api_url, data=params) as response:
                    logger.info(f"巨潮资讯网API请求: {response.status}, searchkey: '{search_key}', 交易所: {detected_exchange}")
                    
                    if response.status == 200:
                        data = await response.json()
                        total_records = data.get('totalRecordNum', 0)
                        logger.info(f"API响应: 找到 {total_records} 条记录")
                        logger.debug(f"完整响应: {data}")
                        return self._parse_search_results(data, report_type, exclude_summary)
                    else:
                        logger.error(f"API请求失败: {response.status}, 参数: {params}")
                        return []
                        
        except Exception as e:
            logger.error(f"搜索请求异常: {e}")
            return []

    def _parse_search_results(self, data: Dict, requested_type: str,
                               exclude_summary: bool = True) -> List[Dict[str, Any]]:
        """解析搜索结果

        Args:
            data: API响应数据
            requested_type: 请求的报告类型
            exclude_summary: 是否排除摘要版本
        """
        results = []

        # 处理None值和空列表
        announcements = data.get('announcements')
        if not announcements:
            logger.warning(f"响应中announcements为空: {announcements}, 总公告数: {data.get('totalAnnouncement', 0)}")
            return results
        logger.info(f"找到 {len(announcements)} 个公告")
        
        for item in announcements:
            try:
                title = item.get('announcementTitle', '')

                # 过滤摘要版本
                if exclude_summary and self._is_summary_report(title):
                    logger.debug(f"跳过摘要版本: {title}")
                    continue

                # 转换时间戳
                timestamp = int(item['announcementTime']) / 1000
                announcement_date = datetime.fromtimestamp(timestamp)

                result = {
                    'announcement_id': item.get('announcementId', ''),
                    'announcement_title': item.get('announcementTitle', ''),
                    'stock_code': item.get('secCode', ''),
                    'stock_name': item.get('secName', ''),
                    'announcement_time': item.get('announcementTime', ''),
                    'announcement_date': announcement_date.strftime('%Y-%m-%d'),
                    'pdf_url': '',
                    'adjunct_url': item.get('adjunctUrl', ''),
                    'file_size': int(item.get('adjunctSize', 0)),
                    'report_type': self._classify_report_type(item.get('announcementTitle', '')),
                    'year': self._extract_year_from_title(item.get('announcementTitle', '')),
                    'exchange': self._detect_exchange(item.get('secCode', '')),
                    'raw_data': item
                }
                
                # 构建PDF下载URL
                if item.get('adjunctUrl'):
                    result['pdf_url'] = f"{self.pdf_base_url}/{item['adjunctUrl']}"
                
                results.append(result)
                
            except Exception as e:
                logger.warning(f"解析公告项失败: {e}, 数据: {item}")
                continue
        
        logger.info(f"成功解析 {len(results)} 个报告")
        return results

    def _is_summary_report(self, title: str) -> bool:
        """判断是否为摘要版本报告

        摘要版本通常包含简化的财务数据，缺少详细的资产负债表明细、
        关联交易等信息。完整报告才包含全部财务数据。

        Args:
            title: 报告标题

        Returns:
            True如果是摘要版本，False如果是完整报告
        """
        summary_keywords = [
            '摘要',           # 年度报告摘要、半年度报告摘要
            '提要',           # 报告提要
            '正文的公告',      # "发布xxx正文的公告"
            '更正公告',        # 更正公告
            '补充公告',        # 补充公告
            '修订说明',        # 修订说明
            '英文版',          # 英文版本
            'English',        # 英文版本
            '已取消',          # 已取消的公告
        ]

        title_lower = title.lower()
        for keyword in summary_keywords:
            if keyword.lower() in title_lower:
                return True

        return False

    def _classify_report_type(self, title: str) -> str:
        """根据标题智能分类报告类型"""
        title_lower = title.lower()
        
        # 年报
        if any(keyword in title for keyword in ['年度报告', '年报', 'annual report']):
            return 'annual'
        # 半年报    
        elif any(keyword in title for keyword in ['半年度报告', '半年报', '中报', 'semi-annual']):
            return 'semi_annual'
        # 一季报
        elif any(keyword in title for keyword in ['第一季度报告', '一季度报告', '一季报', 'first quarter']):
            return 'quarterly_1'
        # 三季报
        elif any(keyword in title for keyword in ['第三季度报告', '三季度报告', '三季报', 'third quarter']):
            return 'quarterly_3'
        # 其他季报
        elif any(keyword in title for keyword in ['季度报告', '季报', 'quarterly']):
            return 'quarterly'
        else:
            return 'other'

    def _extract_year_from_title(self, title: str) -> Optional[int]:
        """从标题中提取年份"""
        # 匹配2000-2099年份
        match = re.search(r'20[0-9]{2}', title)
        return int(match.group()) if match else None

    def _detect_exchange(self, stock_code: str) -> str:
        """根据股票代码检测交易所"""
        if not stock_code:
            return 'unknown'
        
        code = stock_code[:3]
        if code in ['000', '001', '002', '003']:
            return 'sz'  # 深市主板
        elif code in ['300']:
            return 'szcy'  # 创业板
        elif code in ['600', '601', '603', '605']:
            return 'sh'  # 沪市主板
        elif code in ['688']:
            return 'shkcp'  # 科创板
        elif code in ['430', '831', '832', '833', '834', '835', '836', '837', '838', '839']:
            return 'bj'  # 北交所
        else:
            return 'unknown'

    async def download_pdf(self, pdf_url: str, report_data: Dict) -> Tuple[bool, str, Optional[str]]:
        """下载PDF文件"""
        if not pdf_url or not report_data.get('adjunctUrl'):
            return False, "无效的PDF URL", None

        try:
            # 获取股票代码、名称和报告类型
            stock_code = report_data.get('stock_code', report_data.get('secCode', ''))
            stock_name = report_data.get('stock_name', report_data.get('secName', ''))
            report_type = report_data.get('report_type', self._classify_report_type(
                report_data.get('announcement_title', report_data.get('announcementTitle', ''))
            ))

            # 生成文件名和路径（使用新目录结构，并创建名称标识文件）
            subpath = self._get_download_subpath(stock_code, report_type, stock_name)
            filename = self._generate_filename(report_data, include_stock_info=False)
            filepath = subpath / filename

            # 检查是否已存在
            if filepath.exists():
                logger.info(f"文件已存在: {stock_code}/{report_type}/{filename}")
                return True, "文件已存在", str(filepath)

            # 下载文件
            timeout = aiohttp.ClientTimeout(total=300)  # 5分钟超时
            async with aiohttp.ClientSession(headers=self.download_headers, timeout=timeout) as session:
                async with session.get(pdf_url) as response:
                    if response.status == 200:
                        content = await response.read()

                        # 写入文件
                        async with aiofiles.open(filepath, 'wb') as f:
                            await f.write(content)

                        # 记录到数据库
                        await self._insert_to_database(report_data, str(subpath), filename, str(filepath), len(content))

                        # 日志显示完整路径结构
                        relative_path = f"{stock_code}/{self._normalize_report_type(report_type)}/{filename}"
                        logger.info(f"PDF下载成功: {relative_path} ({len(content)} bytes)")
                        return True, "下载成功", str(filepath)
                    else:
                        logger.error(f"下载失败: HTTP {response.status}, URL: {pdf_url}")
                        return False, f"HTTP错误: {response.status}", None

        except Exception as e:
            logger.error(f"下载PDF异常: {e}, URL: {pdf_url}")
            return False, f"下载异常: {str(e)}", None

    async def _insert_to_database(self, report_data: Dict, location: str, filename: str, filepath: str, file_size: int):
        """插入报告元数据到数据库"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # 转换时间戳
            timestamp = int(report_data['announcementTime']) / 1000
            announcement_date = datetime.fromtimestamp(timestamp)
            
            # 插入数据
            cursor.execute('''
                INSERT OR REPLACE INTO reports (
                    _insert_location, _insert_filename, _file_path, _file_size,
                    _download_status, _announcement_time_converted,
                    adjunct_size, adjunct_url, announcement_content, announcement_id,
                    announcement_time, announcement_title, announcement_type, announcement_type_name,
                    associate_announcement, batch_num, column_id, id, important,
                    org_id, org_name, page_column, sec_code, sec_name, storage_time,
                    report_year, report_type, exchange
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                location, filename, filepath, file_size, 'downloaded', announcement_date,
                report_data.get('adjunctSize', ''), report_data.get('adjunctUrl', ''),
                report_data.get('announcementContent', ''), report_data.get('announcementId', ''),
                report_data.get('announcementTime', ''), report_data.get('announcementTitle', ''),
                report_data.get('announcementType', ''), report_data.get('announcementTypeName', ''),
                report_data.get('associateAnnouncement', ''), report_data.get('batchNum', ''),
                report_data.get('columnId', ''), report_data.get('id', ''), report_data.get('important', ''),
                report_data.get('orgId', ''), report_data.get('orgName', ''), report_data.get('pageColumn', ''),
                report_data.get('secCode', ''), report_data.get('secName', ''), report_data.get('storageTime', ''),
                self._extract_year_from_title(report_data.get('announcementTitle', '')),
                self._classify_report_type(report_data.get('announcementTitle', '')),
                self._detect_exchange(report_data.get('secCode', ''))
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"数据库插入失败: {e}")

    async def download_stock_reports(self, 
                                   stock_code: str,
                                   report_type: str = 'annual',
                                   max_count: int = 5,
                                   start_date: str = None,
                                   end_date: str = None) -> List[str]:
        """批量下载股票财报"""
        logger.info(f"开始批量下载 {stock_code} 的 {report_type} 报告，最多 {max_count} 个")
        
        # 搜索报告
        reports = await self.search_reports(
            stock_code=stock_code,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            limit=max_count
        )
        
        if not reports:
            logger.warning(f"未找到 {stock_code} 的 {report_type} 报告")
            return []

        downloaded_files = []
        
        for i, report in enumerate(reports[:max_count]):
            if not report['pdf_url']:
                logger.warning(f"跳过无PDF链接的报告: {report['announcement_title']}")
                continue
            
            logger.info(f"下载进度: {i+1}/{min(len(reports), max_count)} - {report['announcement_title']}")
            
            success, message, filepath = await self.download_pdf(report['pdf_url'], report['raw_data'])
            
            if success and filepath:
                downloaded_files.append(filepath)
                logger.info(f"✓ 下载成功: {Path(filepath).name}")
            else:
                logger.warning(f"✗ 下载失败: {message}")
            
            # 避免请求过于频繁
            if i < len(reports) - 1:
                await asyncio.sleep(2)

        logger.info(f"批量下载完成，成功下载 {len(downloaded_files)} 个文件")
        return downloaded_files

    def get_downloaded_reports(self, stock_code: str = None, report_type: str = None) -> List[Dict[str, Any]]:
        """获取已下载的报告列表"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            query = "SELECT * FROM reports WHERE _download_status = 'downloaded'"
            params = []
            
            if stock_code:
                query += " AND sec_code = ?"
                params.append(stock_code)
                
            if report_type:
                query += " AND report_type = ?"
                params.append(report_type)
                
            query += " ORDER BY _announcement_time_converted DESC"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            
            # 获取列名
            columns = [description[0] for description in cursor.description]
            
            # 转换为字典列表
            reports = []
            for row in results:
                report_dict = dict(zip(columns, row))
                reports.append(report_dict)
                
            return reports
            
        except Exception as e:
            logger.error(f"查询已下载报告失败: {e}")
            return []

    def get_collection_stats(self) -> Dict[str, Any]:
        """获取收集统计信息"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # 总体统计
            cursor.execute("SELECT COUNT(*) FROM reports")
            total_reports = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM reports WHERE _download_status = 'downloaded'")
            downloaded_reports = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(_file_size) FROM reports WHERE _download_status = 'downloaded'")
            total_size = cursor.fetchone()[0] or 0
            
            # 按类型统计
            cursor.execute("""
                SELECT report_type, COUNT(*) 
                FROM reports 
                WHERE _download_status = 'downloaded' 
                GROUP BY report_type
            """)
            by_type = dict(cursor.fetchall())
            
            # 按交易所统计
            cursor.execute("""
                SELECT exchange, COUNT(*) 
                FROM reports 
                WHERE _download_status = 'downloaded' 
                GROUP BY exchange
            """)
            by_exchange = dict(cursor.fetchall())
            
            # 最近下载
            cursor.execute("""
                SELECT _insert_filename, _insert_time 
                FROM reports 
                WHERE _download_status = 'downloaded' 
                ORDER BY _insert_time DESC 
                LIMIT 5
            """)
            recent_downloads = cursor.fetchall()
            
            conn.close()
            
            return {
                'total_reports': total_reports,
                'downloaded_reports': downloaded_reports,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'by_type': by_type,
                'by_exchange': by_exchange,
                'recent_downloads': [{'filename': r[0], 'time': r[1]} for r in recent_downloads]
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}

    def cleanup_old_files(self, days: int = 90) -> int:
        """清理旧文件"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        cleaned_count = 0
        
        try:
            # 清理文件系统中的旧文件
            for pdf_file in self.download_dir.rglob("*.pdf"):
                if pdf_file.stat().st_mtime < cutoff_time:
                    pdf_file.unlink()
                    cleaned_count += 1
                    logger.info(f"清理旧文件: {pdf_file.name}")
            
            # 清理数据库中的相关记录
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM reports 
                WHERE _insert_time < datetime('now', '-{} days')
                AND _download_status = 'downloaded'
            """.format(days))
            conn.commit()
            conn.close()
            
            logger.info(f"清理完成，删除了 {cleaned_count} 个旧文件")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理旧文件失败: {e}")
            return 0

    def list_downloaded_files(self, stock_code: str = None) -> List[Path]:
        """列出已下载的文件路径"""
        files = []
        
        if stock_code:
            pattern = f"*_{stock_code}_*.pdf"
        else:
            pattern = "*.pdf"
            
        for pdf_file in self.download_dir.rglob(pattern):
            files.append(pdf_file)
        
        return sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)


# 使用示例和测试
async def main():
    """测试主函数"""
    downloader = CninfoDownloader()
    
    print("=== 巨潮资讯网下载器测试 ===")
    
    # 测试搜索 - 搜索更早期的年报（2023年）
    print("\n1. 测试搜索2023年年报...")
    reports = await downloader.search_reports("", "annual", 
                                             start_date="2023-03-01", 
                                             end_date="2023-05-31", 
                                             limit=5)
    print(f"找到 {len(reports)} 个年报:")
    for report in reports:
        print(f"  - {report['announcement_title']} ({report['announcement_date']})")
    
    # 测试下载前几个年报，看看哪些能下载成功
    print("\n2. 测试下载前3个年报...")
    for i, report in enumerate(reports[:3]):
        print(f"\n尝试下载 {i+1}: {report['announcement_title']}")
        print(f"股票: {report['stock_code']} {report['stock_name']}")
        print(f"PDF URL: {report['pdf_url']}")
        
        success, message, filepath = await downloader.download_pdf(
            report['pdf_url'], report['raw_data']
        )
        print(f"下载结果: {success}, {message}")
        if filepath:
            print(f"文件路径: {filepath}")
        
        # 避免请求过于频繁
        if i < 2:
            await asyncio.sleep(1)
    
    # 测试统计
    print("\n3. 获取收集统计...")
    stats = downloader.get_collection_stats()
    print(f"统计信息: {stats}")


if __name__ == "__main__":
    asyncio.run(main())