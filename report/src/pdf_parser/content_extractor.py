"""
PDF财报内容提取器
从财报PDF中提取结构化财务数据
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from decimal import Decimal
import pdfplumber
from pypdf import PdfReader
from loguru import logger


@dataclass
class IncomeStatement:
    """利润表数据"""
    revenue: Optional[float] = None                    # 营业收入
    operating_cost: Optional[float] = None             # 营业成本
    gross_profit: Optional[float] = None               # 毛利润
    operating_profit: Optional[float] = None           # 营业利润
    total_profit: Optional[float] = None               # 利润总额（税前利润）
    net_profit: Optional[float] = None                 # 净利润
    net_profit_deducted: Optional[float] = None        # 扣非净利润
    interest_expense: Optional[float] = None           # 财务费用/利息支出
    rd_expense: Optional[float] = None                 # 研发费用
    # 利润率指标
    gross_margin: Optional[float] = None               # 毛利率(%)
    net_margin: Optional[float] = None                 # 净利率(%)


@dataclass
class BalanceSheet:
    """资产负债表数据"""
    # 资产
    total_assets: Optional[float] = None               # 总资产
    current_assets: Optional[float] = None             # 流动资产
    cash_and_equivalents: Optional[float] = None       # 货币资金
    accounts_receivable: Optional[float] = None        # 应收账款
    inventory: Optional[float] = None                  # 存货
    fixed_assets: Optional[float] = None               # 固定资产
    goodwill: Optional[float] = None                   # 商誉
    intangible_assets: Optional[float] = None          # 无形资产
    # 负债
    total_liabilities: Optional[float] = None          # 总负债
    current_liabilities: Optional[float] = None        # 流动负债
    short_term_debt: Optional[float] = None            # 短期借款
    long_term_debt: Optional[float] = None             # 长期借款
    bonds_payable: Optional[float] = None              # 应付债券
    # 权益
    total_equity: Optional[float] = None               # 股东权益


@dataclass
class CashFlowStatement:
    """现金流量表数据"""
    operating_cash_flow: Optional[float] = None        # 经营活动现金流净额
    investing_cash_flow: Optional[float] = None        # 投资活动现金流净额
    financing_cash_flow: Optional[float] = None        # 筹资活动现金流净额
    capital_expenditure: Optional[float] = None        # 资本支出（购建固定资产等）
    free_cash_flow: Optional[float] = None             # 自由现金流


@dataclass
class FinancialMetrics:
    """主要财务指标"""
    # 每股指标
    eps: Optional[float] = None                        # 基本每股收益
    eps_diluted: Optional[float] = None                # 稀释每股收益
    bps: Optional[float] = None                        # 每股净资产
    dividend_per_share: Optional[float] = None         # 每股股息
    # 盈利能力
    roe: Optional[float] = None                        # 净资产收益率(%)
    roa: Optional[float] = None                        # 总资产收益率(%)
    # 偿债能力
    debt_ratio: Optional[float] = None                 # 资产负债率(%)
    current_ratio: Optional[float] = None              # 流动比率
    quick_ratio: Optional[float] = None                # 速动比率
    # 股本
    total_shares: Optional[float] = None               # 总股本


@dataclass
class RelatedPartyTransactions:
    """关联交易数据"""
    total_sales: Optional[float] = None                # 向关联方销售商品/提供劳务金额
    total_purchases: Optional[float] = None            # 向关联方采购商品/接受劳务金额
    total_receivables: Optional[float] = None          # 应收关联方款项
    total_payables: Optional[float] = None             # 应付关联方款项
    total_loans: Optional[float] = None                # 关联方借款
    total_guarantees: Optional[float] = None           # 关联方担保
    transactions_list: Optional[List[Dict]] = None     # 关联交易明细列表


@dataclass
class ReportMetadata:
    """报告元数据"""
    title: Optional[str] = None
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    report_period: Optional[str] = None                # 报告期 如 2024年年度
    report_type: Optional[str] = None                  # annual/semi_annual/quarterly
    total_pages: int = 0
    file_size: int = 0


class PDFContentExtractor:
    """PDF财报内容提取器"""

    # 财务数据正则模式（中文）
    PATTERNS = {
        # 利润表项目
        'revenue': [
            r'营业总?收入[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'一、营业总?收入[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'营业收入\s+([0-9,，]+\.?[0-9]*)',
        ],
        'operating_cost': [
            r'营业成本[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'营业总成本[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'二、营业成本[：:\s]*([0-9,，]+\.?[0-9]*)',
        ],
        'gross_profit': [
            r'毛利(?:润)?[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'营业毛利[：:\s]*([0-9,，-]+\.?[0-9]*)',
        ],
        'operating_profit': [
            r'营业利润[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'三、营业利润[：:\s]*([0-9,，-]+\.?[0-9]*)',
        ],
        'total_profit': [
            r'利润总额[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'四、利润总额[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'税前利润[：:\s]*([0-9,，-]+\.?[0-9]*)',
        ],
        'net_profit': [
            r'(?:归属于母公司|归母)(?:股东的?)?净利润[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'净利润[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'归属于上市公司股东的净利润\s+([0-9,，-]+\.?[0-9]*)',
        ],
        'net_profit_deducted': [
            r'扣除非经常性损益(?:后)?(?:的)?(?:归属于母公司)?(?:股东的?)?净利润[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'扣非净利润[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'扣除非经常性损益后的净利润\s+([0-9,，-]+\.?[0-9]*)',
        ],
        'interest_expense': [
            r'财务费用[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'利息费用[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'利息支出[：:\s]*([0-9,，-]+\.?[0-9]*)',
        ],
        'rd_expense': [
            r'研发费用[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'研发支出[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'研究开发费用[：:\s]*([0-9,，-]+\.?[0-9]*)',
        ],

        # 资产负债表项目
        'total_assets': [
            r'资产总计[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'总资产[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'资产合计\s+([0-9,，]+\.?[0-9]*)',
        ],
        'current_assets': [
            r'流动资产(?:合)?计[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'流动资产总计[：:\s]*([0-9,，]+\.?[0-9]*)',
        ],
        'total_liabilities': [
            r'负债(?:合)?计[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'总负债[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'负债总计\s+([0-9,，]+\.?[0-9]*)',
        ],
        'current_liabilities': [
            r'流动负债(?:合)?计[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'流动负债总计[：:\s]*([0-9,，]+\.?[0-9]*)',
        ],
        'total_equity': [
            r'(?:股东权益|所有者权益)(?:合)?计[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'归属于母公司(?:股东)?(?:的)?(?:所有者)?权益[：:\s]*([0-9,，]+\.?[0-9]*)',
        ],
        'cash_and_equivalents': [
            r'货币资金[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'现金及现金等价物[：:\s]*([0-9,，]+\.?[0-9]*)',
        ],
        'accounts_receivable': [
            r'应收账款[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'应收票据及应收账款[：:\s]*([0-9,，]+\.?[0-9]*)',
        ],
        'inventory': [
            r'存货[：:\s]*([0-9,，]+\.?[0-9]*)',
        ],
        'fixed_assets': [
            r'固定资产[：:\s]*([0-9,，]+\.?[0-9]*)',
        ],
        'short_term_debt': [
            r'短期借款[：:\s]*([0-9,，]+\.?[0-9]*)',
        ],
        'long_term_debt': [
            r'长期借款[：:\s]*([0-9,，]+\.?[0-9]*)',
        ],
        'bonds_payable': [
            r'应付债券[：:\s]*([0-9,，]+\.?[0-9]*)',
        ],
        'goodwill': [
            r'商誉[：:\s]*([0-9,，]+\.?[0-9]*)',
        ],
        'intangible_assets': [
            r'无形资产[：:\s]*([0-9,，]+\.?[0-9]*)',
        ],

        # 现金流量表项目
        'operating_cash_flow': [
            r'经营活动产生的现金流量净额[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'经营活动现金流量净额[：:\s]*([0-9,，-]+\.?[0-9]*)',
        ],
        'investing_cash_flow': [
            r'投资活动产生的现金流量净额[：:\s]*([0-9,，-]+\.?[0-9]*)',
        ],
        'financing_cash_flow': [
            r'筹资活动产生的现金流量净额[：:\s]*([0-9,，-]+\.?[0-9]*)',
        ],
        'capital_expenditure': [
            r'购建固定资产、无形资产和其他长期资产支付的现金[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'购建固定资产.*?支付.*?现金[：:\s]*([0-9,，]+\.?[0-9]*)',
        ],

        # 财务指标
        'eps': [
            r'基本每股收益[（\(]?元/?股?[）\)]?[：:\s]*([0-9,，.-]+)',
            r'每股收益[（\(]?元/?股?[）\)]?[：:\s]*([0-9,，.-]+)',
        ],
        'eps_diluted': [
            r'稀释每股收益[（\(]?元/?股?[）\)]?[：:\s]*([0-9,，.-]+)',
        ],
        'bps': [
            r'每股净资产[（\(]?元/?股?[）\)]?[：:\s]*([0-9,，.]+)',
            r'归属于.*?每股净资产[：:\s]*([0-9,，.]+)',
        ],
        'dividend_per_share': [
            r'每股(?:现金)?股利[（\(]?元/?股?[）\)]?[：:\s]*([0-9,，.]+)',
            r'每股派息[（\(]?元/?股?[）\)]?[：:\s]*([0-9,，.]+)',
            r'每股分红[（\(]?元/?股?[）\)]?[：:\s]*([0-9,，.]+)',
        ],
        'roe': [
            r'(?:加权平均)?净资产收益率[（\(]?%?[）\)]?[：:\s]*([0-9,，.]+)',
            r'(?:加权平均)?ROE[（\(]?%?[）\)]?[：:\s]*([0-9,，.]+)',
        ],
        'current_ratio': [
            r'流动比率[（\(]?%?[）\)]?[：:\s]*([0-9,，.]+)',
        ],
        'quick_ratio': [
            r'速动比率[（\(]?%?[）\)]?[：:\s]*([0-9,，.]+)',
        ],
    }

    # 英文财报正则模式（用于港股英文财报）
    PATTERNS_EN = {
        # Income Statement
        'revenue': [
            r'(?:Total\s+)?Revenue[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'(?:Operating\s+)?Revenue[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'Turnover[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'Sales[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'operating_cost': [
            # 优先匹配千元表格格式（无小数点，数值较大）
            r'Cost\s+of\s+[Ss]ales\s+([0-9,]{10,})',
            r'Cost\s+of\s+[Ss]ales\s*\(?([0-9,]+(?:\.[0-9]+)?)\)?',
            r'Cost\s+of\s+(?:Revenue|Goods\s+Sold)[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'Total\s+cost\s+of\s+sales\s+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'gross_profit': [
            r'Gross\s+Profit[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
        ],
        'operating_profit': [
            r'Operating\s+Profit[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
            r'Profit\s+from\s+Operations[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
        ],
        'total_profit': [
            r'Profit\s+Before\s+(?:Income\s+)?Tax(?:ation)?[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
            r'Pre[\s-]?tax\s+Profit[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
        ],
        'net_profit': [
            r'(?:Net\s+)?Profit\s+(?:for\s+the\s+year|attributable\s+to\s+(?:owners|shareholders))[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
            r'Profit\s+(?:for\s+the\s+(?:year|period))[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
            r'Net\s+(?:Profit|Income)[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
        ],
        'interest_expense': [
            r'(?:Finance|Interest)\s+(?:Costs?|Expenses?)[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'rd_expense': [
            r'R(?:esearch)?\s*&?\s*D(?:evelopment)?\s+(?:Costs?|Expenses?)[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'Research\s+and\s+Development[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],

        # Balance Sheet
        'total_assets': [
            r'Total\s+Assets[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'current_assets': [
            r'(?:Total\s+)?Current\s+Assets[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'total_liabilities': [
            r'Total\s+Liabilities[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'current_liabilities': [
            r'(?:Total\s+)?Current\s+Liabilities[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'total_equity': [
            r'(?:Total\s+)?(?:Shareholders\'?|Owners\'?)\s+(?:Equity|Funds)[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'Equity\s+attributable\s+to\s+(?:owners|shareholders)[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'cash_and_equivalents': [
            r'Cash\s+and\s+cash\s+equivalents\s+at\s+end\s+of\s+(?:year|period)\s+([0-9,]+(?:\.[0-9]+)?)',
            r'Cash\s+and\s+(?:Cash\s+)?Equivalents[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'Bank\s+Balances\s+and\s+Cash[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'Cash\s+and\s+bank\s+balances[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'accounts_receivable': [
            r'(?:Trade\s+)?(?:Accounts?\s+)?Receivables?[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'Trade\s+and\s+(?:Other\s+)?Receivables[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'inventory': [
            r'Inventor(?:y|ies)[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'Stocks?[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'goodwill': [
            r'Goodwill[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'intangible_assets': [
            r'Intangible\s+Assets[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'fixed_assets': [
            r'(?:Property,?\s+)?Plant\s+and\s+Equipment[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'Fixed\s+Assets[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'short_term_debt': [
            r'Short[\s-]?term\s+(?:Borrowings?|Loans?|Debt)[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'long_term_debt': [
            r'Long[\s-]?term\s+(?:Borrowings?|Loans?|Debt)[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],
        'bonds_payable': [
            r'Bonds?\s+Payable[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'Notes?\s+Payable[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],

        # Cash Flow Statement
        'operating_cash_flow': [
            r'(?:Net\s+)?Cash\s+(?:Generated\s+)?from\s+Operating\s+Activities[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
        ],
        'investing_cash_flow': [
            r'(?:Net\s+)?Cash\s+(?:Used\s+in|from)\s+Investing\s+Activities[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
        ],
        'financing_cash_flow': [
            r'(?:Net\s+)?Cash\s+(?:Used\s+in|from)\s+Financing\s+Activities[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
        ],
        'capital_expenditure': [
            r'Capital\s+Expenditure[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'CAPEX[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'Purchase\s+of\s+(?:Property|Fixed\s+Assets)[:\s]+([0-9,]+(?:\.[0-9]+)?)',
        ],

        # Financial Metrics
        'eps': [
            r'(?:Basic\s+)?Earnings?\s+[Pp]er\s+[Ss]hare[:\s]+([0-9,.\-]+)',
            r'EPS[:\s]+([0-9,.\-]+)',
        ],
        'eps_diluted': [
            r'Diluted\s+(?:Earnings?\s+)?[Pp]er\s+[Ss]hare[:\s]+([0-9,.\-]+)',
            r'Diluted\s+EPS[:\s]+([0-9,.\-]+)',
        ],
        'bps': [
            r'(?:Net\s+Asset|Book)\s+[Vv]alue\s+[Pp]er\s+[Ss]hare[:\s]+([0-9,.]+)',
        ],
        'dividend_per_share': [
            r'Dividend\s+[Pp]er\s+[Ss]hare[:\s]+([0-9,.]+)',
            r'DPS[:\s]+([0-9,.]+)',
            r'Final\s+Dividend[:\s]+([0-9,.]+)',
        ],
        'roe': [
            r'Return\s+on\s+(?:Shareholders\'?\s+)?Equity[:\s]+([0-9,.]+)',
            r'ROE[:\s]+([0-9,.]+)',
        ],
        'current_ratio': [
            r'Current\s+Ratio[:\s]+([0-9,.]+)',
        ],
        'quick_ratio': [
            r'Quick\s+Ratio[:\s]+([0-9,.]+)',
            r'Acid[\s-]?Test\s+Ratio[:\s]+([0-9,.]+)',
        ],
    }

    # 英文表格关键词映射（用于港股英文财报）
    TABLE_KEYWORDS_EN = {
        # 利润表
        'revenue': ['Revenue', 'Turnover', 'Sales', 'Operating revenue'],
        'operating_cost': ['Cost of sales', 'Cost of revenue', 'Cost of goods sold'],
        'gross_profit': ['Gross profit'],
        'operating_profit': ['Operating profit', 'Profit from operations'],
        'total_profit': ['Profit before tax', 'Pre-tax profit'],
        'net_profit': ['Profit for the year', 'Net profit', 'Profit attributable to owners', 'Profit attributable to shareholders'],
        'interest_expense': ['Finance costs', 'Interest expense'],
        'rd_expense': ['R&D expense', 'Research and development'],
        # 资产负债表
        'total_assets': ['Total assets'],
        'current_assets': ['Current assets', 'Total current assets'],
        'total_liabilities': ['Total liabilities'],
        'current_liabilities': ['Current liabilities', 'Total current liabilities'],
        'total_equity': ['Total equity', "Shareholders' equity", "Owners' equity", 'Equity attributable to owners'],
        'cash_and_equivalents': ['Cash and cash equivalents', 'Bank balances and cash'],
        'short_term_debt': ['Short-term borrowings', 'Short-term debt'],
        'long_term_debt': ['Long-term borrowings', 'Long-term debt'],
        'bonds_payable': ['Bonds payable', 'Notes payable'],
        'accounts_receivable': ['Trade receivables', 'Accounts receivable', 'Trade and other receivables'],
        'inventory': ['Inventories', 'Inventory', 'Stocks'],
        'goodwill': ['Goodwill'],
        'intangible_assets': ['Intangible assets'],
        'fixed_assets': ['Property, plant and equipment', 'Fixed assets'],
        # 现金流量表
        'operating_cash_flow': ['Cash generated from operating activities', 'Net cash from operating activities'],
        'investing_cash_flow': ['Cash used in investing activities', 'Net cash from investing activities'],
        'financing_cash_flow': ['Cash used in financing activities', 'Net cash from financing activities'],
        'capital_expenditure': ['Capital expenditure', 'CAPEX', 'Purchase of property'],
        # 财务指标
        'eps': ['Basic earnings per share', 'Earnings per share', 'EPS'],
        'eps_diluted': ['Diluted earnings per share', 'Diluted EPS'],
        'bps': ['Net asset value per share', 'Book value per share'],
        'dividend_per_share': ['Dividend per share', 'DPS', 'Final dividend'],
        'roe': ['Return on equity', 'ROE'],
        'current_ratio': ['Current ratio'],
        'quick_ratio': ['Quick ratio', 'Acid-test ratio'],
    }

    def __init__(self):
        self.current_pdf_path: Optional[Path] = None
        self.full_text: str = ""
        self.tables: List[List[List[str]]] = []
        self.is_english_report: bool = False  # 是否为英文财报

    def extract(self, pdf_path: str) -> Dict[str, Any]:
        """提取PDF财报的全部结构化数据"""
        self.current_pdf_path = Path(pdf_path)

        if not self.current_pdf_path.exists():
            logger.error(f"PDF文件不存在: {pdf_path}")
            return {"success": False, "error": "文件不存在"}

        try:
            # 提取基础内容
            self._extract_content()

            # 检测报告语言
            self._detect_language()

            # 提取各类数据
            metadata = self._extract_metadata()
            income_statement = self._extract_income_statement()
            balance_sheet = self._extract_balance_sheet()
            cash_flow = self._extract_cash_flow()
            metrics = self._extract_financial_metrics()
            related_party = self._extract_related_party_transactions()

            # 计算衍生指标
            self._calculate_derived_metrics(balance_sheet, income_statement, cash_flow, metrics)

            result = {
                "success": True,
                "metadata": asdict(metadata),
                "income_statement": asdict(income_statement),
                "balance_sheet": asdict(balance_sheet),
                "cash_flow_statement": asdict(cash_flow),
                "financial_metrics": asdict(metrics),
                "related_party_transactions": asdict(related_party),
                "extraction_summary": {
                    "total_tables_found": len(self.tables),
                    "text_length": len(self.full_text),
                    "fields_extracted": self._count_extracted_fields(
                        income_statement, balance_sheet, cash_flow, metrics
                    )
                }
            }

            logger.info(f"PDF内容提取完成: {pdf_path}, 提取{result['extraction_summary']['fields_extracted']}个字段")
            return result

        except Exception as e:
            logger.error(f"PDF提取失败: {e}")
            return {"success": False, "error": str(e)}

    def _extract_content(self):
        """提取PDF的文本和表格"""
        self.full_text = ""
        self.tables = []

        with pdfplumber.open(self.current_pdf_path) as pdf:
            for page in pdf.pages:
                # 提取文本
                text = page.extract_text()
                if text:
                    self.full_text += text + "\n"

                # 提取表格
                page_tables = page.extract_tables()
                if page_tables:
                    self.tables.extend(page_tables)

    def _detect_language(self):
        """检测报告语言（中文/英文）"""
        # 基于文件名判断
        file_name = self.current_pdf_path.name.lower()
        if '_en.' in file_name or '_en_' in file_name or 'english' in file_name:
            self.is_english_report = True
            logger.info(f"检测到英文财报（基于文件名）: {file_name}")
            return

        # 基于内容判断 - 统计中英文关键词
        cn_keywords = ['营业收入', '净利润', '资产总计', '负债合计', '现金流量', '财务费用', '股东权益']
        en_keywords = ['Revenue', 'Net Profit', 'Total Assets', 'Total Liabilities', 'Cash Flow', 'Finance Costs', 'Equity']

        cn_count = sum(1 for kw in cn_keywords if kw in self.full_text)
        en_count = sum(1 for kw in en_keywords if kw in self.full_text)

        # 如果英文关键词更多，则判定为英文报告
        if en_count > cn_count:
            self.is_english_report = True
            logger.info(f"检测到英文财报（基于内容）: cn={cn_count}, en={en_count}")
        else:
            self.is_english_report = False
            logger.info(f"检测到中文财报: cn={cn_count}, en={en_count}")

    def _extract_metadata(self) -> ReportMetadata:
        """提取报告元数据"""
        metadata = ReportMetadata()

        # 从pypdf获取元数据
        try:
            reader = PdfReader(self.current_pdf_path)
            pdf_meta = reader.metadata
            metadata.total_pages = len(reader.pages)
            metadata.title = pdf_meta.title if pdf_meta else None
        except Exception as e:
            logger.warning(f"读取PDF元数据失败: {e}")

        metadata.file_size = self.current_pdf_path.stat().st_size

        # 从文本提取股票代码
        if self.is_english_report:
            # 港股代码格式：Stock Code: 00700 或 Stock Codes: 1810 (HKD counter)
            code_match = re.search(r'Stock\s+Codes?[：:\s]*(\d{4,5})', self.full_text, re.IGNORECASE)
        else:
            code_match = re.search(r'证券代码[：:\s]*(\d{6})', self.full_text)
        if code_match:
            metadata.stock_code = code_match.group(1)

        # 从文本提取股票简称/公司名称
        if self.is_english_report:
            # 尝试从文件名或标题提取
            name_match = re.search(r'([A-Z][a-zA-Z\s]+(?:Limited|Inc\.|Corporation|Holdings))', self.full_text[:2000])
        else:
            name_match = re.search(r'证券简称[：:\s]*([^\s\n]+)', self.full_text)
        if name_match:
            metadata.stock_name = name_match.group(1).strip()

        # 判断报告类型
        if self.is_english_report:
            text_lower = self.full_text.lower()
            if 'annual report' in text_lower or 'annual results' in text_lower:
                metadata.report_type = 'annual'
            elif 'interim report' in text_lower or 'interim results' in text_lower or 'half-year' in text_lower:
                metadata.report_type = 'semi_annual'
            elif 'quarterly' in text_lower:
                metadata.report_type = 'quarterly'
        else:
            if '年度报告' in self.full_text or '年报' in self.full_text:
                if '半年度' in self.full_text or '中期' in self.full_text:
                    metadata.report_type = 'semi_annual'
                else:
                    metadata.report_type = 'annual'
            elif '季度报告' in self.full_text or '季报' in self.full_text:
                metadata.report_type = 'quarterly'
                if '第一季度' in self.full_text or '一季度' in self.full_text:
                    metadata.report_type = 'quarterly_1'
                elif '第三季度' in self.full_text or '三季度' in self.full_text:
                    metadata.report_type = 'quarterly_3'

        # 提取报告期
        if self.is_english_report:
            period_match = re.search(r'(?:year|period)\s+ended?\s+.*?(20\d{2})', self.full_text, re.IGNORECASE)
            if not period_match:
                period_match = re.search(r'(20\d{2})\s+(?:Annual|Interim)', self.full_text, re.IGNORECASE)
        else:
            period_match = re.search(r'(20\d{2})[年\s]*(?:年度|第[一二三四]季度|半年度)', self.full_text)
        if period_match:
            metadata.report_period = period_match.group(0)

        return metadata

    def _extract_income_statement(self) -> IncomeStatement:
        """提取利润表数据"""
        income = IncomeStatement()

        income.revenue = self._find_value('revenue')
        income.operating_cost = self._find_value('operating_cost')
        income.gross_profit = self._find_value('gross_profit')
        income.operating_profit = self._find_value('operating_profit')
        income.total_profit = self._find_value('total_profit')
        income.net_profit = self._find_value('net_profit')
        income.net_profit_deducted = self._find_value('net_profit_deducted')
        income.interest_expense = self._find_value('interest_expense')
        income.rd_expense = self._find_value('rd_expense')

        # 从表格中补充提取
        self._extract_from_tables_income(income)

        return income

    def _extract_balance_sheet(self) -> BalanceSheet:
        """提取资产负债表数据"""
        balance = BalanceSheet()

        balance.total_assets = self._find_value('total_assets')
        balance.current_assets = self._find_value('current_assets')
        balance.cash_and_equivalents = self._find_value('cash_and_equivalents')
        balance.accounts_receivable = self._find_value('accounts_receivable')
        balance.inventory = self._find_value('inventory')
        balance.fixed_assets = self._find_value('fixed_assets')
        balance.goodwill = self._find_value('goodwill')
        balance.intangible_assets = self._find_value('intangible_assets')
        balance.total_liabilities = self._find_value('total_liabilities')
        balance.current_liabilities = self._find_value('current_liabilities')
        balance.short_term_debt = self._find_value('short_term_debt')
        balance.long_term_debt = self._find_value('long_term_debt')
        balance.bonds_payable = self._find_value('bonds_payable')
        balance.total_equity = self._find_value('total_equity')

        # 从表格中补充提取
        self._extract_from_tables_balance(balance)

        return balance

    def _extract_cash_flow(self) -> CashFlowStatement:
        """提取现金流量表数据"""
        cash_flow = CashFlowStatement()

        cash_flow.operating_cash_flow = self._find_value('operating_cash_flow')
        cash_flow.investing_cash_flow = self._find_value('investing_cash_flow')
        cash_flow.financing_cash_flow = self._find_value('financing_cash_flow')
        cash_flow.capital_expenditure = self._find_value('capital_expenditure')

        # 从表格中补充提取
        self._extract_from_tables_cashflow(cash_flow)

        return cash_flow

    def _extract_financial_metrics(self) -> FinancialMetrics:
        """提取财务指标"""
        metrics = FinancialMetrics()

        metrics.eps = self._find_value('eps')
        metrics.eps_diluted = self._find_value('eps_diluted')
        metrics.bps = self._find_value('bps')
        metrics.dividend_per_share = self._find_value('dividend_per_share')
        metrics.roe = self._find_value('roe')
        metrics.current_ratio = self._find_value('current_ratio')
        metrics.quick_ratio = self._find_value('quick_ratio')

        # 从表格中补充提取
        self._extract_from_tables_metrics(metrics)

        return metrics

    def _extract_related_party_transactions(self) -> RelatedPartyTransactions:
        """提取关联交易数据"""
        rpt = RelatedPartyTransactions()

        # 关联交易关键词模式
        patterns = {
            'total_sales': [
                r'向关联方销售[商品产品服务劳务]*[金额合计：:\s]*([0-9,，]+\.?[0-9]*)',
                r'销售商品[、/]提供劳务[金额合计：:\s]*([0-9,，]+\.?[0-9]*)',
            ],
            'total_purchases': [
                r'向关联方采购[商品产品材料]*[金额合计：:\s]*([0-9,，]+\.?[0-9]*)',
                r'采购商品[、/]接受劳务[金额合计：:\s]*([0-9,，]+\.?[0-9]*)',
            ],
            'total_receivables': [
                r'应收关联方[款项余额：:\s]*([0-9,，]+\.?[0-9]*)',
            ],
            'total_payables': [
                r'应付关联方[款项余额：:\s]*([0-9,，]+\.?[0-9]*)',
            ],
        }

        # 从文本中提取
        for field, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.findall(pattern, self.full_text)
                for match in matches:
                    value = self._parse_number(match)
                    if value is not None:
                        setattr(rpt, field, value)
                        break
                if getattr(rpt, field) is not None:
                    break

        # 从表格中提取关联交易明细
        rpt.transactions_list = self._extract_related_party_from_tables()

        return rpt

    def _extract_related_party_from_tables(self) -> List[Dict]:
        """从表格中提取关联交易明细"""
        transactions = []

        # 关联交易表格关键词
        rpt_keywords = ['关联方', '关联交易', '关联人', '关联企业', '控股股东', '实际控制人']

        for table in self.tables:
            if not table or len(table) < 2:
                continue

            # 检查表头是否包含关联交易相关关键词
            header_row = table[0] if table[0] else []
            header_text = ' '.join(str(cell) for cell in header_row if cell)

            is_rpt_table = any(kw in header_text for kw in rpt_keywords)

            if is_rpt_table:
                # 解析关联交易表格
                for row in table[1:]:
                    if not row or len(row) < 2:
                        continue

                    # 尝试提取关联方名称和交易金额
                    party_name = str(row[0]).strip() if row[0] else ""
                    if not party_name or party_name == 'None':
                        continue

                    # 查找数值列
                    amounts = []
                    for cell in row[1:]:
                        value = self._parse_number(str(cell) if cell else "")
                        if value is not None and abs(value) > 100:  # 过滤小数值
                            amounts.append(value)

                    if amounts:
                        transactions.append({
                            'party_name': party_name.replace('\n', ''),
                            'amounts': amounts
                        })

        return transactions if transactions else None

    def _find_value(self, field_name: str) -> Optional[float]:
        """使用正则从文本中查找数值"""
        # 根据语言选择模式
        if self.is_english_report:
            patterns = self.PATTERNS_EN.get(field_name, [])
        else:
            patterns = self.PATTERNS.get(field_name, [])

        for pattern in patterns:
            matches = re.findall(pattern, self.full_text, re.IGNORECASE)
            for match in matches:
                value = self._parse_number(match)
                if value is not None:
                    return value

        # 如果英文模式没找到，尝试中文模式（或反之）
        if self.is_english_report:
            fallback_patterns = self.PATTERNS.get(field_name, [])
        else:
            fallback_patterns = self.PATTERNS_EN.get(field_name, [])

        for pattern in fallback_patterns:
            matches = re.findall(pattern, self.full_text, re.IGNORECASE)
            for match in matches:
                value = self._parse_number(match)
                if value is not None:
                    return value

        return None

    def _parse_number(self, text: str) -> Optional[float]:
        """解析数字字符串为浮点数"""
        if not text:
            return None

        try:
            # 移除逗号和中文逗号
            cleaned = text.replace(',', '').replace('，', '').strip()

            # 处理负数
            if cleaned.startswith('-') or cleaned.startswith('－'):
                cleaned = '-' + cleaned.lstrip('-－')

            # 转换为浮点数
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _get_first_large_value(self, cells: List, min_value: float = 1000) -> Optional[float]:
        """从单元格列表中获取第一个大于阈值的数值

        用于跳过注释编号等小数值，获取真正的财务数据

        Args:
            cells: 单元格列表
            min_value: 最小值阈值

        Returns:
            第一个大于阈值的数值，或None
        """
        for cell in cells:
            value = self._parse_number(str(cell).replace('\n', '') if cell else "")
            if value is not None and abs(value) > min_value:
                return value
        return None

    def _extract_from_tables_income(self, income: IncomeStatement):
        """从表格中提取利润表数据"""
        if self.is_english_report:
            keywords_map = {
                'revenue': self.TABLE_KEYWORDS_EN.get('revenue', []),
                'operating_cost': self.TABLE_KEYWORDS_EN.get('operating_cost', []),
                'gross_profit': self.TABLE_KEYWORDS_EN.get('gross_profit', []),
                'operating_profit': self.TABLE_KEYWORDS_EN.get('operating_profit', []),
                'total_profit': self.TABLE_KEYWORDS_EN.get('total_profit', []),
                'net_profit': self.TABLE_KEYWORDS_EN.get('net_profit', []),
                'interest_expense': self.TABLE_KEYWORDS_EN.get('interest_expense', []),
                'rd_expense': self.TABLE_KEYWORDS_EN.get('rd_expense', []),
            }
        else:
            keywords_map = {
                'revenue': ['营业收入', '营业总收入', '一、营业收入'],
                'operating_cost': ['营业成本', '营业总成本', '二、营业成本'],
                'gross_profit': ['毛利', '毛利润', '营业毛利'],
                'operating_profit': ['营业利润', '三、营业利润'],
                'total_profit': ['利润总额', '四、利润总额', '税前利润'],
                'net_profit': ['归属于上市公司股东的净利润', '归属于母公司所有者的净利润', '归属于母公司股东的净利润'],
                'net_profit_deducted': ['扣除非经常性损益的净利润', '扣除非经常性损益后的净利润', '扣非净利润'],
                'interest_expense': ['财务费用', '利息费用', '利息支出'],
                'rd_expense': ['研发费用', '研发支出', '研究开发费用'],
            }

        for table in self.tables:
            for row in table:
                if not row or len(row) < 2:
                    continue

                # 清理换行符，合并单元格文本
                row_text = str(row[0]).replace('\n', '') if row[0] else ""

                for field, keywords in keywords_map.items():
                    current_value = getattr(income, field)
                    for keyword in keywords:
                        if keyword in row_text:
                            # 排除"扣除非经常性损益后的基本每股收益"误匹配
                            if field == 'net_profit_deducted' and '每股' in row_text:
                                continue
                            # 排除"归属于母公司所有者的权益"误匹配净利润
                            if field == 'net_profit' and '权益' in row_text:
                                continue
                            # 获取第一个大于阈值的数值（跳过注释编号等）
                            value = self._get_first_large_value(row[1:], min_value=10000)
                            if value is not None:
                                # 如果当前值太小（可能是EPS等），用表格值覆盖
                                if current_value is None or abs(current_value) < 10000:
                                    setattr(income, field, value)
                            break

    def _extract_from_tables_balance(self, balance: BalanceSheet):
        """从表格中提取资产负债表数据"""
        if self.is_english_report:
            keywords_map = {
                'total_assets': self.TABLE_KEYWORDS_EN.get('total_assets', []),
                'current_assets': self.TABLE_KEYWORDS_EN.get('current_assets', []),
                'cash_and_equivalents': self.TABLE_KEYWORDS_EN.get('cash_and_equivalents', []),
                'accounts_receivable': self.TABLE_KEYWORDS_EN.get('accounts_receivable', []),
                'inventory': self.TABLE_KEYWORDS_EN.get('inventory', []),
                'fixed_assets': self.TABLE_KEYWORDS_EN.get('fixed_assets', []),
                'goodwill': self.TABLE_KEYWORDS_EN.get('goodwill', []),
                'intangible_assets': self.TABLE_KEYWORDS_EN.get('intangible_assets', []),
                'total_liabilities': self.TABLE_KEYWORDS_EN.get('total_liabilities', []),
                'current_liabilities': self.TABLE_KEYWORDS_EN.get('current_liabilities', []),
                'short_term_debt': self.TABLE_KEYWORDS_EN.get('short_term_debt', []),
                'long_term_debt': self.TABLE_KEYWORDS_EN.get('long_term_debt', []),
                'bonds_payable': self.TABLE_KEYWORDS_EN.get('bonds_payable', []),
                'total_equity': self.TABLE_KEYWORDS_EN.get('total_equity', []),
            }
        else:
            keywords_map = {
                'total_assets': ['资产总计', '总资产', '资产合计'],
                'current_assets': ['流动资产合计', '流动资产小计'],
                'cash_and_equivalents': ['货币资金'],
                'accounts_receivable': ['应收账款', '应收票据及应收账款'],
                'inventory': ['存货'],
                'fixed_assets': ['固定资产'],
                'goodwill': ['商誉'],
                'intangible_assets': ['无形资产'],
                'total_liabilities': ['负债合计', '总负债', '负债总计'],
                'current_liabilities': ['流动负债合计', '流动负债小计'],
                'short_term_debt': ['短期借款'],
                'long_term_debt': ['长期借款'],
                'bonds_payable': ['应付债券'],
                'total_equity': ['归属于母公司所有者的权益', '所有者权益合计', '股东权益合计'],
            }

        for table in self.tables:
            for row in table:
                if not row or len(row) < 2:
                    continue

                # 清理换行符
                row_text = str(row[0]).replace('\n', '') if row[0] else ""

                for field, keywords in keywords_map.items():
                    current_value = getattr(balance, field)
                    for keyword in keywords:
                        # 精确匹配或前缀匹配（避免"购建固定资产"匹配"固定资产"）
                        if row_text.strip() == keyword or row_text.startswith(keyword):
                            # 排除净利润行误匹配权益
                            if field == 'total_equity' and '净利润' in row_text:
                                continue
                            # 跳过注释编号列，获取真实数值
                            value = self._get_first_large_value(row[1:], min_value=10000)
                            if value is not None:
                                # 如果当前值太小或为空，用表格值覆盖
                                if current_value is None or abs(current_value) < 10000:
                                    setattr(balance, field, value)
                            break

    def _extract_from_tables_cashflow(self, cash_flow: CashFlowStatement):
        """从表格中提取现金流量表数据"""
        if self.is_english_report:
            keywords_map = {
                'operating_cash_flow': self.TABLE_KEYWORDS_EN.get('operating_cash_flow', []),
                'investing_cash_flow': self.TABLE_KEYWORDS_EN.get('investing_cash_flow', []),
                'financing_cash_flow': self.TABLE_KEYWORDS_EN.get('financing_cash_flow', []),
            }
        else:
            keywords_map = {
                'operating_cash_flow': ['经营活动产生的现金流量净额', '经营活动现金流量净额'],
                'investing_cash_flow': ['投资活动产生的现金流量净额'],
                'financing_cash_flow': ['筹资活动产生的现金流量净额'],
                'capital_expenditure': ['购建固定资产、无形资产和其他长期资产支付的现金', '购建固定资产', '购置固定资产'],
            }

        for table in self.tables:
            for row in table:
                if not row or len(row) < 2:
                    continue

                # 清理换行符
                row_text = str(row[0]).replace('\n', '') if row[0] else ""

                for field, keywords in keywords_map.items():
                    if getattr(cash_flow, field) is None:
                        for keyword in keywords:
                            if keyword in row_text:
                                for cell in row[1:]:
                                    value = self._parse_number(str(cell).replace('\n', '') if cell else "")
                                    if value is not None and abs(value) > 1:
                                        setattr(cash_flow, field, value)
                                        break
                                break

    def _extract_from_tables_metrics(self, metrics: FinancialMetrics):
        """从表格中提取财务指标"""
        if self.is_english_report:
            keywords_map = {
                'eps': self.TABLE_KEYWORDS_EN.get('eps', []),
                'eps_diluted': self.TABLE_KEYWORDS_EN.get('eps_diluted', []),
                'bps': self.TABLE_KEYWORDS_EN.get('bps', []),
                'dividend_per_share': self.TABLE_KEYWORDS_EN.get('dividend_per_share', []),
                'roe': self.TABLE_KEYWORDS_EN.get('roe', []),
                'current_ratio': self.TABLE_KEYWORDS_EN.get('current_ratio', []),
                'quick_ratio': self.TABLE_KEYWORDS_EN.get('quick_ratio', []),
            }
        else:
            keywords_map = {
                'eps': ['基本每股收益', '每股收益（元/股）', '每股收益（元'],
                'eps_diluted': ['稀释每股收益'],
                'bps': ['每股净资产', '归属于上市公司股东的每股净资产', '归属于母公司普通股股东的每股净资产'],
                'dividend_per_share': ['每股股利', '每股现金股利', '每股派息', '每股分红'],
                'roe': ['加权平均净资产收益率', '净资产收益率（%）', '净资产收益率'],
                'current_ratio': ['流动比率'],
                'quick_ratio': ['速动比率'],
                'total_shares': ['股份总数', '股本总额', '普通股股份总数', '总股本'],
            }

        for table in self.tables:
            for row in table:
                if not row or len(row) < 2:
                    continue

                # 清理换行符
                row_text = str(row[0]).replace('\n', '') if row[0] else ""

                for field, keywords in keywords_map.items():
                    if getattr(metrics, field) is None:
                        for keyword in keywords:
                            if keyword in row_text:
                                # 排除"扣除非经常性损益后"的每股收益
                                if field == 'eps' and '扣除' in row_text:
                                    continue
                                for cell in row[1:]:
                                    value = self._parse_number(str(cell).replace('\n', '') if cell else "")
                                    if value is not None:
                                        setattr(metrics, field, value)
                                        break
                                break

    def _calculate_derived_metrics(self, balance: BalanceSheet, income: IncomeStatement,
                                   cash_flow: CashFlowStatement, metrics: FinancialMetrics):
        """计算衍生财务指标"""
        # 计算营业成本 = 营业收入 - 毛利润（当直接提取的成本单位不一致时）
        if income.revenue and income.gross_profit:
            calculated_cost = income.revenue - income.gross_profit
            # 如果提取的成本与计算的成本差距过大（单位不一致），使用计算值
            if income.operating_cost is None or abs(income.operating_cost - calculated_cost) > calculated_cost * 0.1:
                income.operating_cost = calculated_cost

        # 计算毛利润 = 营业收入 - 营业成本
        if income.gross_profit is None and income.revenue and income.operating_cost:
            income.gross_profit = income.revenue - income.operating_cost

        # 计算毛利率(%) = 毛利润 / 营业收入 * 100
        if income.gross_margin is None and income.gross_profit and income.revenue:
            income.gross_margin = round(income.gross_profit / income.revenue * 100, 2)

        # 计算净利率(%) = 净利润 / 营业收入 * 100
        if income.net_margin is None and income.net_profit and income.revenue:
            income.net_margin = round(income.net_profit / income.revenue * 100, 2)

        # 计算资产负债率
        if balance.total_assets and balance.total_liabilities:
            metrics.debt_ratio = round(balance.total_liabilities / balance.total_assets * 100, 2)

        # 计算流动比率 = 流动资产 / 流动负债
        if metrics.current_ratio is None and balance.current_assets and balance.current_liabilities:
            metrics.current_ratio = round(balance.current_assets / balance.current_liabilities, 2)

        # 计算速动比率 = (流动资产 - 存货) / 流动负债
        if metrics.quick_ratio is None and balance.current_assets and balance.current_liabilities:
            inventory = balance.inventory or 0
            metrics.quick_ratio = round((balance.current_assets - inventory) / balance.current_liabilities, 2)

        # 计算ROA (需要年化处理，这里简化)
        if balance.total_assets and income.net_profit:
            metrics.roa = round(income.net_profit / balance.total_assets * 100, 2)

        # 计算自由现金流 = 经营现金流 - 资本支出
        if cash_flow.operating_cash_flow is not None and cash_flow.capital_expenditure is not None:
            cash_flow.free_cash_flow = cash_flow.operating_cash_flow - cash_flow.capital_expenditure

        # 计算每股净资产 = 归属于母公司股东权益 / 总股本
        if metrics.bps is None and balance.total_equity and metrics.total_shares:
            metrics.bps = round(balance.total_equity / metrics.total_shares, 2)

        # 如果有每股收益和净利润，可以反推总股本
        if metrics.total_shares is None and metrics.eps and income.net_profit:
            metrics.total_shares = income.net_profit / metrics.eps

        # 用反推的总股本计算每股净资产
        if metrics.bps is None and balance.total_equity and metrics.total_shares:
            metrics.bps = round(balance.total_equity / metrics.total_shares, 2)

    def _count_extracted_fields(self, *dataclasses) -> int:
        """统计成功提取的字段数量"""
        count = 0
        for dc in dataclasses:
            for field_name, value in asdict(dc).items():
                if value is not None:
                    count += 1
        return count

    def extract_tables_raw(self, pdf_path: str) -> List[Dict[str, Any]]:
        """提取所有原始表格数据"""
        tables_data = []

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_tables = page.extract_tables()
                for table_idx, table in enumerate(page_tables, 1):
                    tables_data.append({
                        "page": page_num,
                        "table_index": table_idx,
                        "rows": len(table),
                        "columns": len(table[0]) if table else 0,
                        "data": table
                    })

        return tables_data

    def extract_text_full(self, pdf_path: str) -> str:
        """提取PDF全部文本"""
        full_text = ""

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n\n"

        return full_text


# 便捷函数
def extract_financial_data(pdf_path: str) -> Dict[str, Any]:
    """提取PDF财报数据的便捷函数"""
    extractor = PDFContentExtractor()
    return extractor.extract(pdf_path)
