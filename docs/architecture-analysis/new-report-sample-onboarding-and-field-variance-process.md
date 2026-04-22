# 新增财报样本接入与字段差异处理流程

> **状态:** 流程草案
> **适用范围:** `financial-report-analysis` 新增公司/新增财报样本时的诊断、归类、修复与验收流程
> **目标:** 支持更多公司财报格式，同时避免 issuer-specific 分支和样本补丁式开发

## 1. 背景

`financial-report-analysis` 当前已经形成以下主路径：

`pdf -> structure recovery -> normalized table semantics -> metric mapping registry -> candidate facts -> canonical facts -> API`

Turtle 投资输入覆盖路线已经按字段族推进：

- Core Investor Inputs
- Working Capital And Debt Inputs
- Asset Quality And Capital Allocation Inputs
- Parent Scope And Notes Bridge
- Multi-Year Investor Dataset

新增公司财报时，常见情况不是“完全不能支持”，而是某些环节出现差异：

- 表格结构差异
- 行标签或字段别名差异
- 单位、币种、期间表头差异
- 主表缺细项但附注有披露
- 字段真实不存在
- 当前结构层还没有稳定露出
- 当前 Turtle phase 不纳入该字段

本流程用于把这些差异统一归类和处理，避免为单家公司写硬编码分支。

## 2. 核心原则

### 2.1 新公司样本是“格式家族锚点”，不是公司特例

测试可以使用股票代码和具体 PDF 路径，但实现不应依赖股票代码、公司名或文件名。

允许：

- `09987 2025` 作为 “HK mixed-structure note/disclosure supplement path” 的样本锚点。
- `02498 2022` 作为 “HK statement-row path” 的样本锚点。
- `601919 2025` 作为 “CN standard balance-sheet statement-row path” 的样本锚点。

禁止：

```python
if stock_code == "09987":
    ...
```

应抽象为：

```text
如果目标 metric 没有从 statement-row path 产出，
且存在明确 note/disclosure title 或 table context，
则允许进入受限 deterministic note/disclosure supplement path。
```

### 2.2 Deterministic-first

优先顺序固定为：

1. structure recovery
2. deterministic table semantics
3. metric mapping registry
4. deterministic note/disclosure supplement
5. gated semantic locator

不要把新公司格式差异直接推给 LLM。

### 2.3 主表优先，附注只补缺

当 statement-row path 已经产出稳定事实时，note/disclosure path 默认不能覆盖它。

如果未来确实需要让附注事实覆盖主表事实，必须进入单独的 conflict-governance 设计，不应在新增样本接入时顺手实现。

### 2.4 LLM 只能做受限语义辅助

允许：

- 判断某行更像哪个受支持 metric。
- 判断某个 note/disclosure block 是否包含目标字段。
- 返回受限 JSON，例如 `metric_id`、`matched_label`、`source_text_span`、`semantic_confidence`、`fallback_reason`。

禁止：

- 直接自由抽数。
- 自由传播单位或币种。
- 直接生成 canonical facts。
- 全文泛扫后直接产出财务事实。

### 2.5 缺失必须区分状态

至少区分：

- `present`: 样本中存在可追踪来源，且进入 candidate/canonical。
- `absent`: 样本中明确没有独立披露。
- `not_surfaced`: 当前结构或语义层尚未稳定恢复，不能当作字段不存在。
- `out_of_scope`: 当前 Turtle phase 或当前 feature 不纳入该字段。

不能只通过 candidate omission 表达缺失。

## 3. 新样本登记

新增样本前，先记录基本信息。

建议记录字段：

- `sample_id`
- `market`
  - `CN | HK`
- `language`
  - `zh | en | zh-Hant | other`
- `issuer_code`
- `issuer_name`
- `report_year`
- `report_type`
  - `annual | interim | quarterly`
- `pdf_path`
- `expected_report_family`
- `target_phase`
  - 例如 `Turtle P2B Debt Inputs`
- `target_metric_ids`
- `known_special_shape`
  - 例如 `statement_row_only`
  - 例如 `mixed_statement_and_note`
  - 例如 `note_disclosure_heavy`
- `initial_owner`
- `date_added`

示例：

```text
sample_id: hk-09987-2025-annual-en
market: HK
language: en
issuer_code: 09987
report_year: 2025
report_type: annual
pdf_path: report/downloads/hk_stocks/09987/annual/2025_annual_en.pdf
expected_report_family: hk_mixed_structure_note_disclosure
target_phase: Turtle P2B Debt Inputs
target_metric_ids: st_borr, lt_borr, bond_payable, non_cur_liab_due_1y
known_special_shape: main statement incomplete, debt details may appear in notes
```

## 4. 初跑诊断流程

新增样本后，不要先改代码。先跑诊断，确认失败层。

### 4.1 确认输入边界

检查：

- PDF 是否存在且可读。
- 市场和语言是否属于当前支持范围。
- 报告类型是否属于当前支持范围。
- 是否应进入 `unsupported_in_phase1` 或类似 review 状态。

### 4.2 检查 structure recovery

回答：

- 主表是否被识别为正确 table kind？
- 表头是否恢复出期间、单位、币种？
- 行标签是否完整？
- 跨页续表是否被拼接或至少没有破坏行列绑定？
- parsed table metadata 是否足够支持后续判断？

如果这里失败，优先修：

- `table_source.py`
- `table_structure.py`
- `table_classifier.py`
- `table_header_parser.py`
- `table_stitcher.py`

不要先补 metric aliases。

### 4.3 检查 normalized table semantics

回答：

- row label 是否归一成稳定语义？
- statement scope 是否合理？
- value time shape 是否正确？
- unit/currency semantic source 是否可追踪？
- negative controls 是否被压住？

如果这里失败，优先修：

- `table_semantics.py`
- table semantic model
- semantic provenance metadata

不要进入 note/disclosure path。

### 4.4 检查 metric mapping registry

回答：

- normalized row label 是否已进入 `MetricMappingRegistry`？
- aliases_by_market 是否缺少该市场常见写法？
- allowed_table_kinds 是否过窄或过宽？
- period_scope / value_type / unit_expectation 是否匹配？
- negative controls 是否需要补充？

如果这里失败，优先修：

- `metric_mapping.py`
- `test_metric_mapping_registry.py`

### 4.5 检查 candidate fact builder

回答：

- metric mapping 命中后是否产出 candidate fact？
- `metric_id` 是否正确？
- `period_id` 是否正确？
- `entity_scope` 是否正确？
- `evidence_bundle_id`、`table_id`、`table_coord` 是否保留？
- `extensions.semantic_source` 是否正确？

如果这里失败，优先修：

- `table_fact_builder.py`
- `pdf_ingestion.py` 的 wiring

### 4.6 检查 canonical promotion

回答：

- candidate 是否进入 canonical？
- 如果没进入，是 confidence、source rank、business key、冲突裁决还是 validation 拦截？
- source precedence 是否符合预期？
- lower-priority source 是否错误覆盖 higher-priority source？

如果这里失败，优先修：

- `conflict_resolver.py`
- validation rules
- source rank hints

### 4.7 检查 API exposure

回答：

- canonical fact 是否出现在 expected API layer？
- 如果不在 `key_facts`，是否因为当前 adapter 只暴露少数 API-visible metrics？
- 该字段是否应该对外可见，还是只应留在 canonical facts / review packet？

如果这里失败，先判断是不是 API contract 问题，不要直接改抽取路径。

## 5. 失败归类决策树

### 5.1 表没恢复出来

分类：

`structure_recovery_gap`

处理：

- 补 table source / classifier / header parser / stitcher。
- 加结构层测试。
- 不补 metric registry。

### 5.2 行标签没归一

分类：

`semantic_normalization_gap`

处理：

- 补 `table_semantics.py`。
- 加 normalized label 测试。
- 如果属于 negative control，确保输出为 `None` 或不进入 mapping。

### 5.3 标签归一了，但 metric 没命中

分类：

`metric_mapping_gap`

处理：

- 补 `metric_mapping.py` 的 aliases / normalized labels。
- 检查 allowed table kind、period scope、unit expectation。
- 加 positive 和 negative registry tests。

### 5.4 主表没有细项，但附注独立披露

分类：

`note_disclosure_supplement_gap`

处理：

- 仅在 statement-row path 缺失时进入 note path。
- 限定明确 note/disclosure title 或 table context。
- 只补真实独立披露字段。
- 保留 source precedence 和 provenance。

### 5.5 主表和附注都没有独立披露

分类：

`absent`

处理：

- 不产出 candidate fact。
- 记录 missing status。
- 不推断近似值。

### 5.6 结构或语义层暂时没稳定露出

分类：

`not_surfaced`

处理：

- 不当作业务不存在。
- 记录 missing status。
- 如属于当前 phase 必须字段，评估是否需要补结构/语义能力。

### 5.7 字段有价值但不属于当前 phase

分类：

`out_of_scope`

处理：

- 不塞进当前 Turtle phase。
- 记录到后续 phase 或 extension metric governance。
- 如果结构稳定且有证据，可考虑未来进入 provisional custom metric review。

## 6. 修复策略

### 6.1 补结构层

适用：

- 表格切碎。
- 跨页续表错位。
- 表头单位/期间丢失。
- 主表分类错误。

验证：

- table model tests
- table structure ingestion tests
- focused real-PDF structure regression

### 6.2 补 table semantics

适用：

- 行标签多语言/变体未归一。
- scope / duration / point-in-time 判断错误。
- negative control 没压住。

验证：

- `test_table_semantics.py`
- synthetic row-label tests
- focused real-PDF semantic regression

### 6.3 补 metric mapping registry

适用：

- normalized label 已稳定，但 metric 未命中。
- aliases_by_market 缺少常见写法。
- allowed table kind 或 period scope 约束不合理。

验证：

- `test_metric_mapping_registry.py`
- positive mapping tests
- negative-control tests

### 6.4 补 note/disclosure supplement

适用：

- 主表目标字段缺失。
- 附注中有明确独立披露。
- note block 可通过标题、表格上下文或受限 locator 定位。

验证：

- `test_note_disclosure_ingestion.py`
- source precedence tests
- no hallucination tests
- missing status tests

### 6.5 补 gated semantic locator

适用：

- deterministic note/disclosure block 已定位。
- row label 模糊或多个目标 metric 候选难以判别。
- 仍然可以从结构化片段中解析数值，LLM 只负责语义定位。

验证：

- fallback model/service tests
- budget tests
- provenance tests
- no direct canonical fact tests

## 7. 验收标准

新增样本接入完成，至少应满足：

- 目标样本能稳定产出当前 phase 中真实存在的目标字段。
- 没有独立披露的字段不会被推断产出。
- `absent` / `not_surfaced` / `out_of_scope` 状态清楚。
- positive facts 有 evidence / provenance。
- negative controls 不被误吸。
- note/disclosure path 只补缺，不覆盖 statement-row fact。
- 如果触发 fallback，调用有 gate、budget 和 provenance。
- 旧 anchor 样本不回退。
- API contract 不发生破坏性变化。

## 8. 测试要求

### 8.1 Unit Tests

按失败层补测试：

- structure model
- table semantics
- metric mapping registry
- fact builder
- note disclosure ingestion
- semantic fallback service
- conflict resolver

### 8.2 Focused Integration Tests

每个新增样本至少应有 focused integration test 覆盖：

- 样本路径可解析。
- 目标 metric subset 符合真实披露情况。
- missing status 合理。
- provenance 保留。
- negative controls 不误吸。

### 8.3 Real-PDF Matrix

不要默认每次全量跑 real-PDF + Ollama。

推荐顺序：

1. unit tests
2. narrow integration tests
3. focused real-PDF tests
4. live Ollama smoke
5. 必要时才跑更大的 real-PDF matrix

## 9. 禁止项

禁止：

- issuer-specific branch
- 为单个公司硬编码表格坐标
- 全文关键词扫到数字就产 candidate fact
- LLM 直接抽数
- LLM 直接做单位传播
- LLM 直接生成 canonical facts
- 用 note/disclosure fact 覆盖主表 fact
- 把 `not_surfaced` 当作 `absent`
- 把 out-of-scope 字段塞进当前 Turtle phase
- 为了通过单样本测试放松 negative controls

## 10. 与 Turtle 投资输入路线的关系

Turtle 路线应继续按字段族推进，而不是按公司推进。

新增公司样本的作用是：

- 暴露某类格式家族问题。
- 验证当前 phase 字段在更多 report family 上是否稳定。
- 补强 structure / semantics / registry / note path 的通用能力。

新增公司样本不应改变当前 phase 的字段范围。

如果新样本暴露当前 phase 外的高价值字段：

- 先记录为 `out_of_scope`。
- 如果属于后续 Turtle phase，放入后续 spec。
- 如果不属于 Turtle 主线但有结构化价值，进入 extension metric governance 评估。

## 11. 推荐记录模板

```text
sample_id:
market:
language:
issuer_code:
issuer_name:
report_year:
report_type:
pdf_path:
expected_report_family:
target_phase:
target_metric_ids:

initial_result:
  structure_recovery:
  table_semantics:
  metric_mapping:
  candidate_facts:
  canonical_facts:
  api_exposure:

failure_classification:
  - structure_recovery_gap | semantic_normalization_gap | metric_mapping_gap
  - note_disclosure_supplement_gap | absent | not_surfaced | out_of_scope

planned_fix:
  files:
  tests:
  negative_controls:
  verification:

acceptance:
  present_metrics:
  absent_metrics:
  not_surfaced_metrics:
  out_of_scope_metrics:
  provenance_checked:
  old_anchor_regression_checked:
```

## 12. 一句话原则

新增公司财报样本接入的目标不是“支持这家公司”，而是通过这家公司暴露的差异，补强一类可复用的结构、语义、registry 或附注路径能力。
