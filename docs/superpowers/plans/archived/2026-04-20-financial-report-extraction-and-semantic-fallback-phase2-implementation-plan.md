# 财报提取与语义兜底二期实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破坏当前 candidate/canonical 合约的前提下，继续强化 CN/HK 年报与季报的基础提取能力，并为本地 `Ollama` 增加受限的 `unit/currency` 语义兜底能力。

**Architecture:** 本轮工作分成两个阶段。**Phase A** 继续加强确定性的结构恢复与语义归一化能力，优先提升 annual / quarterly 的基础提取稳定性。**Phase B** 在此基础上增加受限的 `Ollama` 二期兜底，只处理局部 `unit/currency` 语义解释，并保持 deterministic-first、gated-only、provenance-preserving 的边界。

**Tech Stack:** Python 3.12、dataclasses、pytest、Ruff、`pypdf`、现有 `financial_report_analysis` ingestion/semantic pipeline、本地 Ollama HTTP API（`http://127.0.0.1:11434`，`qwen3.5:9b`）

---

## 文件结构

### 需要修改的现有文件

- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_source.py`
  - 继续增强 annual / quarterly 的原始表块保真度与局部上下文保留。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_header_parser.py`
  - 加强多层表头的确定性解析。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_structure.py`
  - 强化 row-to-value binding 和局部语义上下文保留。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_semantics.py`
  - 扩展确定性 `unit/currency` 语义归一化。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\models\table.py`
  - 视需要补充轻量级局部上下文字段。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\models\table_semantics.py`
  - 明确本地 `unit/currency` 语义字段与 provenance 字段。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\registries\metric_mapping.py`
  - 确保 richer semantics 能继续被 registry 消费，但不假设传播策略。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\services\table_fact_builder.py`
  - 把 `unit/currency` 的语义 provenance 带进 candidate facts。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\semantic_fallback\models.py`
  - 增加 `unit/currency` fallback 的 request/response 结构。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\semantic_fallback\ollama_client.py`
  - 增加 `unit/currency` 的 prompt / response 解析。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\semantic_fallback\service.py`
  - 在显式 ambiguity 条件下接入 `unit/currency` fallback。
- `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\pdf_ingestion.py`
  - 将更强的确定性 `unit/currency` 语义和 gated 二期 fallback 接入主路径。

### 需要扩展的测试文件

- `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_source.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_header_parser.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_structure.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_semantics.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_fact_builder.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_fact_pipeline.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_ollama_client.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_semantic_fallback_service.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_public_exports.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_annual_structure_recovery.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_semantic_recovery_regressions.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_analysis_api.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_ollama_real_report_probes.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_ollama_smoke.py`
- `F:\source\git\report-collector\financial-report-analysis\tests\integration\fixtures\ollama_real_report_probes.py`

---

## Phase A：继续强化确定性提取与语义归一化

**Phase A 收口标准**

- CN/HK 年报与 HK Q3 锚点样本能够保留更强的确定性 row/header/unit/currency 结构。
- 在不依赖 LLM 的前提下，更多局部 `unit/currency` 场景能被稳定解释。
- candidate fact 构建仍然可以在 deterministic 语义基础上正常工作。

### Task A1：扩大 annual / quarterly 结构恢复覆盖面

**Files:**
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_annual_structure_recovery.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_source.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_structure.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_source.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_structure.py`

- [ ] **Step 1: 先写失败测试，锁定更强的确定性结构恢复**

```python
def test_hk_q3_anchor_preserves_local_header_and_value_bindings() -> None:
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(_resolve_sample("hk_stocks", "09987", "quarterly", "2025_quarterly_q3_en.pdf")),
        pdf_url=None,
        market="HK",
    )

    income_statement = next(table for table in tables if table.table_kind == "income_statement")
    assert income_statement.header_rows
    assert any(row.value_cells for row in income_statement.body_rows)


def test_cn_annual_anchor_preserves_local_unit_context_without_page_bleed() -> None:
    tables = PdfTableStructureAdapter().extract_tables(
        pdf_path=str(_resolve_sample("cn_stocks", "601919", "annual", "2024_年度报告.pdf")),
        pdf_url=None,
        market="CN",
    )

    assert any(table.table_unit for table in tables)
```

- [ ] **Step 2: 运行测试，确认先红**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/integration/test_annual_structure_recovery.py tests/unit/test_table_source.py tests/unit/test_table_structure.py -v
```

Expected: FAIL，说明当前确定性结构恢复对部分 annual/quarterly 语义上下文仍不够稳。

- [ ] **Step 3: 写最小实现，只增强确定性结构恢复**

```python
def _table_local_context(block: RawTableBlock) -> str:
    segments = [block.title or ""]
    segments.extend(" ".join(row).strip() for row in block.rows[:3])
    return "\n".join(segment for segment in segments if segment)
```

```python
table = ParsedTable(
    ...,
    local_context=_table_local_context(block),
)
```

- [ ] **Step 4: 再跑测试，确认转绿**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/integration/test_annual_structure_recovery.py tests/unit/test_table_source.py tests/unit/test_table_structure.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```powershell
git add F:\source\git\report-collector\financial-report-analysis\tests\integration\test_annual_structure_recovery.py F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_source.py F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_structure.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_source.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_structure.py
git commit -m "feat: strengthen deterministic report structure recovery"
```

### Task A2：强化确定性的 unit / currency 语义归一化

**Files:**
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_semantics.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_fact_pipeline.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_semantic_recovery_regressions.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\models\table_semantics.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_semantics.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\services\table_fact_builder.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\pdf_ingestion.py`

- [ ] **Step 1: 先写失败测试，锁定确定性 unit/currency 语义**

```python
def test_normalize_table_semantics_preserves_local_currency_and_unit() -> None:
    semantics = normalize_table_semantics(parsed_hk_annual_balance_sheet())

    assert semantics.table_currency in {"HKD", "USD", "unknown"}
    assert semantics.table_unit in {"thousand", "million", "billion", "unknown"}


def test_table_fact_builder_preserves_deterministic_unit_currency_provenance() -> None:
    candidate = build_table_candidate_facts(...)[0]
    assert candidate["extensions"]["semantic_source"] == "deterministic"
    assert "unit_semantic_source" in candidate["extensions"]
    assert "currency_semantic_source" in candidate["extensions"]
```

- [ ] **Step 2: 运行测试，确认先红**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_table_semantics.py tests/unit/test_fact_pipeline.py tests/integration/test_semantic_recovery_regressions.py -v
```

Expected: FAIL，说明当前确定性 unit/currency 语义和 provenance 还不够明确。

- [ ] **Step 3: 写最小实现，只加强 deterministic 语义**

```python
@dataclass(frozen=True, slots=True)
class NormalizedTableSemantics:
    ...
    table_unit: str | None = None
    table_currency: str | None = None
    unit_semantic_source: str = "deterministic"
    currency_semantic_source: str = "deterministic"
```

```python
extensions.update(
    {
        "unit_semantic_source": semantics.unit_semantic_source,
        "currency_semantic_source": semantics.currency_semantic_source,
    }
)
```

- [ ] **Step 4: 再跑测试，确认转绿**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_table_semantics.py tests/unit/test_fact_pipeline.py tests/integration/test_semantic_recovery_regressions.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```powershell
git add F:\source\git\report-collector\financial-report-analysis\tests\unit\test_table_semantics.py F:\source\git\report-collector\financial-report-analysis\tests\unit\test_fact_pipeline.py F:\source\git\report-collector\financial-report-analysis\tests\integration\test_semantic_recovery_regressions.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\models\table_semantics.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_semantics.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\services\table_fact_builder.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\pdf_ingestion.py
git commit -m "feat: harden deterministic unit and currency semantics"
```

---

## Phase B：受限 Ollama 语义兜底二期

**Phase B 收口标准**

- `Ollama` 在显式 ambiguity 下支持本地 `unit/currency` 解释。
- 输出被严格限制在受控标准值集合中。
- fallback 结果保留 provenance，且不会被误当成传播策略。
- evaluation 与 promotion 两层验证都建立完成。

### Task B1：扩展 fallback 模型与 client，支持本地 unit/currency

**Files:**
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_ollama_client.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_semantic_fallback_service.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_public_exports.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\semantic_fallback\models.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\semantic_fallback\ollama_client.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\semantic_fallback\service.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\semantic_fallback\__init__.py`

- [ ] **Step 1: 先写失败测试，锁定 unit/currency 的受限输出**

```python
def test_semantic_fallback_service_only_allows_supported_currency_outputs() -> None:
    result = service.resolve_currency(ambiguous_currency_request())
    assert result.value in {"CNY", "HKD", "USD", "unknown"}


def test_semantic_fallback_service_only_allows_supported_unit_outputs() -> None:
    result = service.resolve_unit(ambiguous_unit_request())
    assert result.value in {"yuan", "thousand", "million", "billion", "percent", "unknown"}
```

- [ ] **Step 2: 运行测试，确认先红**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_ollama_client.py tests/unit/test_semantic_fallback_service.py tests/unit/test_public_exports.py -v
```

Expected: FAIL，说明 unit/currency fallback 的 request/response 或 service 方法还不存在。

- [ ] **Step 3: 写最小实现，保持输出集合受限**

```python
@dataclass(frozen=True, slots=True)
class UnitFallbackRequest:
    title_text: str
    local_context: str
    deterministic_candidates: tuple[str, ...]
    ambiguity_reason: str
```

```python
def resolve_currency(self, request: CurrencyFallbackRequest) -> SemanticFallbackResult:
    ...


def resolve_unit(self, request: UnitFallbackRequest) -> SemanticFallbackResult:
    ...
```

- [ ] **Step 4: 再跑测试，确认转绿**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_ollama_client.py tests/unit/test_semantic_fallback_service.py tests/unit/test_public_exports.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```powershell
git add F:\source\git\report-collector\financial-report-analysis\tests\unit\test_ollama_client.py F:\source\git\report-collector\financial-report-analysis\tests\unit\test_semantic_fallback_service.py F:\source\git\report-collector\financial-report-analysis\tests\unit\test_public_exports.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\semantic_fallback\models.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\semantic_fallback\ollama_client.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\semantic_fallback\service.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\semantic_fallback\__init__.py
git commit -m "feat: add unit and currency fallback contracts"
```

### Task B2：把 gated unit/currency fallback 接入主路径

**Files:**
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_analysis_api.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\unit\test_fact_pipeline.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\pdf_ingestion.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_semantics.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\services\table_fact_builder.py`

- [ ] **Step 1: 先写失败测试，锁定 gated 行为**

```python
def test_pdf_ingestion_applies_gated_currency_fallback_only_for_ambiguous_tables(
    monkeypatch,
) -> None:
    payload = PdfIngestionAdapter(semantic_fallback_service=stub_service).extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="HK",
        min_confidence=0.8,
    )
    assert payload["document_metadata"]["parsed_tables"][0]["currency_semantic_source"] == "llm_fallback"


def test_pdf_ingestion_does_not_use_unit_fallback_when_deterministic_unit_is_stable(
    monkeypatch,
) -> None:
    payload = PdfIngestionAdapter(semantic_fallback_service=stub_service).extract_candidate_facts(
        pdf_path="ignored.pdf",
        pdf_url=None,
        market="CN",
        min_confidence=0.8,
    )
    assert payload["document_metadata"]["parsed_tables"][0]["unit_semantic_source"] == "deterministic"
```

- [ ] **Step 2: 运行测试，确认先红**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/integration/test_analysis_api.py tests/unit/test_fact_pipeline.py -v
```

Expected: FAIL，说明 unit/currency fallback 还没接进 live path。

- [ ] **Step 3: 写最小实现，只在 ambiguity 下接入**

```python
if self._should_fallback_currency(semantics):
    currency_result = self.semantic_fallback_service.resolve_currency(...)
    semantics = replace(
        semantics,
        table_currency=currency_result.value,
        currency_semantic_source=currency_result.semantic_source,
        semantic_confidence=currency_result.semantic_confidence,
    )
```

```python
if self._should_fallback_unit(semantics):
    unit_result = self.semantic_fallback_service.resolve_unit(...)
    semantics = replace(
        semantics,
        table_unit=unit_result.value,
        unit_semantic_source=unit_result.semantic_source,
    )
```

- [ ] **Step 4: 再跑测试，确认转绿**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/integration/test_analysis_api.py tests/unit/test_fact_pipeline.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```powershell
git add F:\source\git\report-collector\financial-report-analysis\tests\integration\test_analysis_api.py F:\source\git\report-collector\financial-report-analysis\tests\unit\test_fact_pipeline.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\pdf_ingestion.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\ingestion\table_semantics.py F:\source\git\report-collector\financial-report-analysis\src\financial_report_analysis\services\table_fact_builder.py
git commit -m "feat: wire gated unit and currency fallback"
```

### Task B3：为 unit/currency fallback 建立 real probe 与 promotion

**Files:**
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\integration\fixtures\ollama_real_report_probes.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_ollama_real_report_probes.py`
- Modify: `F:\source\git\report-collector\financial-report-analysis\tests\integration\test_ollama_smoke.py`

- [ ] **Step 1: 先写失败测试，锁定 unit/currency probe dataset**

```python
def test_real_report_probe_dataset_covers_supported_unit_currency_outputs() -> None:
    assert any(case.expected_currency == "HKD" for case in REAL_REPORT_SEMANTIC_PROBE_CASES)
    assert any(case.expected_unit == "thousand" for case in REAL_REPORT_SEMANTIC_PROBE_CASES)


def test_local_ollama_promoted_unit_currency_cases() -> None:
    for case in PROMOTED_REAL_REPORT_SEMANTIC_PROBE_CASES:
        result = resolve_unit_or_currency_with_real_ollama(case)
        assert result.value == case.expected_value
```

- [ ] **Step 2: 运行测试，确认先红**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/integration/test_ollama_real_report_probes.py tests/integration/test_ollama_smoke.py -v
```

Expected: FAIL，说明 unit/currency probe dataset 和 promotion set 还没建立。

- [ ] **Step 3: 补最小 dataset 和 promotion 子集**

```python
SemanticProbeCase(
    market="HK",
    report_family="annual",
    semantic_kind="currency",
    title_text="Consolidated Statement of Financial Position",
    local_context="Presented in HK$ million unless otherwise stated",
    expected_value="HKD",
    expectation_type="positive",
)
```

至少补：

- 正向 unit/currency case
- 至少一个 `unknown` / negative ambiguity case
- 一小组 promotion 子集，只选稳定 case

- [ ] **Step 4: 跑 evaluation 和 promotion 回归**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
$env:FRA_RUN_OLLAMA_REAL_REPORT_PROBES='1'
uv run pytest tests/integration/test_ollama_real_report_probes.py tests/integration/test_ollama_smoke.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```powershell
git add F:\source\git\report-collector\financial-report-analysis\tests\integration\fixtures\ollama_real_report_probes.py F:\source\git\report-collector\financial-report-analysis\tests\integration\test_ollama_real_report_probes.py F:\source\git\report-collector\financial-report-analysis\tests\integration\test_ollama_smoke.py
git commit -m "test: add unit and currency probe promotion coverage"
```

### Task B4：跑完整体验证矩阵

**Files:**
- Verify only

- [ ] **Step 1: 跑确定性提取与语义测试**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_table_source.py tests/unit/test_table_header_parser.py tests/unit/test_table_structure.py tests/unit/test_table_semantics.py tests/unit/test_table_fact_builder.py tests/unit/test_fact_pipeline.py tests/integration/test_annual_structure_recovery.py tests/integration/test_semantic_recovery_regressions.py -v
```

Expected: PASS

- [ ] **Step 2: 跑 fallback 相关 unit 与 integration**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run pytest tests/unit/test_ollama_client.py tests/unit/test_semantic_fallback_service.py tests/unit/test_public_exports.py tests/integration/test_analysis_api.py tests/integration/test_ollama_smoke.py -v
```

Expected: PASS

- [ ] **Step 3: 跑 gated real-report probe evaluation**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
$env:FRA_RUN_OLLAMA_REAL_REPORT_PROBES='1'
uv run pytest tests/integration/test_ollama_real_report_probes.py -v
```

Expected: PASS

- [ ] **Step 4: 跑 Ruff**

Run:
```powershell
cd F:\source\git\report-collector\financial-report-analysis
uv run ruff check src/financial_report_analysis/ingestion src/financial_report_analysis/models src/financial_report_analysis/services src/financial_report_analysis/semantic_fallback tests/unit/test_table_source.py tests/unit/test_table_header_parser.py tests/unit/test_table_structure.py tests/unit/test_table_semantics.py tests/unit/test_table_fact_builder.py tests/unit/test_fact_pipeline.py tests/unit/test_ollama_client.py tests/unit/test_semantic_fallback_service.py tests/unit/test_public_exports.py tests/integration/test_annual_structure_recovery.py tests/integration/test_semantic_recovery_regressions.py tests/integration/test_analysis_api.py tests/integration/test_ollama_real_report_probes.py tests/integration/test_ollama_smoke.py
```

Expected: `All checks passed!`

- [ ] **Step 5: 提交**

```powershell
git commit --allow-empty -m "chore: verify phase 2 extraction and fallback readiness"
```

## Self-Review

### Spec coverage

- 基础提取仍是主目标：由 Phase A Task A1 和 Task A2 覆盖。
- `Ollama` 二期仍是受限副线：由 Phase B Task B1-B3 覆盖。
- `unit/currency` fallback 是 limited scope，不是传播策略：在 Goal、Phase B 任务和测试中都已明确。
- deterministic-first 架构保持不变：通过 Phase A 先做基础提取、Phase B 再接 fallback 的顺序体现。
- provenance 与“可回灌”价值被保留：通过 deterministic provenance、fallback provenance、probe/promotion 体系体现。

### Placeholder scan

- 没有 `TODO`、`TBD` 或“后面再补”的占位内容。
- 每个 task 都给了明确的失败测试、最小实现示例、运行命令和提交步骤。

### Type consistency

- `semantic_source`、`semantic_confidence`、`fallback_reason` 在 deterministic 和 fallback 路径中保持一致。
- `unit/currency` fallback 始终是“局部语义解释”，不被写成传播决策。
- 当前 candidate/canonical/API contract 没有被新引入的 fallback 结构替代。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-20-financial-report-extraction-and-semantic-fallback-phase2-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
