from src.pdf_parser.content_extractor import (
    BalanceSheet,
    CashFlowStatement,
    FinancialMetrics,
    IncomeStatement,
    PDFContentExtractor,
    ReportMetadata,
)


class TestFactEvidenceMapping:
    def setup_method(self) -> None:
        self.extractor = PDFContentExtractor()
        self.extractor.is_english_report = True

    def test_comparison_facts_have_evidence_ids(self) -> None:
        self.extractor.tables = [
            [
                ["Item", "Year ended Dec 31, 2025", "Year ended Dec 31, 2024"],
                ["Total Revenue", "11,300", "10,820"],
                ["Net Income", "900", "850"],
                ["Net cash provided by operating activities", "1,200", "1,100"],
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
        ]

        facts, evidence, _ = self.extractor._build_facts_evidence_quality(
            metadata=metadata,
            periods=periods,
            income=IncomeStatement(revenue=11300, net_profit=900),
            balance=BalanceSheet(),
            cash_flow=CashFlowStatement(operating_cash_flow=1200),
            metrics=FinancialMetrics(),
        )

        comparison = [
            f
            for f in facts
            if f["period_id"] == "2024FY"
            and f["metric"] in {"revenue", "net_profit", "operating_cash_flow"}
        ]
        assert len(comparison) == 3
        assert all(item["evidence_ids"] for item in comparison)
        assert len(evidence) >= 6

    def test_derived_fact_inherits_evidence_ids(self) -> None:
        self.extractor.tables = [
            [
                ["Item", "Nine months ended Sep 30, 2025"],
                ["Total Revenue", "9000"],
                ["Gross Profit", "3600"],
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

        income = IncomeStatement(revenue=9000, gross_profit=3600)
        metrics = FinancialMetrics()
        self.extractor._derived_fact_keys = {("income_statement", "gross_margin")}
        income.gross_margin = 40.0

        facts, _, _ = self.extractor._build_facts_evidence_quality(
            metadata=metadata,
            periods=periods,
            income=income,
            balance=BalanceSheet(),
            cash_flow=CashFlowStatement(),
            metrics=metrics,
        )

        gross_margin_fact = next(
            fact
            for fact in facts
            if fact["statement"] == "income_statement"
            and fact["metric"] == "gross_margin"
            and fact["period_id"] == "2025Q3_YTD"
        )
        assert gross_margin_fact["is_derived"] is True
        assert len(gross_margin_fact["evidence_ids"]) >= 1

    def test_cross_check_failed_issue_is_emitted(self) -> None:
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
        income = IncomeStatement(net_profit=1000)
        metrics = FinancialMetrics(eps=1.0, total_shares=500.0)

        facts, _, quality = self.extractor._build_facts_evidence_quality(
            metadata=metadata,
            periods=periods,
            income=income,
            balance=BalanceSheet(),
            cash_flow=CashFlowStatement(),
            metrics=metrics,
        )

        assert facts
        assert any(issue["type"] == "cross_check_failed" for issue in quality["issues"])

    def test_segment_table_skipped_issue_is_emitted(self) -> None:
        self.extractor.tables = [
            [
                ["Segment Results", "2025", "2024"],
                ["KFC operating results", "100", "90"],
            ]
        ]
        self.extractor.table_locations = [(3, 2)]
        income = IncomeStatement()
        self.extractor._extract_from_tables_income(income)

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

        _, _, quality = self.extractor._build_facts_evidence_quality(
            metadata=metadata,
            periods=periods,
            income=income,
            balance=BalanceSheet(),
            cash_flow=CashFlowStatement(),
            metrics=FinancialMetrics(),
        )
        assert any(issue["type"] == "segment_table_skipped" for issue in quality["issues"])
