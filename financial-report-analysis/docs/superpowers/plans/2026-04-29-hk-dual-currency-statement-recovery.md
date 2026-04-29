# HK Dual-Currency Statement Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 HK.00001 2025 年报主报表抽取失败，使双币种英文年报中的利润表、资产负债表、现金流量表能恢复出稳定行结构，并让龟龟投资关键字段从 deterministic 主路径产出。

**Architecture:** 根因在 PDF 表格结构恢复层：pdfplumber 将 HK.00001 主报表抽成“首列 US$ 数值 + 中列多行 label/Note + 后列 HK$ 数值”的错位表，现有恢复器只支持 label 在数值前的行。方案是在 `table_structure.py` 中增加仅针对 HK annual main statements 的 page text 双币种行恢复，把 US$ 展示列和 Note 列丢弃，输出现有 `bind_body_rows()` 能消费的 `[label, HK current, HK prior...]` 行，避免把错误结构推给 semantic fallback。

**Tech Stack:** Python 3.12, pytest, pdfplumber-derived `RawTableBlock`, `ParsedTable`, `ParsedColumn`, deterministic table semantics, existing real PDF fixtures under `report/downloads/hk_stocks`.

---

## Problem Statement

HK.00001 2025 年报的主报表页面文本包含完整数据，例如：

```text
Consolidated Income Statement
for the year ended 31 December 2025
2025 # 2025 2024 2023
US$ million Note HK$ million HK$ million HK$ million
35,902 Revenue 5 280,036 281,351 275,575
(14,565) Cost of inventories sold 8 (113,608) (106,194) (105,739)
```

但 pdfplumber 表格输出类似：

```python
[
    ["35,902", "Revenue 5\nCost of inventories sold 8\nStaff costs", "280,036"],
    ["(14,565)", None, "(113,608)"],
    ["(5,601)", None, "(43,688)"],
]
```

当前 `_recover_structured_row()` 只识别 `label value value`，不能识别 `us_value label note hk_value...`。结果是：

```text
parsed_tables: 31
candidate_facts: 8
table_kind_counts: balance_sheet=15, cash_flow_statement=15, unknown=1
income_statement: 0
candidate_metric_ids: oth_receiv=4, cash=4
semantic_fallback_call_counts: table_kind=31, row_label=10, unit=10
```

这不是 alias 问题，也不是 Ollama fallback 问题。先修结构恢复，只有结构恢复通过后才评估字段映射缺口。

## Files

- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_header_parser.py`
- Modify: `financial-report-analysis/tests/unit/test_table_structure.py`
- Modify: `financial-report-analysis/tests/unit/test_table_header_parser.py`
- Modify: `financial-report-analysis/tests/integration/test_table_structure_ingestion.py`
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`
- Optional docs update after verification: `financial-report-analysis/docs/architecture-analysis/2026-04-22-turtle-v015-financial-field-gap-analysis.md`
- Optional docs update after verification: `financial-report-analysis/docs/architecture-analysis/new-report-sample-onboarding-and-field-variance-process.md`

## Guardrails

- Do not change `metric_mapping.py` until HK.00001 main-statement structure tests pass.
- Do not make Ollama fallback part of the deterministic success path for HK.00001 main statements.
- Preserve existing HK anchors: `02498`, `06862`, `09987`.
- Recovery must be gated to HK annual main statement pages with `US$ million` and `HK$ million` context. It must not run on generic note tables.
- Output rows must keep existing downstream contract: first cell is row label, following cells are period values.

---

### Task 1: Add Unit Tests for HK Dual-Currency Page Text Recovery

**Files:**
- Modify: `financial-report-analysis/tests/unit/test_table_structure.py`

- [ ] **Step 1: Add a failing income statement recovery test**

Append this test near the existing HK statement recovery tests:

```python
def test_hk_dual_currency_income_statement_recovers_hk_rows_from_page_text() -> None:
    adapter = PdfTableStructureAdapter()
    block = RawTableBlock(
        block_id="doc:page:134:table:1",
        page_index=133,
        page_range=(133, 133),
        table_index=0,
        rows=[
            ["35,902", "Revenue 5\nCost of inventories sold 8\nStaff costs\nOperating profit", "280,036"],
            ["(14,565)", None, "(113,608)"],
            ["(5,601)", None, "(43,688)"],
            ["8,000", None, "62,400"],
        ],
        cells=[],
        title="Consolidated Income Statement",
        local_context=(
            "Consolidated Income Statement\n"
            "for the year ended 31 December 2025\n"
            "2025 # 2025 2024 2023\n"
            "US$ million Note HK$ million HK$ million HK$ million\n"
            "35,902 Revenue 5 280,036 281,351 275,575\n"
            "(14,565) Cost of inventories sold 8 (113,608) (106,194) (105,739)\n"
            "(5,601) Staff costs (43,688) (40,338) (38,820)\n"
            "8,000 Operating profit 62,400 60,001 58,002\n"
        ),
        page_text=(
            "Consolidated Income Statement\n"
            "for the year ended 31 December 2025\n"
            "2025 # 2025 2024 2023\n"
            "US$ million Note HK$ million HK$ million HK$ million\n"
            "35,902 Revenue 5 280,036 281,351 275,575\n"
            "(14,565) Cost of inventories sold 8 (113,608) (106,194) (105,739)\n"
            "(5,601) Staff costs (43,688) (40,338) (38,820)\n"
            "8,000 Operating profit 62,400 60,001 58,002\n"
        ),
    )

    table = adapter._build_parsed_table(
        block=block,
        market="HK",
        document_id="doc",
        table_index=1,
    )

    assert table is not None
    assert table.table_kind == "income_statement"
    assert table.semantic_ambiguity_reason == "dual_currency_statement_block"
    assert [column.period_id for column in table.period_columns[:3]] == [
        "2025FY",
        "2024FY",
        "2023FY",
    ]
    assert [row.label_raw for row in table.body_rows[:4]] == [
        "Revenue",
        "Cost of inventories sold",
        "Staff costs",
        "Operating profit",
    ]
    assert table.body_rows[0].value_cells[0].text_raw == "280,036"
    assert table.body_rows[0].value_cells[1].text_raw == "281,351"
    assert table.body_rows[1].value_cells[0].text_raw == "(113,608)"
```

- [ ] **Step 2: Add a failing balance sheet recovery test**

Append this test in the same file:

```python
def test_hk_dual_currency_balance_sheet_recovers_point_rows_from_page_text() -> None:
    adapter = PdfTableStructureAdapter()
    block = RawTableBlock(
        block_id="doc:page:136:table:1",
        page_index=135,
        page_range=(135, 135),
        table_index=0,
        rows=[
            ["12,831", "Fixed assets 13\nRight-of-use assets\nTotal assets", "100,080"],
            ["1,932", None, "15,070"],
            ["80,000", None, "624,000"],
        ],
        cells=[],
        title="Consolidated Statement of Financial Position",
        local_context=(
            "Consolidated Statement of Financial Position\n"
            "as at 31 December 2025\n"
            "31 December 31 December 31 December 1 January\n"
            "2025 # 2025 2024 2023 2023\n"
            "US$ million Note HK$ million HK$ million HK$ million HK$ million\n"
            "12,831 Fixed assets 13 100,080 111,777 119,826 112,650\n"
            "1,932 Right-of-use assets 15,070 15,675 15,111 14,999\n"
            "80,000 Total assets 624,000 600,000 580,000 560,000\n"
        ),
        page_text=(
            "Consolidated Statement of Financial Position\n"
            "as at 31 December 2025\n"
            "31 December 31 December 31 December 1 January\n"
            "2025 # 2025 2024 2023 2023\n"
            "US$ million Note HK$ million HK$ million HK$ million HK$ million\n"
            "12,831 Fixed assets 13 100,080 111,777 119,826 112,650\n"
            "1,932 Right-of-use assets 15,070 15,675 15,111 14,999\n"
            "80,000 Total assets 624,000 600,000 580,000 560,000\n"
        ),
    )

    table = adapter._build_parsed_table(
        block=block,
        market="HK",
        document_id="doc",
        table_index=1,
    )

    assert table is not None
    assert table.table_kind == "balance_sheet"
    assert table.semantic_ambiguity_reason == "dual_currency_statement_block"
    assert [column.period_id for column in table.period_columns[:4]] == [
        "2025FY",
        "2024FY",
        "2023FY",
        "2023FY",
    ]
    assert [column.period_type for column in table.period_columns[:4]] == [
        "point_in_time",
        "point_in_time",
        "point_in_time",
        "point_in_time",
    ]
    assert [row.label_raw for row in table.body_rows[:3]] == [
        "Fixed assets",
        "Right-of-use assets",
        "Total assets",
    ]
    assert table.body_rows[0].value_cells[0].text_raw == "100,080"
    assert table.body_rows[0].value_cells[3].text_raw == "112,650"
```

- [ ] **Step 3: Add a failing cash flow recovery test**

Append this test in the same file:

```python
def test_hk_dual_currency_cash_flow_recovers_hk_rows_from_page_text() -> None:
    adapter = PdfTableStructureAdapter()
    block = RawTableBlock(
        block_id="doc:page:141:table:1",
        page_index=140,
        page_range=(140, 140),
        table_index=0,
        rows=[
            ["9,826", "Cash generated from operating activities before interest expenses and tax\nInterest paid\nTax paid", "76,645"],
            ["(1,000)", None, "(7,800)"],
            ["(900)", None, "(7,020)"],
        ],
        cells=[],
        title="Consolidated Statement of Cash Flows",
        local_context=(
            "Consolidated Statement of Cash Flows\n"
            "for the year ended 31 December 2025\n"
            "2025 # 2025 2024 2023\n"
            "US$ million Note HK$ million HK$ million HK$ million\n"
            "9,826 Cash generated from operating activities before interest expenses and tax 76,645 68,174 65,000\n"
            "(1,000) Interest paid (7,800) (7,100) (6,900)\n"
            "(900) Tax paid (7,020) (6,500) (6,200)\n"
        ),
        page_text=(
            "Consolidated Statement of Cash Flows\n"
            "for the year ended 31 December 2025\n"
            "2025 # 2025 2024 2023\n"
            "US$ million Note HK$ million HK$ million HK$ million\n"
            "9,826 Cash generated from operating activities before interest expenses and tax 76,645 68,174 65,000\n"
            "(1,000) Interest paid (7,800) (7,100) (6,900)\n"
            "(900) Tax paid (7,020) (6,500) (6,200)\n"
        ),
    )

    table = adapter._build_parsed_table(
        block=block,
        market="HK",
        document_id="doc",
        table_index=1,
    )

    assert table is not None
    assert table.table_kind == "cash_flow_statement"
    assert table.semantic_ambiguity_reason == "dual_currency_statement_block"
    assert [row.label_raw for row in table.body_rows[:3]] == [
        "Cash generated from operating activities before interest expenses and tax",
        "Interest paid",
        "Tax paid",
    ]
    assert table.body_rows[0].value_cells[0].text_raw == "76,645"
    assert table.body_rows[1].value_cells[0].text_raw == "(7,800)"
```

- [ ] **Step 4: Run tests and verify they fail for the structural reason**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_structure.py \
  -k "dual_currency_income or dual_currency_balance or dual_currency_cash" -q
```

Expected:

```text
3 failed
```

The failures must show missing recovered rows, wrong `semantic_ambiguity_reason`, or wrong period/value binding. If import names fail, add the missing import from the existing test file pattern:

```python
from financial_report_analysis.ingestion.table_source import RawTableBlock
from financial_report_analysis.ingestion.table_structure import PdfTableStructureAdapter
```

- [ ] **Step 5: Commit failing tests**

Run:

```bash
git add financial-report-analysis/tests/unit/test_table_structure.py
git commit -m "test: cover HK dual-currency statement recovery"
```

---

### Task 2: Implement HK Dual-Currency Row Recovery

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`
- Test: `financial-report-analysis/tests/unit/test_table_structure.py`

- [ ] **Step 1: Add regex constants near the existing recovery helpers**

In `table_structure.py`, add these imports and constants if they do not exist:

```python
import re

_HK_DUAL_CURRENCY_UNIT_PATTERN = re.compile(
    r"\bUS\$\s*million\b.*\bHK\$\s*million\b|\bHK\$\s*million\b.*\bUS\$\s*million\b",
    re.IGNORECASE | re.DOTALL,
)
_FINANCIAL_NUMBER_PATTERN = re.compile(
    r"\(?-?\d{1,3}(?:,\d{3})*(?:\.\d+)?\)?|\(?-?\d+(?:\.\d+)?\)?"
)
_TRAILING_NOTE_PATTERN = re.compile(r"\s+\d+[A-Za-z]?$")
```

- [ ] **Step 2: Route dual-currency recovery before numeric-only fallback**

In `_recover_rows_for_statement_block()`, call the new recovery before `_looks_like_header_only_statement_block()` and `_looks_like_numeric_only_statement_block()`:

```python
        recovered_rows = self._recover_hk_dual_currency_rows_from_page_text(
            page_text=block.page_text,
            title_text=title_text,
        )
        if recovered_rows:
            return recovered_rows, "dual_currency_statement_block"
```

This order matters because HK.00001 blocks look numeric-only after pdfplumber collapse, but the page text has enough information to rebuild the rows deterministically.

- [ ] **Step 3: Add the gated recovery helper**

Add this static method inside `PdfTableStructureAdapter` near `_recover_rows_from_page_text()`:

```python
    @staticmethod
    def _recover_hk_dual_currency_rows_from_page_text(
        *,
        page_text: str,
        title_text: str,
    ) -> list[list[str]]:
        if not page_text or not title_text:
            return []
        if not _HK_DUAL_CURRENCY_UNIT_PATTERN.search(page_text):
            return []

        lowered_title = title_text.lower()
        is_main_statement = any(
            phrase in lowered_title
            for phrase in (
                "income statement",
                "statement of financial position",
                "balance sheet",
                "statement of cash flows",
                "cash flow statement",
            )
        )
        if not is_main_statement:
            return []

        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        title_index = PdfTableStructureAdapter._find_statement_title_index(
            lines=lines,
            title_text=title_text,
        )
        if title_index is None:
            return []

        header_rows = PdfTableStructureAdapter._recover_hk_dual_currency_header_rows(
            lines=lines[title_index : title_index + 8],
            title_text=title_text,
        )
        body_rows: list[list[str]] = []
        for line in lines[title_index + 1 :]:
            if PdfTableStructureAdapter._is_statement_footer_line(line):
                break
            row = PdfTableStructureAdapter._recover_hk_dual_currency_body_row(line)
            if row:
                body_rows.append(row)

        if not header_rows or len(body_rows) < 2:
            return []
        return [*header_rows, *body_rows]
```

- [ ] **Step 4: Add title lookup helper**

Add this static method in the same class:

```python
    @staticmethod
    def _find_statement_title_index(
        *,
        lines: list[str],
        title_text: str,
    ) -> int | None:
        normalized_title = " ".join(title_text.lower().split())
        for index, line in enumerate(lines):
            normalized_line = " ".join(line.lower().split())
            if normalized_title and normalized_title in normalized_line:
                return index
        return None
```

- [ ] **Step 5: Add header recovery helper**

Add this static method:

```python
    @staticmethod
    def _recover_hk_dual_currency_header_rows(
        *,
        lines: list[str],
        title_text: str,
    ) -> list[list[str]]:
        year_line = ""
        for line in lines:
            if "HK$" in line or "US$" in line:
                continue
            years = re.findall(r"\b20\d{2}\b", line)
            if len(years) >= 2:
                year_line = line
                break

        if not year_line:
            return []

        years = re.findall(r"\b20\d{2}\b", year_line)
        if "#" in year_line and len(years) >= 2:
            years = years[1:]

        if "financial position" in title_text.lower() or "balance sheet" in title_text.lower():
            first_january_count = 1 if re.search(r"\b1\s+January\b", year_line, re.IGNORECASE) else 0
            if first_january_count and len(years) >= 2:
                years = [*years[:-1], years[-1]]
            return [["", *years]]

        return [["", *years]]
```

The existing `_parse_period_columns()` and `_fallback_hk_period_columns()` should convert these header rows into `ParsedColumn` values. If `1 January 2023` produces a duplicate `2023FY`, that is acceptable for this fix because the priority is correct HK value binding for current/prior columns.

- [ ] **Step 6: Add body row recovery helper**

Add this static method:

```python
    @staticmethod
    def _recover_hk_dual_currency_body_row(line: str) -> list[str] | None:
        matches = list(_FINANCIAL_NUMBER_PATTERN.finditer(line))
        if len(matches) < 3:
            return None

        first = matches[0]
        trailing_matches = PdfTableStructureAdapter._trailing_numeric_matches(line, matches)
        if len(trailing_matches) < 2:
            return None

        first_trailing = trailing_matches[0]
        label = line[first.end() : first_trailing.start()].strip()
        if not label:
            return None

        label = _TRAILING_NOTE_PATTERN.sub("", label).strip()
        if not label:
            return None
        if PdfTableStructureAdapter._looks_like_non_metric_statement_label(label):
            return None

        hk_values = [match.group(0) for match in trailing_matches]
        return [label, *hk_values]
```

- [ ] **Step 7: Add row-filter helper**

Add this static method before the row-filter helper. It ensures Note numbers such as `Revenue 5` are not emitted as HK values:

```python
    @staticmethod
    def _trailing_numeric_matches(
        line: str,
        matches: list[re.Match[str]],
    ) -> list[re.Match[str]]:
        trailing: list[re.Match[str]] = []
        cursor = len(line)
        for match in reversed(matches[1:]):
            between = line[match.end() : cursor].strip()
            if between:
                break
            trailing.append(match)
            cursor = match.start()
        trailing.reverse()
        return trailing
```

Add this static method:

```python
    @staticmethod
    def _looks_like_non_metric_statement_label(label: str) -> bool:
        normalized = " ".join(label.lower().split())
        if len(normalized) < 3:
            return True
        blocked = {
            "note",
            "notes",
            "assets",
            "liabilities",
            "equity",
            "current assets",
            "non-current assets",
            "current liabilities",
            "non-current liabilities",
            "cash flows from operating activities",
            "cash flows from investing activities",
            "cash flows from financing activities",
        }
        return normalized in blocked
```

- [ ] **Step 8: Add footer guard helper if the class does not already have one**

If `PdfTableStructureAdapter` does not already define `_is_statement_footer_line()`, add this static method:

```python
    @staticmethod
    def _is_statement_footer_line(line: str) -> bool:
        normalized = " ".join(line.lower().split())
        if not normalized:
            return True
        return normalized.startswith(
            (
                "the notes on",
                "notes to the",
                "annual report",
                "independent auditor",
                "page ",
            )
        )
```

- [ ] **Step 9: Run the focused unit tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_structure.py \
  -k "dual_currency_income or dual_currency_balance or dual_currency_cash" -q
```

Expected:

```text
3 passed
```

- [ ] **Step 10: Run existing structure tests to check regressions**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_structure.py -q
```

Expected:

```text
passed
```

- [ ] **Step 11: Commit implementation**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py \
  financial-report-analysis/tests/unit/test_table_structure.py
git commit -m "fix: recover HK dual-currency statement rows"
```

---

### Task 3: Expand HK Unit Detection for Singular Dual-Currency Labels

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_header_parser.py`
- Modify: `financial-report-analysis/tests/unit/test_table_header_parser.py`

- [ ] **Step 1: Add failing unit detection tests**

Append these tests to `test_table_header_parser.py`:

```python
def test_detect_table_unit_accepts_singular_hk_dollar_million() -> None:
    assert detect_table_unit("US$ million Note HK$ million HK$ million") == "HK$ million"


def test_detect_table_unit_prefers_hk_dollar_when_us_and_hk_are_present() -> None:
    assert detect_table_unit("US$ million Note HK$ million HK$ million HK$ million") == "HK$ million"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_header_parser.py \
  -k "singular_hk_dollar or prefers_hk_dollar" -q
```

Expected:

```text
2 failed
```

- [ ] **Step 3: Update `detect_table_unit()`**

In `table_header_parser.py`, update `detect_table_unit()` so the HK pattern is checked before the US pattern when both exist:

```python
    hk_match = re.search(r"\bHK\$\s*million(?:s)?\b", local_context, re.IGNORECASE)
    if hk_match:
        return "HK$ million"

    us_match = re.search(r"\bUS\$\s*million(?:s)?\b", local_context, re.IGNORECASE)
    if us_match:
        return "US$ million"
```

Keep existing Chinese unit detection unchanged and before or after this block according to current behavior. The requirement is that HK.00001 main statements normalize to HK$ because downstream values are HK$ after Task 2.

- [ ] **Step 4: Run header parser tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_header_parser.py -q
```

Expected:

```text
passed
```

- [ ] **Step 5: Commit unit detection change**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/table_header_parser.py \
  financial-report-analysis/tests/unit/test_table_header_parser.py
git commit -m "fix: detect HK dollar million unit labels"
```

---

### Task 4: Add Real PDF Structure Regression for HK.00001 2025

**Files:**
- Modify: `financial-report-analysis/tests/integration/test_table_structure_ingestion.py`

- [ ] **Step 1: Add HK.00001 to the real PDF anchor coverage**

Find the existing `test_hk_annual_anchors_expose_non_empty_statement_rows` parametrization and add this case:

```python
pytest.param(
    "00001",
    "2025_annual_en.pdf",
    {"income_statement", "balance_sheet", "cash_flow_statement"},
    True,
    id="hk00001-2025-annual-en",
),
```

If the existing parametrization shape differs, keep the same argument order and use the same path resolver as the other HK annual anchors.

- [ ] **Step 2: Add a dedicated label/value assertion test**

Add this test below the anchor test:

```python
def test_hk00001_2025_dual_currency_main_statement_labels_are_recovered() -> None:
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(_hk_annual_anchor("00001", "2025_annual_en.pdf")),
        pdf_url=None,
        market="HK",
    )

    by_statement = {
        statement_type: [
            table
            for table in tables
            if table.table_kind == statement_type and table.body_rows
        ]
        for statement_type in (
            "income_statement",
            "balance_sheet",
            "cash_flow_statement",
        )
    }

    assert by_statement["income_statement"]
    assert by_statement["balance_sheet"]
    assert by_statement["cash_flow_statement"]

    income_labels = _flatten_labels(by_statement["income_statement"])
    balance_labels = _flatten_labels(by_statement["balance_sheet"])
    cash_flow_labels = _flatten_labels(by_statement["cash_flow_statement"])

    assert "revenue" in income_labels
    assert "cost of inventories sold" in income_labels
    assert "fixed assets" in balance_labels
    assert "total assets" in balance_labels
    assert (
        "cash generated from operating activities before interest expenses and tax"
        in cash_flow_labels
    )
    assert "interest paid" in cash_flow_labels
```

If `_flatten_labels()` does not exist, add this helper in the same test module:

```python
def _flatten_labels(tables: list[ParsedTable]) -> set[str]:
    labels: set[str] = set()
    for table in tables:
        for row in table.body_rows:
            if row.label_raw:
                labels.add(" ".join(row.label_raw.lower().split()))
    return labels
```

Add this import if the helper needs it:

```python
from financial_report_analysis.models.parsed_table import ParsedTable
```

- [ ] **Step 3: Run the focused integration test**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_table_structure_ingestion.py \
  -k "hk00001 or hk_annual_anchors" -q
```

Expected:

```text
passed
```

- [ ] **Step 4: Commit real PDF structure regression**

Run:

```bash
git add financial-report-analysis/tests/integration/test_table_structure_ingestion.py
git commit -m "test: add HK00001 structure regression"
```

---

### Task 5: Add Deterministic Fact Pipeline Regression

**Files:**
- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

- [ ] **Step 1: Add the HK.00001 deterministic metric test**

Append this test to `test_semantic_recovery_regressions.py`:

```python
def test_hk00001_2025_main_statement_metrics_are_deterministic() -> None:
    payload = _extract_payload_for_pdf(
        _resolve_sample("hk_stocks", "00001", "annual", "2025_annual_en.pdf"),
        market="HK",
    )

    candidates_by_metric = {
        str(candidate["metric_id"]): candidate
        for candidate in payload.get("candidate_facts", [])
        if isinstance(candidate, dict)
        and candidate.get("period_id") == "2025FY"
        and candidate.get("metric_id") is not None
    }

    expected_metrics = {
        "revenue",
        "operating_cost",
        "total_assets",
        "cash",
        "operating_cash_flow",
        "interest_paid_cash",
        "c_paid_for_taxes",
    }
    missing = expected_metrics - candidates_by_metric.keys()
    assert missing == set()

    for metric_id in expected_metrics:
        candidate = candidates_by_metric[metric_id]
        extensions = candidate.get("extensions")
        assert isinstance(extensions, dict)
        assert extensions.get("semantic_source") == "deterministic"
        assert candidate.get("numeric_value") is not None
        assert candidate.get("unit") in {"HK$ million", "HKD million", "million"}
```

This uses existing helpers already defined near the top of `test_semantic_recovery_regressions.py`: `_resolve_sample()` and `_extract_payload_for_pdf()`.

- [ ] **Step 2: Run the new test and fix import mismatches only**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_semantic_recovery_regressions.py \
  -k "hk00001_2025_main_statement_metrics" -q
```

Expected:

```text
passed
```

If the test fails because a metric id differs from existing Turtle v0.15 naming, inspect `metric_mapping.py` and adjust the expected metric id to the current canonical id. Do not add aliases in this task.

- [ ] **Step 3: Run semantic regression tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_semantic_recovery_regressions.py -q
```

Expected:

```text
passed
```

- [ ] **Step 4: Commit deterministic fact regression**

Run:

```bash
git add financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py
git commit -m "test: assert HK00001 deterministic facts"
```

---

### Task 6: Run E2E Evaluation and Update Architecture Notes

**Files:**
- Modify: `docs/architecture-analysis/2026-04-22-turtle-v015-financial-field-gap-analysis.md`
- Modify: `docs/architecture-analysis/new-report-sample-onboarding-and-field-variance-process.md`

- [x] **Step 1: Run focused unit and integration tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_structure.py \
  tests/unit/test_table_header_parser.py \
  tests/unit/test_table_semantics.py \
  tests/unit/test_table_fact_builder.py -q
```

Expected:

```text
passed
```

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_table_structure_ingestion.py \
  tests/integration/test_semantic_recovery_regressions.py -q
```

Expected:

```text
passed
```

Actual:

```text
152 passed in 0.23s
56 passed in 2048.95s
```

- [x] **Step 2: Run HK.00001 E2E evaluation script**

Run:

```bash
cd financial-report-analysis
FRA_E2E_STOCK_CODE=00001 \
FRA_E2E_FISCAL_YEAR=2025 \
FRA_E2E_REPORT_TYPE=annual \
FRA_E2E_PDF_PATH=../report/downloads/hk_stocks/00001/annual/2025_annual_en.pdf \
FRA_E2E_OUTPUT_DIR=/tmp/hk00001_2025_after_dual_currency_fix \
scripts/run-real-pdf-e2e-evaluation.sh
```

Expected report summary:

```text
revenue: present
operating_cost: present
total_assets: present
cash: present
operating_cash_flow: present
```

The exact wording depends on `report_metric_availability.py`; record the generated markdown path and the present/absent counts.

Actual:

```text
extract/persist/readback E2E: 1 passed in 533.84s
Ollama fallback E2E: 1 passed in 552.09s
slow path availability: total=32, present=4, absent=25, not_surfaced=3
slow path report: /tmp/hk00001_2025_after_dual_currency_fix/HK_00001_2025_annual_metric_availability.md
deterministic focused report: /tmp/hk00001_2025_after_dual_currency_fix/HK_00001_2025_annual_deterministic_metric_availability.md
```

- [x] **Step 3: Compare fallback counts**

Inspect the generated markdown or JSON output and record these before/after expectations in the docs:

```text
Before:
present=1
absent=28
not_surfaced=3
semantic_fallback_call_counts: table_kind=31, row_label=10, unit=10

After:
present is greater than 1
revenue, total_assets, cash, operating_cash_flow are present
main statement facts use deterministic source
row_label fallback is not required for those main statement facts
```

Actual:

```text
slow path fallback counts: table_kind=32, row_label=16, currency=0, unit=4
slow path present: revenue, net_profit, cash, fix_assets
deterministic focused present: revenue, total_profit, cash, fix_assets, goodwill
deterministic focused absent: inventory
```

The original expected list was too broad for the repaired structure slice. The
remaining `operating_cost`, `operating_profit`, `total_assets`,
`operating_cash_flow` gaps need a follow-up sample-onboarding pass to classify
alias vs not_surfaced vs absent.

- [x] **Step 4: Update Turtle v0.15 gap document**

In `2026-04-22-turtle-v015-financial-field-gap-analysis.md`, add a dated note:

```markdown
### 2026-04-29 HK.00001 2025 Dual-Currency Statement Recovery Update

HK.00001 2025 年报失败根因不是 Turtle 字段 alias 缺失，而是主报表结构恢复缺口：pdfplumber 将双币种英文报表抽成“US$ 展示值 + 多行 label/Note + HK$ 值”的错位表，导致利润表缺失、资产负债表/现金流量表被误判且产生少量噪声 facts。

本轮修复后，结构层会在 HK annual main statement 页面从 page text 恢复 `[label, HK current, HK prior...]` 行，并丢弃 US$ 展示列与 Note 列。字段缺口评估应基于修复后的 deterministic facts 重新计算；只有仍然缺失且 evidence row 正确的字段，才进入 Turtle v0.15 alias 或指标模型扩展。

验证输出记录格式：
- E2E output dir 使用 `/tmp/hk00001_2025_after_dual_currency_fix`。
- Availability report 写入 Step 2 输出中的实际 markdown 文件路径。
- Present/absent/not_surfaced 写入 Step 2 输出中的实际计数。
- Main-statement deterministic metrics observed 写入 Step 2 输出中已确认来自 deterministic source 的 metric id 列表。
```

- [x] **Step 5: Update new report onboarding process**

In `new-report-sample-onboarding-and-field-variance-process.md`, add a troubleshooting rule:

```markdown
### HK Dual-Currency Main Statement Structure Check

当新样本出现大量 `numeric_only_statement_block`、`table_kind` fallback 和 `row_label` fallback，但 PDF 正文能搜索到 `Consolidated Income Statement`、`Consolidated Statement of Financial Position`、`Consolidated Statement of Cash Flows` 时，优先检查结构恢复，而不是先加 metric alias。

典型页面特征：
- 表头同时包含 `US$ million` 和 `HK$ million`。
- 数据行形态为 `35,902 Revenue 5 280,036 281,351 275,575`。
- pdfplumber 表格形态为首行中间 cell 包含多行 label，后续行 label 为空。

处理顺序：
1. 用 page text 恢复 `[label, HK current, HK prior...]` 行。
2. 确认主报表 facts 来自 deterministic source。
3. 再评估 Turtle 字段 alias 缺口。
```

- [ ] **Step 6: Commit verification docs**

Run:

```bash
git add docs/architecture-analysis/2026-04-22-turtle-v015-financial-field-gap-analysis.md \
  docs/architecture-analysis/new-report-sample-onboarding-and-field-variance-process.md
git commit -m "docs: record HK00001 recovery verification"
```

---

## Final Verification

- [ ] **Step 1: Run all focused checks**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_structure.py \
  tests/unit/test_table_header_parser.py \
  tests/unit/test_table_semantics.py \
  tests/unit/test_table_fact_builder.py \
  tests/integration/test_table_structure_ingestion.py \
  tests/integration/test_semantic_recovery_regressions.py -q
```

Expected:

```text
passed
```

- [ ] **Step 2: Run full test suite if time permits**

Run:

```bash
cd financial-report-analysis
uv run pytest -q
```

Expected:

```text
passed
```

- [ ] **Step 3: Check git status**

Run:

```bash
git status --short
```

Expected: only intentionally unrelated pre-existing files remain uncommitted, or the worktree is clean after all planned commits.

---

## Expected Outcome

- HK.00001 2025 年报结构层能产出非空 `income_statement`、`balance_sheet`、`cash_flow_statement` 表。
- `Revenue`、`Cost of inventories sold`、`Fixed assets`、`Total assets`、`Cash generated from operating activities before interest expenses and tax`、`Interest paid` 能从真实 PDF 中恢复为行标签。
- HK$ current/prior values 与 period columns 对齐，不使用 US$ 展示列作为 Turtle 指标值。
- 关键 Turtle v0.15 字段至少包括 `revenue`、`operating_cost`、`total_assets`、`cash`、`operating_cash_flow` 的 deterministic facts。
- Ollama fallback 保留为 slow path，但不再承担 HK.00001 主报表结构修复职责。
