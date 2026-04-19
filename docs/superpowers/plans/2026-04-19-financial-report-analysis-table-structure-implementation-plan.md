# Financial Report Analysis Table Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `financial-report-analysis` 增加可复用的表格结构抽取与对齐层，稳定识别 P0 主表与 P1 主要财务数据表，并产出可供后续 fact builder 消费的 `ParsedTable` 中间对象。

**Architecture:** 不继续在 `src/financial_report_analysis/ingestion/pdf_ingestion.py` 单文件里堆 regex，而是在 `ingestion/` 下拆出 `table_models + classifier + header_parser + stitcher + adapter` 五层。新层先负责页面级文本块、表标题、表头语义、跨页续表和行列绑定，再由现有 `PdfIngestionAdapter` 选择性消费 `ParsedTable` 生成最小 candidate facts，并把 `parsed_tables` 放到 `document_metadata` 供后续阶段复用。

**Tech Stack:** Python 3.10, dataclasses, pypdf, FastAPI (existing service), pytest, Ruff

---

## File Structure

### New files

- Create: `financial-report-analysis/src/financial_report_analysis/models/table.py`
  - 定义 `ParsedTable`、`ParsedColumn`、`ParsedRow`、`ParsedCell`、`PageTextBlock`。
- Create: `financial-report-analysis/src/financial_report_analysis/ingestion/table_classifier.py`
  - 标题规范化、表格类型识别、P0/P1 优先级判定。
- Create: `financial-report-analysis/src/financial_report_analysis/ingestion/table_header_parser.py`
  - 解析期间列、比较列、单位、币种，避免全文级误判。
- Create: `financial-report-analysis/src/financial_report_analysis/ingestion/table_stitcher.py`
  - 处理跨页续表、重复表头、行列拼接。
- Create: `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`
  - 提供 `PdfTableStructureAdapter`，把 PDF 文本转成 `ParsedTable` 列表。
- Create: `financial-report-analysis/tests/unit/test_table_models.py`
- Create: `financial-report-analysis/tests/unit/test_table_classifier.py`
- Create: `financial-report-analysis/tests/unit/test_table_header_parser.py`
- Create: `financial-report-analysis/tests/unit/test_table_stitcher.py`
- Create: `financial-report-analysis/tests/integration/test_table_structure_ingestion.py`

### Existing files to modify

- Modify: `financial-report-analysis/src/financial_report_analysis/models/__init__.py`
  - 导出表格结构模型。
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py`
  - 导出 `PdfTableStructureAdapter`。
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
  - 复用新表格结构层；从 `ParsedTable` 读取 period/unit/currency/row-cell 绑定，而不是继续单点 regex。
- Modify: `financial-report-analysis/src/financial_report_analysis/__init__.py`
  - 导出 `PdfTableStructureAdapter`，方便 service 内部与测试引用。
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`
  - 为真实样本增加 `parsed_tables` 与主表识别断言。

## Task 1: 建立表格结构模型

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/models/table.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/models/__init__.py`
- Test: `financial-report-analysis/tests/unit/test_table_models.py`

- [ ] **Step 1: 写失败测试，固定 `ParsedTable` 最小契约**

```python
from financial_report_analysis.models.table import (
    ParsedCell,
    ParsedColumn,
    ParsedRow,
    ParsedTable,
)


def test_parsed_table_preserves_period_columns_and_page_range() -> None:
    table = ParsedTable(
        table_id="doc-1:table:income:1",
        document_id="doc-1",
        page_range=(10, 11),
        table_kind="income_statement",
        title_text="合并利润表",
        header_rows=[["项目", "2024年度", "2023年度"]],
        body_rows=[],
        table_unit="万元",
        table_currency="CNY",
        period_columns=[
            ParsedColumn(
                column_id="col-current",
                column_index=1,
                header_text="2024年度",
                period_id="2024FY",
                period_scope="duration",
                comparison_axis="current",
                is_current=True,
                is_comparison=False,
            )
        ],
        comparison_columns=[],
        source_blocks=[],
    )

    assert table.page_range == (10, 11)
    assert table.period_columns[0].period_id == "2024FY"


def test_parsed_row_tracks_totals_and_value_cells() -> None:
    row = ParsedRow(
        row_id="row-revenue",
        row_index=5,
        label_raw="营业收入",
        normalized_label_hint="revenue",
        value_cells=[
            ParsedCell(
                row_index=5,
                column_index=1,
                text_raw="3,638,911,068.29",
                numeric_value=3638911068.29,
                bbox=None,
                page_index=0,
            )
        ],
        indent_level=0,
        is_subtotal=False,
        is_total=True,
    )

    assert row.is_total is True
    assert row.value_cells[0].numeric_value == 3638911068.29
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_models.py -v`

Expected: FAIL，提示 `ModuleNotFoundError` 或 `cannot import name 'ParsedTable'`

- [ ] **Step 3: 写最小实现，增加表格 dataclass**

```python
# financial-report-analysis/src/financial_report_analysis/models/table.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(kw_only=True)
class ParsedCell:
    row_index: int
    column_index: int
    text_raw: str
    numeric_value: float | None
    bbox: tuple[float, float, float, float] | None = None
    page_index: int | None = None


@dataclass(kw_only=True)
class ParsedColumn:
    column_id: str
    column_index: int
    header_text: str
    period_id: str | None
    period_scope: str | None
    comparison_axis: str | None
    is_current: bool = False
    is_comparison: bool = False


@dataclass(kw_only=True)
class ParsedRow:
    row_id: str
    row_index: int
    label_raw: str
    normalized_label_hint: str | None
    value_cells: list[ParsedCell] = field(default_factory=list)
    indent_level: int = 0
    is_subtotal: bool = False
    is_total: bool = False


@dataclass(kw_only=True)
class PageTextBlock:
    page_index: int
    lines: list[str]
    raw_text: str


@dataclass(kw_only=True)
class ParsedTable:
    table_id: str
    document_id: str
    page_range: tuple[int, int]
    table_kind: str
    title_text: str
    header_rows: list[list[str]] = field(default_factory=list)
    body_rows: list[ParsedRow] = field(default_factory=list)
    table_unit: str | None = None
    table_currency: str | None = None
    period_columns: list[ParsedColumn] = field(default_factory=list)
    comparison_columns: list[ParsedColumn] = field(default_factory=list)
    source_blocks: list[PageTextBlock] = field(default_factory=list)
```

```python
# financial-report-analysis/src/financial_report_analysis/models/__init__.py
from .table import ParsedCell, ParsedColumn, ParsedRow, ParsedTable, PageTextBlock

__all__ = [
    "ParsedCell",
    "ParsedColumn",
    "ParsedRow",
    "ParsedTable",
    "PageTextBlock",
]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_models.py -v`

Expected: PASS，`2 passed`

- [ ] **Step 5: 提交**

```bash
git add financial-report-analysis/src/financial_report_analysis/models/table.py \
  financial-report-analysis/src/financial_report_analysis/models/__init__.py \
  financial-report-analysis/tests/unit/test_table_models.py
git commit -m "feat: add parsed table models"
```

## Task 2: 实现主表与摘要表识别

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/ingestion/table_classifier.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py`
- Test: `financial-report-analysis/tests/unit/test_table_classifier.py`

- [ ] **Step 1: 写失败测试，固定 P0/P1 表格识别规则**

```python
from financial_report_analysis.ingestion.table_classifier import classify_table_kind


def test_classify_chinese_income_statement_title() -> None:
    assert classify_table_kind("合并利润表", market="CN") == "income_statement"


def test_classify_english_balance_sheet_title() -> None:
    assert classify_table_kind("Condensed Consolidated Statement of Financial Position", market="HK") == "balance_sheet"


def test_classify_key_metrics_table_as_p1() -> None:
    assert classify_table_kind("主要财务数据", market="CN") == "key_metrics"


def test_unknown_title_falls_back_to_unknown() -> None:
    assert classify_table_kind("董事会报告", market="CN") == "unknown"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_classifier.py -v`

Expected: FAIL，提示 `No module named 'financial_report_analysis.ingestion.table_classifier'`

- [ ] **Step 3: 写最小实现，增加标题规范化和识别函数**

```python
# financial-report-analysis/src/financial_report_analysis/ingestion/table_classifier.py
from __future__ import annotations

import re


def normalize_table_title(raw_title: str) -> str:
    collapsed = re.sub(r"\s+", "", raw_title).lower()
    return collapsed.replace("（续）", "").replace("(continued)", "")


def classify_table_kind(raw_title: str, *, market: str | None) -> str:
    title = normalize_table_title(raw_title)
    if any(token in title for token in ("利润表", "损益表", "statementofprofit", "statementofloss")):
        return "income_statement"
    if any(token in title for token in ("资产负债表", "financialposition")):
        return "balance_sheet"
    if any(token in title for token in ("现金流量表", "cashflows")):
        return "cash_flow_statement"
    if any(token in title for token in ("主要财务数据", "financialhighlights", "keyfinancialdata")):
        return "key_metrics"
    return "unknown"
```

```python
# financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py
from .table_classifier import classify_table_kind, normalize_table_title

__all__ = ["classify_table_kind", "normalize_table_title"]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_classifier.py -v`

Expected: PASS，`4 passed`

- [ ] **Step 5: 提交**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/table_classifier.py \
  financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py \
  financial-report-analysis/tests/unit/test_table_classifier.py
git commit -m "feat: add table kind classifier"
```

## Task 3: 实现表头语义解析与局部单位币种判定

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/ingestion/table_header_parser.py`
- Test: `financial-report-analysis/tests/unit/test_table_header_parser.py`

- [ ] **Step 1: 写失败测试，固定期间列、比较列、单位币种优先级**

```python
from financial_report_analysis.ingestion.table_header_parser import (
    detect_table_currency,
    detect_table_unit,
    parse_header_rows,
)


def test_parse_cn_annual_header_rows() -> None:
    columns = parse_header_rows(
        title_text="合并利润表",
        header_rows=[["项目", "2024年度", "2023年度"]],
        market="CN",
    )

    assert columns[0].period_id == "2024FY"
    assert columns[0].comparison_axis == "current"
    assert columns[1].period_id == "2023FY"
    assert columns[1].comparison_axis == "prior"


def test_parse_hk_quarter_header_rows() -> None:
    columns = parse_header_rows(
        title_text="Condensed Consolidated Statement of Profit or Loss",
        header_rows=[["", "Three months ended 30 September 2025", "Three months ended 30 September 2024"]],
        market="HK",
    )

    assert columns[0].period_id == "2025Q3"
    assert columns[0].period_scope == "duration"


def test_detect_currency_prefers_local_table_context() -> None:
    context = "合并利润表\n单位：元  币种：人民币\n营业收入 3,638,911,068.29"
    assert detect_table_currency(context, market="CN") == "CNY"


def test_detect_unit_prefers_table_level_declaration() -> None:
    context = "主要会计数据\n单位：万元\n营业收入 363,891.11"
    assert detect_table_unit(context) == "万元"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_header_parser.py -v`

Expected: FAIL，提示 `No module named 'financial_report_analysis.ingestion.table_header_parser'`

- [ ] **Step 3: 写最小实现，解析表头列语义与局部上下文**

```python
# financial-report-analysis/src/financial_report_analysis/ingestion/table_header_parser.py
from __future__ import annotations

import re

from financial_report_analysis.models import ParsedColumn


def parse_header_rows(
    *,
    title_text: str,
    header_rows: list[list[str]],
    market: str | None,
) -> list[ParsedColumn]:
    flattened = [" ".join(cell for cell in row if cell).strip() for row in header_rows]
    header_text = " | ".join(flattened)
    columns: list[ParsedColumn] = []
    for index, text in enumerate(header_rows[-1][1:], start=1):
        period_id = _detect_period_id(text)
        comparison_axis = "current" if index == 1 else "prior"
        columns.append(
            ParsedColumn(
                column_id=f"column-{index}",
                column_index=index,
                header_text=text,
                period_id=period_id,
                period_scope="duration" if period_id and ("Q" in period_id or "FY" in period_id) else None,
                comparison_axis=comparison_axis,
                is_current=index == 1,
                is_comparison=index != 1,
            )
        )
    return columns


def detect_table_currency(local_context: str, *, market: str | None) -> str:
    if re.search(r"币种[:：]\s*人民币", local_context):
        return "CNY"
    if re.search(r"币种[:：]\s*港元", local_context):
        return "HKD"
    if "HK$" in local_context or "HKD" in local_context.upper():
        return "HKD"
    if "RMB" in local_context.upper() or "人民币" in local_context:
        return "CNY"
    return "HKD" if market == "HK" else "CNY"


def detect_table_unit(local_context: str) -> str | None:
    unit_match = re.search(r"单位[:：]\s*([^\s]+)", local_context)
    if unit_match:
        return unit_match.group(1)
    if "百万元" in local_context:
        return "百万元"
    if "万元" in local_context:
        return "万元"
    if "亿元" in local_context:
        return "亿元"
    return None


def _detect_period_id(header_text: str) -> str | None:
    annual = re.search(r"(20\d{2})\s*年度", header_text)
    if annual:
        return f"{annual.group(1)}FY"
    quarter = re.search(r"30\s+September\s+(20\d{2})", header_text, re.IGNORECASE)
    if quarter:
        return f"{quarter.group(1)}Q3"
    return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_header_parser.py -v`

Expected: PASS，`4 passed`

- [ ] **Step 5: 提交**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/table_header_parser.py \
  financial-report-analysis/tests/unit/test_table_header_parser.py
git commit -m "feat: add table header parser"
```

## Task 4: 实现跨页续表拼接与行列绑定

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/ingestion/table_stitcher.py`
- Test: `financial-report-analysis/tests/unit/test_table_stitcher.py`

- [ ] **Step 1: 写失败测试，固定续表合并与行标签绑定**

```python
from financial_report_analysis.ingestion.table_stitcher import (
    bind_body_rows,
    should_merge_tables,
    stitch_tables,
)
from financial_report_analysis.models import PageTextBlock, ParsedTable


def test_should_merge_tables_for_continued_income_statement() -> None:
    first = ParsedTable(
        table_id="doc:table:1",
        document_id="doc",
        page_range=(20, 20),
        table_kind="income_statement",
        title_text="合并利润表",
    )
    second = ParsedTable(
        table_id="doc:table:2",
        document_id="doc",
        page_range=(21, 21),
        table_kind="income_statement",
        title_text="合并利润表（续）",
    )

    assert should_merge_tables(first, second) is True


def test_bind_body_rows_extracts_numeric_cells() -> None:
    rows = bind_body_rows(
        page_index=0,
        body_lines=[
            "营业收入 3,638,911,068.29 3,049,155,693.42",
            "总资产 15,444,000,000.00 13,210,000,000.00",
        ],
    )

    assert rows[0].label_raw == "营业收入"
    assert rows[0].value_cells[0].numeric_value == 3638911068.29
    assert rows[1].label_raw == "总资产"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_stitcher.py -v`

Expected: FAIL，提示 `No module named 'financial_report_analysis.ingestion.table_stitcher'`

- [ ] **Step 3: 写最小实现，增加续表判定与行值解析**

```python
# financial-report-analysis/src/financial_report_analysis/ingestion/table_stitcher.py
from __future__ import annotations

import re

from financial_report_analysis.models import ParsedCell, ParsedRow, ParsedTable


def should_merge_tables(previous: ParsedTable, current: ParsedTable) -> bool:
    same_kind = previous.table_kind == current.table_kind and previous.table_kind != "unknown"
    continued = "续" in current.title_text or "continued" in current.title_text.lower()
    adjacent = current.page_range[0] - previous.page_range[1] <= 1
    return same_kind and continued and adjacent


def bind_body_rows(*, page_index: int, body_lines: list[str]) -> list[ParsedRow]:
    rows: list[ParsedRow] = []
    for row_index, line in enumerate(body_lines):
        numbers = re.findall(r"[0-9][0-9,]*(?:\.\d+)?", line)
        label = re.sub(r"[0-9,\.\s]+$", "", line).strip()
        value_cells = [
            ParsedCell(
                row_index=row_index,
                column_index=column_index,
                text_raw=value,
                numeric_value=float(value.replace(",", "")),
                bbox=None,
                page_index=page_index,
            )
            for column_index, value in enumerate(numbers, start=1)
        ]
        rows.append(
            ParsedRow(
                row_id=f"row-{page_index}-{row_index}",
                row_index=row_index,
                label_raw=label,
                normalized_label_hint=None,
                value_cells=value_cells,
                indent_level=0,
                is_subtotal=False,
                is_total=any(token in label for token in ("收入", "资产", "现金")),
            )
        )
    return rows


def stitch_tables(tables: list[ParsedTable]) -> list[ParsedTable]:
    if not tables:
        return []
    stitched: list[ParsedTable] = [tables[0]]
    for table in tables[1:]:
        previous = stitched[-1]
        if should_merge_tables(previous, table):
            previous.page_range = (previous.page_range[0], table.page_range[1])
            previous.body_rows.extend(table.body_rows)
            continue
        stitched.append(table)
    return stitched
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_stitcher.py -v`

Expected: PASS，`2 passed`

- [ ] **Step 5: 提交**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/table_stitcher.py \
  financial-report-analysis/tests/unit/test_table_stitcher.py
git commit -m "feat: add table stitcher and row binder"
```

## Task 5: 集成 `PdfTableStructureAdapter`

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/__init__.py`
- Test: `financial-report-analysis/tests/integration/test_table_structure_ingestion.py`

- [ ] **Step 1: 写失败集成测试，固定真实样本主表识别与结构输出**

```python
from pathlib import Path

from financial_report_analysis.ingestion import PdfTableStructureAdapter


def _sample_pdf(*parts: str) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    main_repo_root = repo_root.parent.parent
    for root in (repo_root, main_repo_root):
        candidate = root / "report" / "downloads" / Path(*parts)
        if candidate.exists():
            return str(candidate)
    raise AssertionError(f"Sample PDF not found for {parts}")


def test_cn_annual_sample_exposes_income_statement_and_balance_sheet() -> None:
    adapter = PdfTableStructureAdapter()

    tables = adapter.extract_tables(
        pdf_path=_sample_pdf("cn_stocks", "688008", "annual", "2024_年度报告.pdf"),
        pdf_url=None,
        market="CN",
    )

    kinds = {table.table_kind for table in tables}
    assert "income_statement" in kinds
    assert "balance_sheet" in kinds


def test_hk_quarter_sample_exposes_period_columns() -> None:
    adapter = PdfTableStructureAdapter()

    tables = adapter.extract_tables(
        pdf_path=_sample_pdf("hk_stocks", "09987", "quarterly", "2025_quarterly_q3_en.pdf"),
        pdf_url=None,
        market="HK",
    )

    income_table = next(table for table in tables if table.table_kind == "income_statement")
    assert income_table.period_columns
    assert income_table.period_columns[0].period_id is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd financial-report-analysis && uv run pytest tests/integration/test_table_structure_ingestion.py -v`

Expected: FAIL，提示 `cannot import name 'PdfTableStructureAdapter'`

- [ ] **Step 3: 写最小实现，组装分类、表头解析、续表拼接**

```python
# financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import httpx
from pypdf import PdfReader

from financial_report_analysis.ingestion.table_classifier import classify_table_kind
from financial_report_analysis.ingestion.table_header_parser import (
    detect_table_currency,
    detect_table_unit,
    parse_header_rows,
)
from financial_report_analysis.ingestion.table_stitcher import bind_body_rows, stitch_tables
from financial_report_analysis.models import PageTextBlock, ParsedTable


class PdfTableStructureAdapter:
    def extract_tables(
        self,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
        market: str | None,
    ) -> list[ParsedTable]:
        pages = self._read_pages(pdf_path=pdf_path, pdf_url=pdf_url)
        raw_tables: list[ParsedTable] = []
        document_id = pdf_path or pdf_url or "unknown-document"
        for page_index, page_text in enumerate(pages):
            lines = [line.strip() for line in page_text.splitlines() if line.strip()]
            for line_index, line in enumerate(lines):
                table_kind = classify_table_kind(line, market=market)
                if table_kind == "unknown":
                    continue
                local_lines = lines[line_index : line_index + 8]
                header_rows = [self._split_row(local_lines[1])] if len(local_lines) > 1 else []
                context = "\n".join(local_lines)
                raw_tables.append(
                    ParsedTable(
                        table_id=f"{document_id}:table:{page_index}:{line_index}",
                        document_id=document_id,
                        page_range=(page_index, page_index),
                        table_kind=table_kind,
                        title_text=line,
                        header_rows=header_rows,
                        body_rows=bind_body_rows(page_index=page_index, body_lines=local_lines[2:]),
                        table_unit=detect_table_unit(context),
                        table_currency=detect_table_currency(context, market=market),
                        period_columns=parse_header_rows(
                            title_text=line,
                            header_rows=header_rows or [["项目"]],
                            market=market,
                        ),
                        comparison_columns=[],
                        source_blocks=[
                            PageTextBlock(page_index=page_index, lines=local_lines, raw_text="\n".join(local_lines))
                        ],
                    )
                )
        return stitch_tables(raw_tables)

    @staticmethod
    def _read_pages(*, pdf_path: str | None, pdf_url: str | None) -> list[str]:
        if pdf_path:
            reader = PdfReader(str(Path(pdf_path)))
            return [page.extract_text() or "" for page in reader.pages]
        response = httpx.get(pdf_url, timeout=30.0)
        response.raise_for_status()
        reader = PdfReader(BytesIO(response.content))
        return [page.extract_text() or "" for page in reader.pages]

    @staticmethod
    def _split_row(raw_line: str) -> list[str]:
        return [part for part in raw_line.split("  ") if part]
```

```python
# financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py
from .table_structure import PdfTableStructureAdapter

__all__ = ["PdfTableStructureAdapter"]
```

```python
# financial-report-analysis/src/financial_report_analysis/__init__.py
from .ingestion import PdfTableStructureAdapter

__all__ = ["PdfTableStructureAdapter"]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd financial-report-analysis && uv run pytest tests/integration/test_table_structure_ingestion.py -v`

Expected: PASS，真实样本至少识别出 `income_statement`，且有非空 `period_columns`

- [ ] **Step 5: 提交**

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py \
  financial-report-analysis/src/financial_report_analysis/ingestion/__init__.py \
  financial-report-analysis/src/financial_report_analysis/__init__.py \
  financial-report-analysis/tests/integration/test_table_structure_ingestion.py
git commit -m "feat: add pdf table structure adapter"
```

## Task 6: 让现有 `PdfIngestionAdapter` 消费 `ParsedTable`

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`

- [ ] **Step 1: 写失败测试，固定 API 返回里保留 `parsed_tables` 元数据**

```python
from pathlib import Path

from fastapi.testclient import TestClient

from financial_report_analysis.api.app import create_app


def _resolve_sample_pdf(*parts: str) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    main_repo_root = repo_root.parent.parent
    for root in (repo_root, main_repo_root):
        candidate = root / "report" / "downloads" / Path(*parts)
        if candidate.exists():
            return str(candidate)
    raise AssertionError(f"Sample PDF not found for {parts}")


def test_extract_endpoint_includes_parsed_tables_for_cn_sample() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": _resolve_sample_pdf("cn_stocks", "688008", "annual", "2024_年度报告.pdf"),
            "market": "CN",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["metadata"]["parsed_tables"]
    first_table = payload["document"]["metadata"]["parsed_tables"][0]
    assert first_table["table_kind"] in {
        "income_statement",
        "balance_sheet",
        "cash_flow_statement",
        "key_metrics",
    }
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd financial-report-analysis && uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_includes_parsed_tables_for_cn_sample -v`

Expected: FAIL，提示 `KeyError: 'parsed_tables'`

- [ ] **Step 3: 写最小实现，复用 `PdfTableStructureAdapter` 并透出元数据**

```python
# financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py
from typing import Any

from financial_report_analysis.ingestion.table_structure import PdfTableStructureAdapter


class PdfIngestionAdapter:
    def __init__(self) -> None:
        self._table_adapter = PdfTableStructureAdapter()

    def extract_candidate_facts(
        self,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
        market: str | None,
        min_confidence: float | None,
    ) -> dict[str, Any]:
        text = self._extract_text(pdf_path=pdf_path, pdf_url=pdf_url)
        language = self._detect_language(text, market)
        candidate_facts: list[dict[str, Any]] = []
        parsed_tables = self._table_adapter.extract_tables(
            pdf_path=pdf_path,
            pdf_url=pdf_url,
            market=market,
        )
        period_id = next(
            (
                column.period_id
                for table in parsed_tables
                for column in table.period_columns
                if column.period_id is not None
            ),
            None,
        ) or self._detect_period_id(text)
        revenue_table = next(
            (table for table in parsed_tables if table.table_kind in {"income_statement", "key_metrics"}),
            None,
        )
        if revenue_table is not None:
            currency = revenue_table.table_currency or self._detect_currency(text, market)
            raw_unit = revenue_table.table_unit or self._detect_raw_unit(text)
            revenue_row = next(
                (row for row in revenue_table.body_rows if row.label_raw in {"营业收入", "Revenue", "Turnover"}),
                None,
            )
            if revenue_row is not None and revenue_row.value_cells:
                numeric_value = revenue_row.value_cells[0].numeric_value
                candidate_facts.append(
                    {
                        "fact_id": f"{pdf_path or pdf_url}:candidate:1",
                        "fact_kind": "candidate",
                        "metric_id": "raw_revenue",
                        "metric_label_raw": revenue_row.label_raw,
                        "statement_type": revenue_table.table_kind,
                        "entity_scope": "consolidated",
                        "comparison_axis": "current",
                        "adjustment_basis": "reported",
                        "period_id": period_id,
                        "currency": currency,
                        "raw_value": revenue_row.value_cells[0].text_raw,
                        "numeric_value": numeric_value,
                        "raw_unit": raw_unit,
                        "normalized_unit": None,
                        "precision": self._precision(numeric_value or 0.0),
                        "confidence": 0.9,
                        "extensions": {"market": market or "CN", "accounting_standard": "OTHER"},
                        "document_id": pdf_path or pdf_url or "unknown-document",
                        "block_id": f"{pdf_path or pdf_url}:block:1",
                        "page_index": revenue_row.value_cells[0].page_index,
                        "evidence_bundle_id": f"{pdf_path or pdf_url}:bundle:1",
                        "table_coord": (
                            revenue_row.value_cells[0].row_index,
                            revenue_row.value_cells[0].column_index,
                        ),
                        "extraction_method": "table_structure",
                        "extraction_version": "v2",
                        "source_rank_hint": 1,
                    }
                )
        return {
            "candidate_facts": candidate_facts,
            "document_metadata": {
                "language": language,
                "parsed_tables": [
                    {
                        "table_id": table.table_id,
                        "table_kind": table.table_kind,
                        "title_text": table.title_text,
                        "page_range": list(table.page_range),
                        "table_unit": table.table_unit,
                        "table_currency": table.table_currency,
                        "period_columns": [
                            {
                                "column_index": column.column_index,
                                "period_id": column.period_id,
                                "comparison_axis": column.comparison_axis,
                            }
                            for column in table.period_columns
                        ],
                    }
                    for table in parsed_tables
                ],
            },
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd financial-report-analysis && uv run pytest tests/integration/test_analysis_api.py::test_extract_endpoint_includes_parsed_tables_for_cn_sample -v`

Expected: PASS，`document.metadata.parsed_tables` 非空，且表格类型命中 P0/P1

- [ ] **Step 5: 运行回归并提交**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_models.py tests/unit/test_table_classifier.py tests/unit/test_table_header_parser.py tests/unit/test_table_stitcher.py tests/integration/test_table_structure_ingestion.py tests/integration/test_analysis_api.py -v`

Expected: PASS，所有新增表结构测试与既有 API 回归通过

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py \
  financial-report-analysis/tests/integration/test_analysis_api.py
git commit -m "feat: expose parsed table metadata"
```

## Task 7: 代码质量检查与 README 补充

**Files:**
- Modify: `financial-report-analysis/README.md`

- [ ] **Step 1: 写 README 增量说明，记录表格结构调试入口**

````md
## Table Structure Debugging

Use the analysis API or `PdfTableStructureAdapter` directly to inspect parsed table metadata before adding new fact mappings.

```python
from financial_report_analysis.ingestion import PdfTableStructureAdapter

adapter = PdfTableStructureAdapter()
tables = adapter.extract_tables(
    pdf_path="report/downloads/cn_stocks/688008/annual/2024_年度报告.pdf",
    pdf_url=None,
    market="CN",
)
print([(table.table_kind, table.title_text, table.page_range) for table in tables])
```
````

- [ ] **Step 2: 运行 Ruff**

Run: `cd financial-report-analysis && uv run ruff check src tests`

Expected: PASS，`All checks passed`

- [ ] **Step 3: 运行最终测试集**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_table_models.py tests/unit/test_table_classifier.py tests/unit/test_table_header_parser.py tests/unit/test_table_stitcher.py tests/integration/test_table_structure_ingestion.py tests/integration/test_analysis_api.py tests/unit/test_fact_pipeline.py -v`

Expected: PASS，新增表结构测试与既有 ingestion/pipeline 回归共同通过

- [ ] **Step 4: 提交**

```bash
git add financial-report-analysis/README.md
git commit -m "docs: document table structure debugging"
```

## Self-Review

- Spec coverage:
  - 主表与摘要表识别：Task 2
  - 表头期间/比较列/单位/币种：Task 3
  - 跨页续表：Task 4
  - 行列绑定：Task 4
  - 结构化中间对象：Task 1
  - 真实样本回归：Task 5、Task 6、Task 7
- Placeholder scan:
  - 已检查，无 `TODO`、`TBD`、`implement later`、`write tests for the above` 这类占位语句。
- Type consistency:
  - `ParsedTable / ParsedColumn / ParsedRow / ParsedCell / PdfTableStructureAdapter` 在所有任务中保持同名。
  - `parsed_tables` 始终位于 `document_metadata`，避免 API 字段名漂移。
