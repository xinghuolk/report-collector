# HK 09987 2025 Extraction Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover deterministic extraction for `HK_09987` 2025 annual English PDF so it produces non-empty API `key_facts`, statement-row canonical facts, correct language status, valid note supplements, and unique fact ids.

**Architecture:** Keep the existing pipeline path intact: `pdf -> structure recovery -> normalized table semantics -> metric mapping registry -> candidate facts -> canonical facts -> API`. Add deterministic language heuristics, HK text-statement row recovery, bare-year header parsing, and note/disclosure hardening without issuer-specific branches.

**Tech Stack:** Python 3.11/3.12, pytest, Ruff, pypdf, pdfplumber, existing `financial_report_analysis` ingestion, registry, pipeline, and API modules.

---

## File Structure

Modify:

- `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
  - Language detection.
  - Report-level currency/unit propagation to note builders if needed.
- `financial-report-analysis/src/financial_report_analysis/ingestion/table_header_parser.py`
  - HK bare-year annual header parsing.
- `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`
  - Statement page-text row recovery for header-only table blocks.
- `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
  - Title-row skipping.
  - Source-specific candidate id prefixes or shared allocator.
  - Currency/unit parameters for note candidates.
- `financial-report-analysis/tests/unit/test_table_header_parser.py`
- `financial-report-analysis/tests/unit/test_table_structure.py`
- `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`
- `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- `financial-report-analysis/tests/integration/test_real_pdf_extract_persist_e2e.py`
- `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

Do not modify:

- P5 storage schema.
- Dataset assembly.
- LLM fallback contracts, unless a test proves an existing type blocks this deterministic fix.

---

## Task 1: Fix HK English-Dominant Language Detection

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Test: `financial-report-analysis/tests/unit/test_fact_pipeline.py`

- [ ] **Step 1: Add failing language detection tests**

Add tests near the existing `PdfIngestionAdapter` unit tests in `test_fact_pipeline.py`:

```python
def test_pdf_ingestion_detects_hk_english_dominant_report_with_small_chinese_name() -> None:
    text = (
        "Yum China Holdings, Inc.\n"
        "百勝中國控股有限公司\n"
        "2025 Annual Report\n"
        + ("Consolidated Statements of Income Revenue Operating Profit " * 200)
    )

    assert PdfIngestionAdapter._detect_language(text, "HK") == "en"


def test_pdf_ingestion_keeps_hk_chinese_dominant_report_as_traditional_chinese() -> None:
    text = (
        "2025 年年度報告\n"
        + ("合併財務報表 營業收入 淨利潤 資產總計 " * 200)
        + "Annual Report"
    )

    assert PdfIngestionAdapter._detect_language(text, "HK") == "zh-Hant"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_fact_pipeline.py::test_pdf_ingestion_detects_hk_english_dominant_report_with_small_chinese_name tests/unit/test_fact_pipeline.py::test_pdf_ingestion_keeps_hk_chinese_dominant_report_as_traditional_chinese -q
```

Expected: the English-dominant case fails because any CJK character returns `zh-Hant`.

- [ ] **Step 3: Implement minimal language heuristic**

In `PdfIngestionAdapter._detect_language`, replace the any-CJK check with a ratio/signal rule:

```python
    @staticmethod
    def _detect_language(text: str, market: str | None) -> str:
        cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
        ascii_letter_count = len(re.findall(r"[A-Za-z]", text))
        english_report_signal = re.search(
            r"\b(?:annual report|consolidated statements?|financial statements?)\b",
            text,
            re.IGNORECASE,
        ) is not None

        if cjk_count == 0:
            return "en"
        if market == "HK":
            if english_report_signal and ascii_letter_count >= cjk_count * 20:
                return "en"
            return "zh-Hant"
        return "zh-Hans"
```

- [ ] **Step 4: Re-run focused tests**

Run the command from Step 2.

Expected: both tests pass.

---

## Task 2: Parse HK Bare-Year Annual Headers

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_header_parser.py`
- Test: `financial-report-analysis/tests/unit/test_table_header_parser.py`

- [ ] **Step 1: Add failing bare-year header tests**

Add:

```python
def test_parse_hk_bare_year_income_statement_headers_as_duration() -> None:
    columns = parse_header_rows(
        title_text="Consolidated Statements of Income",
        header_rows=[["2025", "2024", "2023"]],
        market="HK",
    )

    assert [(column.column_index, column.period_id, column.value_time_shape) for column in columns] == [
        (0, "2025FY", "duration"),
        (1, "2024FY", "duration"),
        (2, "2023FY", "duration"),
    ]


def test_parse_hk_bare_year_balance_sheet_headers_as_point() -> None:
    columns = parse_header_rows(
        title_text="Consolidated Balance Sheets",
        header_rows=[["2025", "2024"]],
        market="HK",
    )

    assert [(column.column_index, column.period_id, column.value_time_shape) for column in columns] == [
        (0, "2025FY", "point"),
        (1, "2024FY", "point"),
    ]
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_header_parser.py::test_parse_hk_bare_year_income_statement_headers_as_duration tests/unit/test_table_header_parser.py::test_parse_hk_bare_year_balance_sheet_headers_as_point -q
```

Expected: both tests fail because bare years are ignored.

- [ ] **Step 3: Implement bare-year parsing**

In `table_header_parser.py`, add:

```python
_HK_BARE_YEAR_HEADER_RE = re.compile(r"^(20\d{2})$")
```

Then extend `_parse_period_from_header()` inside the `market == "HK"` branch:

```python
        bare_year_match = _HK_BARE_YEAR_HEADER_RE.search(header_text)
        if bare_year_match is not None and _looks_like_hk_annual_statement_title(title_text):
            value_time_shape = (
                "point"
                if "balance sheet" in title_text.casefold()
                or "financial position" in title_text.casefold()
                else "duration"
            )
            return f"{bare_year_match.group(1)}FY", value_time_shape
```

Add helper:

```python
def _looks_like_hk_annual_statement_title(title_text: str) -> bool:
    normalized = title_text.casefold()
    return any(
        token in normalized
        for token in (
            "statement of income",
            "statements of income",
            "statement of cash flows",
            "statements of cash flows",
            "balance sheet",
            "financial position",
        )
    )
```

- [ ] **Step 4: Re-run focused tests**

Run the command from Step 2.

Expected: both tests pass.

---

## Task 3: Recover HK Text Statement Rows From Page Text

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py`
- Test: `financial-report-analysis/tests/unit/test_table_structure.py`

- [ ] **Step 1: Add failing recovery tests**

Add tests that instantiate `RawTableBlock` and call `_build_parsed_table()` through `PdfTableStructureAdapter`.

```python
def test_hk_income_statement_header_only_block_recovers_rows_from_page_text() -> None:
    adapter = PdfTableStructureAdapter()
    block = RawTableBlock(
        block_id="doc:page:153:table:1",
        page_index=153,
        page_range=(153, 153),
        rows=[["2025", "2024", "2023"]],
        page_text="\n".join(
            [
                "Consolidated Statements of Income",
                "Years ended December 31, 2025, 2024 and 2023",
                "(in US$ millions, except per share data)",
                "2025 2024 2023",
                "Total revenues 11,797 11,303 10,978",
                "Operating Profit 1,290 1,162 1,106",
                "Net Income — Yum China Holdings, Inc. $ 929 $ 911 $ 827",
                "Basic Earnings Per Common Share $ 2.52 $ 2.34 $ 1.99",
                "See accompanying Notes to Consolidated Financial Statements.",
            ]
        ),
        local_context="2025 2024 2023",
    )

    table = adapter._build_parsed_table(
        block=block,
        market="HK",
        document_id="doc",
        table_index=1,
    )

    assert table is not None
    assert table.table_kind == "income_statement"
    assert [(column.column_index, column.period_id) for column in table.period_columns] == [
        (1, "2025FY"),
        (2, "2024FY"),
        (3, "2023FY"),
    ]
    assert [row.label_raw for row in table.body_rows] == [
        "Total revenues",
        "Operating Profit",
        "Net Income — Yum China Holdings, Inc.",
        "Basic Earnings Per Common Share",
    ]
    assert table.table_currency == "USD"
    assert table.table_unit == "US$ millions"


def test_hk_balance_sheet_header_only_block_recovers_point_rows_from_page_text() -> None:
    adapter = PdfTableStructureAdapter()
    block = RawTableBlock(
        block_id="doc:page:156:table:1",
        page_index=156,
        page_range=(156, 156),
        rows=[["2025", "2024"]],
        page_text="\n".join(
            [
                "Consolidated Balance Sheets",
                "December 31, 2025 and 2024",
                "(in US$ millions)",
                "2025 2024",
                "Cash and cash equivalents $ 506 $ 723",
                "Total Assets 10,783 11,121",
                "Short-term borrowings 30 127",
                "Total Liabilities 4,684 4,694",
                "Total Equity 6,099 6,414",
                "See accompanying Notes to Consolidated Financial Statements.",
            ]
        ),
        local_context="2025 2024",
    )

    table = adapter._build_parsed_table(
        block=block,
        market="HK",
        document_id="doc",
        table_index=1,
    )

    assert table is not None
    assert table.table_kind == "balance_sheet"
    assert [(column.column_index, column.period_id, column.value_time_shape) for column in table.period_columns] == [
        (1, "2025FY", "point"),
        (2, "2024FY", "point"),
    ]
    assert [row.label_raw for row in table.body_rows] == [
        "Cash and cash equivalents",
        "Total Assets",
        "Short-term borrowings",
        "Total Liabilities",
        "Total Equity",
    ]
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_structure.py::test_hk_income_statement_header_only_block_recovers_rows_from_page_text tests/unit/test_table_structure.py::test_hk_balance_sheet_header_only_block_recovers_point_rows_from_page_text -q
```

Expected: tests fail because header-only blocks keep zero body rows and unit detection does not return `US$ millions`.

- [ ] **Step 3: Add gated page-text recovery**

In `table_structure.py`, extend `_recover_rows_for_statement_block()` so it also attempts recovery when a statement block has only header rows:

```python
        if self._looks_like_header_only_statement_block(block.rows):
            recovered_rows = self._recover_rows_from_page_text(
                page_text=block.page_text,
                title_text=title_text,
            )
            if recovered_rows:
                return recovered_rows, "header_only_statement_block"
```

Add helper:

```python
    @staticmethod
    def _looks_like_header_only_statement_block(rows: list[list[str]]) -> bool:
        non_empty_rows = [row for row in rows if any(cell.strip() for cell in row)]
        if len(non_empty_rows) != 1:
            return False
        non_empty_cells = [cell.strip() for cell in non_empty_rows[0] if cell.strip()]
        if len(non_empty_cells) < 2:
            return False
        return all(re.fullmatch(r"20\d{2}", cell) for cell in non_empty_cells)
```

Update `_recover_structured_row()` so it strips dollar markers and parses rows where the first numeric value starts after a `$`:

```python
        normalized_line = re.sub(r"\$\s*", "", line)
        matches = list(_NUMERIC_CELL_PATTERN.finditer(normalized_line))
```

Keep existing paragraph stops in `_recover_rows_from_page_text()` and add a stop for:

```python
            if line.startswith("See accompanying Notes"):
                break
```

- [ ] **Step 4: Teach unit detection US million context**

In `table_header_parser.detect_table_unit()`, add:

```python
    if re.search(r"\bin\s+US\$\s+millions\b", text, re.IGNORECASE):
        return "US$ millions"
    if re.search(r"\bin\s+HK\$\s+millions\b", text, re.IGNORECASE):
        return "HK$ millions"
```

- [ ] **Step 5: Re-run focused tests**

Run the command from Step 2.

Expected: both tests pass.

---

## Task 4: Harden Note/Disclosure Rows And Identity

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
- Test: `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`

- [ ] **Step 1: Add failing tests for title-row skipping and ids**

Add:

```python
def test_working_capital_note_skips_title_years_for_accounts_receivable() -> None:
    pages = [
        (
            179,
            "\n".join(
                [
                    "Note 6 — Supplemental Balance Sheet Information",
                    "Accounts Receivable, net 2025 2024",
                    "Accounts receivable, gross $ 97 $ 80",
                    "Allowance for doubtful accounts (2) (1)",
                    "Accounts receivable, net $ 95 $ 79",
                ]
            ),
        )
    ]

    candidates, missing = build_working_capital_note_candidate_facts(
        pages=pages,
        document_id="doc",
        period_id="2025FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
    )

    accounts = [candidate for candidate in candidates if candidate["metric_id"] == "accounts_receiv"]
    assert missing["accounts_receiv"] == "present"
    assert accounts[0]["numeric_value"] == 95.0
    assert accounts[0]["raw_value"] == "95"


def test_note_disclosure_candidate_ids_are_unique_across_builders() -> None:
    pages = [
        (
            1,
            "\n".join(
                [
                    "Accounts Receivable, net 2025 2024",
                    "Accounts receivable, net $ 95 $ 79",
                    "Accounts payable and other current liabilities 2025 2024",
                    "Accounts payable $ 793 $ 801",
                    "Contract liabilities 205 192",
                    "Borrowings 2025 2024",
                    "Short-term borrowings 30 127",
                    "Cash, Cash Equivalents and Restricted Cash — End of Year $ 506 $ 723",
                    "Cash paid for interest 4 3",
                    "Long-term bank deposits and notes 678 1,088",
                ]
            ),
        )
    ]
    existing: set[str] = set()
    working, _ = build_working_capital_note_candidate_facts(
        pages=pages,
        document_id="doc",
        period_id="2025FY",
        market="HK",
        existing_metric_ids=existing,
        semantic_fallback_service=None,
    )
    existing.update(candidate["metric_id"] for candidate in working)
    debt, _ = build_debt_note_candidate_facts(
        pages=pages,
        document_id="doc",
        period_id="2025FY",
        market="HK",
        existing_metric_ids=existing,
    )
    existing.update(candidate["metric_id"] for candidate in debt)
    cash, _ = build_cash_health_note_candidate_facts(
        pages=pages,
        document_id="doc",
        period_id="2025FY",
        market="HK",
        existing_metric_ids=existing,
        semantic_fallback_service=None,
    )
    fact_ids = [candidate["fact_id"] for candidate in [*working, *debt, *cash]]

    assert len(fact_ids) == len(set(fact_ids))
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_note_disclosure_ingestion.py::test_working_capital_note_skips_title_years_for_accounts_receivable tests/unit/test_note_disclosure_ingestion.py::test_note_disclosure_candidate_ids_are_unique_across_builders -q
```

Expected: first test returns `2025`; second test shows duplicate fact ids.

- [ ] **Step 3: Skip note title rows**

In `_match_metric_in_text()`, skip rows that are table titles with only year-like numbers:

```python
            if _is_year_header_line(line) or _is_note_title_year_line(line):
                continue
```

Add:

```python
def _is_note_title_year_line(line: str) -> bool:
    if re.search(r"[$(),]", line) is not None:
        return False
    numbers = re.findall(r"\b\d+\b", line)
    if len(numbers) < 2:
        return False
    if not all(len(number) == 4 and number.startswith("20") for number in numbers):
        return False
    return re.search(
        r"(?i)\b(accounts receivable|accounts payable|contract liabilities|borrowings|assets)\b",
        line,
    ) is not None
```

- [ ] **Step 4: Make note candidate ids source-specific**

Add a `source_prefix` argument to `_build_note_candidate_facts()` and `_build_candidate_payload()`. Use:

```python
source_prefix="working-capital-note"
source_prefix="debt-note"
source_prefix="asset-note"
source_prefix="cash-health-note"
```

Change fact id construction to:

```python
        "fact_id": f"{document_id}:{source_prefix}:candidate:{candidate_index}",
```

- [ ] **Step 5: Re-run focused tests**

Run the command from Step 2.

Expected: both tests pass.

---

## Task 5: Propagate Report Currency And Unit To Note Facts

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py`
- Test: `financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py`

- [ ] **Step 1: Add failing note currency/unit test**

Add:

```python
def test_note_candidate_payload_uses_report_currency_and_unit() -> None:
    pages = [
        (
            179,
            "\n".join(
                [
                    "Note 6 — Supplemental Balance Sheet Information",
                    "(in US$ millions)",
                    "Accounts Receivable, net 2025 2024",
                    "Accounts receivable, net $ 95 $ 79",
                ]
            ),
        )
    ]

    candidates, _ = build_working_capital_note_candidate_facts(
        pages=pages,
        document_id="doc",
        period_id="2025FY",
        market="HK",
        existing_metric_ids=set(),
        semantic_fallback_service=None,
        report_currency="USD",
        report_unit="US$ millions",
    )

    assert candidates[0]["currency"] == "USD"
    assert candidates[0]["raw_unit"] == "US$ millions"
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_note_disclosure_ingestion.py::test_note_candidate_payload_uses_report_currency_and_unit -q
```

Expected: test fails because builders do not accept `report_currency` / `report_unit` and hard-code HKD.

- [ ] **Step 3: Add optional note builder parameters**

Add optional keyword parameters to all note builder public functions:

```python
    report_currency: str = "HKD",
    report_unit: str | None = None,
```

Thread them into `_build_note_candidate_facts()` and `_build_candidate_payload()`.

Update `_build_candidate_payload()` fields:

```python
        "currency": report_currency,
        "raw_unit": report_unit,
```

- [ ] **Step 4: Resolve report currency/unit in ingestion**

In `PdfIngestionAdapter.extract_candidate_facts()`, after `normalized_tables` is built, derive:

```python
        report_currency = self._first_known_table_currency(normalized_tables, market)
        report_unit = self._first_known_table_unit(normalized_tables)
```

Add helpers:

```python
    @staticmethod
    def _first_known_table_currency(
        tables: list[NormalizedTableSemantics],
        market: str | None,
    ) -> str:
        for table in tables:
            if table.table_currency:
                return table.table_currency
        return "HKD" if market == "HK" else "CNY"

    @staticmethod
    def _first_known_table_unit(tables: list[NormalizedTableSemantics]) -> str | None:
        for table in tables:
            if table.table_unit:
                return table.table_unit
        return None
```

Pass `report_currency=report_currency` and `report_unit=report_unit` to each note builder call.

- [ ] **Step 5: Re-run focused test**

Run the command from Step 2.

Expected: test passes.

---

## Task 6: Add Focused 09987 Real-PDF Regression

**Files:**

- Modify: `financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py`

- [ ] **Step 1: Add focused integration test**

Add:

```python
@pytest.mark.real_pdf
@pytest.mark.slow
def test_hk_09987_2025_annual_en_recovers_statement_and_note_facts() -> None:
    sample_pdf = _sample_pdf("hk_stocks", "09987", "annual", "2025_annual_en.pdf")
    if sample_pdf is None:
        pytest.skip("HK 09987 2025 annual English PDF sample not found")

    payload = PdfIngestionAdapter().extract_candidate_facts(
        pdf_path=str(sample_pdf),
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )

    metadata = payload["document_metadata"]
    candidates = payload["candidate_facts"]
    by_metric = {candidate["metric_id"]: candidate for candidate in candidates}

    assert metadata["language"] == "en"
    assert "revenue" in by_metric
    assert "cash" in by_metric
    assert "total_assets" in by_metric
    assert "total_liabilities" in by_metric
    assert by_metric["accounts_receiv"]["numeric_value"] != 2025.0
    assert by_metric["accounts_receiv"]["currency"] == "USD"
    assert by_metric["accounts_receiv"]["raw_unit"] == "US$ millions"
    assert len({candidate["fact_id"] for candidate in candidates}) == len(candidates)
```

If `_sample_pdf()` is not available in this module, copy the small helper from
`test_real_pdf_extract_persist_e2e.py` and keep it local to the test module.

- [ ] **Step 2: Run focused real-PDF regression**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_semantic_recovery_regressions.py::test_hk_09987_2025_annual_en_recovers_statement_and_note_facts -q -s
```

Expected before all fixes: fail. Expected after Tasks 1-5: pass.

---

## Task 7: Verify API E2E And Existing Anchors

**Files:**

- Existing tests only unless a narrow assertion needs to be added to `test_real_pdf_extract_persist_e2e.py`.

- [ ] **Step 1: Run 09987 E2E**

Run:

```bash
cd financial-report-analysis
FRA_REAL_PDF_E2E_STOCK_CODE=09987 FRA_REAL_PDF_E2E_MARKET=HK FRA_REAL_PDF_E2E_FISCAL_YEAR=2025 FRA_REAL_PDF_E2E_FILENAME=2025_annual_en.pdf uv run pytest tests/integration/test_real_pdf_extract_persist_e2e.py -q -s
```

Expected: pass, with non-empty `key_facts`.

- [ ] **Step 2: Run default real-PDF E2E anchors**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_real_pdf_extract_persist_e2e.py -q -s
```

Expected: default `CN_601919` and `HK_02498` anchors pass.

- [ ] **Step 3: Run focused unit suites**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_table_header_parser.py tests/unit/test_table_structure.py tests/unit/test_note_disclosure_ingestion.py tests/unit/test_fact_pipeline.py -q
```

Expected: pass.

- [ ] **Step 4: Run Ruff**

Run:

```bash
cd financial-report-analysis
uv run ruff check src tests
```

Expected: pass.

---

## Task 8: Commit Implementation

**Files:**

- All modified implementation and test files.

- [ ] **Step 1: Review diff**

Run:

```bash
git diff -- financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py financial-report-analysis/src/financial_report_analysis/ingestion/table_header_parser.py financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py financial-report-analysis/tests
```

Expected: only scoped extraction recovery and tests changed.

- [ ] **Step 2: Commit**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/ingestion/pdf_ingestion.py financial-report-analysis/src/financial_report_analysis/ingestion/table_header_parser.py financial-report-analysis/src/financial_report_analysis/ingestion/table_structure.py financial-report-analysis/src/financial_report_analysis/ingestion/note_disclosure.py financial-report-analysis/tests/unit/test_table_header_parser.py financial-report-analysis/tests/unit/test_table_structure.py financial-report-analysis/tests/unit/test_note_disclosure_ingestion.py financial-report-analysis/tests/unit/test_fact_pipeline.py financial-report-analysis/tests/integration/test_semantic_recovery_regressions.py
git commit -m "fix: recover hk 09987 annual report extraction"
```

Expected: commit succeeds.

---

## Self-Review

- Spec coverage: The plan covers language detection, statement row recovery,
  header parsing, note row hardening, unit/currency propagation, unique ids,
  focused real-PDF regression, and existing anchor verification.
- Completion scan: No incomplete markers or unspecified implementation step remains.
- Type consistency: Function and file names match the current codebase paths
  inspected before this plan was written.
- Scope check: Storage, P5 assembly, LLM extraction, and issuer-specific logic are
  excluded.
