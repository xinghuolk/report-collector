"""
港交所披露易PDF财报下载器 - MCP集成版本
香港交易所官方信息披露平台 (www.hkexnews.hk)

功能特点：
1. 支持按股票代码搜索港股财报
2. 同时下载繁体中文和英文两个版本
3. 完整的SQLite元数据管理
4. 异步下载和错误处理
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
from urllib.parse import urljoin, quote, urlencode
from loguru import logger
import json
from bs4 import BeautifulSoup


class HKEXDownloader:
    """港交所披露易财报下载器 - MCP专用版本"""

    # 港股报告分类映射
    CATEGORY_MAP = {
        'annual': ['年報', '年度報告', 'Annual Report', 'Annual Results'],
        'semi_annual': [
            '中期報告', '中期業績',
            'Interim Report', 'Interim Results',
            'Results Announcement', 'Half Year', 'Half-Year',
            'Six Months', 'Six-month', 'H1', '1H',
        ],
        'quarterly': [
            '季度報告', '季度業績', '季報', '季度成績',
            'Quarterly Report', 'Quarterly Results', 'Quarterly Update',
            '[Quarterly Results]', '[Quarterly',  # 港交所標題格式
            'First Quarter', 'Second Quarter', 'Third Quarter', 'Fourth Quarter',
            'Q1 ', 'Q2 ', 'Q3 ', 'Q4 ',
            '1Q', '2Q', '3Q', '4Q',
            'Results Announcement', 'Q1 Results', 'Q2 Results', 'Q3 Results', 'Q4 Results',
        ],
        'results': ['業績公告', '全年業績', 'Results Announcement'],
    }

    # 報告類型中英文對照
    REPORT_TYPE_NAMES = {
        'annual': {'zh': '年報', 'en': 'Annual Report'},
        'semi_annual': {'zh': '中期報告', 'en': 'Interim Report'},
        'quarterly': {'zh': '季度報告', 'en': 'Quarterly Report'},
    }

    # 市場板塊
    MARKET_MAP = {
        'sehk': '主板',      # Main Board
        'gem': '創業板',     # Growth Enterprise Market
    }

    def __init__(self, download_dir: str = "downloads/hk_stocks", db_path: str = None):
        """初始化下載器"""
        self.base_url = "https://www1.hkexnews.hk"

        # 搜索API端点
        self.search_url = "https://www1.hkexnews.hk/search/titlesearch.xhtml"

        # 公告列表JSON端點（用於獲取最新公告）
        self.announcements_url = "https://www1.hkexnews.hk/ncms/json/eds/lcisehk1relsdc_{page}.json"

        # 上市公司信息頁面
        self.company_url = "https://www1.hkexnews.hk/listedco/listconews/advancedsearch/search_active_main.aspx"

        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # 數據庫路徑
        self.db_path = db_path or self.download_dir / "hkex_reports.db"
        self.init_database()

        # 請求頭
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

        # JSON API請求頭
        self.json_headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://www1.hkexnews.hk/',
        }

        # 股票列表 API（用於獲取內部 ID）
        self.stock_list_url = "https://www1.hkexnews.hk/ncms/script/eds/activestock_sehk_c.json"

        # 股票代碼到內部 ID 的緩存
        self._stock_id_cache: Dict[str, int] = {}

        # 文件組織
        self.max_files_per_dir = 1000

    def init_database(self):
        """初始化SQLite數據庫"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # 創建報告元數據表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    _id INTEGER PRIMARY KEY AUTOINCREMENT,
                    _insert_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    _insert_location TEXT,
                    _insert_filename TEXT,
                    _file_path TEXT,
                    _file_size INTEGER,
                    _download_status TEXT DEFAULT 'pending',
                    _language TEXT,

                    -- 港交所原始字段
                    news_id TEXT,
                    stock_code TEXT,
                    stock_name TEXT,
                    title TEXT,
                    web_path TEXT UNIQUE,
                    release_time TEXT,
                    file_size TEXT,
                    market TEXT,

                    -- 索引字段
                    report_year INTEGER,
                    report_type TEXT
                )
            ''')

            # 創建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_code ON reports(stock_code)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_report_type ON reports(report_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_release_time ON reports(release_time)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_web_path ON reports(web_path)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_language ON reports(_language)')

            conn.commit()
            conn.close()
            logger.info(f"港股數據庫初始化完成: {self.db_path}")

        except Exception as e:
            logger.error(f"數據庫初始化失敗: {e}")
            raise

    def _get_download_subpath(self, stock_code: str = None, report_type: str = None,
                               stock_name: str = None) -> Path:
        """
        獲取下載子目錄（按股票代碼和報告類型組織）

        目錄結構: downloads/hk_stocks/{stock_code}/{report_type}/
        例如: downloads/hk_stocks/00700/annual/
        """
        if stock_code and report_type:
            # 標準化股票代碼為5位
            stock_code = stock_code.zfill(5)
            stock_dir = self.download_dir / stock_code
            stock_dir.mkdir(parents=True, exist_ok=True)

            # 創建股票名稱標識文件
            if stock_name:
                self._create_stock_name_file(stock_dir, stock_name)

            report_type_dir = self._normalize_report_type(report_type)
            subpath = stock_dir / report_type_dir
            subpath.mkdir(parents=True, exist_ok=True)
            return subpath
        elif stock_code:
            stock_code = stock_code.zfill(5)
            subpath = self.download_dir / stock_code
            subpath.mkdir(parents=True, exist_ok=True)
            if stock_name:
                self._create_stock_name_file(subpath, stock_name)
            return subpath
        else:
            return self.download_dir

    def _create_stock_name_file(self, stock_dir: Path, stock_name: str):
        """在股票目錄下創建名稱標識文件"""
        clean_name = re.sub(r'[<>:"/\\|?*]', '', stock_name)
        clean_name = clean_name.strip()

        if not clean_name:
            return

        # 檢查是否已有標識文件
        name_file = stock_dir / ".stock_name.txt"
        if name_file.exists():
            existing_name = name_file.read_text(encoding='utf-8').strip()
            if existing_name == clean_name:
                return

        # 寫入股票名稱
        name_file.write_text(clean_name, encoding='utf-8')
        logger.debug(f"創建股票標識文件: {name_file}")

    def _normalize_report_type(self, report_type: str) -> str:
        """標準化報告類型目錄名"""
        type_map = {
            'annual': 'annual',
            'semi_annual': 'semi_annual',
            'quarterly': 'quarterly',
            'results': 'results',
            'other': 'other'
        }
        return type_map.get(report_type, 'other')

    def _extract_period_label(self, title: str, report_type: str) -> Optional[str]:
        """從標題中提取期間標籤（用於文件名去重）

        主要用於 quarterly 報告，避免同一年 Q1/Q3 文件同名覆蓋。
        """
        if report_type != "quarterly" or not title:
            return None

        title_lower = title.lower()

        quarter_patterns = [
            ("q1", [r"\bq1\b", r"first quarter", r"第一季度", r"一季度", r"\b1q\b"]),
            ("q2", [r"\bq2\b", r"second quarter", r"第二季度", r"二季度", r"\b2q\b"]),
            ("q3", [r"\bq3\b", r"third quarter", r"第三季度", r"三季度", r"\b3q\b"]),
            ("q4", [r"\bq4\b", r"fourth quarter", r"第四季度", r"四季度", r"\b4q\b"]),
        ]

        matched_quarter: Optional[str] = None
        for quarter, patterns in quarter_patterns:
            if any(re.search(pattern, title_lower, re.IGNORECASE) for pattern in patterns):
                matched_quarter = quarter
                break

        if not matched_quarter:
            return None

        has_full_year = any(
            keyword in title_lower
            for keyword in (
                "full year",
                "全年",
                "年度",
                "annual results",
                "year ended",
            )
        )
        if matched_quarter == "q4" and has_full_year:
            return "q4_fy"

        return matched_quarter

    async def _get_stock_internal_id(self, stock_code: str) -> Optional[int]:
        """
        獲取股票的港交所內部 ID

        Args:
            stock_code: 股票代碼（如 01810, 00700）

        Returns:
            內部 ID，如果找不到返回 None
        """
        # 標準化股票代碼
        stock_code = stock_code.zfill(5)

        # 檢查緩存
        if stock_code in self._stock_id_cache:
            return self._stock_id_cache[stock_code]

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    self.stock_list_url,
                    headers=self.json_headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # 查找匹配的股票代碼
                        for item in data:
                            if item.get('c') == stock_code:
                                internal_id = item.get('i')
                                stock_name = item.get('n', '')
                                self._stock_id_cache[stock_code] = internal_id
                                logger.info(f"找到股票 {stock_code} ({stock_name}) 內部ID: {internal_id}")
                                return internal_id

                        logger.warning(f"未找到股票代碼 {stock_code} 的內部ID")
                        return None
                    else:
                        logger.error(f"獲取股票列表失敗: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"獲取股票內部ID異常: {e}")
            return None

    async def search_reports(self,
                           stock_code: str = "",
                           report_type: str = 'annual',
                           start_date: str = None,
                           end_date: str = None,
                           limit: int = 30,
                           include_both_languages: bool = True) -> List[Dict[str, Any]]:
        """
        搜索港股財報

        使用HTML表單搜索獲取結果

        Args:
            stock_code: 股票代碼（5位，如00700）
            report_type: 報告類型 (annual/semi_annual/quarterly)
            start_date: 開始日期
            end_date: 結束日期
            limit: 返回數量限制
            include_both_languages: 是否同時返回中英文版本
        """
        # 標準化股票代碼
        if stock_code:
            stock_code = stock_code.zfill(5)

        logger.info(f"搜索港股財報: 股票={stock_code}, 類型={report_type}, 限制={limit}")

        # 獲取股票內部 ID
        internal_id = None
        if stock_code:
            internal_id = await self._get_stock_internal_id(stock_code)
            if not internal_id:
                logger.warning(f"無法獲取股票 {stock_code} 的內部ID，搜索可能失敗")

        # 使用HTML搜索
        all_results = await self._search_via_html(stock_code, report_type, limit, internal_id)

        # 過濾報告類型
        filtered_results = []
        for item in all_results:
            title = item.get('title', '')
            if self._match_report_type(title, report_type):
                filtered_results.append(item)

        logger.info(f"找到 {len(filtered_results)} 個符合條件的財報")
        return filtered_results[:limit]

    async def _search_via_html(self, stock_code: str, report_type: str, limit: int, internal_id: Optional[int] = None) -> List[Dict]:
        """通過HTML搜索頁面獲取結果（只搜索英文版本）"""
        # 計算日期範圍（過去5年）
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * 5)

        # 使用內部 ID（如果有）或股票代碼
        stock_id_value = str(internal_id) if internal_id else stock_code

        results = []

        # 根據報告類型設置不同的搜索參數
        # 季度報告在港交所屬於"公告與通知"類別，不是"財務報告"類別
        if report_type == 'quarterly':
            t1code = '-1'  # 搜索所有類別
            headline = 'quarterly'  # 通過標題關鍵字過濾
        else:
            t1code = '40000'  # 財務報告類別（年報、中報）
            headline = ''

        # 只搜索英文界面，獲取英文版本
        form_data = {
            'lang': 'EN',  # 使用英文界面獲取英文版本
            'category': '0',
            'market': 'SEHK',
            'searchType': '0',
            'documentType': '-1',  # 使用 -1 獲取所有類型，後續過濾
            't1code': t1code,
            't2Gcode': '-2',
            't2code': '-2',
            'stockId': stock_id_value,
            'from': start_date.strftime('%Y%m%d'),
            'to': end_date.strftime('%Y%m%d'),
            'headline': headline,
            'searchText': '',
            'sortDir': '0',
            'sortByDate': 'desc',
        }

        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.search_url,
                    data=form_data,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Origin': 'https://www1.hkexnews.hk',
                        'Referer': 'https://www1.hkexnews.hk/search/titlesearch.xhtml',
                    }
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        results = self._parse_search_html(html, stock_code, report_type)
                        logger.info(f"搜索英文界面找到 {len(results)} 個結果")
                    else:
                        logger.warning(f"搜索請求失敗: {response.status}")

        except Exception as e:
            logger.error(f"HTML搜索異常: {e}")

        return results

    def _parse_search_html(self, html: str, stock_code: str, report_type: str) -> List[Dict]:
        """解析搜索結果HTML"""
        results = []

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # 查找結果表格
            table = soup.find('table', class_='table')
            if not table:
                # 嘗試其他方式查找
                tables = soup.find_all('table')
                for t in tables:
                    if t.find('a', href=lambda x: x and '.pdf' in x.lower() if x else False):
                        table = t
                        break

            if not table:
                logger.warning("未找到結果表格")
                return results

            # 解析表格行
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 3:
                    continue

                # 查找PDF鏈接
                link = row.find('a', href=lambda x: x and '.pdf' in x.lower() if x else False)
                if not link:
                    continue

                href = link.get('href', '')
                link_title = link.get_text(strip=True)

                # 獲取完整的headline（包含類別信息如[Quarterly Results]）
                headline_div = row.find('div', class_='headline')
                if headline_div:
                    # 獲取整個headline的文本，包括類別和鏈接文本
                    full_headline = headline_div.get_text(separator=' ', strip=True)
                    title = full_headline
                else:
                    title = link_title

                # 獲取發布日期
                date_cell = cells[0] if cells else None
                date_text = date_cell.get_text(strip=True) if date_cell else ''

                # 構建完整URL
                if href.startswith('/'):
                    pdf_url = f"{self.base_url}{href}"
                elif not href.startswith('http'):
                    pdf_url = f"{self.base_url}/{href}"
                else:
                    pdf_url = href

                # 判斷語言（更准确的检测）
                language = self._detect_language(title, href)

                # 提取年份（從標題、URL或發布時間）
                year = self._extract_year_from_title(title, href, date_text)

                results.append({
                    'stock_code': stock_code,
                    'stock_name': '',
                    'title': title,
                    'pdf_url': pdf_url,
                    'web_path': href,
                    'release_time': date_text,
                    'language': language,
                    'report_type': report_type,
                    'year': year,
                })

        except Exception as e:
            logger.error(f"解析HTML失敗: {e}")

        return results

    async def _fetch_announcements_page(self, page: int) -> List[Dict]:
        """獲取公告列表頁面"""
        url = self.announcements_url.format(page=page)

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(headers=self.json_headers, timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        # API返回格式: {"genDate": "...", "maxNumOfFile": 1, "newsInfoLst": [...]}
                        if isinstance(data, dict):
                            return data.get('newsInfoLst', [])
                        elif isinstance(data, list):
                            return data
                        else:
                            return []
                    else:
                        logger.warning(f"API請求失敗: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"獲取公告頁面異常: {e}")
            return []

    def _match_report_type(self, title: str, report_type: str) -> bool:
        """檢查標題是否匹配報告類型"""
        keywords = self.CATEGORY_MAP.get(report_type, [])
        title_lower = title.lower()

        for keyword in keywords:
            if keyword.lower() in title_lower:
                return True

        return False

    def _parse_announcement(self, item: Dict, report_type: str) -> Optional[Dict]:
        """解析公告項目"""
        try:
            # 獲取股票信息
            stocks = item.get('stock', [])
            if not stocks:
                return None

            stock = stocks[0]
            stock_code = stock.get('sc', '').zfill(5)
            stock_name = stock.get('sn', '')

            # 獲取公告信息
            title = item.get('title', '')
            web_path = item.get('webPath', '')
            news_id = item.get('newsId', '')
            release_time = item.get('relTime', '')
            file_size = item.get('size', '')
            market = item.get('market', 'SEHK')

            # 構建PDF URL
            if web_path:
                pdf_url = f"{self.base_url}{web_path}"
            else:
                return None

            # 判斷語言版本
            language = self._detect_language(title, web_path)

            # 提取年份（從標題、URL或發布時間）
            year = self._extract_year_from_title(title, web_path, release_time)

            return {
                'news_id': news_id,
                'stock_code': stock_code,
                'stock_name': stock_name,
                'title': title,
                'pdf_url': pdf_url,
                'web_path': web_path,
                'release_time': release_time,
                'file_size': file_size,
                'market': market,
                'language': language,
                'report_type': report_type,
                'year': year,
                'raw_data': item
            }

        except Exception as e:
            logger.warning(f"解析公告項目失敗: {e}")
            return None

    def _detect_language(self, title: str, web_path: str) -> str:
        """檢測文檔語言"""
        # 根據標題判斷
        if any(c in title for c in '的是在有年月日報告公司股份'):
            return 'zh'

        # 根據文件路徑判斷（通常中文版本以_c結尾）
        if '_c.' in web_path or web_path.endswith('_c.pdf'):
            return 'zh'

        # 默認英文
        return 'en'

    def _extract_year_from_title(self, title: str, url: str = None, release_time: str = None) -> Optional[int]:
        """從標題、URL或發布時間中提取年份"""
        # 優先從標題提取
        match = re.search(r'20[0-9]{2}', title)
        if match:
            return int(match.group())

        # 從URL路徑提取 (如 /sehk/2025/1118/xxx.pdf)
        if url:
            match = re.search(r'/20([0-9]{2})/', url)
            if match:
                return int('20' + match.group(1))

        # 從發布時間提取 (如 "Release Time:18/11/2025 17:25" 或 "18/11/2025")
        if release_time:
            match = re.search(r'(\d{2})/(\d{2})/(20\d{2})', release_time)
            if match:
                return int(match.group(3))

        return None

    def _get_english_url(self, chinese_url: str) -> Optional[str]:
        """從中文版URL推斷英文版URL

        港交所PDF URL規律：
        - 中文版: xxxxx_c.pdf
        - 英文版: xxxxx.pdf (去掉_c后缀)
        
        注意：中英文URL的數字編號可能不同，所以這個推導不一定准確
        """
        if not chinese_url:
            return None

        # 將 _c.pdf 去掉 _c
        if chinese_url.endswith('_c.pdf'):
            return chinese_url.replace('_c.pdf', '.pdf')
        elif '_c.' in chinese_url:
            return chinese_url.replace('_c.', '.')

        return None

    def _get_chinese_url(self, english_url: str) -> Optional[str]:
        """從英文版URL推斷中文版URL

        港交所PDF URL規律：
        - 英文版: xxxxx.pdf (不带后缀)
        - 中文版: xxxxx_c.pdf (加上_c)
        
        注意：中英文URL的數字編號可能不同，所以這個推導不一定准確
        """
        if not english_url:
            return None

        # 如果已經有 _c 後綴，不處理
        if '_c.pdf' in english_url or '_c.' in english_url:
            return None

        # 將 .pdf 替換為 _c.pdf
        if english_url.endswith('.pdf'):
            return english_url.replace('.pdf', '_c.pdf')

        return None

    async def download_pdf(self, pdf_url: str, report_data: Dict) -> Tuple[bool, str, Optional[str]]:
        """下載PDF文件"""
        if not pdf_url:
            return False, "無效的PDF URL", None

        try:
            stock_code = report_data.get('stock_code', '')
            stock_name = report_data.get('stock_name', '')
            report_type = report_data.get('report_type', 'other')
            language = report_data.get('language', 'en')
            year = report_data.get('year', datetime.now().year)
            title = report_data.get('title', '')

            # 生成文件名: {年份}_{報告類型}_{語言}.pdf
            lang_suffix = 'zh' if language == 'zh' else 'en'
            filename_parts = [str(year), report_type]
            period_label = self._extract_period_label(title, report_type)
            if period_label:
                filename_parts.append(period_label)
            filename = f"{'_'.join(filename_parts)}_{lang_suffix}.pdf"

            # 獲取下載路徑
            subpath = self._get_download_subpath(stock_code, report_type, stock_name)
            filepath = subpath / filename

            # 檢查是否已存在
            if filepath.exists():
                logger.info(f"文件已存在: {stock_code}/{report_type}/{filename}")
                return True, "文件已存在", str(filepath)

            # 下載文件
            timeout = aiohttp.ClientTimeout(total=300)
            async with aiohttp.ClientSession(headers=self.headers, timeout=timeout) as session:
                async with session.get(pdf_url) as response:
                    if response.status == 200:
                        content = await response.read()

                        # 寫入文件
                        async with aiofiles.open(filepath, 'wb') as f:
                            await f.write(content)

                        # 記錄到數據庫
                        await self._insert_to_database(report_data, str(subpath), filename, str(filepath), len(content))

                        relative_path = f"{stock_code}/{self._normalize_report_type(report_type)}/{filename}"
                        logger.info(f"PDF下載成功: {relative_path} ({len(content)} bytes)")
                        return True, "下載成功", str(filepath)
                    else:
                        logger.error(f"下載失敗: HTTP {response.status}, URL: {pdf_url}")
                        return False, f"HTTP錯誤: {response.status}", None

        except Exception as e:
            logger.error(f"下載PDF異常: {e}, URL: {pdf_url}")
            return False, f"下載異常: {str(e)}", None

    async def _insert_to_database(self, report_data: Dict, location: str, filename: str, filepath: str, file_size: int):
        """插入報告元數據到數據庫"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO reports (
                    _insert_location, _insert_filename, _file_path, _file_size,
                    _download_status, _language,
                    news_id, stock_code, stock_name, title, web_path,
                    release_time, file_size, market, report_year, report_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                location, filename, filepath, file_size, 'downloaded',
                report_data.get('language', 'en'),
                report_data.get('news_id', ''),
                report_data.get('stock_code', ''),
                report_data.get('stock_name', ''),
                report_data.get('title', ''),
                report_data.get('web_path', ''),
                report_data.get('release_time', ''),
                report_data.get('file_size', ''),
                report_data.get('market', 'SEHK'),
                report_data.get('year'),
                report_data.get('report_type', '')
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"數據庫插入失敗: {e}")

    async def download_stock_reports(self,
                                   stock_code: str,
                                   report_type: str = 'annual',
                                   max_count: int = 5,
                                   download_both_languages: bool = False) -> List[str]:
        """
        批量下載股票財報（只下載英文版本）

        Args:
            stock_code: 股票代碼
            report_type: 報告類型
            max_count: 最多下載數量
            download_both_languages: 已廢棄，保留參數以兼容性（現在只下載英文版本）
        """
        logger.info(f"開始批量下載 {stock_code} 的 {report_type} 英文報告，最多 {max_count} 個")

        # 搜索報告（只搜索英文版本）
        reports = await self.search_reports(
            stock_code=stock_code,
            report_type=report_type,
            limit=max_count * 2  # 多搜索一些作為備選
        )

        if not reports:
            logger.warning(f"未找到 {stock_code} 的 {report_type} 英文報告")
            return []

        # 只保留英文版本
        english_reports = [r for r in reports if r.get('language') == 'en']
        
        logger.info(f"找到 {len(english_reports)} 個英文財報")

        downloaded_files = []
        downloaded_count = 0

        for report in english_reports:
            if downloaded_count >= max_count:
                break

            if not report.get('pdf_url'):
                continue

            pdf_url = report.get('pdf_url')
            title = report.get('title', '')
            
            # 下載英文版本
            logger.info(f"下載英文財報: {title}")
            success, message, filepath = await self.download_pdf(pdf_url, report)
            
            if success and filepath:
                downloaded_files.append(filepath)
                downloaded_count += 1
                logger.info(f"✓ 下載成功 ({downloaded_count}/{max_count}): {Path(filepath).name}")
            else:
                logger.warning(f"✗ 下載失敗: {message}")

            # 避免請求過於頻繁
            await asyncio.sleep(2)

        logger.info(f"批量下載完成，成功下載 {len(downloaded_files)} 個英文財報")
        return downloaded_files

    async def search_by_stock_code_web(self, stock_code: str, report_type: str = 'annual',
                                       limit: int = 30) -> List[Dict[str, Any]]:
        """
        通過網頁搜索按股票代碼搜索（備用方法）

        使用披露易的標題搜索功能
        """
        stock_code = stock_code.zfill(5)

        # 獲取報告類型關鍵詞
        keywords = self.REPORT_TYPE_NAMES.get(report_type, {})
        search_term = keywords.get('zh', '年報')

        # 構建搜索URL
        params = {
            'lang': 'ZH',
            'category': '0',
            'market': 'SEHK',
            'searchType': '0',
            'documentType': '-1',
            'fromDate': '',
            'toDate': '',
            't1code': '-2',
            't2Gcode': '-2',
            'rowRange': '100',
            'stockId': stock_code,
        }

        search_url = f"{self.search_url}?{urlencode(params)}"

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(headers=self.headers, timeout=timeout) as session:
                async with session.get(search_url) as response:
                    if response.status == 200:
                        html = await response.text()
                        return self._parse_search_html(html, report_type)
                    else:
                        logger.error(f"網頁搜索失敗: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"網頁搜索異常: {e}")
            return []

    def get_downloaded_reports(self, stock_code: str = None, report_type: str = None) -> List[Dict[str, Any]]:
        """獲取已下載的報告列表"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            query = "SELECT * FROM reports WHERE _download_status = 'downloaded'"
            params = []

            if stock_code:
                query += " AND stock_code = ?"
                params.append(stock_code.zfill(5))

            if report_type:
                query += " AND report_type = ?"
                params.append(report_type)

            query += " ORDER BY release_time DESC"

            cursor.execute(query, params)
            results = cursor.fetchall()

            columns = [description[0] for description in cursor.description]
            conn.close()

            reports = []
            for row in results:
                report_dict = dict(zip(columns, row))
                reports.append(report_dict)

            return reports

        except Exception as e:
            logger.error(f"查詢已下載報告失敗: {e}")
            return []

    def get_collection_stats(self) -> Dict[str, Any]:
        """獲取收集統計信息"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM reports")
            total_reports = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM reports WHERE _download_status = 'downloaded'")
            downloaded_reports = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(_file_size) FROM reports WHERE _download_status = 'downloaded'")
            total_size = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT report_type, COUNT(*)
                FROM reports
                WHERE _download_status = 'downloaded'
                GROUP BY report_type
            """)
            by_type = dict(cursor.fetchall())

            cursor.execute("""
                SELECT _language, COUNT(*)
                FROM reports
                WHERE _download_status = 'downloaded'
                GROUP BY _language
            """)
            by_language = dict(cursor.fetchall())

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
                'by_language': by_language,
                'recent_downloads': [{'filename': r[0], 'time': r[1]} for r in recent_downloads]
            }

        except Exception as e:
            logger.error(f"獲取統計信息失敗: {e}")
            return {}

    def list_downloaded_files(self, stock_code: str = None) -> List[Path]:
        """列出已下載的文件路徑"""
        files = []

        if stock_code:
            stock_code = stock_code.zfill(5)
            stock_dir = self.download_dir / stock_code
            if stock_dir.exists():
                for pdf_file in stock_dir.rglob("*.pdf"):
                    files.append(pdf_file)
        else:
            for pdf_file in self.download_dir.rglob("*.pdf"):
                files.append(pdf_file)

        return sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)


# 測試函數
async def main():
    """測試主函數"""
    downloader = HKEXDownloader()

    print("=== 港交所披露易下載器測試 ===")

    # 測試獲取最新公告
    print("\n1. 測試獲取最新公告...")
    reports = await downloader.search_reports(
        stock_code="00700",  # 騰訊
        report_type="annual",
        limit=5
    )

    print(f"找到 {len(reports)} 個年報:")
    for report in reports:
        print(f"  - {report['title']} ({report.get('release_time', 'N/A')})")

    # 測試統計
    print("\n2. 獲取收集統計...")
    stats = downloader.get_collection_stats()
    print(f"統計信息: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
