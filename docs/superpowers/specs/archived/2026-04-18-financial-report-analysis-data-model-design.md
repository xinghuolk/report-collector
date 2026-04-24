# 财报分析数据模型设计文档

## 1. 目的

本文档描述财报分析包的第二阶段数据模型设计。

重点覆盖：

- `Period`
- `MetricRegistry`
- `CandidateFact`
- `CanonicalFact`
- `DerivedFact`
- `ValidationIssue`
- `ValidationReport`
- `EvidenceItem`
- `EvidenceBundle`
- 存储、血缘与版本

本文档是以下总设计文档的配套细化：

- `docs/superpowers/specs/2026-04-18-financial-report-analysis-design.md`

## 2. 设计原则

数据模型应优先满足：

- 可审计
- 可追溯
- 可版本化重算
- 跨项目复用稳定
- 披露事实与派生事实分离

核心原则：

1. `Fact` 是领域中间表示层，不能随着解析器变化而频繁漂移
2. `Period` 是逻辑坐标，不是展示标签
3. 披露值与计算值不能混用
4. 证据必须是一等对象
5. registry 与 lineage 必须是关系型核心对象，不能退化为 JSON blob

第一阶段港股语言输入约束：

- 港股仅使用英文版财报作为主输入源
- 繁体中文版不进入第一阶段 canonical numeric sourcing
- 后续阶段可将繁体中文版作为辅助证据或解释性分析来源

## 3. Period 模型

### 3.1 为什么 Period 必须独立

`period_id` 必须引用独立的 `Period` 对象。

原因：

- 期间语义远比字符串标签复杂
- TTM 和单季度差分需要期间代数
- 非自然财年必须被显式表达
- 调整后期间与比较期间必须可区分

### 3.2 Period 字段

建议字段：

- `period_id`
- `period_type`
  - `POINT | DURATION`
- `reporting_scope`
  - `Q1 | Q2 | H1 | Q3 | Q3_YTD | FY | CUSTOM`
- `fiscal_year`
- `fiscal_period_index`
- `start_date`
- `end_date`
- `as_of_date`
- `calendar_year`
- `adjusted_status`
  - `ORIGINAL | RESTATED`
- `disclosure_label_raw`
- `fiscal_label`
- `accounting_standard`
  - `CAS | IFRS | HKFRS | OTHER`
- `is_stub_period`
- `period_metadata`

### 3.3 Period 约束

- `Fact` 只存 `period_id`，不重复存期间日期
- `POINT` 用于资产负债表时点值
- `DURATION` 用于利润表与现金流量表时段值
- 优先归并到标准期间范围
- 无法安全标准化时，标记 `is_stub_period = true`
- `Period` 只描述时间坐标；表内比较语义属于 `comparison_axis` 这类事实层字段

### 3.4 Stub Period 策略

第一阶段应：

- 能安全归并时优先归并到标准 `Q/H1/FY`
- 只有归并会误导时，才使用 `CUSTOM + is_stub_period=true`
- 对 stub period 保留原始披露标签和真实日期范围

## 4. Metric Registry

### 4.1 标准指标与自定义指标

系统必须同时支持：

- 标准 metric 库
- 受控的 custom metric registry

不能采用以下做法：

- 只依赖一个庞大的预定义标准库
- 生成不稳定的一次性 custom metric ID

### 4.2 Registry 策略

推荐的第一阶段流程：

1. 先尝试匹配标准 metric
2. 若无法安全命中，则生成 provisional custom metric
3. 执行 shadow merge
4. 允许后续人工执行转正、合并、映射或拉黑

### 4.3 Metric Registry 字段

建议字段：

- `metric_registry_id`
- `metric_id`
- `namespace`
- `is_custom`
- `registry_status`
  - `provisional | approved | mapped_to_standard | deprecated | blacklisted`
- `statement_type`
- `parent_metric_id`
- `accounting_standard`
- `industry_slug`
- `raw_label_canonical`
- `aliases`
- `canonical_label`
- `domain`
- `statement_scope`
- `canonical_unit_hint`
- `negative_value_semantics`
- `formula_definition`
- `context_embedding_ref`
- `shadow_merge_flag`
- `merge_score`
- `potential_duplicate_ids`
- `original_raw_label`
- `created_from_fact_id`
- `review_status`

### 4.4 Custom Metric 命名空间

推荐命名空间格式：

- `custom::<accounting_standard>::<industry_slug>::<metric_slug>`

例子：

- `custom::cas::real_estate::presale_deposit`

### 4.5 Shadow Merge 策略

第一阶段采用混合策略：

1. hard filtering
2. feature weighting
3. thresholding

硬过滤候选条件：

- `statement_type`
- 存在时要求 `parent_metric_id` 一致
- `accounting_standard`
- 行业相关场景下要求 `industry_slug` 匹配

特征加权应综合：

- 原始标签文本相似度
- 上下文 embedding 相似度
- 单位与数量级兼容性

建议阈值：

- `score > 0.9`：静默合并
- `0.7 < score <= 0.9`：注册为潜在重复
- `score <= 0.7`：新建 provisional metric

### 4.6 Custom Metric 的消费规则

第一阶段行为：

- `provisional` custom metric 可以进入事实账本
- `provisional` custom metric 不进入核心分析、比率计算或 TTM
- `approved` custom metric 后续可以逐步放开进入分析
- 计划和输出里必须明确提示哪些 provisional metric 被排除在核心分析之外

## 5. Fact 模型

### 5.1 Fact 分层

系统应使用三层事实对象：

1. `CandidateFact`
2. `CanonicalFact`
3. `DerivedFact`

优先于“一个大而全的万能 Fact”方案。

### 5.2 BaseFact 字段

共享字段：

- `fact_id`
- `fact_kind`
  - `candidate | canonical | derived`
- `metric_id`
- `metric_label_raw`
- `statement_type`
  - `income_statement | balance_sheet | cash_flow_statement | metrics`
  - 这是最小枚举，后续可以扩展到 note/disclosure 上下文
- `entity_scope`
  - `consolidated | parent | segment | other`
- `comparison_axis`
  - `current | prior | period_end | period_begin`
- `adjustment_basis`
  - `reported | adjusted | deducted | parent_attributable | other`
- `period_id`
- `currency`
- `raw_value`
- `numeric_value`
- `raw_unit`
- `normalized_unit`
- `precision`
- `confidence`
- `extensions`

### 5.3 CandidateFact 字段

附加字段：

- `document_id`
- `block_id`
- `table_id`
- `page_index`
- `table_coord`
- `evidence_bundle_id`
- `evidence_span`
- `snapshot_path`
- `extraction_method`
- `extraction_version`
- `source_rank_hint`

约束：

- 每个 `CandidateFact` 都必须引用证据
- Candidate facts 允许冲突、重叠、不完整

### 5.4 CanonicalFact 字段

附加字段：

- `source_candidate_fact_ids`
- `resolution_reason`
- `resolution_score`
- `validation_flags`
- `quality_status`
- `is_primary`
- `evidence_bundle_id`

约束：

- 每个 `CanonicalFact` 必须至少由一个 `CandidateFact` 支撑
- Canonical facts 是下游分析默认消费的事实层
- canonical 唯一性基准是 `metric_id + period_id + entity_scope + comparison_axis + adjustment_basis + currency`
- 若多个 candidate facts 映射到同一 canonical 唯一性基准，resolver 必须选出一个 canonical fact，或明确标记为 unresolved

### 5.5 DerivedFact 字段

附加字段：

- `source_canonical_fact_ids`
- `derivation_type`
  - `single_quarter_delta | ttm | unit_conversion | ratio | other`
- `derivation_formula`
- `derivation_version`
- `validation_status`
- `consistency_check_against_fact_id`
- `evidence_bundle_id`

约束：

- 每个 `DerivedFact` 必须至少由一个 `CanonicalFact` 支撑
- 派生事实必须始终能与原始披露值区分开

### 5.6 Metric 语义规则

采用混合策略：

- 核心会计语义进入 `metric_id`
- 普通视角或口径差异进入维度字段
- 会计意义显著不同的指标拆成独立 `metric_id`

例如：

- 同一 metric 通过维度区分：
  - `revenue` + `entity_scope`
- 不同 metric_id：
  - `net_profit`
  - `net_profit_parent`
  - `net_profit_deducted`

### 5.7 CanonicalFact 身份定义

CanonicalFact 的业务身份定义为：

- `metric_id + period_id + entity_scope + comparison_axis + adjustment_basis + currency`

这是领域层面的唯一性规则。

## 6. 披露值与单季度派生值

第一阶段规则：

- 披露的 YTD、FY、时点值进入 `CanonicalFact`
- 需要时，单季度值通过 `DerivedFact` 差分得出

例如：

- `Q2_SINGLE = H1_YTD - Q1_YTD`
- `Q3_SINGLE = Q3_YTD - H1_YTD`
- `Q4_SINGLE = FY - Q3_YTD`

如果报告中直接披露了单季度值：

- 直接披露值仍是 `CanonicalFact`
- 差分值仍是 `DerivedFact`
- 两者之间要做一致性校验

## 7. TTM 设计

第一阶段 TTM 规则：

- TTM 作为 `DerivedFact` 存储
- TTM 同时支持动态重算
- TTM 必须保留完整 derivation lineage

TTM 最低血缘字段：

- `derivation_type = "ttm"`
- `derivation_formula`
- `source_canonical_fact_ids`
- `derivation_version`
- `validation_status`

## 8. 证据模型

### 8.1 为什么证据必须独立

证据必须是一等对象。

原因：

- 同一组证据可能支撑多个事实
- 分析结论可能同时依赖事实和正文证据
- 如果到处直接挂原始对象引用，lineage 会迅速失控

### 8.2 EvidenceItem 字段

建议字段：

- `evidence_item_id`
- `document_id`
- `source_type`
  - `block | table | page_image | text_span | model_output | external_market_data`
- `block_id`
- `table_id`
- `page_no`
- `text_excerpt`
- `table_coord`
- `object_uri`
- `content_hash`
- `confidence`
- `created_by`
- `schema_version`

财报原文证据与外部证据必须明确区分，不能在 canonical numeric sourcing 中静默混用。

### 8.3 EvidenceBundle 字段

建议字段：

- `evidence_bundle_id`
- `document_id`
- `bundle_type`
  - `fact_support | derivation_support | validation_support | analysis_support`
- `primary_evidence_item_id`
- `summary`
- `bundle_confidence`
- `created_at`
- `schema_version`

### 8.4 Evidence 引用规则

推荐引用关系：

- `CandidateFact -> EvidenceBundle`
- `CanonicalFact -> EvidenceBundle`
- `DerivedFact -> EvidenceBundle`
- `ValidationIssue -> EvidenceBundle`
- `AnalysisSnapshot -> EvidenceBundle`

对象应通过 bundle 引用证据，而不应直接四处连接原始源对象。

Bundle 与 item 的成员关系在关系型层面必须使用 link table 作为 source of truth，而不是把数组字段嵌在 `EvidenceBundle` 中作为主表达。

## 9. 校验模型

### 9.1 ValidationIssue 字段

建议字段：

- `issue_id`
- `issue_type`
  - `accounting_equation_failed | unit_mismatch | period_mismatch | derived_discrepancy | duplicate_candidate | abnormal_magnitude | unsupported_custom_metric | missing_dependency`
- `severity`
  - `info | warning | error`
- `status`
  - `open | accepted | resolved | ignored`
- `message`
- `affected_fact_ids`
- `affected_period_ids`
- `evidence_bundle_id`
- `rule_id`
- `rule_version`
- `detected_at`

### 9.2 ValidationReport 字段

建议字段：

- `validation_report_id`
- `document_id`
- `canonical_fact_set_id`
- `derived_fact_set_id`
- `overall_status`
  - `ok | partial | review_required | failed`
- `issue_count`
- `error_count`
- `warning_count`
- `generated_at`

ValidationReport 是问题汇总视图，不替代 issue 级别的 lineage。

## 10. AnalysisSnapshot 模型

### 10.1 目的

`AnalysisSnapshot` 是一次分析运行对外消费的冻结视图。

它不是：

- facts 的唯一存储形式
- validation 输出的替代品

### 10.2 AnalysisSnapshot 字段

建议字段：

- `analysis_snapshot_id`
- `document_id`
- `analysis_version`
- `canonical_fact_set_version`
- `derived_fact_set_version`
- `validation_report_id`
- `presentation_unit_policy_version`
- `summary`
- `key_metrics`
- `risk_points`
- `variance_explanations`
- `review_notes`
- `blocked_items`
- `evidence_bundle_id`
- `generated_at`

关系型主表应只保留分析元数据和紧凑字段。较大的 narrative body 可以在合适时外置到 object URI。

### 10.3 与 Validation 的边界

- `ValidationReport` 回答“这些事实是否可信”
- `AnalysisSnapshot` 回答“对消费方呈现什么分析结论”

两者必须保持分离。

## 11. 数据模型中的单位策略

单位策略是横切能力，不是局部 extractor 细节。

每个事实至少要保留支撑以下三层的字段：

- 原始披露保真
- 规范计算
- 展示渲染

最小单位相关字段：

- `raw_value`
- `raw_unit`
- `currency`
- `numeric_value`
- `normalized_unit`

如果展示值被物化，也应同时保留：

- `presentation_value`
- `presentation_unit`
- `currency_conversion_basis`
- `unit_conversion_formula`

核心原则：

`原始披露单位 != 规范计算单位 != 展示单位`

## 12. 存储设计

### 12.1 总原则

采用关系型为主的混合存储模型。

- 关系型存稳定、可查询、可审计的对象
- 对象存储存大体积、结构易变或主要用于回放的 payload

这不是平均用力的混合，而是“关系型为主”。

### 12.2 必须作为关系型一等对象存储的内容

建议关系型表或集合包括：

- `documents`
- `pipeline_runs`
- `period_registry`
- `metric_registry`
- `candidate_fact_sets`
- `canonical_fact_sets`
- `derived_fact_sets`
- `candidate_facts`
- `canonical_facts`
- `derived_facts`
- `validation_reports`
- `validation_issues`
- `analysis_snapshots` 的 metadata
- lineage link tables

### 12.3 适合进入对象存储的内容

建议放入对象存储的 payload：

- 原始 PDF
- OCR 原始输出
- 页面渲染图
- 完整 `document_blocks` payload
- 完整表格 cell matrix
- prompt / completion 原始 dump
- 大型 analysis 正文
- replay bundle
- 调试附件

### 12.4 JSON 字段使用原则

关系型中允许少量 JSON 或 JSONB，用于：

- extensions
- debug metadata
- 非核心、仍在演进中的辅助字段

核心事实、registry、lineage 和 version 语义不能被丢给 JSON blob。

## 13. 文档块与表格存储

第一阶段在关系型中索引文档结构时，粒度到：

- block 级
- table 级

不做到 cell 级关系型建模。

### 13.1 document_blocks 索引字段

- `block_id`
- `document_id`
- `page_no`
- `block_type`
  - `title | paragraph | table | footnote | header | footer | figure`
- `bbox`
- `reading_order`
- `text_excerpt`
- `content_hash`
- `raw_payload_uri`
- `parent_table_id`
- `schema_version`

### 13.2 document_tables 索引字段

- `table_id`
- `document_id`
- `page_no`
- `source_block_id`
- `bbox`
- `table_title`
- `statement_type_hint`
- `unit_hint`
- `currency_hint`
- `period_header_hint`
- `row_count`
- `column_count`
- `content_hash`
- `raw_payload_uri`
- `schema_version`

### 13.3 Cell 级规则

第一阶段完整 cell 结构只放对象存储。

如果后续发现 cell 级 lineage 变成高频查询需求，再把它提升为关系型一等结构。

## 14. 版本设计

### 14.1 Registry 版本

建议版本化引用：

- `metric_registry_version`
- `period_registry_version`
- `unit_policy_version`
- `statement_mapping_version`

### 14.2 Pipeline 版本

建议版本化引用：

- `extractor_version`
- `normalizer_version`
- `resolver_version`
- `derivation_version`
- `validation_rule_version`
- `analysis_version`

### 14.3 Fact Set 版本

Fact sets 应作为独立对象，而不是散落的版本号。

建议标识：

- `candidate_fact_set_id`
- `canonical_fact_set_id`
- `derived_fact_set_id`

建议元数据：

- `version_no`
- `run_id`
- `status`
- `is_current`

## 15. 血缘规则

推荐的 lineage 图：

- `CandidateFact -> DocumentBlock / DocumentTable / EvidenceBundle`
- `CanonicalFact -> CandidateFact[] / EvidenceBundle`
- `DerivedFact -> CanonicalFact[] / EvidenceBundle`
- `ValidationIssue -> CanonicalFact[] or DerivedFact[] / EvidenceBundle`
- `AnalysisSnapshot -> CanonicalFactSet + DerivedFactSet + ValidationReport + EvidenceBundle`

不要允许任意跨层乱连。

lineage 必须分层、显式。

### 15.1 推荐 link tables

- `canonical_fact_candidate_links`
- `derived_fact_canonical_links`
- `validation_issue_fact_links`
- `analysis_snapshot_evidence_bundle_links`

## 16. 重算策略

第一阶段应支持以下重算粒度：

1. `document_rerun`
2. `stage_rerun`
3. `analysis_rerun`

同时在设计上预留：

4. `selective_recompute`

例如：

- 重算一部分 metrics
- 重算某个 derivation formula
- 重新评估某条 validation rule

## 17. 推荐数据库形态

第一阶段优先实现：

- PostgreSQL 作为主关系型存储
- S3、MinIO 或本地对象/文件存储承载大 payload

原因：

- schema 与约束表达力强
- 更适合 lineage 与版本查询
- 可有限使用 JSONB 兼顾扩展
- 在严谨性和迭代速度之间比较平衡

## 18. 结论摘要

第二阶段数据模型应建立在以下稳定原则上：

- 独立的 `Period` 对象
- 标准 metric 库 + 受控 custom registry
- 三层 Fact 模型
- 一等的 EvidenceBundle
- 分离的 Validation 与 Analysis 对象
- 关系型为主的混合存储
- 显式版本与血缘关系

这样即使未来解析器、skills、分析模板发生变化，也不会破坏下游事实账本和审计模型。
