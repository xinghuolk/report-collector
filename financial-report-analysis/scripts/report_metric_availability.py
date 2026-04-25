#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from financial_report_analysis.ingestion import PdfIngestionAdapter
from financial_report_analysis.p5.metric_availability_report import (
    build_metric_availability_report,
    render_metric_availability_markdown,
)
from financial_report_analysis.semantic_fallback import build_semantic_fallback_service

_TURTLE_INVESTMENT_METRIC_IDS = (
    "revenue",
    "operating_cost",
    "operating_profit",
    "net_profit",
    "cash",
    "restricted_cash",
    "interest_paid_cash",
    "time_deposits_or_wealth_products",
    "accounts_receiv",
    "acct_payable",
    "contract_liab",
    "inventory",
    "fix_assets",
    "cip",
    "rd_exp",
    "invest_income",
    "asset_disp_income",
    "n_recp_disp_fiolta",
    "c_recp_return_invest",
    "st_borr",
    "lt_borr",
    "bond_payable",
    "non_cur_liab_due_1y",
    "total_assets",
    "total_liabilities",
    "equity",
    "equity_attributable_to_owners",
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "c_pay_to_staff",
    "c_paid_for_taxes",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract a PDF and render metric availability as Markdown."
    )
    parser.add_argument("--pdf-path", required=True)
    parser.add_argument("--market", required=True)
    parser.add_argument(
        "--metric-profile",
        default="turtle_investment",
        choices=("turtle_investment",),
    )
    parser.add_argument(
        "--expected-metric-id",
        action="append",
        dest="expected_metric_ids",
        help="Metric id to include; may be passed more than once.",
    )
    parser.add_argument("--min-confidence", type=float, default=0.8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    expected_metric_ids = tuple(args.expected_metric_ids or ())
    if not expected_metric_ids:
        expected_metric_ids = _TURTLE_INVESTMENT_METRIC_IDS

    adapter = PdfIngestionAdapter(
        semantic_fallback_service=build_semantic_fallback_service(),
    )
    payload = adapter.extract_candidate_facts(
        pdf_path=args.pdf_path,
        pdf_url=None,
        market=args.market,
        min_confidence=args.min_confidence,
    )
    report = build_metric_availability_report(
        payload=payload,
        expected_metric_ids=expected_metric_ids,
        metric_profile=args.metric_profile,
        pdf_path=args.pdf_path,
        market=args.market,
    )
    markdown = render_metric_availability_markdown(report)
    if args.output is None:
        print(markdown, end="")
        return
    args.output.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
