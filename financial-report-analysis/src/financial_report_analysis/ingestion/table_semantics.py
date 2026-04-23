from __future__ import annotations

import re

from financial_report_analysis.models import (
    NormalizedTableCellValue,
    NormalizedTableColumn,
    NormalizedTableRow,
    NormalizedTableSemantics,
    ParsedRow,
    ParsedTable,
)

_SUPPRESSED_SUMMARY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(growth|margin|ratio)\b", re.IGNORECASE),
    re.compile(
        r"\b(free cash flow|cash flow trend|cash flow variance|cash flow ratio)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bbook value\b", re.IGNORECASE),
    re.compile(r"\bnet increase(?:/decrease)? in cash(?: and cash equivalents)?\b", re.IGNORECASE),
    re.compile(r"\bsubtotal\b", re.IGNORECASE),
    re.compile(r"(增长率|增长|比率|利润率|毛利率)"),
    re.compile(r"小计"),
)

_WORKING_CAPITAL_SUPPRESSED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\baccounts receivable financing\b", re.IGNORECASE),
    re.compile(r"\blong[- ]term receivables\b", re.IGNORECASE),
    re.compile(r"\bemployee compensation payable\b", re.IGNORECASE),
    re.compile(r"\btaxes payable\b", re.IGNORECASE),
    re.compile(r"\bchanges in accounts receivable\b", re.IGNORECASE),
    re.compile(r"应收款项融资"),
    re.compile(r"长期应收款"),
    re.compile(r"应付职工薪酬"),
    re.compile(r"应交税费"),
    re.compile(r"应付债券"),
    re.compile(r"经营性应收项目的减少"),
)

_P2B_DEBT_SUPPRESSED_LABELS: frozenset[str] = frozenset(
    {
        "lease liabilities",
        "total borrowings",
        "borrowings and other liabilities",
        "租赁负债",
        "借款及其他负债",
        "借款合计",
    }
)

_P3_ASSET_NOTE_ONLY_LABELS: frozenset[str] = frozenset(
    {
        "contract assets",
        "other non-current assets",
        "合同资产",
        "其他非流动资产",
    }
)

_P3_ASSET_SUPPRESSED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bassets held for sale\b", re.IGNORECASE),
    re.compile(r"\binvestment properties\b", re.IGNORECASE),
    re.compile(r"\bprepayments\b", re.IGNORECASE),
    re.compile(r"\bright[- ]of[- ]use assets\b", re.IGNORECASE),
    re.compile(r"\bdeferred tax assets\b", re.IGNORECASE),
    re.compile(r"\bcapitali[sz]ed development costs\b", re.IGNORECASE),
    re.compile(r"\btotal non[- ]current assets\b", re.IGNORECASE),
    re.compile(r"受限资金"),
    re.compile(r"持有待售资产"),
    re.compile(r"投资性房地产"),
    re.compile(r"预付款项"),
    re.compile(r"使用权资产"),
    re.compile(r"递延所得税资产"),
    re.compile(r"开发支出"),
    re.compile(r"非流动资产合计"),
)

_ROW_LABEL_ALIASES: dict[str, str] = {
    "restricted cash": "restricted cash",
    "restricted cash and cash equivalents": "restricted cash and cash equivalents",
    "restricted monetary funds": "restricted monetary funds",
    "受限货币资金": "受限货币资金",
    "cash paid for interest": "cash paid for interest",
    "支付的利息": "支付的利息",
    "time deposits": "time deposits",
    "term deposits": "term deposits",
    "wealth management products": "wealth management products",
    "structured deposits": "structured deposits",
    "long-term bank deposits and notes": "long-term bank deposits and notes",
    "定期存款": "定期存款",
    "理财产品": "理财产品",
    "结构性存款": "结构性存款",
    "cash and cash equivalents": "cash and cash equivalents",
    "货币资金": "cash and cash equivalents",
    "现金及现金等价物": "cash and cash equivalents",
    "revenue": "revenue",
    "turnover": "revenue",
    "营业收入": "revenue",
    "营业总收入": "revenue",
    "trading assets": "trading assets",
    "交易性金融资产": "trading assets",
    "inventories": "inventories",
    "inventory": "inventories",
    "存货": "inventories",
    "goodwill": "goodwill",
    "商誉": "goodwill",
    "intangible assets": "intangible assets",
    "无形资产": "intangible assets",
    "cost of sales": "operating cost",
    "cost of revenue": "operating cost",
    "营业成本": "operating cost",
    "operating profit": "operating profit",
    "profit from operations": "operating profit",
    "营业利润": "operating profit",
    "net profit": "net profit",
    "net income": "net profit",
    "profit for the period": "net profit",
    "净利润": "net profit",
    "gross profit for the period": "gross profit",
    "gross profit attributable to operations": "gross profit",
    "accounts receivable, net": "accounts receivable",
    "accounts receivable": "accounts receivable",
    "accounts receivables": "accounts receivables",
    "应收账款": "accounts receivables",
    "notes receivable": "notes receivable",
    "notes receivables": "notes receivables",
    "应收票据": "notes receivable",
    "other receivables": "other receivables",
    "其他应收款": "other receivables",
    "contract liabilities": "contract liabilities",
    "合同负债": "contract liabilities",
    "payments received in advance": "advances from customers",
    "advances from customers": "advances from customers",
    "预收款项": "advances from customers",
    "accounts payable": "accounts payable",
    "应付账款": "accounts payable",
    "notes payable": "notes payable",
    "应付票据": "notes payable",
    "short-term borrowings": "short-term borrowings",
    "long-term borrowings": "long-term borrowings",
    "bonds payable": "bonds payable",
    "current portion of long-term debt": "current portion of long-term debt",
    "\u77ed\u671f\u501f\u6b3e": "short-term borrowings",
    "\u957f\u671f\u501f\u6b3e": "long-term borrowings",
    "\u5e94\u4ed8\u503a\u5238": "bonds payable",
    "\u4e00\u5e74\u5185\u5230\u671f\u7684\u975e\u6d41\u52a8\u8d1f\u503a": "current portion of long-term debt",
    "net cash from operating activities": "operating cash flow",
    "net cash generated from operating activities": "operating cash flow",
    "net cash used in operating activities": "operating cash flow",
    "经营活动产生的现金流量净额": "operating cash flow",
    "net cash generated from investing activities": "investing cash flow",
    "net cash from investing activities": "investing cash flow",
    "net cash used in investing activities": "investing cash flow",
    "投资活动产生的现金流量净额": "investing cash flow",
    "net cash generated from financing activities": "financing cash flow",
    "net cash from financing activities": "financing cash flow",
    "net cash used in financing activities": "financing cash flow",
    "筹资活动产生的现金流量净额": "financing cash flow",
    "cash paid to and on behalf of employees": "cash paid to and on behalf of employees",
    "cash paid to employees": "cash paid to and on behalf of employees",
    "支付给职工以及为职工支付的现金": "cash paid to and on behalf of employees",
    "taxes paid": "taxes paid",
    "tax paid": "taxes paid",
    "cash paid for taxes": "taxes paid",
    "支付的各项税费": "taxes paid",
    "毛利润": "gross profit",
    "毛利": "gross profit",
    "营业毛利": "gross profit",
    "total assets": "total assets",
    "资产总计": "total assets",
    "总资产": "total assets",
    "total liabilities": "total liabilities",
    "负债合计": "total liabilities",
    "总负债": "total liabilities",
    "equity attributable to owners of the parent": "equity attributable to owners of the parent",
    "equity attributable to equity holders of the company": "equity attributable to equity holders of the company",
    "total equity": "equity",
    "total shareholders' equity": "equity",
    "所有者权益合计": "equity",
    "股东权益合计": "equity",
    "归属于母公司股东权益": "equity attributable to owners of the parent",
    "归属于母公司所有者权益": "equity attributable to owners of the parent",
    "profit attributable to equity holders": "net profit",
    "profit attributable to shareholders": "net profit",
    "profit attributable to owners of the parent": "net profit attributable to owners of the parent",
    "profit attributable to equity holders of the company": "net profit attributable to owners of the parent",
    "归属于母公司股东的净利润": "net profit attributable to owners of the parent",
    "归属于上市公司股东的净利润": "net profit attributable to owners of the parent",
    "finance costs": "finance expense",
    "finance expenses": "finance expense",
    "财务费用": "finance expense",
    "profit before tax": "total profit",
    "利润总额": "total profit",
    "income tax expense": "income tax",
    "tax expense": "income tax",
    "所得税费用": "income tax",
    "profit attributable to non-controlling interests": "minority interest profit",
    "profit attributable to non controlling interests": "minority interest profit",
    "少数股东损益": "minority interest profit",
    "payments for acquisition of property, plant and equipment": "capital expenditure cash outflow",
    "payments for acquisition of property plant and equipment": "capital expenditure cash outflow",
    "payments for acquisition of property, plant and equipment and intangible assets": "capital expenditure cash outflow",
    "payments for acquisition of property plant and equipment and intangible assets": "capital expenditure cash outflow",
    "payments for acquisition and construction of long-term assets": "capital expenditure cash outflow",
    "购建固定资产、无形资产和其他长期资产支付的现金": "capital expenditure cash outflow",
    "depreciation of property, plant and equipment": "depreciation of fixed assets",
    "depreciation of property plant and equipment": "depreciation of fixed assets",
    "depreciation of fixed assets oil and gas assets and productive biological assets": "depreciation of fixed assets",
    "固定资产折旧": "depreciation of fixed assets",
    "amortisation of intangible assets": "amortisation of intangible assets",
    "amortization of intangible assets": "amortisation of intangible assets",
    "无形资产摊销": "amortisation of intangible assets",
    "amortisation of long-term deferred expenses": "amortisation of long-term deferred expenses",
    "amortization of long-term deferred expenses": "amortisation of long-term deferred expenses",
    "长期待摊费用摊销": "amortisation of long-term deferred expenses",
    "dividends paid": "cash paid for dividends or interest",
    "dividends and interest paid": "cash paid for dividends or interest",
    "cash paid for dividends or interest": "cash paid for dividends or interest",
    "cash paid for distribution of dividends or profits and interest expenses": "cash paid for dividends or interest",
    "分配股利、利润或偿付利息支付的现金": "cash paid for dividends or interest",
}


def normalize_table_semantics(table: ParsedTable) -> NormalizedTableSemantics:
    all_columns = [*table.period_columns, *table.comparison_columns]
    normalized_columns = [
        NormalizedTableColumn(
            column_id=column.column_id,
            header_text=column.header_text,
            period_id=column.period_id,
            comparison_axis=column.comparison_axis,
            value_time_shape=column.value_time_shape,
            is_current=column.is_current,
            is_comparison=column.is_comparison,
        )
        for column in all_columns
    ]
    column_by_index = {column.column_index: column for column in all_columns}

    return NormalizedTableSemantics(
        table_id=table.table_id,
        document_id=table.document_id,
        page_range=table.page_range,
        table_kind=table.table_kind,
        title_text=table.title_text,
        statement_scope_guess=table.statement_scope_guess,
        table_unit=_normalized_semantic_value(table.table_unit),
        table_currency=_normalized_semantic_value(table.table_currency),
        unit_semantic_source="deterministic",
        currency_semantic_source="deterministic",
        semantic_source="deterministic",
        semantic_confidence=None,
        semantic_ambiguity_reason=table.semantic_ambiguity_reason,
        columns=normalized_columns,
        rows=[
            _normalize_row(row, column_by_index=column_by_index)
            for row in table.body_rows
        ],
    )


def _normalize_row(
    row: ParsedRow,
    *,
    column_by_index: dict[int, object],
) -> NormalizedTableRow:
    normalized_label = row.normalized_label_hint or _normalize_label(row.label_raw)
    return NormalizedTableRow(
        row_id=row.row_id,
        label_raw=row.label_raw,
        normalized_row_label=normalized_label,
        semantic_source="deterministic",
        semantic_confidence=None,
        fallback_reason=None,
        values=[
            NormalizedTableCellValue(
                row_index=cell.row_index,
                column_index=cell.column_index,
                raw_text=cell.text_raw,
                numeric_value=cell.numeric_value,
                period_id=getattr(column_by_index.get(cell.column_index), "period_id", None),
                comparison_axis=getattr(
                    column_by_index.get(cell.column_index),
                    "comparison_axis",
                    None,
                ),
                value_time_shape=getattr(
                    column_by_index.get(cell.column_index),
                    "value_time_shape",
                    None,
                ),
            )
            for cell in row.value_cells
        ],
    )


def _normalize_label(raw_label: str) -> str | None:
    normalized = raw_label.strip()
    normalized = re.sub(r"^[（(]?[一二三四五六七八九十]+[)）\.、]\s*", "", normalized)
    normalized = re.sub(r"^[（(]?\d+[)）\.、]\s*", "", normalized)
    normalized = re.sub(r"^[IVXLCM]+\.\s*", "", normalized, flags=re.IGNORECASE)
    normalized = _strip_note_suffixes(normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().casefold()
    if not normalized:
        return None

    # Keep ratio / growth style rows fact-agnostic so they do not compete with
    # core statement metrics in summary or key-metrics tables.
    if _is_summary_style_core_metric_row(normalized):
        return None
    if _is_basic_eps_label(normalized):
        return "basic earnings per share"
    if _is_excluded_eps_label(normalized):
        return None
    if _is_narrative_cash_flow_label(normalized):
        return None
    if normalized == "\u5e94\u4ed8\u503a\u5238":
        return "bonds payable"
    if any(pattern.search(normalized) for pattern in _SUPPRESSED_SUMMARY_PATTERNS):
        return None
    if any(pattern.search(normalized) for pattern in _WORKING_CAPITAL_SUPPRESSED_PATTERNS):
        return None
    if _is_p2b_debt_negative_control(normalized):
        return None
    if normalized in {label.casefold() for label in _P3_ASSET_NOTE_ONLY_LABELS}:
        return None
    if any(pattern.search(normalized) for pattern in _P3_ASSET_SUPPRESSED_PATTERNS):
        return None

    return _ROW_LABEL_ALIASES.get(normalized, normalized)


def _is_summary_style_core_metric_row(normalized_label: str) -> bool:
    summary_match = re.fullmatch(
        r"(revenue|gross profit|operating profit|net profit)\s+summary",
        normalized_label,
    )
    if summary_match is not None:
        return True
    return normalized_label == "summary"


def _is_basic_eps_label(normalized_label: str) -> bool:
    english_eps = (
        ("earnings per share" in normalized_label or re.search(r"\bbasic eps\b", normalized_label))
        and "basic" in normalized_label
    )
    chinese_eps = ("每股收益" in normalized_label or "每股盈利" in normalized_label) and "基本" in normalized_label
    return bool(english_eps or chinese_eps)


def _is_excluded_eps_label(normalized_label: str) -> bool:
    if "per share" not in normalized_label and "eps" not in normalized_label and "每股" not in normalized_label:
        return False

    exclusion_patterns = (
        r"\bdiluted\b",
        r"\badjusted\b",
        r"\bnon[- ]gaap\b",
        r"\bnon[- ]ifrs\b",
        r"\bheadline\b",
        r"稀释",
        r"调整后",
        r"非公认会计准则",
        r"非国际财务报告准则",
        r"每股净资产",
    )
    if any(re.search(pattern, normalized_label, re.IGNORECASE) for pattern in exclusion_patterns):
        return True
    return True


def _is_narrative_cash_flow_label(normalized_label: str) -> bool:
    return any(
        re.search(pattern, normalized_label, re.IGNORECASE) is not None
        for pattern in (
            r"\banalysis of balances? of cash and cash equivalents\b",
            r"\bcash flows? before (?:changes|movements) in working capital\b",
            r"\bcash generated from operations before (?:changes|movements) in working capital\b",
            r"\breconciliation of .* cash flows?\b",
            r"\bnet increase(?:/decrease)? in cash(?: and cash equivalents)?\b",
            r"现金及现金等价物.*分析",
            r"营运资金变动前的现金流量",
        )
    )


def _is_p2b_debt_negative_control(normalized_label: str) -> bool:
    return normalized_label in _P2B_DEBT_SUPPRESSED_LABELS


def _strip_note_suffixes(value: str) -> str:
    normalized = re.sub(
        r"\s+(?:[IVXLCM]+(?:\.\d+)+|[IVXLCM]+)\s*[.\-、．]?\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"\s+(?:[一二三四五六七八九十百千]+)\s*[、.\-．]?\s*$",
        "",
        normalized,
    )
    normalized = re.sub(r"\s*[-‐‑–—]\s*$", "", normalized)
    return normalized


def _normalized_semantic_value(value: str | None) -> str:
    if value is None:
        return "unknown"
    normalized = value.strip()
    return normalized or "unknown"
