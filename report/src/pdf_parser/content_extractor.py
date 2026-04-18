"""
PDF财报内容提取器
从财报PDF中提取结构化财务数据
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
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
    net_profit_attributable_to_parent: Optional[float] = None  # 归属于母公司股东的净利润
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
    equity_attributable_to_parent: Optional[float] = None  # 归属于母公司股东的净资产


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
    period_type: Optional[str] = None                  # quarter/semi_annual/annual/full_year_in_quarterly_announcement
    currency: Optional[str] = None                     # USD/HKD/CNY
    amount_unit: Optional[str] = None                  # million/billion/none
    per_share_currency: Optional[str] = None           # EPS币种
    doc_type: Optional[str] = None                     # annual_report/interim_report/results_announcement/quarterly_report
    fiscal_year: Optional[int] = None                  # 财年
    primary_period_id: Optional[str] = None            # 主期间ID
    is_audited: Optional[bool] = None                  # 是否审计
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
        'net_profit_attributable_to_parent': [
            r'归属于母公司(?:股东)?(?:的)?净利润[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'归母净利润[：:\s]*([0-9,，-]+\.?[0-9]*)',
            r'归属于上市公司股东的净利润[：:\s]*([0-9,，-]+\.?[0-9]*)',
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
        'equity_attributable_to_parent': [
            r'归属于母公司(?:股东)?(?:的)?(?:所有者)?权益[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'归母(?:股东)?权益[：:\s]*([0-9,，]+\.?[0-9]*)',
            r'归属于上市公司股东的权益[：:\s]*([0-9,，]+\.?[0-9]*)',
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
            # 双语主报表行优先（例如 "Revenue 收入 20,703,294 21,490,903"）
            r'(?:^|\n)\s*(?:Total\s+)?Revenue\s+(?:收入|總收入)\s+([0-9,]+(?:\.[0-9]+)?)',
            # 优先匹配Total Revenue/Total revenues（带单位识别）
            r'Total\s+Revenues?[:\s]+\$?\s*([0-9,]+(?:\.[0-9]+)?)',
            r'Total\s+Revenues?\s+\$?\s*([0-9,]+(?:\.[0-9]+)?)',
            # 匹配Revenue（带billion单位的文本格式，如"$11.3 billion of revenues"）
            r'\$?\s*([0-9,]+(?:\.[0-9]+)?)\s*billion\s+of\s+revenues?',
            r'revenues?\s+(?:of|in)\s+\$?\s*([0-9,]+(?:\.[0-9]+)?)\s*billion',
            # 匹配Revenue（一般格式）
            r'Revenue[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'Revenue[:\s]+\$?\s*([0-9,]+(?:\.[0-9]+)?)',
            # 匹配Turnover
            r'Turnover[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            # 最后匹配Sales（但要避免Company sales等部分收入）
            r'(?:^|\n)(?:Total\s+)?(?:Operating\s+)?Sales[:\s]+([0-9,]+(?:\.[0-9]+)?)',
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
            r'(?:^|\n)\s*Profit\s+before\s+tax\s+除稅前溢利\s+([0-9,\-]+(?:\.[0-9]+)?)',
            r'Profit\s+Before\s+(?:Income\s+)?Tax(?:ation)?[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
            r'Pre[\s-]?tax\s+Profit[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
        ],
        'net_profit': [
            (
                r'(?:^|\n)\s*Profit\s+for\s+the\s+(?:year|period)\s+'
                r'(?:年內溢利|期內溢利)\s+(?:\d{1,3}\s+)?([0-9,]+(?:\.[0-9]+)?)'
            ),
            r'Net\s+Income\s+[–-]\s+including\s+noncontrolling\s+interests[:\s]+\$?\s*([0-9,\-]+(?:\.[0-9]+)?)',
            r'(?:Net\s+)?Profit\s+(?:for\s+the\s+year|attributable\s+to\s+(?:owners|shareholders))[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
            r'Profit\s+(?:for\s+the\s+(?:year|period))[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
            r'Net\s+(?:Profit|Income)[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
        ],
        'net_profit_attributable_to_parent': [
            r'Profit\s+attributable\s+to\s+(?:owners|equity\s+holders|shareholders)\s+of\s+(?:the\s+)?(?:Company|Parent)[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
            r'Net\s+profit\s+attributable\s+to\s+(?:owners|equity\s+holders|shareholders)[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
            r'Profit\s+attributable\s+to\s+equity\s+holders[:\s]+([0-9,\-]+(?:\.[0-9]+)?)',
            r'Net\s+Income\s+[–-]\s+.*?(?:Holdings|Company|Inc\.)[:\s]+\$?\s*([0-9,\-]+(?:\.[0-9]+)?)',
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
        'equity_attributable_to_parent': [
            r'Equity\s+attributable\s+to\s+(?:owners|equity\s+holders|shareholders)\s+of\s+(?:the\s+)?(?:Company|Parent)[:\s]+([0-9,]+(?:\.[0-9]+)?)',
            r'Total\s+equity\s+attributable\s+to\s+(?:owners|equity\s+holders|shareholders)[:\s]+([0-9,]+(?:\.[0-9]+)?)',
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
            r'(?:Basic\s+)?Earnings?\s+Per\s+(?:Common\s+)?Share[:\s]+\$?\s*([0-9,.\-]+)',
            r'EPS[:\s]+([0-9,.\-]+)',
        ],
        'eps_diluted': [
            r'Diluted\s+(?:Earnings?\s+)?Per\s+(?:Common\s+)?Share[:\s]+\$?\s*([0-9,.\-]+)',
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
        'revenue': ['Revenue', 'Revenues', 'Total revenues', 'Turnover', 'Sales', 'Operating revenue'],
        'operating_cost': ['Cost of sales', 'Cost of revenue', 'Cost of goods sold'],
        'gross_profit': ['Gross profit'],
        'operating_profit': ['Operating profit', 'Profit from operations'],
        'total_profit': ['Profit before tax', 'Pre-tax profit'],
        'net_profit': [
            'Profit for the year',
            'Net profit',
            'Net income',
            'Net Income',
            'Profit attributable to owners',
            'Profit attributable to shareholders',
        ],
        'interest_expense': ['Finance costs', 'Interest expense'],
        'rd_expense': ['R&D expense', 'Research and development'],
        # 资产负债表
        'total_assets': ['Total assets'],
        'current_assets': ['Current assets', 'Total current assets'],
        'total_liabilities': ['Total liabilities'],
        'current_liabilities': ['Current liabilities', 'Total current liabilities'],
        'total_equity': [
            'Total equity',
            "Shareholders' equity",
            "Owners' equity",
            'Equity attributable to owners',
            "Stockholders' equity",
            'Total stockholders’ equity',
            'Total stockholders\' equity',
        ],
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
        'operating_cash_flow': [
            'Cash generated from operating activities',
            'Net cash from operating activities',
            'Net cash provided by operating activities',
        ],
        'investing_cash_flow': [
            'Cash used in investing activities',
            'Net cash from investing activities',
            'Net cash used in investing activities',
        ],
        'financing_cash_flow': [
            'Cash used in financing activities',
            'Net cash from financing activities',
            'Net cash used in financing activities',
        ],
        'capital_expenditure': ['Capital expenditure', 'CAPEX', 'Purchase of property'],
        # 财务指标
        'eps': [
            'Basic earnings per share',
            'Basic earnings per common share',
            'Earnings per share',
            'Earnings per common share',
            'EPS',
        ],
        'eps_diluted': [
            'Diluted earnings per share',
            'Diluted earnings per common share',
            'Diluted EPS',
        ],
        'bps': ['Net asset value per share', 'Book value per share'],
        'dividend_per_share': ['Dividend per share', 'DPS', 'Final dividend'],
        'roe': ['Return on equity', 'ROE'],
        'current_ratio': ['Current ratio'],
        'quick_ratio': ['Quick ratio', 'Acid-test ratio'],
    }

    def __init__(self):
        self.current_pdf_path: Optional[Path] = None
        self.current_metadata: Optional[ReportMetadata] = None
        self.current_periods: List[Dict[str, Any]] = []
        self.full_text: str = ""
        self.tables: List[List[List[str]]] = []
        self.table_locations: List[Tuple[int, int]] = []
        self.is_english_report: bool = False  # 是否为英文财报
        self._derived_fact_keys: Set[Tuple[str, str]] = set()
        self._runtime_quality_issues: List[Dict[str, Any]] = []
        self._segment_skip_keys: Set[str] = set()

    def extract(self, pdf_path: str) -> Dict[str, Any]:
        """提取PDF财报的全部结构化数据"""
        self.current_pdf_path = Path(pdf_path)

        if not self.current_pdf_path.exists():
            logger.error(f"PDF文件不存在: {pdf_path}")
            return {"success": False, "error": "文件不存在"}

        try:
            # 提取基础内容
            self._extract_content()
            self._derived_fact_keys = set()

            # 检测报告语言
            self._detect_language()

            # 提取各类数据
            metadata = self._extract_metadata()
            periods = self._build_periods(metadata)
            self.current_metadata = metadata
            self.current_periods = periods
            document = self._build_document(metadata, periods)
            income_statement = self._extract_income_statement()
            balance_sheet = self._extract_balance_sheet()
            cash_flow = self._extract_cash_flow()
            metrics = self._extract_financial_metrics()
            related_party = self._extract_related_party_transactions()

            # 计算衍生指标
            self._calculate_derived_metrics(balance_sheet, income_statement, cash_flow, metrics)
            facts, evidence, quality = self._build_facts_evidence_quality(
                metadata=metadata,
                periods=periods,
                income=income_statement,
                balance=balance_sheet,
                cash_flow=cash_flow,
                metrics=metrics,
            )

            result = {
                "success": True,
                "schema_version": "v2",
                "compat_mode": True,
                "metadata": asdict(metadata),
                "document": document,
                "periods": periods,
                "facts": facts,
                "evidence": evidence,
                "quality": quality,
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
        self.current_metadata = None
        self.current_periods = []
        self.full_text = ""
        self.tables = []
        self.table_locations = []
        self._runtime_quality_issues = []
        self._segment_skip_keys = set()

        with pdfplumber.open(self.current_pdf_path) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                # 提取文本
                text = page.extract_text()
                if text:
                    self.full_text += text + "\n"

                # 提取表格
                page_tables = page.extract_tables()
                if page_tables:
                    for table_index, table in enumerate(page_tables, start=1):
                        self.tables.append(table)
                        self.table_locations.append((page_index, table_index))

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

    @staticmethod
    def _extract_quarter_number(text: str) -> Optional[int]:
        """从文本中识别季度编号"""
        patterns: List[Tuple[int, List[str]]] = [
            (1, [r"\bq1\b", r"\b1q\b", r"first quarter", r"第一季度", r"一季度"]),
            (2, [r"\bq2\b", r"\b2q\b", r"second quarter", r"第二季度", r"二季度"]),
            (3, [r"\bq3\b", r"\b3q\b", r"third quarter", r"第三季度", r"三季度"]),
            (4, [r"\bq4\b", r"\b4q\b", r"fourth quarter", r"第四季度", r"四季度"]),
        ]
        text_lower = text.lower()
        for quarter, regex_list in patterns:
            if any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in regex_list):
                return quarter
        return None

    @staticmethod
    def _date_range_for_period(fiscal_year: int, period_name: str) -> Tuple[Optional[str], Optional[str]]:
        """根据期间名称返回日期区间"""
        if period_name == "q1":
            return f"{fiscal_year}-01-01", f"{fiscal_year}-03-31"
        if period_name == "q2":
            return f"{fiscal_year}-04-01", f"{fiscal_year}-06-30"
        if period_name == "q3":
            return f"{fiscal_year}-07-01", f"{fiscal_year}-09-30"
        if period_name == "q4":
            return f"{fiscal_year}-10-01", f"{fiscal_year}-12-31"
        if period_name == "h1":
            return f"{fiscal_year}-01-01", f"{fiscal_year}-06-30"
        if period_name == "fy":
            return f"{fiscal_year}-01-01", f"{fiscal_year}-12-31"
        return None, None

    def _is_audited_report(self) -> Optional[bool]:
        """根据文本估算是否审计"""
        text_lower = self.full_text[:10000].lower()
        if "unaudited" in text_lower or "未經審核" in text_lower or "未经审计" in text_lower:
            return False
        if "audited" in text_lower or "經審核" in text_lower or "经审计" in text_lower:
            return True
        return None

    def _extract_fiscal_year(self, report_period: Optional[str] = None) -> Optional[int]:
        """提取财年，优先匹配与期间关键字相邻的年份"""
        title_text = self.full_text[:4000]
        patterns = [
            r'(20\d{2})\s*(?:q[1-4]|first quarter|second quarter|third quarter|fourth quarter|interim|annual|full year)',
            r'(?:year|period)\s+ended?\s+.*?(20\d{2})',
        ]
        for pattern in patterns:
            match = re.search(pattern, title_text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        if report_period:
            match = re.search(r'(20\d{2})', report_period)
            if match:
                return int(match.group(1))

        # 文件名兜底：2025_quarterly_xxx.pdf
        file_match = re.search(r'(20\d{2})', self.current_pdf_path.name)
        if file_match:
            return int(file_match.group(1))

        return None

    def _classify_report_identity(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """识别 report_type/doc_type/period_type，优先避免Q4+全年误判为annual"""
        text = self.full_text[:10000]
        text_lower = text.lower()

        has_results_announcement = (
            "results announcement" in text_lower
            or "業績公告" in text
            or "业绩公告" in text
        )
        has_full_year = (
            "full year" in text_lower
            or "全年" in text
            or "年度" in text
            or "year ended" in text_lower
        )
        quarter_num = self._extract_quarter_number(text)
        has_quarter_signal = (
            quarter_num is not None
            or "quarterly" in text_lower
            or "季度报告" in text
            or "季度業績" in text
            or "季报" in text
        )
        has_interim_signal = (
            "interim report" in text_lower
            or "interim results" in text_lower
            or "half-year" in text_lower
            or "half year" in text_lower
            or "six months" in text_lower
            or "中期報告" in text
            or "半年度报告" in text
            or "中期业绩" in text
        )
        has_annual_report_signal = (
            "annual report" in text_lower
            or "年度报告" in text
            or "年報" in text
            or "年报" in text
        )
        has_annual_results_signal = "annual results" in text_lower or "全年業績" in text or "全年业绩" in text

        if has_interim_signal:
            return "semi_annual", "interim_report", "semi_annual"

        if has_quarter_signal:
            if quarter_num == 4 and has_full_year:
                return "quarterly", "results_announcement", "full_year_in_quarterly_announcement"
            if has_results_announcement:
                return "quarterly", "results_announcement", "quarter"
            return "quarterly", "quarterly_report", "quarter"

        if has_annual_report_signal:
            return "annual", "annual_report", "annual"

        if has_annual_results_signal:
            return "annual", "results_announcement", "annual"

        return None, None, None

    def _build_periods(self, metadata: ReportMetadata) -> List[Dict[str, Any]]:
        """构建标准化期间列表（V2骨架）"""
        periods: List[Dict[str, Any]] = []
        fiscal_year = metadata.fiscal_year
        if fiscal_year is None:
            return periods

        def add_period(
            period_id: str,
            scope: str,
            *,
            fiscal_quarter: Optional[int] = None,
            ytd_through_quarter: Optional[int] = None,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            as_of_date: Optional[str] = None,
            is_primary: bool = False,
            is_comparison: bool = False,
        ) -> None:
            periods.append(
                {
                    "period_id": period_id,
                    "scope": scope,
                    "fiscal_quarter": fiscal_quarter,
                    "ytd_through_quarter": ytd_through_quarter,
                    "start_date": start_date,
                    "end_date": end_date,
                    "as_of_date": as_of_date,
                    "is_primary": is_primary,
                    "is_comparison": is_comparison,
                }
            )

        def add_balance_as_of_period(
            date_str: Optional[str],
            *,
            is_primary: bool = False,
            is_comparison: bool = False,
        ) -> None:
            if not date_str:
                return
            add_period(
                period_id=f"BS_{date_str}",
                scope="point_in_time",
                fiscal_quarter=None,
                ytd_through_quarter=None,
                start_date=None,
                end_date=None,
                as_of_date=date_str,
                is_primary=is_primary,
                is_comparison=is_comparison,
            )

        quarter_num = self._extract_quarter_number(self.full_text[:10000])

        if metadata.report_type == "semi_annual":
            start_date, end_date = self._date_range_for_period(fiscal_year, "h1")
            add_period(
                period_id=f"{fiscal_year}H1_YTD",
                scope="year_to_date",
                ytd_through_quarter=2,
                start_date=start_date,
                end_date=end_date,
                is_primary=True,
            )
            add_balance_as_of_period(end_date, is_primary=True)
            metadata.primary_period_id = f"{fiscal_year}H1_YTD"
            return periods

        if metadata.report_type == "quarterly":
            if metadata.period_type == "full_year_in_quarterly_announcement":
                q4_start, q4_end = self._date_range_for_period(fiscal_year, "q4")
                fy_start, fy_end = self._date_range_for_period(fiscal_year, "fy")
                add_period(
                    period_id=f"{fiscal_year}Q4_SINGLE",
                    scope="single_quarter",
                    fiscal_quarter=4,
                    start_date=q4_start,
                    end_date=q4_end,
                )
                add_period(
                    period_id=f"{fiscal_year}FY",
                    scope="full_year",
                    ytd_through_quarter=4,
                    start_date=fy_start,
                    end_date=fy_end,
                    is_primary=True,
                )
                add_period(
                    period_id=f"{fiscal_year - 1}FY",
                    scope="full_year",
                    ytd_through_quarter=4,
                    start_date=f"{fiscal_year - 1}-01-01",
                    end_date=f"{fiscal_year - 1}-12-31",
                    is_comparison=True,
                )
                add_balance_as_of_period(f"{fiscal_year}-12-31", is_primary=True)
                add_balance_as_of_period(
                    f"{fiscal_year - 1}-12-31", is_comparison=True
                )
                metadata.primary_period_id = f"{fiscal_year}FY"
                return periods

            if quarter_num == 1:
                q1_start, q1_end = self._date_range_for_period(fiscal_year, "q1")
                add_period(
                    period_id=f"{fiscal_year}Q1_YTD",
                    scope="year_to_date",
                    ytd_through_quarter=1,
                    start_date=q1_start,
                    end_date=q1_end,
                    is_primary=True,
                )
                add_balance_as_of_period(q1_end, is_primary=True)
                metadata.primary_period_id = f"{fiscal_year}Q1_YTD"
                return periods

            if quarter_num == 2:
                h1_start, h1_end = self._date_range_for_period(fiscal_year, "h1")
                q2_start, q2_end = self._date_range_for_period(fiscal_year, "q2")
                add_period(
                    period_id=f"{fiscal_year}H1_YTD",
                    scope="year_to_date",
                    ytd_through_quarter=2,
                    start_date=h1_start,
                    end_date=h1_end,
                    is_primary=True,
                )
                add_period(
                    period_id=f"{fiscal_year}Q2_SINGLE",
                    scope="single_quarter",
                    fiscal_quarter=2,
                    start_date=q2_start,
                    end_date=q2_end,
                )
                add_balance_as_of_period(h1_end, is_primary=True)
                metadata.primary_period_id = f"{fiscal_year}H1_YTD"
                return periods

            if quarter_num == 3:
                q3_ytd_start = f"{fiscal_year}-01-01"
                q3_ytd_end = f"{fiscal_year}-09-30"
                q3_start, q3_end = self._date_range_for_period(fiscal_year, "q3")
                add_period(
                    period_id=f"{fiscal_year}Q3_YTD",
                    scope="year_to_date",
                    ytd_through_quarter=3,
                    start_date=q3_ytd_start,
                    end_date=q3_ytd_end,
                    is_primary=True,
                )
                add_period(
                    period_id=f"{fiscal_year}Q3_SINGLE",
                    scope="single_quarter",
                    fiscal_quarter=3,
                    start_date=q3_start,
                    end_date=q3_end,
                )
                add_balance_as_of_period(q3_ytd_end, is_primary=True)
                metadata.primary_period_id = f"{fiscal_year}Q3_YTD"
                return periods

            if quarter_num == 4:
                q4_ytd_start = f"{fiscal_year}-01-01"
                q4_ytd_end = f"{fiscal_year}-12-31"
                q4_start, q4_end = self._date_range_for_period(fiscal_year, "q4")
                add_period(
                    period_id=f"{fiscal_year}Q4_YTD",
                    scope="year_to_date",
                    ytd_through_quarter=4,
                    start_date=q4_ytd_start,
                    end_date=q4_ytd_end,
                    is_primary=True,
                )
                add_period(
                    period_id=f"{fiscal_year}Q4_SINGLE",
                    scope="single_quarter",
                    fiscal_quarter=4,
                    start_date=q4_start,
                    end_date=q4_end,
                )
                add_balance_as_of_period(q4_ytd_end, is_primary=True)
                metadata.primary_period_id = f"{fiscal_year}Q4_YTD"
                return periods

        if metadata.report_type == "annual":
            fy_start, fy_end = self._date_range_for_period(fiscal_year, "fy")
            add_period(
                period_id=f"{fiscal_year}FY",
                scope="full_year",
                ytd_through_quarter=4,
                start_date=fy_start,
                end_date=fy_end,
                is_primary=True,
            )
            add_period(
                period_id=f"{fiscal_year - 1}FY",
                scope="full_year",
                ytd_through_quarter=4,
                start_date=f"{fiscal_year - 1}-01-01",
                end_date=f"{fiscal_year - 1}-12-31",
                is_comparison=True,
            )
            add_balance_as_of_period(f"{fiscal_year}-12-31", is_primary=True)
            add_balance_as_of_period(f"{fiscal_year - 1}-12-31", is_comparison=True)
            metadata.primary_period_id = f"{fiscal_year}FY"

        return periods

    @staticmethod
    def _build_document(metadata: ReportMetadata, periods: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构建统一文档层结构"""
        primary_period_id = metadata.primary_period_id
        if not primary_period_id:
            primary = next((period for period in periods if period.get("is_primary")), None)
            primary_period_id = primary.get("period_id") if primary else None

        return {
            "stock_code": metadata.stock_code,
            "stock_name": metadata.stock_name,
            "market": "HK" if metadata.stock_code and len(metadata.stock_code) <= 5 else None,
            "doc_type": metadata.doc_type,
            "fiscal_year": metadata.fiscal_year,
            "report_type": metadata.report_type,
            "period_type": metadata.period_type,
            "report_period": metadata.report_period,
            "primary_period_id": primary_period_id,
            "is_audited": metadata.is_audited,
        }

    def _add_runtime_issue(
        self,
        issue_type: str,
        severity: str,
        message: str,
        affected_facts: Optional[List[str]] = None,
        dedupe_key: Optional[str] = None,
    ) -> None:
        """记录运行时质量问题（提取过程中产生）"""
        if dedupe_key and dedupe_key in self._segment_skip_keys:
            return
        if dedupe_key:
            self._segment_skip_keys.add(dedupe_key)
        self._runtime_quality_issues.append(
            {
                "type": issue_type,
                "severity": severity,
                "message": message,
                "affected_facts": affected_facts or [],
            }
        )

    def _build_facts_evidence_quality(
        self,
        metadata: ReportMetadata,
        periods: List[Dict[str, Any]],
        income: IncomeStatement,
        balance: BalanceSheet,
        cash_flow: CashFlowStatement,
        metrics: FinancialMetrics,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """构建 facts/evidence/quality（V2）"""
        self.current_metadata = metadata
        self.current_periods = periods
        primary_period_id = metadata.primary_period_id
        comparison_period_ids = [
            p["period_id"] for p in periods if p.get("is_comparison") and p.get("period_id")
        ]
        balance_period_id = self._resolve_balance_period_id(periods, primary_period_id)
        observations = self._collect_table_metric_observations()
        evidence: List[Dict[str, Any]] = []
        evidence_key_to_id: Dict[Tuple[Any, ...], str] = {}
        fact_evidence_map: Dict[Tuple[str, str, str], List[str]] = {}
        facts: List[Dict[str, Any]] = []

        def to_fact_ref(statement: str, metric: str, period_id: str) -> str:
            return f"{statement}.{metric}@{period_id}"

        def ensure_evidence(obs: Dict[str, Any]) -> str:
            key = (
                obs["page"],
                obs["table_index"],
                obs["row_label"],
                obs.get("column_header"),
                obs.get("raw_value"),
            )
            existing_id = evidence_key_to_id.get(key)
            if existing_id:
                return existing_id

            evidence_id = f"ev_{len(evidence_key_to_id) + 1:04d}"
            evidence_key_to_id[key] = evidence_id
            evidence.append(
                {
                    "evidence_id": evidence_id,
                    "page": obs["page"],
                    "table_index": obs["table_index"],
                    "row_label": obs["row_label"],
                    "column_header": obs.get("column_header"),
                    "column_role": obs.get("column_role"),
                    "raw_value": obs.get("raw_value"),
                    "snippet": obs.get("snippet"),
                }
            )
            return evidence_id

        def select_primary_and_comparison_obs(
            metric_obs: List[Dict[str, Any]],
            target_value: float,
            *,
            prefer_max_abs: bool = False,
        ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
            if not metric_obs:
                return None, None
            primary_candidates = [
                item for item in metric_obs if not item.get("is_comparison_col", False)
            ]
            if not primary_candidates:
                primary_candidates = metric_obs
            if prefer_max_abs:
                sorted_primary = sorted(
                    primary_candidates,
                    key=lambda item: abs(item["value"]),
                    reverse=True,
                )
            else:
                sorted_primary = sorted(
                    primary_candidates,
                    key=lambda item: abs(item["value"] - target_value),
                )
            primary_obs = sorted_primary[0]

            primary_row_label = self._normalize_row_label(primary_obs.get("row_label", ""))
            same_row_candidates = [
                item
                for item in metric_obs
                if item is not primary_obs
                and self._normalize_row_label(item.get("row_label", "")) == primary_row_label
                and abs(item["value"] - primary_obs["value"]) > 1e-9
            ]
            if same_row_candidates:
                primary_page = primary_obs.get("page")
                primary_table = primary_obs.get("table_index")
                comparison_obs = sorted(
                    same_row_candidates,
                    key=lambda item: (
                        0
                        if item.get("page") == primary_page
                        and item.get("table_index") == primary_table
                        else 1,
                        abs(item["value"] - primary_obs["value"]),
                        0 if item.get("is_comparison_col", False) else 1,
                    ),
                )[0]
                return primary_obs, comparison_obs

            comparison_candidates = [
                item for item in metric_obs if item.get("is_comparison_col", False)
            ]
            if comparison_candidates:
                comparison_obs = sorted(
                    comparison_candidates,
                    key=lambda item: (
                        abs(item["value"] - primary_obs["value"]),
                        0 if item.get("is_comparison_col", False) else 1,
                    ),
                )[0]
            else:
                comparison_obs = None
                for candidate in sorted_primary[1:]:
                    if abs(candidate["value"] - primary_obs["value"]) > 1e-9:
                        comparison_obs = candidate
                        break
            return primary_obs, comparison_obs

        metric_specs: List[Tuple[str, str, Optional[float], str]] = [
            ("income_statement", "revenue", income.revenue, primary_period_id),
            ("income_statement", "operating_cost", income.operating_cost, primary_period_id),
            ("income_statement", "gross_profit", income.gross_profit, primary_period_id),
            ("income_statement", "operating_profit", income.operating_profit, primary_period_id),
            ("income_statement", "total_profit", income.total_profit, primary_period_id),
            ("income_statement", "net_profit", income.net_profit, primary_period_id),
            (
                "income_statement",
                "net_profit_attributable_to_parent",
                income.net_profit_attributable_to_parent,
                primary_period_id,
            ),
            ("income_statement", "net_profit_deducted", income.net_profit_deducted, primary_period_id),
            ("income_statement", "interest_expense", income.interest_expense, primary_period_id),
            ("income_statement", "rd_expense", income.rd_expense, primary_period_id),
            ("income_statement", "gross_margin", income.gross_margin, primary_period_id),
            ("income_statement", "net_margin", income.net_margin, primary_period_id),
            ("balance_sheet", "total_assets", balance.total_assets, balance_period_id),
            ("balance_sheet", "current_assets", balance.current_assets, balance_period_id),
            (
                "balance_sheet",
                "cash_and_equivalents",
                balance.cash_and_equivalents,
                balance_period_id,
            ),
            (
                "balance_sheet",
                "accounts_receivable",
                balance.accounts_receivable,
                balance_period_id,
            ),
            ("balance_sheet", "inventory", balance.inventory, balance_period_id),
            ("balance_sheet", "fixed_assets", balance.fixed_assets, balance_period_id),
            ("balance_sheet", "goodwill", balance.goodwill, balance_period_id),
            ("balance_sheet", "intangible_assets", balance.intangible_assets, balance_period_id),
            ("balance_sheet", "total_liabilities", balance.total_liabilities, balance_period_id),
            (
                "balance_sheet",
                "current_liabilities",
                balance.current_liabilities,
                balance_period_id,
            ),
            ("balance_sheet", "short_term_debt", balance.short_term_debt, balance_period_id),
            ("balance_sheet", "long_term_debt", balance.long_term_debt, balance_period_id),
            ("balance_sheet", "bonds_payable", balance.bonds_payable, balance_period_id),
            ("balance_sheet", "total_equity", balance.total_equity, balance_period_id),
            (
                "balance_sheet",
                "equity_attributable_to_parent",
                balance.equity_attributable_to_parent,
                balance_period_id,
            ),
            (
                "cash_flow_statement",
                "operating_cash_flow",
                cash_flow.operating_cash_flow,
                primary_period_id,
            ),
            (
                "cash_flow_statement",
                "investing_cash_flow",
                cash_flow.investing_cash_flow,
                primary_period_id,
            ),
            (
                "cash_flow_statement",
                "financing_cash_flow",
                cash_flow.financing_cash_flow,
                primary_period_id,
            ),
            (
                "cash_flow_statement",
                "capital_expenditure",
                cash_flow.capital_expenditure,
                primary_period_id,
            ),
            ("cash_flow_statement", "free_cash_flow", cash_flow.free_cash_flow, primary_period_id),
            ("financial_metrics", "eps", metrics.eps, primary_period_id),
            ("financial_metrics", "eps_diluted", metrics.eps_diluted, primary_period_id),
            ("financial_metrics", "bps", metrics.bps, primary_period_id),
            (
                "financial_metrics",
                "dividend_per_share",
                metrics.dividend_per_share,
                primary_period_id,
            ),
            ("financial_metrics", "roe", metrics.roe, primary_period_id),
            ("financial_metrics", "roa", metrics.roa, primary_period_id),
            ("financial_metrics", "debt_ratio", metrics.debt_ratio, primary_period_id),
            ("financial_metrics", "current_ratio", metrics.current_ratio, primary_period_id),
            ("financial_metrics", "quick_ratio", metrics.quick_ratio, primary_period_id),
            ("financial_metrics", "total_shares", metrics.total_shares, primary_period_id),
        ]

        for statement, metric, value, period_id in metric_specs:
            if value is None or not period_id:
                continue

            metric_obs_all = observations.get((statement, metric), [])
            allowed_roles = self._allowed_column_roles_for_period(
                periods=periods,
                period_id=period_id,
                statement=statement,
            )
            strict_allowed_roles = {role for role in allowed_roles if role != "unknown"}
            strict_metric_obs = [
                obs
                for obs in metric_obs_all
                if obs.get("column_role", "unknown") in strict_allowed_roles
            ]
            if strict_metric_obs:
                # 保留严格角色列作为主值候选，同时补入 unknown 且标记为对比列的候选，
                # 以处理英文表格中“日期列有角色、相邻数据列为 unknown”的常见结构。
                supplemental_comparison_obs = [
                    obs
                    for obs in metric_obs_all
                    if obs.get("column_role", "unknown") == "unknown"
                    and obs.get("is_comparison_col", False)
                ]
                metric_obs = strict_metric_obs + supplemental_comparison_obs
            else:
                metric_obs = [
                    obs
                    for obs in metric_obs_all
                    if obs.get("column_role", "unknown") in allowed_roles
                ]
                if not metric_obs:
                    metric_obs = metric_obs_all
            primary_obs, comparison_obs = select_primary_and_comparison_obs(
                metric_obs, value, prefer_max_abs=bool(strict_metric_obs)
            )

            evidence_ids: List[str] = []
            if primary_obs:
                evidence_ids.append(ensure_evidence(primary_obs))
            fact_key = (statement, metric, period_id)
            fact_evidence_map[fact_key] = evidence_ids

            is_derived = (statement, metric) in self._derived_fact_keys
            derivation_formula = self._get_derivation_formula(statement, metric)
            selected_value = value
            # 当列角色可明确识别时，优先使用表格主列值，避免文本/兜底路径误取。
            if not is_derived and primary_obs and strict_metric_obs:
                selected_value = primary_obs["value"]
            if is_derived:
                dependencies = self._get_derivation_dependencies(statement, metric)
                inherited: List[str] = []
                for dep_statement, dep_metric in dependencies:
                    dep_key = (dep_statement, dep_metric, period_id)
                    inherited.extend(fact_evidence_map.get(dep_key, []))
                evidence_ids = list(dict.fromkeys(evidence_ids + inherited))
                fact_evidence_map[fact_key] = evidence_ids

            fact_currency, fact_unit = self._get_fact_currency_unit(metadata, metric)
            source_method = (
                "derived" if is_derived else ("table" if evidence_ids else "text_regex")
            )
            if is_derived:
                confidence = 1.0
            elif evidence_ids:
                confidence = 0.96
                if primary_obs and primary_obs.get("column_role") not in allowed_roles:
                    confidence = 0.85
            else:
                confidence = 0.75
            facts.append(
                {
                    "statement": statement,
                    "metric": metric,
                    "period_id": period_id,
                    "value": selected_value,
                    "currency": fact_currency,
                    "unit": fact_unit,
                    "source_method": source_method,
                    "confidence": confidence,
                    "evidence_ids": evidence_ids,
                    "is_derived": is_derived,
                    "derivation_formula": derivation_formula,
                }
            )

            # 对同比列追加 comparison facts（仅核心指标）
            if comparison_period_ids and comparison_obs and metric in {
                "revenue",
                "net_profit",
                "operating_cash_flow",
            }:
                comparison_period_id = comparison_period_ids[0]
                comparison_fact_key = (statement, metric, comparison_period_id)
                if comparison_fact_key not in fact_evidence_map:
                    comparison_evidence_id = ensure_evidence(comparison_obs)
                    fact_evidence_map[comparison_fact_key] = [comparison_evidence_id]
                    facts.append(
                        {
                            "statement": statement,
                            "metric": metric,
                            "period_id": comparison_period_id,
                            "value": comparison_obs["value"],
                            "currency": fact_currency,
                            "unit": fact_unit,
                            "source_method": "table",
                            "confidence": 0.95 if comparison_obs.get("is_comparison_col", False) else 0.85,
                            "evidence_ids": [comparison_evidence_id],
                            "is_derived": False,
                            "derivation_formula": None,
                        }
                    )

        # 若期间定义包含单季度，补充 single_quarter 指标（例如 Q3_SINGLE / Q4_SINGLE）
        single_period = next(
            (
                p
                for p in periods
                if p.get("scope") == "single_quarter" and not p.get("is_comparison")
            ),
            None,
        )
        if single_period:
            single_period_id = single_period.get("period_id")
            if single_period_id:
                existing_fact_keys = {
                    (fact.get("statement"), fact.get("metric"), fact.get("period_id"))
                    for fact in facts
                }
                single_metric_keys: List[Tuple[str, str]] = [
                    ("income_statement", "revenue"),
                    ("income_statement", "operating_cost"),
                    ("income_statement", "gross_profit"),
                    ("income_statement", "operating_profit"),
                    ("income_statement", "total_profit"),
                    ("income_statement", "net_profit"),
                    ("income_statement", "net_profit_attributable_to_parent"),
                    ("income_statement", "net_profit_deducted"),
                    ("income_statement", "interest_expense"),
                    ("income_statement", "rd_expense"),
                    ("financial_metrics", "eps"),
                    ("financial_metrics", "eps_diluted"),
                ]

                for statement, metric in single_metric_keys:
                    fact_key = (statement, metric, single_period_id)
                    if fact_key in existing_fact_keys:
                        continue

                    metric_obs = [
                        obs
                        for obs in observations.get((statement, metric), [])
                        if obs.get("column_role") == "single_q"
                    ]
                    if not metric_obs:
                        continue

                    metric_obs_sorted = sorted(
                        metric_obs,
                        key=lambda item: (
                            1 if item.get("is_comparison_col", False) else 0,
                            -abs(item["value"]),
                        ),
                    )
                    chosen_obs = metric_obs_sorted[0]
                    evidence_id = ensure_evidence(chosen_obs)
                    fact_evidence_map[fact_key] = [evidence_id]
                    existing_fact_keys.add(fact_key)
                    fact_currency, fact_unit = self._get_fact_currency_unit(metadata, metric)
                    facts.append(
                        {
                            "statement": statement,
                            "metric": metric,
                            "period_id": single_period_id,
                            "value": chosen_obs["value"],
                            "currency": fact_currency,
                            "unit": fact_unit,
                            "source_method": "table",
                            "confidence": 0.9,
                            "evidence_ids": [evidence_id],
                            "is_derived": False,
                            "derivation_formula": None,
                        }
                    )

        issues: List[Dict[str, Any]] = []
        for fact in facts:
            if not fact["is_derived"] and not fact["evidence_ids"]:
                issues.append(
                    {
                        "type": "unit_inferred",
                        "severity": "warning",
                        "message": (
                            f"{fact['statement']}.{fact['metric']} 使用文本回退提取，缺少表格证据。"
                        ),
                        "affected_facts": [
                            to_fact_ref(
                                fact["statement"],
                                fact["metric"],
                                fact["period_id"],
                            )
                        ],
                    }
                )
            if (
                not fact["is_derived"]
                and fact["evidence_ids"]
                and fact["confidence"] < 0.9
            ):
                issues.append(
                    {
                        "type": "period_ambiguous",
                        "severity": "warning",
                        "message": (
                            f"{fact['statement']}.{fact['metric']} 列定位不够明确，已降置信度。"
                        ),
                        "affected_facts": [
                            to_fact_ref(
                                fact["statement"],
                                fact["metric"],
                                fact["period_id"],
                            )
                        ],
                    }
                )

        if comparison_period_ids:
            comparison_period_id = comparison_period_ids[0]
            required_comparison = [
                ("income_statement", "revenue"),
                ("income_statement", "net_profit"),
                ("cash_flow_statement", "operating_cash_flow"),
            ]
            missing = []
            for statement, metric in required_comparison:
                matched = any(
                    fact["statement"] == statement
                    and fact["metric"] == metric
                    and fact["period_id"] == comparison_period_id
                    for fact in facts
                )
                if not matched:
                    missing.append(f"{statement}.{metric}@{comparison_period_id}")
            if missing:
                issues.append(
                    {
                        "type": "period_ambiguous",
                        "severity": "warning",
                        "message": "未完整提取同比列核心指标。",
                        "affected_facts": missing,
                    }
                )

        issues.extend(self._build_cross_check_issues(facts))
        issues.extend(self._runtime_quality_issues)

        quality_status = "ok"
        if any(issue["severity"] == "error" for issue in issues):
            quality_status = "review"
        elif issues:
            quality_status = "partial"

        quality = {
            "status": quality_status,
            "issues": issues,
        }
        return facts, evidence, quality

    def _build_cross_check_issues(self, facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """构建交叉校验问题（cross_check_failed）"""
        fact_map: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for fact in facts:
            key = (fact.get("statement"), fact.get("metric"), fact.get("period_id"))
            fact_map[key] = fact

        period_ids = sorted({fact.get("period_id") for fact in facts if fact.get("period_id")})
        issues: List[Dict[str, Any]] = []

        for period_id in period_ids:
            # EPS * shares ≈ net_profit
            eps = fact_map.get(("financial_metrics", "eps", period_id))
            shares = fact_map.get(("financial_metrics", "total_shares", period_id))
            net_profit = fact_map.get(("income_statement", "net_profit", period_id))
            if eps and shares and net_profit:
                try:
                    expected = float(eps["value"]) * float(shares["value"])
                    actual = float(net_profit["value"])
                    if abs(actual) > 1e-6:
                        deviation = abs(expected - actual) / abs(actual)
                        if deviation > 0.2:
                            issues.append(
                                {
                                    "type": "cross_check_failed",
                                    "severity": "warning",
                                    "message": (
                                        "EPS × shares 与 net_profit 偏差过大。"
                                        f" period={period_id}, deviation={deviation:.2%}"
                                    ),
                                    "affected_facts": [
                                        f"financial_metrics.eps@{period_id}",
                                        f"financial_metrics.total_shares@{period_id}",
                                        f"income_statement.net_profit@{period_id}",
                                    ],
                                }
                            )
                except (TypeError, ValueError):
                    pass

            # gross_margin ≈ gross_profit / revenue * 100
            gross_profit = fact_map.get(("income_statement", "gross_profit", period_id))
            revenue = fact_map.get(("income_statement", "revenue", period_id))
            gross_margin = fact_map.get(("income_statement", "gross_margin", period_id))
            if gross_profit and revenue and gross_margin:
                try:
                    if abs(float(revenue["value"])) > 1e-6:
                        computed = float(gross_profit["value"]) / float(revenue["value"]) * 100
                        actual_margin = float(gross_margin["value"])
                        if abs(computed - actual_margin) > 3.0:
                            issues.append(
                                {
                                    "type": "cross_check_failed",
                                    "severity": "warning",
                                    "message": (
                                        "gross_margin 与 gross_profit/revenue 不一致。"
                                        f" period={period_id}, delta={abs(computed - actual_margin):.2f}pp"
                                    ),
                                    "affected_facts": [
                                        f"income_statement.gross_profit@{period_id}",
                                        f"income_statement.revenue@{period_id}",
                                        f"income_statement.gross_margin@{period_id}",
                                    ],
                                }
                            )
                except (TypeError, ValueError, ZeroDivisionError):
                    pass

            # free_cash_flow ≈ operating_cash_flow - capital_expenditure
            op_cf = fact_map.get(("cash_flow_statement", "operating_cash_flow", period_id))
            capex = fact_map.get(("cash_flow_statement", "capital_expenditure", period_id))
            fcf = fact_map.get(("cash_flow_statement", "free_cash_flow", period_id))
            if op_cf and capex and fcf:
                try:
                    computed_fcf = float(op_cf["value"]) - float(capex["value"])
                    actual_fcf = float(fcf["value"])
                    base = max(abs(actual_fcf), 1.0)
                    deviation = abs(computed_fcf - actual_fcf) / base
                    if deviation > 0.1:
                        issues.append(
                            {
                                "type": "cross_check_failed",
                                "severity": "warning",
                                "message": (
                                    "free_cash_flow 与 operating_cash_flow-capital_expenditure 不一致。"
                                    f" period={period_id}, deviation={deviation:.2%}"
                                ),
                                "affected_facts": [
                                    f"cash_flow_statement.operating_cash_flow@{period_id}",
                                    f"cash_flow_statement.capital_expenditure@{period_id}",
                                    f"cash_flow_statement.free_cash_flow@{period_id}",
                                ],
                            }
                        )
                except (TypeError, ValueError):
                    pass

        return issues

    def _resolve_balance_period_id(
        self, periods: List[Dict[str, Any]], fallback_period_id: Optional[str]
    ) -> Optional[str]:
        """资产负债表优先绑定时点期间"""
        primary_point = next(
            (
                p
                for p in periods
                if p.get("scope") == "point_in_time" and p.get("is_primary")
            ),
            None,
        )
        if primary_point:
            return primary_point.get("period_id")
        any_point = next((p for p in periods if p.get("scope") == "point_in_time"), None)
        if any_point:
            return any_point.get("period_id")
        return fallback_period_id

    def _get_fact_currency_unit(
        self, metadata: ReportMetadata, metric: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """根据指标类型返回 currency / unit"""
        percent_metrics = {"gross_margin", "net_margin", "roe", "roa", "debt_ratio"}
        ratio_metrics = {"current_ratio", "quick_ratio"}
        per_share_metrics = {"eps", "eps_diluted", "bps", "dividend_per_share"}
        share_metrics = {"total_shares"}

        if metric in percent_metrics:
            return None, "percent"
        if metric in ratio_metrics:
            return None, "ratio"
        if metric in per_share_metrics:
            return metadata.per_share_currency or metadata.currency, "per_share"
        if metric in share_metrics:
            return None, "shares"
        return metadata.currency, metadata.amount_unit

    @staticmethod
    def _get_derivation_formula(statement: str, metric: str) -> Optional[str]:
        formulas = {
            ("income_statement", "operating_cost"): "operating_cost = revenue - gross_profit",
            ("income_statement", "gross_profit"): "gross_profit = revenue - operating_cost",
            ("income_statement", "gross_margin"): "gross_margin = gross_profit / revenue * 100",
            ("income_statement", "net_margin"): "net_margin = net_profit / revenue * 100",
            ("financial_metrics", "debt_ratio"): "debt_ratio = total_liabilities / total_assets * 100",
            ("financial_metrics", "current_ratio"): "current_ratio = current_assets / current_liabilities",
            ("financial_metrics", "quick_ratio"): "quick_ratio = (current_assets - inventory) / current_liabilities",
            ("financial_metrics", "roa"): "roa = net_profit / total_assets * 100",
            ("financial_metrics", "roe"): "roe = net_profit / equity * 100",
            ("cash_flow_statement", "free_cash_flow"): "free_cash_flow = operating_cash_flow - capital_expenditure",
            ("financial_metrics", "bps"): "bps = total_equity / total_shares",
            ("financial_metrics", "total_shares"): "total_shares = net_profit / eps",
        }
        return formulas.get((statement, metric))

    @staticmethod
    def _get_derivation_dependencies(
        statement: str, metric: str
    ) -> List[Tuple[str, str]]:
        dependencies = {
            ("income_statement", "operating_cost"): [
                ("income_statement", "revenue"),
                ("income_statement", "gross_profit"),
            ],
            ("income_statement", "gross_profit"): [
                ("income_statement", "revenue"),
                ("income_statement", "operating_cost"),
            ],
            ("income_statement", "gross_margin"): [
                ("income_statement", "gross_profit"),
                ("income_statement", "revenue"),
            ],
            ("income_statement", "net_margin"): [
                ("income_statement", "net_profit"),
                ("income_statement", "revenue"),
            ],
            ("financial_metrics", "debt_ratio"): [
                ("balance_sheet", "total_liabilities"),
                ("balance_sheet", "total_assets"),
            ],
            ("financial_metrics", "current_ratio"): [
                ("balance_sheet", "current_assets"),
                ("balance_sheet", "current_liabilities"),
            ],
            ("financial_metrics", "quick_ratio"): [
                ("balance_sheet", "current_assets"),
                ("balance_sheet", "inventory"),
                ("balance_sheet", "current_liabilities"),
            ],
            ("financial_metrics", "roa"): [
                ("income_statement", "net_profit"),
                ("balance_sheet", "total_assets"),
            ],
            ("financial_metrics", "roe"): [
                ("income_statement", "net_profit"),
                ("balance_sheet", "total_equity"),
            ],
            ("cash_flow_statement", "free_cash_flow"): [
                ("cash_flow_statement", "operating_cash_flow"),
                ("cash_flow_statement", "capital_expenditure"),
            ],
            ("financial_metrics", "bps"): [
                ("balance_sheet", "total_equity"),
                ("financial_metrics", "total_shares"),
            ],
            ("financial_metrics", "total_shares"): [
                ("income_statement", "net_profit"),
                ("financial_metrics", "eps"),
            ],
        }
        return dependencies.get((statement, metric), [])

    def _collect_table_metric_observations(
        self,
    ) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
        """扫描表格并采集指标证据候选"""
        keyword_map = self._get_metric_keyword_map()
        observations: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

        for table_idx, table in enumerate(self.tables):
            if not table:
                continue
            table_statement = self._classify_table_statement(table)
            if self.is_english_report and self._is_segment_operating_table(table):
                page, tb_idx = (
                    self.table_locations[table_idx]
                    if table_idx < len(self.table_locations)
                    else (None, table_idx + 1)
                )
                self._add_runtime_issue(
                    issue_type="segment_table_skipped",
                    severity="warning",
                    message=(
                        "检测到分部经营表，已跳过以避免误提取。"
                        f" page={page}, table={tb_idx}"
                    ),
                    dedupe_key=f"segment:{page}:{tb_idx}",
                )
                continue
            page, table_index = self.table_locations[table_idx] if table_idx < len(
                self.table_locations
            ) else (None, table_idx + 1)
            column_profiles = self._build_table_column_profiles(table)

            for row in table:
                if not row:
                    continue
                row_label = str(row[0]).replace("\n", " ").strip() if row[0] else ""
                if not row_label:
                    continue
                snippet = " ".join(
                    str(cell).replace("\n", " ").strip()
                    for cell in row[:4]
                    if cell
                )[:200]

                for key, keywords in keyword_map.items():
                    statement, metric = key
                    if table_statement in {
                        "income_statement",
                        "balance_sheet",
                        "cash_flow_statement",
                    } and statement != table_statement:
                        continue
                    if table_statement == "financial_metrics" and statement != "financial_metrics":
                        continue
                    if not self._row_label_matches_metric(metric, row_label, keywords):
                        continue

                    min_abs = self._get_metric_min_abs(metric)
                    for col_index in range(1, len(row)):
                        raw_value = row[col_index]
                        value = self._parse_number(
                            str(raw_value).replace("\n", " ").strip() if raw_value else ""
                        )
                        if value is None:
                            continue
                        if abs(value) < min_abs:
                            continue

                        profile = column_profiles.get(col_index, {})
                        column_header = profile.get("column_header")
                        observation = {
                            "page": page,
                            "table_index": table_index,
                            "row_label": row_label,
                            "column_header": column_header,
                            "column_role": profile.get("column_role", "unknown"),
                            "column_year": profile.get("column_year"),
                            "is_comparison_col": profile.get("is_comparison_col", False),
                            "raw_value": str(raw_value).strip() if raw_value is not None else None,
                            "value": value,
                            "snippet": snippet,
                        }
                        observations.setdefault(key, []).append(observation)
        return observations

    def _normalize_row_label(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        normalized = normalized.replace("（", "(").replace("）", ")")
        normalized = normalized.replace("–", "-").replace("—", "-")
        return normalized

    def _row_label_matches_metric(
        self, metric: str, row_label: str, keywords: List[str]
    ) -> bool:
        normalized = self._normalize_row_label(row_label)
        blacklist = {
            "revenue": [
                "company sales",
                "other revenue",
                "other revenues",
                "other operating revenue",
                "excluding the impact of f/x",
                "deferred revenue",
                "unearned revenue",
                "interest revenue",
                "investment revenue",
                "franchise fees",
                "franchisee",
                "其他收益",
                "其他业务收入",
                "递延收入",
                "利息收入",
            ],
            "net_profit_attributable_to_parent": [
                "noncontrolling",
                "non-controlling",
                "minority interests",
                "非控股",
                "少数股东",
            ],
            "cash_and_equivalents": [
                "restricted cash",
                "pledged deposits",
                "time deposits",
                "受限制现金",
                "受限货币资金",
                "受限制銀行存款",
                "抵押存款",
            ],
            "accounts_receivable": [
                "other receivables",
                "receivables financing",
                "due from related parties",
                "其他应收",
                "应收关联方",
                "应收款项融资",
            ],
            "operating_cash_flow": [
                "before changes in working capital",
                "excluding working capital",
                "未计营运资金变动",
                "營運資金變動前",
            ],
            "total_equity": ["net profit", "净利润"],
            "operating_cost": ["sales and marketing", "selling expenses", "销售费用"],
            "operating_profit": [
                "core operating profit",
                "adjusted operating profit",
            ],
            "net_profit": [
                "noncontrolling",
                "non-controlling",
                "minority interests",
                "非控股",
                "少数股东",
                "net profit margin",
                "profit ratio",
                "adjusted net income",
            ],
        }
        if any(token in normalized for token in blacklist.get(metric, [])):
            return False

        for keyword in keywords:
            normalized_keyword = self._normalize_row_label(keyword)
            if self.is_english_report:
                pattern = rf"(^|[^a-z0-9]){re.escape(normalized_keyword)}([^a-z0-9]|$)"
                if re.search(pattern, normalized):
                    return True
            elif normalized_keyword in normalized:
                return True
        return False

    def _is_segment_operating_table(self, table: List[List[Any]]) -> bool:
        """识别英文报告中的分部经营表（如 KFC/Pizza Hut 分部列）"""
        if not self.is_english_report:
            return False

        header_text = " ".join(
            str(cell).replace("\n", " ").lower()
            for row in table[:6]
            for cell in row
            if cell
        )

        if "segment results" in header_text:
            return True
        if "kfc operating results" in header_text or "pizza hut operating results" in header_text:
            return True
        if "kfc" in header_text and "pizza hut" in header_text:
            return True
        if "all other segments" in header_text:
            return True
        return False

    def _classify_table_statement(self, table: List[List[Any]]) -> str:
        table_text = " ".join(
            str(cell).replace("\n", " ").lower()
            for row in table[:8]
            for cell in row
            if cell
        )

        cash_keywords = [
            "cash flow",
            "cash flows",
            "现金流量",
            "現金流量",
        ]
        balance_keywords = [
            "balance sheet",
            "financial position",
            "assets and liabilities",
            "资产负债",
            "財務狀況",
        ]
        income_keywords = [
            "income statement",
            "statement of income",
            "profit or loss",
            "营收",
            "损益",
            "收益",
            "业绩",
            "業績",
        ]
        metric_keywords = [
            "financial highlights",
            "key financial",
            "主要财务指标",
            "主要財務指標",
        ]

        if any(token in table_text for token in cash_keywords):
            return "cash_flow_statement"
        if any(token in table_text for token in balance_keywords):
            return "balance_sheet"
        if any(token in table_text for token in income_keywords):
            return "income_statement"
        if any(token in table_text for token in metric_keywords):
            return "financial_metrics"
        return "unknown"

    def _iter_tables_for_statement(
        self, statement: str
    ) -> List[Tuple[List[List[Any]], Optional[int]]]:
        matched: List[Tuple[List[List[Any]], Optional[int]]] = []
        unknown: List[Tuple[List[List[Any]], Optional[int]]] = []
        all_tables: List[Tuple[List[List[Any]], Optional[int]]] = []
        for table_idx, table in enumerate(self.tables):
            if not table:
                continue
            matched_statement = self._classify_table_statement(table)
            year_end_index = (
                self._get_table_year_end_index(table) if self.is_english_report else None
            )
            all_tables.append((table, year_end_index))
            if matched_statement == statement:
                matched.append((table, year_end_index))
            elif matched_statement == "unknown":
                unknown.append((table, year_end_index))
        if matched:
            return matched
        if unknown:
            return unknown
        return all_tables if statement == "financial_metrics" else []

    def _build_table_column_profiles(
        self, table: List[List[Any]]
    ) -> Dict[int, Dict[str, Any]]:
        profiles: Dict[int, Dict[str, Any]] = {}
        header_rows = table[: min(3, len(table))]
        max_col = max((len(row) for row in header_rows if row), default=0)
        last_non_empty_header = ""
        for col_index in range(1, max_col):
            header_parts: List[str] = []
            for row in header_rows:
                if col_index < len(row) and row[col_index]:
                    header_parts.append(str(row[col_index]).replace("\n", " ").strip())
            header_text = " ".join(part for part in header_parts if part).strip()
            if not header_text and last_non_empty_header:
                header_text = last_non_empty_header
            if header_text:
                last_non_empty_header = header_text
            column_year = self._infer_column_year(header_text)
            role = self._infer_column_role(header_text)
            is_comparison_col = False
            if "comparative" in header_text.lower() or "corresponding" in header_text.lower():
                is_comparison_col = True
            if (
                column_year is not None
                and self.current_metadata
                and self.current_metadata.fiscal_year
                and column_year < self.current_metadata.fiscal_year
            ):
                is_comparison_col = True
            profiles[col_index] = {
                "column_header": header_text or None,
                "column_year": column_year,
                "column_role": role,
                "is_comparison_col": is_comparison_col,
            }
        return profiles

    @staticmethod
    def _infer_column_year(header_text: str) -> Optional[int]:
        match = re.search(r"(20\d{2})", header_text)
        if match:
            return int(match.group(1))
        return None

    def _infer_column_role(self, header_text: str) -> str:
        text = header_text.lower()
        if not text.strip():
            return "unknown"
        if any(token in text for token in ["as at", "as of"]):
            return "point_in_time"
        if any(
            token in text
            for token in [
                "three months",
                "3 months",
                "quarter ended",
                "single quarter",
                "本季度",
                "单季",
                "單季",
                "三个月",
                "三個月",
            ]
        ):
            return "single_q"
        if any(
            token in text
            for token in [
                "nine months",
                "9 months",
                "six months",
                "6 months",
                "year to date",
                "year to date ended",
                "year-to-date",
                "ytd",
                "cumulative",
                "累计",
                "累計",
                "年初至今",
                "九个月",
                "九個月",
                "半年",
                "六个月",
                "六個月",
            ]
        ):
            return "ytd"
        if any(
            token in text
            for token in [
                "year ended",
                "full year",
                "12 months",
                "annual",
                "全年",
                "年度",
            ]
        ):
            return "full_year"
        if any(token in text for token in ["截至", "於", "于"]):
            return "point_in_time"
        return "unknown"

    def _get_period_by_id(
        self, periods: List[Dict[str, Any]], period_id: str
    ) -> Optional[Dict[str, Any]]:
        for period in periods:
            if period.get("period_id") == period_id:
                return period
        return None

    def _allowed_column_roles_for_period(
        self,
        periods: List[Dict[str, Any]],
        period_id: Optional[str],
        statement: str,
    ) -> Set[str]:
        if not period_id:
            return {"unknown", "full_year", "ytd", "single_q", "point_in_time"}
        period = self._get_period_by_id(periods, period_id)
        if not period:
            return {"unknown", "full_year", "ytd", "single_q", "point_in_time"}
        scope = period.get("scope")
        if statement == "balance_sheet":
            return {"point_in_time", "unknown"}
        if scope == "single_quarter":
            return {"single_q", "unknown"}
        if scope == "year_to_date":
            return {"ytd", "unknown"}
        if scope == "full_year":
            return {"full_year", "unknown"}
        if scope == "point_in_time":
            return {"point_in_time", "unknown"}
        return {"unknown", "full_year", "ytd", "single_q", "point_in_time"}

    def _get_metric_keyword_map(self) -> Dict[Tuple[str, str], List[str]]:
        """statement.metric 到表格关键字映射"""
        if self.is_english_report:
            return {
                ("income_statement", "revenue"): self.TABLE_KEYWORDS_EN.get("revenue", []),
                ("income_statement", "operating_cost"): self.TABLE_KEYWORDS_EN.get("operating_cost", []),
                ("income_statement", "gross_profit"): self.TABLE_KEYWORDS_EN.get("gross_profit", []),
                ("income_statement", "operating_profit"): self.TABLE_KEYWORDS_EN.get("operating_profit", []),
                ("income_statement", "total_profit"): self.TABLE_KEYWORDS_EN.get("total_profit", []),
                ("income_statement", "net_profit"): self.TABLE_KEYWORDS_EN.get("net_profit", []),
                ("income_statement", "net_profit_attributable_to_parent"): [
                    "Profit attributable to",
                    "Net income attributable to",
                ],
                ("income_statement", "interest_expense"): self.TABLE_KEYWORDS_EN.get("interest_expense", []),
                ("income_statement", "rd_expense"): self.TABLE_KEYWORDS_EN.get("rd_expense", []),
                ("cash_flow_statement", "operating_cash_flow"): self.TABLE_KEYWORDS_EN.get("operating_cash_flow", []),
                ("cash_flow_statement", "investing_cash_flow"): self.TABLE_KEYWORDS_EN.get("investing_cash_flow", []),
                ("cash_flow_statement", "financing_cash_flow"): self.TABLE_KEYWORDS_EN.get("financing_cash_flow", []),
                ("cash_flow_statement", "capital_expenditure"): self.TABLE_KEYWORDS_EN.get("capital_expenditure", []),
                ("balance_sheet", "total_assets"): self.TABLE_KEYWORDS_EN.get("total_assets", []),
                ("balance_sheet", "current_assets"): self.TABLE_KEYWORDS_EN.get("current_assets", []),
                ("balance_sheet", "cash_and_equivalents"): self.TABLE_KEYWORDS_EN.get("cash_and_equivalents", []),
                ("balance_sheet", "accounts_receivable"): self.TABLE_KEYWORDS_EN.get("accounts_receivable", []),
                ("balance_sheet", "inventory"): self.TABLE_KEYWORDS_EN.get("inventory", []),
                ("balance_sheet", "fixed_assets"): self.TABLE_KEYWORDS_EN.get("fixed_assets", []),
                ("balance_sheet", "goodwill"): self.TABLE_KEYWORDS_EN.get("goodwill", []),
                ("balance_sheet", "intangible_assets"): self.TABLE_KEYWORDS_EN.get("intangible_assets", []),
                ("balance_sheet", "total_liabilities"): self.TABLE_KEYWORDS_EN.get("total_liabilities", []),
                ("balance_sheet", "current_liabilities"): self.TABLE_KEYWORDS_EN.get("current_liabilities", []),
                ("balance_sheet", "short_term_debt"): self.TABLE_KEYWORDS_EN.get("short_term_debt", []),
                ("balance_sheet", "long_term_debt"): self.TABLE_KEYWORDS_EN.get("long_term_debt", []),
                ("balance_sheet", "bonds_payable"): self.TABLE_KEYWORDS_EN.get("bonds_payable", []),
                ("balance_sheet", "total_equity"): self.TABLE_KEYWORDS_EN.get("total_equity", []),
                ("financial_metrics", "eps"): self.TABLE_KEYWORDS_EN.get("eps", []),
                ("financial_metrics", "eps_diluted"): self.TABLE_KEYWORDS_EN.get("eps_diluted", []),
                ("financial_metrics", "bps"): self.TABLE_KEYWORDS_EN.get("bps", []),
                ("financial_metrics", "dividend_per_share"): self.TABLE_KEYWORDS_EN.get("dividend_per_share", []),
                ("financial_metrics", "roe"): self.TABLE_KEYWORDS_EN.get("roe", []),
                ("financial_metrics", "current_ratio"): self.TABLE_KEYWORDS_EN.get("current_ratio", []),
                ("financial_metrics", "quick_ratio"): self.TABLE_KEYWORDS_EN.get("quick_ratio", []),
            }

        return {
            ("income_statement", "revenue"): ["营业收入", "营业总收入"],
            ("income_statement", "operating_cost"): ["营业成本", "营业总成本"],
            ("income_statement", "gross_profit"): ["毛利", "毛利润"],
            ("income_statement", "operating_profit"): ["营业利润"],
            ("income_statement", "total_profit"): ["利润总额", "税前利润"],
            ("income_statement", "net_profit"): ["净利润", "归属于母公司股东的净利润"],
            ("income_statement", "net_profit_attributable_to_parent"): ["归属于母公司股东的净利润"],
            ("income_statement", "net_profit_deducted"): ["扣非净利润", "扣除非经常性损益后的净利润"],
            ("income_statement", "interest_expense"): ["财务费用", "利息支出"],
            ("income_statement", "rd_expense"): ["研发费用", "研发支出"],
            ("cash_flow_statement", "operating_cash_flow"): ["经营活动产生的现金流量净额"],
            ("cash_flow_statement", "investing_cash_flow"): ["投资活动产生的现金流量净额"],
            ("cash_flow_statement", "financing_cash_flow"): ["筹资活动产生的现金流量净额"],
            ("cash_flow_statement", "capital_expenditure"): ["购建固定资产、无形资产和其他长期资产支付的现金"],
            ("balance_sheet", "total_assets"): ["资产总计", "总资产"],
            ("balance_sheet", "current_assets"): ["流动资产合计"],
            ("balance_sheet", "cash_and_equivalents"): ["货币资金"],
            ("balance_sheet", "accounts_receivable"): ["应收账款"],
            ("balance_sheet", "inventory"): ["存货"],
            ("balance_sheet", "fixed_assets"): ["固定资产"],
            ("balance_sheet", "goodwill"): ["商誉"],
            ("balance_sheet", "intangible_assets"): ["无形资产"],
            ("balance_sheet", "total_liabilities"): ["负债合计", "总负债"],
            ("balance_sheet", "current_liabilities"): ["流动负债合计"],
            ("balance_sheet", "short_term_debt"): ["短期借款"],
            ("balance_sheet", "long_term_debt"): ["长期借款"],
            ("balance_sheet", "bonds_payable"): ["应付债券"],
            ("balance_sheet", "total_equity"): ["所有者权益合计", "股东权益合计"],
            ("balance_sheet", "equity_attributable_to_parent"): ["归属于母公司所有者权益"],
            ("financial_metrics", "eps"): ["基本每股收益"],
            ("financial_metrics", "eps_diluted"): ["稀释每股收益"],
            ("financial_metrics", "bps"): ["每股净资产"],
            ("financial_metrics", "dividend_per_share"): ["每股股利", "每股派息"],
            ("financial_metrics", "roe"): ["净资产收益率"],
            ("financial_metrics", "current_ratio"): ["流动比率"],
            ("financial_metrics", "quick_ratio"): ["速动比率"],
        }

    @staticmethod
    def _get_metric_min_abs(metric: str) -> float:
        per_share_or_ratio = {
            "eps",
            "eps_diluted",
            "bps",
            "dividend_per_share",
            "roe",
            "roa",
            "debt_ratio",
            "gross_margin",
            "net_margin",
            "current_ratio",
            "quick_ratio",
        }
        return 0.0 if metric in per_share_or_ratio else 1.0

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

        def extract_stock_code_from_path(pdf_path: Path) -> Optional[str]:
            normalized = str(pdf_path).replace("\\", "/")
            # 兼容 downloads/{hk_stocks|cn_stocks}/{stock_code}/... 目录结构
            path_match = re.search(r"/(?:hk_stocks|cn_stocks)/(\d{5,6})(?:/|$)", normalized)
            if path_match:
                return path_match.group(1)
            return None

        # 从文本提取股票代码
        if self.is_english_report:
            # 仅在文档前部查找，避免命中董事履历中的其他公司股票代码。
            leading_text = self.full_text[:20000]
            code_match = (
                re.search(r'\bHKEX\s*[:：]\s*0?(\d{4,5})\b', leading_text, re.IGNORECASE)
                or re.search(r'\bStock\s+Codes?\s*[:：]\s*0?(\d{4,5})\b', leading_text, re.IGNORECASE)
            )
            if code_match:
                metadata.stock_code = code_match.group(1).zfill(5)
        else:
            code_match = re.search(r'证券代码[：:\s]*(\d{6})', self.full_text)
            if code_match:
                metadata.stock_code = code_match.group(1)

        # 兜底：从标准下载路径回填股票代码（避免英文报告提取失败/误命中）
        if not metadata.stock_code:
            metadata.stock_code = extract_stock_code_from_path(self.current_pdf_path)

        # 从文本提取股票简称/公司名称
        if self.is_english_report:
            # 尝试从文件名或标题提取
            name_match = re.search(r'([A-Z][a-zA-Z\s]+(?:Limited|Inc\.|Corporation|Holdings))', self.full_text[:2000])
        else:
            name_match = re.search(r'证券简称[：:\s]*([^\s\n]+)', self.full_text)
        if name_match:
            metadata.stock_name = name_match.group(1).strip()

        # 判断报告类型与文档类型（优先避免Q4+全年误判）
        report_type, doc_type, period_type = self._classify_report_identity()
        metadata.report_type = report_type
        metadata.doc_type = doc_type
        metadata.period_type = period_type

        # 提取币种与单位
        currency_map = {
            'us$': 'USD',
            'usd': 'USD',
            'hk$': 'HKD',
            'hkd': 'HKD',
            'rmb': 'CNY',
            'cny': 'CNY',
            '人民币': 'CNY',
            '港元': 'HKD',
            '美元': 'USD',
        }
        unit_map = {
            'million': 'million',
            'mn': 'million',
            'billion': 'billion',
            '千': 'none',
            '百万': 'million',
            '亿': 'billion',
        }

        # 优先识别“币种+千元”口径（如 RMB’000 / HK$'000），统一按 million 存储
        thousand_currency_match = re.search(
            r'(US\$|HK\$|USD|HKD|RMB|CNY)[’\'` ]?0{3}|(人民币|港元|美元)\s*(?:千元|千)',
            self.full_text,
            re.IGNORECASE,
        )
        if thousand_currency_match:
            token = (thousand_currency_match.group(1) or thousand_currency_match.group(2) or "").lower()
            if token:
                metadata.currency = currency_map.get(token, token.upper())
            metadata.amount_unit = 'million'
        else:
            currency_match = re.search(r'(US\$|HK\$|USD|HKD|RMB|CNY|人民币|港元|美元)', self.full_text, re.IGNORECASE)
            if currency_match:
                key = currency_match.group(1).lower()
                metadata.currency = currency_map.get(key, currency_match.group(1).upper())

            unit_match = re.search(r'(million|mn|billion|百万|亿|千)', self.full_text, re.IGNORECASE)
            if unit_match:
                unit_key = unit_match.group(1).lower()
                metadata.amount_unit = unit_map.get(unit_key, 'none')
            else:
                metadata.amount_unit = 'none'

        if metadata.currency:
            metadata.per_share_currency = metadata.currency

        # 提取报告期
        if self.is_english_report:
            period_match = re.search(r'(?:year|period)\s+ended?\s+.*?(20\d{2})', self.full_text, re.IGNORECASE)
            if not period_match:
                period_match = re.search(r'(20\d{2})\s+(?:Annual|Interim)', self.full_text, re.IGNORECASE)
            if not period_match:
                period_match = re.search(r'(20\d{2})\s*Q([1-4])', self.full_text, re.IGNORECASE)
        else:
            period_match = re.search(r'(20\d{2})[年\s]*(?:年度|第[一二三四]季度|半年度)', self.full_text)
        if period_match:
            metadata.report_period = period_match.group(0)

        metadata.fiscal_year = self._extract_fiscal_year(metadata.report_period)
        metadata.is_audited = self._is_audited_report()

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
        income.net_profit_attributable_to_parent = self._find_value('net_profit_attributable_to_parent')
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
        balance.equity_attributable_to_parent = self._find_value('equity_attributable_to_parent')

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

    @staticmethod
    def _extract_text_line(full_text: str, start: int, end: int) -> str:
        """提取匹配所在行文本"""
        line_start = full_text.rfind("\n", 0, start)
        if line_start < 0:
            line_start = 0
        else:
            line_start += 1
        line_end = full_text.find("\n", end)
        if line_end < 0:
            line_end = len(full_text)
        return full_text[line_start:line_end]

    @staticmethod
    def _infer_unit_multiplier(match_text_lower: str, context_lower: str) -> float:
        """根据命中片段与上下文推断单位倍率（统一换算至 million）"""
        if re.search(r"(?:rmb|cny|usd|hkd|hk\$|us\$)[’'` ]?0{3}", context_lower):
            return 0.001
        if "billion" in match_text_lower or "billion" in context_lower:
            return 1000.0
        if "thousand" in context_lower:
            return 0.001
        if " million " in context_lower or "mn" in context_lower:
            return 1.0
        return 1.0

    @staticmethod
    def _score_text_match(field_name: str, value_str: str, value: float, context_lower: str) -> int:
        """为文本回退候选打分，分值更高者优先"""
        score = 0
        if "," in value_str or "." in value_str:
            score += 1
        if any(token in context_lower for token in ("rmb", "hkd", "usd", "million", "billion", "thousand")):
            score += 2
        if field_name in {"revenue", "total_assets", "total_liabilities", "total_equity"} and abs(value) >= 1000:
            score += 1
        if field_name in {"eps", "eps_diluted"} and abs(value) <= 20:
            score += 1
        if field_name == "revenue" and any(token in context_lower for token in (" revenue 收入", " total revenue ", "總收入")):
            score += 2
        if field_name == "net_profit" and any(token in context_lower for token in ("profit for the period", "profit for the year", "期內溢利", "年內溢利")):
            score += 2
        if "non-ifrs" in context_lower:
            score -= 2
        if "note" in context_lower or "附注" in context_lower:
            score -= 1
        return score

    def _is_suspicious_text_match(
        self,
        field_name: str,
        match_text: str,
        line_text: str,
        context_lower: str,
        value: float,
    ) -> bool:
        """过滤明显错误的文本命中（章节编号/分部统计等）"""
        line_lower = " ".join(line_text.lower().split())
        match_text_lower = match_text.lower()

        # 章节标题（例如 "11. PROFIT FOR THE YEAR 11."）不应作为财务值。
        if re.match(r"^\d{1,2}\.\s+[a-z].*\s+\d{1,2}\.?$", line_lower):
            return True
        if re.search(r"\b\d{1,2}\.\s+(profit|earnings|revenue)\b", line_lower):
            if abs(value) <= 100:
                return True

        if field_name in {"revenue", "operating_profit", "net_profit", "total_profit"}:
            nums = re.findall(r"-?\d[\d,]*(?:\.\d+)?", line_text)
            parsed = []
            for num in nums:
                parsed_val = self._parse_number(num)
                if parsed_val is not None:
                    parsed.append(abs(parsed_val))
            if parsed and max(parsed) >= 1000 and abs(value) < 1000:
                return True

        if field_name in {"eps", "eps_diluted"} and abs(value) > 100:
            return True

        if field_name == "revenue":
            revenue_blacklist = (
                "gross revenue",
                "other revenue",
                "franchise fees",
                "franchisee",
                "total number of restaurants",
                "average spending",
            )
            if any(token in match_text_lower for token in revenue_blacklist):
                return True
            if any(token in line_lower for token in revenue_blacklist):
                return True

        return False

    def _find_value(self, field_name: str) -> Optional[float]:
        """使用正则从文本中查找数值（支持单位识别）"""
        # 根据语言选择模式
        if self.is_english_report:
            patterns = self.PATTERNS_EN.get(field_name, [])
        else:
            patterns = self.PATTERNS.get(field_name, [])

        best_candidate: Optional[Tuple[int, float]] = None

        for pattern in patterns:
            # 查找匹配，包括单位信息
            matches = re.finditer(pattern, self.full_text, re.IGNORECASE)
            for match in matches:
                # 获取匹配的数值
                value_str = match.group(1) if match.groups() else match.group(0)

                # 获取匹配前后的上下文，查找单位
                match_start = max(0, match.start() - 240)
                match_end = min(len(self.full_text), match.end() + 240)
                context = self.full_text[match_start:match_end]
                context_lower = context.lower()
                line_text = self._extract_text_line(self.full_text, match.start(), match.end())

                # 识别单位（检查匹配文本本身和上下文）
                match_text_lower = match.group(0).lower()
                unit_multiplier = self._infer_unit_multiplier(match_text_lower, context_lower)

                value = self._parse_number(value_str)
                if value is not None:
                    # 应用单位转换（转换为百万单位）
                    converted_value = value * unit_multiplier

                    # 对于revenue等大额字段，如果值很小（<100）且没有识别到单位，可能是billion
                    # 但这种情况要谨慎，避免误判
                    if field_name == "revenue" and converted_value < 100 and unit_multiplier == 1.0:
                        # 检查上下文，如果明确是表格中的数值（通常表格是million单位），保持原值
                        # 如果是在文本描述中（如"$11.3 billion"），可能是billion
                        if "billion" in context_lower and value < 20:
                            converted_value = value * 1000.0

                    if self._is_suspicious_text_match(
                        field_name=field_name,
                        match_text=match.group(0),
                        line_text=line_text,
                        context_lower=context_lower,
                        value=converted_value,
                    ):
                        continue

                    score = self._score_text_match(
                        field_name=field_name,
                        value_str=value_str,
                        value=converted_value,
                        context_lower=context_lower,
                    )
                    if best_candidate is None or score > best_candidate[0]:
                        best_candidate = (score, converted_value)
                    elif best_candidate and score == best_candidate[0]:
                        # 同分时，优先量级更大的值（更可能是主报表口径）
                        if abs(converted_value) > abs(best_candidate[1]):
                            best_candidate = (score, converted_value)

        if best_candidate is not None:
            return best_candidate[1]

        # 如果英文模式没找到，尝试中文模式（或反之）
        if self.is_english_report:
            fallback_patterns = self.PATTERNS.get(field_name, [])
        else:
            fallback_patterns = self.PATTERNS_EN.get(field_name, [])

        best_fallback: Optional[Tuple[int, float]] = None
        for pattern in fallback_patterns:
            matches = re.finditer(pattern, self.full_text, re.IGNORECASE)
            for match in matches:
                value_str = match.group(1) if match.groups() else match.group(0)
                value = self._parse_number(value_str)
                if value is not None:
                    context = self.full_text[
                        max(0, match.start() - 240):min(len(self.full_text), match.end() + 240)
                    ]
                    context_lower = context.lower()
                    line_text = self._extract_text_line(self.full_text, match.start(), match.end())
                    if self._is_suspicious_text_match(
                        field_name=field_name,
                        match_text=match.group(0),
                        line_text=line_text,
                        context_lower=context_lower,
                        value=value,
                    ):
                        continue

                    score = self._score_text_match(
                        field_name=field_name,
                        value_str=value_str,
                        value=value,
                        context_lower=context_lower,
                    )
                    if best_fallback is None or score > best_fallback[0]:
                        best_fallback = (score, value)
                    elif best_fallback and score == best_fallback[0]:
                        if abs(value) > abs(best_fallback[1]):
                            best_fallback = (score, value)

        if best_fallback is not None:
            return best_fallback[1]

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

    def _get_table_year_end_index(self, table: List[List[Any]]) -> Optional[int]:
        """从表格头部识别全年(Year Ended)列索引"""
        date_cells: List[Tuple[int, int]] = []
        for row in table:
            if not row:
                continue
            row_text = " ".join(str(cell) for cell in row if cell)
            if not row_text:
                continue
            for idx, cell in enumerate(row):
                if not cell:
                    continue
                cell_text = str(cell)
                match = re.search(r'(?:12/31|31/12)/?(20\d{2})', cell_text)
                if match:
                    year = int(match.group(1))
                    date_cells.append((idx, year))
            if len(date_cells) >= 2:
                # 优先使用当前行的日期列
                break

        if not date_cells:
            return None

        date_cells.sort(key=lambda item: item[0])
        if len(date_cells) >= 4:
            year_end_cells = date_cells[-2:]
        else:
            year_end_cells = date_cells[-2:]

        # 选择年份最大的列（通常是最新年度）
        target_index = max(year_end_cells, key=lambda item: item[1])[0]
        return target_index

    def _get_row_value_by_index(self, row: List[Any], index: Optional[int]) -> Optional[float]:
        """按列索引提取数值"""
        if index is None or index >= len(row):
            return None
        def parse_cell(cell_index: int) -> Optional[float]:
            if cell_index < 0 or cell_index >= len(row):
                return None
            cell = row[cell_index]
            text = str(cell).replace('\n', '') if cell else ""
            return self._parse_number(text)

        value = parse_cell(index)
        if value is not None:
            return value

        # 英文报表常见 "$" 与数字拆列，允许小范围探测相邻列
        for delta in (1, 2, -1):
            nearby = parse_cell(index + delta)
            if nearby is not None:
                return nearby
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
                'net_profit_attributable_to_parent': [
                    'Net Income',
                    'Net income',
                    'Net Profit',
                    'Net profit',
                    'Profit attributable to',
                ],
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

        min_value = 1 if self.is_english_report else 10000

        for table_idx, (table, year_end_index) in enumerate(
            self._iter_tables_for_statement("income_statement"), start=1
        ):
            if self._is_segment_operating_table(table):
                page, tb_idx = (
                    self.table_locations[table_idx - 1]
                    if table_idx - 1 < len(self.table_locations)
                    else (None, table_idx)
                )
                self._add_runtime_issue(
                    issue_type="segment_table_skipped",
                    severity="warning",
                    message=(
                        "检测到分部经营表，已跳过以避免误提取。"
                        f" page={page}, table={tb_idx}"
                    ),
                    dedupe_key=f"segment:{page}:{tb_idx}",
                )
                continue

            for row in table:
                if not row or len(row) < 2:
                    continue

                # 清理换行符，合并单元格文本
                row_text = str(row[0]).replace('\n', '') if row[0] else ""
                row_text_lower = row_text.lower()

                for field, keywords in keywords_map.items():
                    current_value = getattr(income, field)
                    if not self._row_label_matches_metric(field, row_text, keywords):
                        continue
                    # 排除"扣除非经常性损益后的基本每股收益"误匹配
                    if field == 'net_profit_deducted' and '每股' in row_text:
                        continue
                    # 排除"归属于母公司所有者的权益"误匹配净利润
                    if field == 'net_profit' and '权益' in row_text:
                        continue
                    # 获取第一个大于阈值的数值（跳过注释编号等）
                    if self.is_english_report and field in (
                        'net_profit',
                        'net_profit_attributable_to_parent',
                        'operating_profit',
                        'total_profit',
                    ):
                        value = self._get_row_value_by_index(row, year_end_index)
                        if value is None:
                            value = self._get_first_large_value(row[1:], min_value=1)
                    else:
                        value = self._get_row_value_by_index(row, year_end_index)
                        if value is None:
                            value = self._get_first_large_value(row[1:], min_value=min_value)
                    if value is not None:
                        # 英文报表多期并列时，优先保留量级更大的值（通常对应累计/全年）
                        if current_value is None or abs(value) >= abs(current_value):
                            if self.is_english_report and field in (
                                'net_profit',
                                'net_profit_attributable_to_parent',
                            ):
                                if 'including noncontrolling' in row_text_lower:
                                    income.net_profit = value
                                elif 'noncontrolling' in row_text_lower:
                                    continue
                                elif 'attributable' in row_text_lower or 'holdings' in row_text_lower or 'inc.' in row_text_lower:
                                    income.net_profit_attributable_to_parent = value
                                    if (
                                        income.net_profit is None
                                        or abs(value) >= abs(income.net_profit)
                                    ):
                                        income.net_profit = value
                                else:
                                    setattr(income, field, value)
                            else:
                                setattr(income, field, value)

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

        min_value = 1 if self.is_english_report else 10000

        for table, year_end_index in self._iter_tables_for_statement("balance_sheet"):

            for row in table:
                if not row or len(row) < 2:
                    continue

                # 清理换行符
                row_text = str(row[0]).replace('\n', '') if row[0] else ""

                for field, keywords in keywords_map.items():
                    current_value = getattr(balance, field)
                    if not self._row_label_matches_metric(field, row_text, keywords):
                        continue
                    # 排除净利润行误匹配权益
                    if field == 'total_equity' and '净利润' in row_text:
                        continue
                    # 跳过注释编号列，获取真实数值
                    value = self._get_row_value_by_index(row, year_end_index)
                    if value is None:
                        value = self._get_first_large_value(row[1:], min_value=min_value)
                    if value is not None:
                        # 如果当前值太小或为空，用表格值覆盖
                        if current_value is None or abs(current_value) < min_value:
                            setattr(balance, field, value)

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

        for table, year_end_index in self._iter_tables_for_statement("cash_flow_statement"):
            for row in table:
                if not row or len(row) < 2:
                    continue

                # 清理换行符
                row_text = str(row[0]).replace('\n', '') if row[0] else ""

                for field, keywords in keywords_map.items():
                    if getattr(cash_flow, field) is None:
                        if not self._row_label_matches_metric(field, row_text, keywords):
                            continue
                        value = self._get_row_value_by_index(row, year_end_index)
                        if value is None:
                            for cell in row[1:]:
                                value = self._parse_number(str(cell).replace('\n', '') if cell else "")
                                if value is not None and abs(value) > 1:
                                    break
                        if value is not None and abs(value) > 1:
                            setattr(cash_flow, field, value)

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

        for table, year_end_index in self._iter_tables_for_statement("financial_metrics"):
            for row in table:
                if not row or len(row) < 2:
                    continue

                # 清理换行符
                row_text = str(row[0]).replace('\n', '') if row[0] else ""

                for field, keywords in keywords_map.items():
                    if getattr(metrics, field) is None:
                        if not self._row_label_matches_metric(field, row_text, keywords):
                            continue
                        # 排除"扣除非经常性损益后"的每股收益
                        if field == 'eps' and '扣除' in row_text:
                            continue
                        value = self._get_row_value_by_index(row, year_end_index)
                        if value is None:
                            for cell in row[1:]:
                                value = self._parse_number(str(cell).replace('\n', '') if cell else "")
                                if value is not None:
                                    break
                        if value is not None:
                            setattr(metrics, field, value)

    def _calculate_derived_metrics(self, balance: BalanceSheet, income: IncomeStatement,
                                   cash_flow: CashFlowStatement, metrics: FinancialMetrics):
        """计算衍生财务指标"""
        def mark(statement: str, metric: str) -> None:
            self._derived_fact_keys.add((statement, metric))

        # 计算营业成本 = 营业收入 - 毛利润（当直接提取的成本单位不一致时）
        if income.revenue and income.gross_profit:
            calculated_cost = income.revenue - income.gross_profit
            # 如果提取的成本与计算的成本差距过大（单位不一致），使用计算值
            if income.operating_cost is None or abs(income.operating_cost - calculated_cost) > calculated_cost * 0.1:
                income.operating_cost = calculated_cost
                mark("income_statement", "operating_cost")

        # 计算毛利润 = 营业收入 - 营业成本
        if income.gross_profit is None and income.revenue and income.operating_cost:
            income.gross_profit = income.revenue - income.operating_cost
            mark("income_statement", "gross_profit")

        # 计算毛利率(%) = 毛利润 / 营业收入 * 100
        if income.gross_margin is None and income.gross_profit and income.revenue:
            income.gross_margin = round(income.gross_profit / income.revenue * 100, 2)
            mark("income_statement", "gross_margin")

        # 计算净利率(%) = 净利润 / 营业收入 * 100
        if income.net_margin is None and income.net_profit and income.revenue:
            income.net_margin = round(income.net_profit / income.revenue * 100, 2)
            mark("income_statement", "net_margin")

        # 计算资产负债率
        if balance.total_assets and balance.total_liabilities:
            metrics.debt_ratio = round(balance.total_liabilities / balance.total_assets * 100, 2)
            mark("financial_metrics", "debt_ratio")

        # 计算流动比率 = 流动资产 / 流动负债
        if metrics.current_ratio is None and balance.current_assets and balance.current_liabilities:
            metrics.current_ratio = round(balance.current_assets / balance.current_liabilities, 2)
            mark("financial_metrics", "current_ratio")

        # 计算速动比率 = (流动资产 - 存货) / 流动负债
        if metrics.quick_ratio is None and balance.current_assets and balance.current_liabilities:
            inventory = balance.inventory or 0
            metrics.quick_ratio = round((balance.current_assets - inventory) / balance.current_liabilities, 2)
            mark("financial_metrics", "quick_ratio")

        # 计算ROA (需要年化处理，这里简化)
        if balance.total_assets and income.net_profit:
            metrics.roa = round(income.net_profit / balance.total_assets * 100, 2)
            mark("financial_metrics", "roa")

        # 计算ROE (净资产收益率) = 净利润 / 净资产 * 100
        # 优先使用归母数据（更精准）：归属于母公司股东的净利润 / 归属于母公司股东的净资产
        if metrics.roe is None:
            # 最优：归母净利润 / 归母净资产
            if income.net_profit_attributable_to_parent and balance.equity_attributable_to_parent:
                metrics.roe = round(income.net_profit_attributable_to_parent / balance.equity_attributable_to_parent * 100, 2)
                mark("financial_metrics", "roe")
            # 次优：归母净利润 / 总净资产（如果只有归母净利润）
            elif income.net_profit_attributable_to_parent and balance.total_equity:
                metrics.roe = round(income.net_profit_attributable_to_parent / balance.total_equity * 100, 2)
                mark("financial_metrics", "roe")
            # 再次：净利润 / 归母净资产（如果只有归母净资产）
            elif income.net_profit and balance.equity_attributable_to_parent:
                metrics.roe = round(income.net_profit / balance.equity_attributable_to_parent * 100, 2)
                mark("financial_metrics", "roe")
            # 备选：净利润 / 总净资产
            elif income.net_profit and balance.total_equity:
                metrics.roe = round(income.net_profit / balance.total_equity * 100, 2)
                mark("financial_metrics", "roe")
            # 最后：如果没有净资产，尝试用总资产-总负债计算净资产
            elif income.net_profit and balance.total_assets and balance.total_liabilities:
                calculated_equity = balance.total_assets - balance.total_liabilities
                if calculated_equity > 0:
                    # 优先使用归母净利润
                    net_profit_for_roe = income.net_profit_attributable_to_parent or income.net_profit
                    metrics.roe = round(net_profit_for_roe / calculated_equity * 100, 2)
                    mark("financial_metrics", "roe")

        # 计算自由现金流 = 经营现金流 - 资本支出
        if cash_flow.operating_cash_flow is not None and cash_flow.capital_expenditure is not None:
            cash_flow.free_cash_flow = cash_flow.operating_cash_flow - cash_flow.capital_expenditure
            mark("cash_flow_statement", "free_cash_flow")

        # 计算每股净资产 = 归属于母公司股东权益 / 总股本
        if metrics.bps is None and balance.total_equity and metrics.total_shares:
            metrics.bps = round(balance.total_equity / metrics.total_shares, 2)
            mark("financial_metrics", "bps")

        # 如果有每股收益和净利润，可以反推总股本
        if metrics.total_shares is None and metrics.eps and income.net_profit:
            metrics.total_shares = income.net_profit / metrics.eps
            mark("financial_metrics", "total_shares")

        # 用反推的总股本计算每股净资产
        if metrics.bps is None and balance.total_equity and metrics.total_shares:
            metrics.bps = round(balance.total_equity / metrics.total_shares, 2)
            mark("financial_metrics", "bps")

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
