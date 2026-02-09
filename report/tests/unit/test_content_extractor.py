"""
PDF内容提取器单元测试
测试 PDFContentExtractor 类的各种方法
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.pdf_parser.content_extractor import (
    PDFContentExtractor,
    IncomeStatement,
    BalanceSheet,
    CashFlowStatement,
    FinancialMetrics,
    ReportMetadata,
    extract_financial_data,
)
from tests.fixtures.sample_data import NUMBER_PARSING_SAMPLES, INVALID_NUMBER_SAMPLES


class TestNumberParsing:
    """数字解析测试"""

    def setup_method(self):
        """每个测试方法前初始化提取器"""
        self.extractor = PDFContentExtractor()

    @pytest.mark.parametrize("input_text,expected", [
        ("1234567", 1234567),
        ("1,234,567", 1234567),
        ("1,234,567.89", 1234567.89),
        ("12345.67", 12345.67),
        ("100", 100),
        ("0", 0),
        ("0.5", 0.5),
    ])
    def test_parse_positive_numbers(self, input_text, expected):
        """测试解析正数"""
        result = self.extractor._parse_number(input_text)
        assert result == expected

    @pytest.mark.parametrize("input_text,expected", [
        ("-1234567", -1234567),
        ("-1,234,567", -1234567),
        ("-50.5", -50.5),
    ])
    def test_parse_negative_numbers(self, input_text, expected):
        """测试解析负数"""
        result = self.extractor._parse_number(input_text)
        assert result == expected

    def test_parse_chinese_comma(self):
        """测试解析中文逗号"""
        result = self.extractor._parse_number("1，234，567")
        assert result == 1234567

    def test_parse_empty_string(self):
        """测试空字符串返回None"""
        result = self.extractor._parse_number("")
        assert result is None

    def test_parse_none(self):
        """测试None返回None"""
        result = self.extractor._parse_number(None)
        assert result is None

    @pytest.mark.parametrize("input_text", [
        "abc",
        "N/A",
        "-",
        "不适用",
        "无",
    ])
    def test_parse_invalid_returns_none(self, input_text):
        """测试无效输入返回None"""
        result = self.extractor._parse_number(input_text)
        assert result is None

    def test_parse_with_whitespace(self):
        """测试带空格的数字"""
        result = self.extractor._parse_number("  123456  ")
        assert result == 123456


class TestGetFirstLargeValue:
    """获取第一个大值测试"""

    def setup_method(self):
        self.extractor = PDFContentExtractor()

    def test_get_first_large_value_from_list(self):
        """测试从列表中获取第一个大值"""
        cells = ["5", "100000", "200000"]
        result = self.extractor._get_first_large_value(cells, min_value=1000)
        assert result == 100000

    def test_get_first_large_value_skip_small(self):
        """测试跳过小值（如注释编号）"""
        cells = ["1", "2", "3", "100000"]
        result = self.extractor._get_first_large_value(cells, min_value=1000)
        assert result == 100000

    def test_get_first_large_value_none_found(self):
        """测试没有找到大值"""
        cells = ["1", "2", "3"]
        result = self.extractor._get_first_large_value(cells, min_value=1000)
        assert result is None

    def test_get_first_large_value_with_none_cells(self):
        """测试包含None的单元格"""
        cells = [None, "100000", None]
        result = self.extractor._get_first_large_value(cells, min_value=1000)
        assert result == 100000


class TestLanguageDetection:
    """语言检测测试"""

    def setup_method(self):
        self.extractor = PDFContentExtractor()

    def test_detect_chinese_by_content(self):
        """测试通过内容检测中文"""
        self.extractor.full_text = "营业收入 净利润 资产总计 负债合计 现金流量"
        self.extractor.current_pdf_path = Path("/test/report.pdf")
        self.extractor._detect_language()
        assert self.extractor.is_english_report is False

    def test_detect_english_by_content(self):
        """测试通过内容检测英文"""
        self.extractor.full_text = "Revenue Net Profit Total Assets Total Liabilities Cash Flow Finance Costs Equity"
        self.extractor.current_pdf_path = Path("/test/report.pdf")
        self.extractor._detect_language()
        assert self.extractor.is_english_report is True

    def test_detect_english_by_filename(self):
        """测试通过文件名检测英文"""
        self.extractor.full_text = ""
        self.extractor.current_pdf_path = Path("/test/2023_annual_en.pdf")
        self.extractor._detect_language()
        assert self.extractor.is_english_report is True

    def test_detect_english_by_filename_with_underscore(self):
        """测试通过带下划线的文件名检测英文"""
        self.extractor.full_text = ""
        self.extractor.current_pdf_path = Path("/test/report_en_2023.pdf")
        self.extractor._detect_language()
        assert self.extractor.is_english_report is True


class TestMetadataExtraction:
    """元数据提取测试"""

    def setup_method(self):
        self.extractor = PDFContentExtractor()

    def test_extract_cn_stock_code(self):
        """测试提取A股代码"""
        self.extractor.full_text = "证券代码：000001 证券简称：平安银行"
        self.extractor.is_english_report = False
        self.extractor.current_pdf_path = Path("/test/report.pdf")

        with patch.object(self.extractor, 'current_pdf_path') as mock_path:
            mock_path.stat.return_value.st_size = 1024
            mock_path.name = "report.pdf"

            with patch('src.pdf_parser.content_extractor.PdfReader') as mock_reader:
                mock_reader.return_value.metadata = None
                mock_reader.return_value.pages = [1, 2, 3]

                metadata = self.extractor._extract_metadata()

        assert metadata.stock_code == "000001"

    def test_extract_hk_stock_code(self):
        """测试提取港股代码"""
        self.extractor.full_text = "Stock Code: 00700"
        self.extractor.is_english_report = True
        self.extractor.current_pdf_path = Path("/test/report.pdf")

        with patch.object(self.extractor, 'current_pdf_path') as mock_path:
            mock_path.stat.return_value.st_size = 1024
            mock_path.name = "report.pdf"

            with patch('src.pdf_parser.content_extractor.PdfReader') as mock_reader:
                mock_reader.return_value.metadata = None
                mock_reader.return_value.pages = [1]

                metadata = self.extractor._extract_metadata()

        assert metadata.stock_code == "00700"

    def test_extract_report_type_annual_cn(self):
        """测试识别中文年报"""
        self.extractor.full_text = "2023年年度报告"
        self.extractor.is_english_report = False
        self.extractor.current_pdf_path = Path("/test/report.pdf")

        with patch.object(self.extractor, 'current_pdf_path') as mock_path:
            mock_path.stat.return_value.st_size = 1024
            mock_path.name = "report.pdf"

            with patch('src.pdf_parser.content_extractor.PdfReader') as mock_reader:
                mock_reader.return_value.metadata = None
                mock_reader.return_value.pages = [1]

                metadata = self.extractor._extract_metadata()

        assert metadata.report_type == "annual"

    def test_extract_report_type_semi_annual_cn(self):
        """测试识别中文半年报"""
        self.extractor.full_text = "2023年半年度报告"
        self.extractor.is_english_report = False
        self.extractor.current_pdf_path = Path("/test/report.pdf")

        with patch.object(self.extractor, 'current_pdf_path') as mock_path:
            mock_path.stat.return_value.st_size = 1024
            mock_path.name = "report.pdf"

            with patch('src.pdf_parser.content_extractor.PdfReader') as mock_reader:
                mock_reader.return_value.metadata = None
                mock_reader.return_value.pages = [1]

                metadata = self.extractor._extract_metadata()

        assert metadata.report_type == "semi_annual"

    def test_extract_report_type_annual_en(self):
        """测试识别英文年报"""
        self.extractor.full_text = "Annual Report 2023"
        self.extractor.is_english_report = True
        self.extractor.current_pdf_path = Path("/test/report.pdf")

        with patch.object(self.extractor, 'current_pdf_path') as mock_path:
            mock_path.stat.return_value.st_size = 1024
            mock_path.name = "report.pdf"

            with patch('src.pdf_parser.content_extractor.PdfReader') as mock_reader:
                mock_reader.return_value.metadata = None
                mock_reader.return_value.pages = [1]

                metadata = self.extractor._extract_metadata()

        assert metadata.report_type == "annual"

    def test_extract_q4_full_year_results_as_quarterly(self):
        """测试 Q4+全年业绩公告优先识别为季度结果公告"""
        self.extractor.full_text = (
            "ANNOUNCEMENT OF THE 2025 Q4 AND FULL YEAR FINANCIAL RESULTS "
            "unaudited results for the fourth quarter and full year ended December 31, 2025"
        )
        self.extractor.is_english_report = True
        self.extractor.current_pdf_path = Path("/test/2026_quarterly_en.pdf")

        with patch.object(self.extractor, 'current_pdf_path') as mock_path:
            mock_path.stat.return_value.st_size = 1024
            mock_path.name = "2026_quarterly_en.pdf"

            with patch('src.pdf_parser.content_extractor.PdfReader') as mock_reader:
                mock_reader.return_value.metadata = None
                mock_reader.return_value.pages = [1]

                metadata = self.extractor._extract_metadata()
                periods = self.extractor._build_periods(metadata)

        period_ids = {period["period_id"] for period in periods}
        assert metadata.report_type == "quarterly"
        assert metadata.doc_type == "results_announcement"
        assert metadata.period_type == "full_year_in_quarterly_announcement"
        assert metadata.fiscal_year == 2025
        assert metadata.is_audited is False
        assert metadata.primary_period_id == "2025FY"
        assert "2025FY" in period_ids
        assert "2025Q4_SINGLE" in period_ids
        assert "2024FY" in period_ids

    def test_build_periods_for_q3_results(self):
        """测试Q3公告构建Q3累计与单季期间"""
        self.extractor.full_text = (
            "ANNOUNCEMENT OF THE 2025 Q3 FINANCIAL RESULTS "
            "results for the third quarter ended September 30, 2025 "
            "and nine months ended September 30, 2025"
        )
        self.extractor.is_english_report = True
        self.extractor.current_pdf_path = Path("/test/2025_quarterly_en.pdf")

        with patch.object(self.extractor, 'current_pdf_path') as mock_path:
            mock_path.stat.return_value.st_size = 1024
            mock_path.name = "2025_quarterly_en.pdf"

            with patch('src.pdf_parser.content_extractor.PdfReader') as mock_reader:
                mock_reader.return_value.metadata = None
                mock_reader.return_value.pages = [1]

                metadata = self.extractor._extract_metadata()
                periods = self.extractor._build_periods(metadata)

        period_ids = {period["period_id"] for period in periods}
        assert metadata.report_type == "quarterly"
        assert metadata.fiscal_year == 2025
        assert metadata.primary_period_id == "2025Q3_YTD"
        assert "2025Q3_YTD" in period_ids
        assert "2025Q3_SINGLE" in period_ids

    def test_build_periods_adds_point_in_time_for_balance_sheet(self):
        """测试期间包含资产负债表时点语义"""
        self.extractor.full_text = (
            "ANNOUNCEMENT OF THE 2025 Q4 AND FULL YEAR FINANCIAL RESULTS "
            "year ended December 31, 2025"
        )
        self.extractor.is_english_report = True
        self.extractor.current_pdf_path = Path("/test/2026_quarterly_en.pdf")

        with patch.object(self.extractor, "current_pdf_path") as mock_path:
            mock_path.stat.return_value.st_size = 1024
            mock_path.name = "2026_quarterly_en.pdf"

            with patch("src.pdf_parser.content_extractor.PdfReader") as mock_reader:
                mock_reader.return_value.metadata = None
                mock_reader.return_value.pages = [1]

                metadata = self.extractor._extract_metadata()
                periods = self.extractor._build_periods(metadata)

        bs_period = next(
            (period for period in periods if period["period_id"] == "BS_2025-12-31"),
            None,
        )
        assert bs_period is not None
        assert bs_period["scope"] == "point_in_time"
        assert bs_period["as_of_date"] == "2025-12-31"
        assert bs_period["start_date"] is None
        assert bs_period["end_date"] is None


class TestFactEvidenceModel:
    """facts/evidence 模型测试"""

    def setup_method(self):
        self.extractor = PDFContentExtractor()

    def test_build_facts_and_evidence_with_comparison_period(self):
        """测试核心指标生成事实与同比证据"""
        self.extractor.is_english_report = True
        self.extractor.tables = [
            [
                ["Item", "Year ended Dec 31, 2025", "Year ended Dec 31, 2024"],
                ["Total Revenue", "11,300", "10,820"],
                ["Net Income", "900", "850"],
                [
                    "Net cash provided by operating activities",
                    "1,200",
                    "1,100",
                ],
            ]
        ]
        self.extractor.table_locations = [(2, 1)]

        metadata = ReportMetadata(
            stock_code="09987",
            report_type="quarterly",
            period_type="full_year_in_quarterly_announcement",
            fiscal_year=2025,
            primary_period_id="2025FY",
            currency="USD",
            amount_unit="million",
            per_share_currency="USD",
        )
        periods = [
            {
                "period_id": "2025FY",
                "scope": "full_year",
                "fiscal_quarter": None,
                "ytd_through_quarter": 4,
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "as_of_date": None,
                "is_primary": True,
                "is_comparison": False,
            },
            {
                "period_id": "2024FY",
                "scope": "full_year",
                "fiscal_quarter": None,
                "ytd_through_quarter": 4,
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "as_of_date": None,
                "is_primary": False,
                "is_comparison": True,
            },
            {
                "period_id": "BS_2025-12-31",
                "scope": "point_in_time",
                "fiscal_quarter": None,
                "ytd_through_quarter": None,
                "start_date": None,
                "end_date": None,
                "as_of_date": "2025-12-31",
                "is_primary": True,
                "is_comparison": False,
            },
        ]

        income = IncomeStatement(revenue=11300, net_profit=900)
        balance = BalanceSheet()
        cash_flow = CashFlowStatement(operating_cash_flow=1200)
        metrics = FinancialMetrics()

        facts, evidence, quality = self.extractor._build_facts_evidence_quality(
            metadata=metadata,
            periods=periods,
            income=income,
            balance=balance,
            cash_flow=cash_flow,
            metrics=metrics,
        )

        fact_map = {
            (fact["statement"], fact["metric"], fact["period_id"]): fact for fact in facts
        }

        revenue_primary = fact_map[("income_statement", "revenue", "2025FY")]
        revenue_comparison = fact_map[("income_statement", "revenue", "2024FY")]
        net_profit_comparison = fact_map[("income_statement", "net_profit", "2024FY")]
        cashflow_comparison = fact_map[("cash_flow_statement", "operating_cash_flow", "2024FY")]

        assert revenue_primary["evidence_ids"]
        assert revenue_comparison["value"] == 10820.0
        assert net_profit_comparison["value"] == 850.0
        assert cashflow_comparison["value"] == 1100.0
        assert len(evidence) >= 6
        assert quality["status"] == "ok"

    def test_prefers_ytd_column_for_q3_ytd_period(self):
        """测试列级约束：Q3_YTD 优先命中 nine months 列"""
        self.extractor.is_english_report = True
        self.extractor.current_metadata = ReportMetadata(fiscal_year=2025)
        self.extractor.tables = [
            [
                [
                    "Item",
                    "Three months ended Sep 30, 2025",
                    "Nine months ended Sep 30, 2025",
                ],
                ["Total Revenue", "3000", "9000"],
            ]
        ]
        self.extractor.table_locations = [(1, 1)]

        metadata = ReportMetadata(
            report_type="quarterly",
            fiscal_year=2025,
            primary_period_id="2025Q3_YTD",
            currency="USD",
            amount_unit="million",
        )
        periods = [
            {
                "period_id": "2025Q3_YTD",
                "scope": "year_to_date",
                "fiscal_quarter": None,
                "ytd_through_quarter": 3,
                "start_date": "2025-01-01",
                "end_date": "2025-09-30",
                "as_of_date": None,
                "is_primary": True,
                "is_comparison": False,
            }
        ]
        facts, evidence, _ = self.extractor._build_facts_evidence_quality(
            metadata=metadata,
            periods=periods,
            income=IncomeStatement(revenue=9000),
            balance=BalanceSheet(),
            cash_flow=CashFlowStatement(),
            metrics=FinancialMetrics(),
        )

        revenue_fact = next(
            (
                fact
                for fact in facts
                if fact["statement"] == "income_statement"
                and fact["metric"] == "revenue"
                and fact["period_id"] == "2025Q3_YTD"
            ),
            None,
        )
        assert revenue_fact is not None
        assert revenue_fact["evidence_ids"]
        ev = next(
            item for item in evidence if item["evidence_id"] == revenue_fact["evidence_ids"][0]
        )
        assert ev["column_role"] == "ytd"
        assert "Nine months ended" in (ev["column_header"] or "")

    def test_avoids_noncontrolling_row_for_net_profit(self):
        """测试行级约束：不命中 noncontrolling interests 行"""
        self.extractor.is_english_report = True
        self.extractor.current_metadata = ReportMetadata(fiscal_year=2025)
        self.extractor.tables = [
            [
                ["Item", "Year ended Dec 31, 2025"],
                ["Net income attributable to noncontrolling interests", "100"],
                ["Net income attributable to shareholders", "900"],
            ]
        ]
        self.extractor.table_locations = [(1, 1)]

        metadata = ReportMetadata(
            report_type="annual",
            fiscal_year=2025,
            primary_period_id="2025FY",
            currency="USD",
            amount_unit="million",
        )
        periods = [
            {
                "period_id": "2025FY",
                "scope": "full_year",
                "fiscal_quarter": None,
                "ytd_through_quarter": 4,
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "as_of_date": None,
                "is_primary": True,
                "is_comparison": False,
            }
        ]
        facts, evidence, _ = self.extractor._build_facts_evidence_quality(
            metadata=metadata,
            periods=periods,
            income=IncomeStatement(net_profit=900),
            balance=BalanceSheet(),
            cash_flow=CashFlowStatement(),
            metrics=FinancialMetrics(),
        )

        net_profit_fact = next(
            (
                fact
                for fact in facts
                if fact["statement"] == "income_statement"
                and fact["metric"] == "net_profit"
                and fact["period_id"] == "2025FY"
            ),
            None,
        )
        assert net_profit_fact is not None
        assert net_profit_fact["evidence_ids"]
        ev = next(
            item for item in evidence if item["evidence_id"] == net_profit_fact["evidence_ids"][0]
        )
        assert "noncontrolling" not in (ev["row_label"] or "").lower()
        assert ev["raw_value"] == "900"


class TestPatternMatching:
    """正则匹配测试"""

    def setup_method(self):
        self.extractor = PDFContentExtractor()

    def test_find_revenue_cn(self):
        """测试匹配中文营业收入"""
        self.extractor.full_text = "营业收入：1,234,567,890.00"
        self.extractor.is_english_report = False

        result = self.extractor._find_value('revenue')
        assert result == 1234567890.0

    def test_find_revenue_cn_format2(self):
        """测试匹配中文营业收入格式2"""
        self.extractor.full_text = "一、营业总收入 1234567890"
        self.extractor.is_english_report = False

        result = self.extractor._find_value('revenue')
        assert result == 1234567890

    def test_find_revenue_en(self):
        """测试匹配英文Revenue"""
        self.extractor.full_text = "Revenue: 1,234,567,890"
        self.extractor.is_english_report = True

        result = self.extractor._find_value('revenue')
        assert result == 1234567890

    def test_find_net_profit_cn(self):
        """测试匹配中文净利润"""
        self.extractor.full_text = "归属于母公司股东的净利润：100,000,000"
        self.extractor.is_english_report = False

        result = self.extractor._find_value('net_profit')
        assert result == 100000000

    def test_find_net_profit_en(self):
        """测试匹配英文Net Profit"""
        self.extractor.full_text = "Net Profit: 100,000,000"
        self.extractor.is_english_report = True

        result = self.extractor._find_value('net_profit')
        assert result == 100000000

    def test_find_total_assets_cn(self):
        """测试匹配中文总资产"""
        self.extractor.full_text = "资产总计 5,000,000,000"
        self.extractor.is_english_report = False

        result = self.extractor._find_value('total_assets')
        assert result == 5000000000

    def test_find_total_assets_en(self):
        """测试匹配英文Total Assets"""
        self.extractor.full_text = "Total Assets: 5,000,000,000"
        self.extractor.is_english_report = True

        result = self.extractor._find_value('total_assets')
        assert result == 5000000000

    def test_find_value_not_found(self):
        """测试未找到值"""
        self.extractor.full_text = "这是一些无关文本"
        self.extractor.is_english_report = False

        result = self.extractor._find_value('revenue')
        assert result is None

    def test_find_negative_value(self):
        """测试匹配负值"""
        self.extractor.full_text = "投资活动产生的现金流量净额：-500,000,000"
        self.extractor.is_english_report = False

        result = self.extractor._find_value('investing_cash_flow')
        assert result == -500000000


class TestDerivedMetricsCalculation:
    """衍生指标计算测试"""

    def setup_method(self):
        self.extractor = PDFContentExtractor()

    def test_calculate_gross_margin(self):
        """测试计算毛利率"""
        income = IncomeStatement(revenue=1000000, gross_profit=400000)
        balance = BalanceSheet()
        cash_flow = CashFlowStatement()
        metrics = FinancialMetrics()

        self.extractor._calculate_derived_metrics(balance, income, cash_flow, metrics)

        assert income.gross_margin == 40.0

    def test_calculate_net_margin(self):
        """测试计算净利率"""
        income = IncomeStatement(revenue=1000000, net_profit=100000)
        balance = BalanceSheet()
        cash_flow = CashFlowStatement()
        metrics = FinancialMetrics()

        self.extractor._calculate_derived_metrics(balance, income, cash_flow, metrics)

        assert income.net_margin == 10.0

    def test_calculate_debt_ratio(self):
        """测试计算资产负债率"""
        income = IncomeStatement()
        balance = BalanceSheet(total_assets=1000000, total_liabilities=600000)
        cash_flow = CashFlowStatement()
        metrics = FinancialMetrics()

        self.extractor._calculate_derived_metrics(balance, income, cash_flow, metrics)

        assert metrics.debt_ratio == 60.0

    def test_calculate_current_ratio(self):
        """测试计算流动比率"""
        income = IncomeStatement()
        balance = BalanceSheet(current_assets=500000, current_liabilities=250000)
        cash_flow = CashFlowStatement()
        metrics = FinancialMetrics()

        self.extractor._calculate_derived_metrics(balance, income, cash_flow, metrics)

        assert metrics.current_ratio == 2.0

    def test_calculate_quick_ratio(self):
        """测试计算速动比率"""
        income = IncomeStatement()
        balance = BalanceSheet(current_assets=500000, current_liabilities=250000, inventory=100000)
        cash_flow = CashFlowStatement()
        metrics = FinancialMetrics()

        self.extractor._calculate_derived_metrics(balance, income, cash_flow, metrics)

        assert metrics.quick_ratio == 1.6

    def test_calculate_roa(self):
        """测试计算ROA"""
        income = IncomeStatement(net_profit=100000)
        balance = BalanceSheet(total_assets=1000000)
        cash_flow = CashFlowStatement()
        metrics = FinancialMetrics()

        self.extractor._calculate_derived_metrics(balance, income, cash_flow, metrics)

        assert metrics.roa == 10.0

    def test_calculate_free_cash_flow(self):
        """测试计算自由现金流"""
        income = IncomeStatement()
        balance = BalanceSheet()
        cash_flow = CashFlowStatement(operating_cash_flow=500000, capital_expenditure=200000)
        metrics = FinancialMetrics()

        self.extractor._calculate_derived_metrics(balance, income, cash_flow, metrics)

        assert cash_flow.free_cash_flow == 300000

    def test_calculate_gross_profit_from_revenue_and_cost(self):
        """测试从收入和成本计算毛利润"""
        income = IncomeStatement(revenue=1000000, operating_cost=600000)
        balance = BalanceSheet()
        cash_flow = CashFlowStatement()
        metrics = FinancialMetrics()

        self.extractor._calculate_derived_metrics(balance, income, cash_flow, metrics)

        assert income.gross_profit == 400000

    def test_calculate_operating_cost_correction(self):
        """测试营业成本修正（当单位不一致时）"""
        # 收入100万，毛利润40万，但提取的成本只有1000（单位可能是千元）
        income = IncomeStatement(revenue=1000000, gross_profit=400000, operating_cost=1000)
        balance = BalanceSheet()
        cash_flow = CashFlowStatement()
        metrics = FinancialMetrics()

        self.extractor._calculate_derived_metrics(balance, income, cash_flow, metrics)

        # 成本应该被修正为 1000000 - 400000 = 600000
        assert income.operating_cost == 600000


class TestFieldCounting:
    """字段计数测试"""

    def setup_method(self):
        self.extractor = PDFContentExtractor()

    def test_count_extracted_fields(self):
        """测试计数提取的字段"""
        income = IncomeStatement(revenue=1000000, net_profit=100000)
        balance = BalanceSheet(total_assets=5000000)
        cash_flow = CashFlowStatement(operating_cash_flow=200000)
        metrics = FinancialMetrics(eps=5.0, roe=10.0)

        count = self.extractor._count_extracted_fields(income, balance, cash_flow, metrics)

        # income: 2字段, balance: 1字段, cash_flow: 1字段, metrics: 2字段 = 6
        assert count == 6

    def test_count_no_fields(self):
        """测试没有提取到字段"""
        income = IncomeStatement()
        balance = BalanceSheet()
        cash_flow = CashFlowStatement()
        metrics = FinancialMetrics()

        count = self.extractor._count_extracted_fields(income, balance, cash_flow, metrics)

        assert count == 0


class TestMainExtraction:
    """主提取方法测试"""

    def test_extract_file_not_exists(self):
        """测试提取不存在的文件"""
        extractor = PDFContentExtractor()
        result = extractor.extract("/nonexistent/file.pdf")

        assert result["success"] is False
        assert "不存在" in result["error"]

    def test_extract_function(self):
        """测试便捷函数"""
        result = extract_financial_data("/nonexistent/file.pdf")
        assert result["success"] is False


class TestTableExtraction:
    """表格提取测试"""

    def setup_method(self):
        self.extractor = PDFContentExtractor()

    def test_extract_from_tables_income(self):
        """测试从表格提取利润表数据"""
        self.extractor.tables = [
            [["营业收入", "100000000", "90000000"]],
            [["净利润", "10000000", "9000000"]],
        ]
        self.extractor.is_english_report = False

        income = IncomeStatement()
        self.extractor._extract_from_tables_income(income)

        assert income.revenue == 100000000

    def test_extract_from_tables_balance(self):
        """测试从表格提取资产负债表数据"""
        self.extractor.tables = [
            [["资产总计", "500000000", "400000000"]],
            [["负债合计", "300000000", "250000000"]],
        ]
        self.extractor.is_english_report = False

        balance = BalanceSheet()
        self.extractor._extract_from_tables_balance(balance)

        assert balance.total_assets == 500000000
        assert balance.total_liabilities == 300000000

    def test_extract_from_tables_cashflow(self):
        """测试从表格提取现金流量表数据"""
        self.extractor.tables = [
            [["经营活动产生的现金流量净额", "50000000", "40000000"]],
        ]
        self.extractor.is_english_report = False

        cash_flow = CashFlowStatement()
        self.extractor._extract_from_tables_cashflow(cash_flow)

        assert cash_flow.operating_cash_flow == 50000000

    def test_extract_from_tables_en(self):
        """测试从英文表格提取数据"""
        self.extractor.tables = [
            [["Revenue", "100,000,000", "90,000,000"]],
            [["Net Profit", "10,000,000", "9,000,000"]],
        ]
        self.extractor.is_english_report = True

        income = IncomeStatement()
        self.extractor._extract_from_tables_income(income)

        assert income.revenue == 100000000


class TestRelatedPartyTransactions:
    """关联交易提取测试"""

    def setup_method(self):
        self.extractor = PDFContentExtractor()

    def test_extract_related_party_from_text(self):
        """测试从文本提取关联交易"""
        self.extractor.full_text = "向关联方销售商品金额合计：100,000,000"
        self.extractor.tables = []

        rpt = self.extractor._extract_related_party_transactions()

        assert rpt.total_sales == 100000000

    def test_extract_related_party_from_tables(self):
        """测试从表格提取关联交易明细"""
        self.extractor.full_text = ""
        self.extractor.tables = [
            [
                ["关联方", "交易类型", "金额"],
                ["子公司A", "销售商品", "50000000"],
                ["子公司B", "采购商品", "30000000"],
            ]
        ]

        transactions = self.extractor._extract_related_party_from_tables()

        assert transactions is not None
        assert len(transactions) == 2


class TestDataclasses:
    """数据类测试"""

    def test_income_statement_defaults(self):
        """测试利润表数据类默认值"""
        income = IncomeStatement()
        assert income.revenue is None
        assert income.net_profit is None

    def test_balance_sheet_defaults(self):
        """测试资产负债表数据类默认值"""
        balance = BalanceSheet()
        assert balance.total_assets is None
        assert balance.total_equity is None

    def test_cash_flow_defaults(self):
        """测试现金流量表数据类默认值"""
        cash_flow = CashFlowStatement()
        assert cash_flow.operating_cash_flow is None

    def test_financial_metrics_defaults(self):
        """测试财务指标数据类默认值"""
        metrics = FinancialMetrics()
        assert metrics.eps is None
        assert metrics.roe is None

    def test_report_metadata_defaults(self):
        """测试报告元数据数据类默认值"""
        metadata = ReportMetadata()
        assert metadata.stock_code is None
        assert metadata.doc_type is None
        assert metadata.fiscal_year is None
        assert metadata.total_pages == 0
