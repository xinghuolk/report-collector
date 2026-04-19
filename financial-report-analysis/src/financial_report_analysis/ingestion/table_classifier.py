from __future__ import annotations

import re


def normalize_table_title(raw_title: str) -> str:
    title = re.sub(r"\s+", "", raw_title).lower()
    return title.replace("（续）", "").replace("(continued)", "")


def classify_table_kind(raw_title: str, *, market: str | None) -> str:
    title = normalize_table_title(raw_title)

    if any(
        token in title
        for token in (
            "利润表",
            "损益表",
            "statementsofincome",
            "statementofincome",
            "statementofprofit",
            "statementofloss",
        )
    ):
        return "income_statement"

    if any(
        token in title
        for token in (
            "资产负债表",
            "statementoffinancialposition",
            "balancesheet",
        )
    ):
        return "balance_sheet"

    if any(
        token in title
        for token in (
            "现金流量表",
            "statementofcashflows",
            "cashflows",
        )
    ):
        return "cash_flow_statement"

    if any(
        token in title
        for token in (
            "主要财务数据",
            "财务数据",
            "financialhighlights",
            "keyfinancialdata",
        )
    ):
        return "key_metrics"

    return "unknown"
