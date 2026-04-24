# HK 09987 2025 Extraction Recovery Design

> **Status:** Draft for implementation
> **Scope Type:** Focused real-PDF sample recovery
> **Anchor Sample:** `HK_09987`, fiscal year `2025`, `2025_annual_en.pdf`

## 1. Background

The real-PDF integration test for `HK_09987` 2025 currently posts to
`/api/v1/analysis/extract` successfully, but `key_facts` is empty. The endpoint
does not fail at IO or API validation. It fails because extract output is
blocked or incomplete before API exposure.

The sample should be treated as a report-family anchor, not as an issuer
special case. The implementation must not branch on stock code, issuer name, or
file name. The family is:

`HK English annual report with text-table financial statements and note/disclosure supplements`

## 2. Diagnostic Summary

Initial diagnostics found five independent gaps.

1. The language detector classifies the English PDF as `zh-Hant` because the
   cover page contains the Chinese issuer name. The document has a very small
   number of CJK characters relative to English text. This causes
   `analyze_report()` to return `unsupported_in_phase1` before candidate facts
   can become canonical facts.

2. The statement-row path does not produce facts for the main financial
   statements. `pdfplumber` extracts only the year header rows on key pages such
   as the consolidated income statement, cash flow statement, and balance sheet.
   `ParsedTable` objects are classified, but `body_rows` is empty.

3. HK annual statement headers using bare years, such as `2025 2024 2023`, are
   not converted into period columns. The current HK annual parser expects
   month-day-year date headers.

4. The note/disclosure supplement path can find some facts, but it can misread
   note section titles as value rows. For example,
   `Accounts Receivable, net 2025 2024` must be treated as a note table title,
   not as a value row whose current-year value is `2025`.

5. Note/disclosure candidate ids are generated independently by each note
   builder. Multiple builder groups can emit `...:note-disclosure:candidate:1`,
   which promotes to duplicate canonical fact ids and leaves validation in
   `review_required`.

## 3. Goals

This recovery must make `HK_09987` 2025 produce stable, traceable facts through
the existing extraction path:

`pdf -> structure recovery -> normalized table semantics -> metric mapping registry -> candidate facts -> canonical facts -> API`

Target outcomes:

- `2025_annual_en.pdf` is detected as English.
- Main statement text pages produce statement-row candidates for real current
  fiscal year values.
- HK bare-year annual headers produce `2025FY`, `2024FY`, and `2023FY` columns
  where present.
- Balance sheet bare-year headers use point-in-time value shape; income and
  cash flow headers use duration value shape.
- Note/disclosure facts do not use section title years as numeric values.
- Note/disclosure facts carry correct currency/unit for the report context,
  especially `USD` and `US$ millions` for this anchor.
- Candidate and canonical fact ids are unique.
- The real-PDF E2E test for `HK_09987` 2025 passes with non-empty `key_facts`.

## 4. Non-Goals

This work does not:

- Add issuer-specific or file-specific logic.
- Expand the Turtle metric universe.
- Let LLM fallback freely extract numbers.
- Use note/disclosure facts to overwrite statement-row facts.
- Relax existing negative controls.
- Rework storage, P5 dataset assembly, lineage, or recompute behavior.

## 5. Architecture

### 5.1 Language Detection

Replace binary "any CJK means Chinese" detection with a document-level heuristic.
For HK reports, English should win when English text dominates CJK text by a
large margin or when English annual report signals are present. Chinese should
still win for Chinese annual reports with substantial CJK content.

The language output remains a simple string consumed by `analyze_report()`:

- `en`
- `zh-Hant`
- `zh-Hans`

### 5.2 Statement Row Recovery

Add a deterministic page-text recovery path for statement pages where
`pdfplumber` table blocks contain header-only or numeric-only fragments but the
page text contains structured rows.

The recovery should:

- run only for classified statement table kinds;
- use the statement title and page text as boundary signals;
- parse rows shaped like `Label $ 1,234 $ 1,111` and
  `Label (24) 40 (49)`;
- preserve the statement title, page range, source block, unit, currency, and
  table kind;
- avoid paragraphs and note prose.

### 5.3 HK Bare-Year Headers

Support HK annual header rows that contain bare years. A row like
`2025 2024 2023` is valid when the surrounding table title or page context
establishes a fiscal-year statement.

Value shape:

- `balance_sheet`: `point`
- `income_statement`: `duration`
- `cash_flow_statement`: `duration`

### 5.4 Note/Disclosure Supplement

Keep note/disclosure supplement deterministic and supplement-only. Fix row
matching so note table titles such as `Accounts Receivable, net 2025 2024` are
not considered data rows. The current-year value must come from the first real
value row, for example `Accounts receivable, gross $ 97 $ 80` or the total row
`Accounts receivable, net $ 95 $ 79`.

Note/disclosure candidate builders must receive or derive report currency/unit
instead of hard-coding HKD.

### 5.5 Candidate Identity

Candidate fact ids must be unique across all builders in one document. The
simplest acceptable design is to allocate each builder a stable source prefix:

- `working-capital-note`
- `debt-note`
- `asset-note`
- `cash-health-note`

Alternatively, pass a shared candidate id allocator through note builder calls.
The implementation should choose the smallest change that keeps ids stable and
readable.

## 6. Data Flow

1. `PdfIngestionAdapter.extract_candidate_facts()` extracts text pages.
2. Language is detected from whole-document text using ratio and report signals.
3. `PdfTableStructureAdapter.extract_tables()` recovers statement rows from
   page text when table blocks have insufficient body rows.
4. `table_header_parser.parse_header_rows()` resolves bare-year columns.
5. `normalize_table_semantics()` and `build_table_candidate_facts()` build
   statement-row facts.
6. Note/disclosure builders supplement only missing supported metrics.
7. `analyze_report()` promotes candidates to canonical facts.
8. `ReportAdapter` exposes consumable canonical facts in `key_facts`.

## 7. Acceptance Criteria

Focused unit tests must cover:

- HK English-dominant reports with a small CJK issuer-name footer or cover are
  detected as `en`.
- HK Chinese-dominant text is still detected as `zh-Hant`.
- HK bare-year headers parse into fiscal-year columns.
- Text statement rows are recovered for income statement, balance sheet, and
  cash flow statement examples.
- Note titles with years are skipped as value rows.
- Note builders do not emit duplicate fact ids.
- Report-level USD currency and million unit can be propagated to note facts.

Focused integration tests must cover:

- `HK_09987` 2025 annual English real PDF produces non-empty `key_facts`.
- The result includes statement-row facts from main statements, not only note
  facts.
- `accounts_receiv` for 2025 is not `2025`.
- The response is not blocked as `unsupported_in_phase1`.
- Existing anchors `HK_02498` 2022 and `CN_601919` 2025 continue to pass the
  existing real-PDF E2E path.

## 8. Risk Controls

- Do not use stock-code branches.
- Do not parse arbitrary prose into facts.
- Keep all page-text recovery gated by statement title/table kind signals.
- Keep note/disclosure supplement lower precedence than statement-row facts.
- Preserve provenance through `extraction_method`, `table_id`, `table_coord`,
  `extensions.source_kind`, and source rank hints.

## 9. Open Implementation Choices

Two choices are left to the implementation plan:

- Whether statement page-text recovery should live directly in
  `table_structure.py` or in a small helper module imported by it.
- Whether note candidate uniqueness should use source-specific prefixes or a
  shared allocator.

Both choices must remain deterministic and test-covered.

