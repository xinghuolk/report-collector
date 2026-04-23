# 财报分析核心数据库架构规划

> **状态:** Planning analysis for review
> **日期:** 2026-04-23
> **阶段:** Post-P5 Core Database Architecture
> **范围类型:** 数据库设计规划、事实账本、灵活字段治理

## 1. 目的

本文把 P5 收口后暴露出的数据库问题单独整理成一份更仔细的规划文档。

当前 `financial-report-analysis` 已经具备 P5 多年 dataset、artifact 持久化、review surface、lineage 和 recompute 的初步能力。但现有数据库模型主要服务于 P5 artifact contract，它还不是完整的财报分析主数据库。

后续数据库设计必须同时承接两类需求：

1. 基础抽取业务：报告、PDF、文档结构、三大表、候选事实、标准事实、派生事实、证据与校验结果。
2. 上层消费业务：P5 dataset、Turtle export、review、recompute、query API、灵活字段治理。

一句话说：

> P5 storage 可以作为上层快照层保留，但主数据库应以事实账本和指标治理为中心重新规划。

## 2. 当前状态判断

### 2.1 已有数据库模型

当前数据库模型已经包含：

- `issuers`
- `reports`
- `manifests`
- `manifest_entries`
- `extracted_artifacts`
- `dataset_artifacts`
- `turtle_export_artifacts`
- `extracted_review_surfaces`
- `dataset_review_surfaces`
- `turtle_export_review_surfaces`
- `dataset_lineage_records`
- `recompute_runs`

这些表适合支撑：

- P5 manifest 管理
- 单份报告 extracted artifact 持久化
- 多年 dataset artifact 持久化
- Turtle export artifact 持久化
- review surface round-trip
- recompute run 记录

### 2.2 当前模型的边界

当前模型仍是 P5/post-P5 oriented。

它缺少基础抽取业务的一等对象：

- `documents`
- `document_versions`
- `extraction_runs`
- `statement_tables`
- `statement_table_rows`
- `statement_table_columns`
- `statement_table_cells`
- `fact_sets`
- `candidate_facts`
- `canonical_facts`
- `derived_facts`
- `fact_lineage`
- `evidence_bundles`
- `evidence_items`
- `validation_reports`
- `validation_issues`
- durable metric registry / custom metric lifecycle

因此，当前 DB 可以回答“P5 某个 artifact 是否存在”，但还不能稳定回答：

- 某份 PDF 解析出了哪些三大表？
- 某个 canonical fact 来自哪一页、哪张表、哪一行？
- 某个派生指标由哪些标准事实计算得到？
- 某个 custom metric 是 provisional、approved，还是已经映射到标准指标？
- 某次 pipeline version 变更后，哪些 fact set 需要重算？

### 2.3 三大表现状

三大表目前在代码模型和 artifact payload 中存在，但在数据库中不是一等实体。

已有模型层使用：

- `income_statement`
- `balance_sheet`
- `cash_flow_statement`
- `metrics`

P5 dataset row 也保留 `statement_type`。

但数据库没有 `statement_tables` 这样的结构化入口。因此后续如果需要查询、审计、review 三大表来源，不能只依赖 `extracted_artifacts.payload_json`。

## 3. 设计原则

### 3.1 事实账本优先

主数据库应围绕 fact ledger 设计。

推荐主路径：

```text
report_file
-> document
-> extraction_run
-> statement_tables
-> candidate_facts
-> canonical_facts
-> derived_facts
-> validation / quality gates
-> P5 dataset / Turtle export
```

P5 dataset 是事实账本的消费结果，不应反过来成为基础事实的唯一存储位置。

### 3.2 Artifact 快照仍然保留

现有 artifact 层不应删除。

原因：

- artifact contract 已经支撑 P5 closeout
- JSON payload 适合保存某次 pipeline 输出的完整快照
- review / diff / recompute 仍需要可回放的版本化 artifact

但 artifact 应从“唯一事实来源”调整为“事实账本上的可回放快照”。

### 3.3 关系索引与 JSON payload 混合

不要 day one 把 PDF 中每个 cell、每段文本、每个中间 block 都完整关系化。

推荐策略：

- 对查询、审计、重算、治理需要稳定引用的对象建关系表。
- 对体积大、结构易变、只用于回放的对象保留 JSON payload 或 object artifact。

必须关系化的对象包括：

- issuer / report / document identity
- extraction run identity
- statement table identity
- fact identity
- fact lineage
- metric registry state
- validation issue
- review decision

可以先 payload 化的对象包括：

- raw document blocks
- full table cell matrix
- parser debug traces
- prompt / completion dumps
- large evidence snapshots

### 3.4 灵活字段必须受治理

`extensions` 字段只能作为兼容扩展，不应承担 custom metric 生命周期。

未知指标可以进入事实账本，但必须有 durable registry 状态。否则后续核心分析、P5、Turtle export 会面临静默污染风险。

### 3.5 SQLite First, Postgres Compatible

当前阶段仍建议 SQLite-first。

原因：

- 本地开发和测试成本低
- 适合 seed dataset、focused integration、单机 recompute
- 当前主要风险是 schema contract，而不是数据库吞吐量

但 schema 和 repository 边界必须保持 Postgres-compatible：

- 不依赖 SQLite-only 业务语义
- 保留 migration discipline
- 避免上层代码绑定本地文件数据库行为

## 4. 推荐数据库分层

### 4.1 Source Registry Layer

负责报告来源和文档身份。

建议表：

- `issuers`
- `reports`
- `report_files`
- `documents`
- `document_versions`

关键字段：

- issuer identity: `issuer_id`, `market`, `stock_code`, `company_name`
- report identity: `issuer_id`, `fiscal_year`, `report_type`, `report_language`
- source identity: `source`, `source_url`, `downloaded_at`, `pdf_path`, `content_hash`
- document identity: `document_id`, `document_version`, `parser_family`, `source_file_id`

设计重点：

- `reports` 表达业务报告，例如“09987 2024 年报”。
- `report_files` 表达文件版本，例如英文 PDF、中文 PDF、重新下载文件。
- `documents` 表达进入 analysis pipeline 的解析对象。

### 4.2 Extraction Run Layer

负责每次抽取运行。

建议表：

- `extraction_runs`
- `extraction_run_inputs`
- `extraction_run_artifacts`

关键字段：

- `extraction_run_id`
- `document_id`
- `pipeline_version`
- `registry_version`
- `parser_version`
- `started_at`
- `completed_at`
- `status`
- `quality_gate`
- `failure_reason`

设计重点：

- 同一份 PDF 可以被不同 pipeline version 多次重跑。
- fact set 应引用 extraction run。
- recompute 应能按 `pipeline_version`、`document_hash`、`registry_version` 判断影响范围。

### 4.3 Statement Table Layer

负责三大表和表格结构。

建议表：

- `statement_tables`
- `statement_table_rows`
- `statement_table_columns`
- `statement_table_cells`

`statement_tables` 关键字段：

- `statement_table_id`
- `extraction_run_id`
- `document_id`
- `statement_type`
- `entity_scope`
- `table_title_raw`
- `page_start`
- `page_end`
- `period_context_json`
- `unit_context_json`
- `confidence`
- `semantic_source`

`statement_type` 起步枚举：

- `income_statement`
- `balance_sheet`
- `cash_flow_statement`
- `metrics`
- `note`
- `unknown`

设计重点：

- 三大表应是一等 DB 对象。
- fact 可以通过 evidence 或 table coordinate 回链到 table row/cell。
- `note` 不应和三大主表混用，避免 disclosure supplement 污染主表事实。

### 4.4 Fact Ledger Layer

负责候选事实、标准事实和派生事实。

建议表：

- `fact_sets`
- `candidate_facts`
- `canonical_facts`
- `derived_facts`
- `fact_lineage`

`fact_sets` 关键字段：

- `fact_set_id`
- `fact_set_kind`: `candidate | canonical | derived`
- `extraction_run_id`
- `issuer_id`
- `report_id`
- `fiscal_year`
- `pipeline_version`
- `registry_version`
- `created_at`
- `status`

fact 共享字段：

- `fact_id`
- `metric_id`
- `metric_label_raw`
- `statement_type`
- `entity_scope`
- `period_id`
- `comparison_axis`
- `adjustment_basis`
- `currency`
- `raw_value`
- `numeric_value`
- `raw_unit`
- `normalized_unit`
- `precision`
- `confidence`
- `evidence_bundle_id`
- `extensions_json`

设计重点：

- `candidate_facts` 允许冲突、重复和低置信度。
- `canonical_facts` 是可消费的披露事实。
- `derived_facts` 是计算结果，不能和披露事实混存。
- `fact_lineage` 记录 canonical <- candidate、derived <- canonical。

### 4.5 Evidence And Validation Layer

负责证据、校验和质量门。

建议表：

- `evidence_bundles`
- `evidence_items`
- `validation_reports`
- `validation_issues`
- `quality_gate_results`

设计重点：

- 每个 candidate fact 必须能引用证据。
- validation issue 应能定位到 fact、metric、statement table 或 extraction run。
- quality gate 应能说明 `pass/review/fail` 的原因，而不是只存状态。

### 4.6 Metric Governance Layer

负责标准指标、别名、custom metric 和灵活字段升级。

建议表：

- `metric_definitions`
- `metric_aliases`
- `metric_registry_entries`
- `metric_mapping_versions`
- `metric_shadow_merge_candidates`
- `custom_metric_review_decisions`

`metric_registry_entries` 关键字段：

- `metric_registry_id`
- `metric_id`
- `namespace`
- `is_custom`
- `registry_status`
- `statement_type`
- `parent_metric_id`
- `accounting_standard`
- `industry_slug`
- `raw_label_canonical`
- `canonical_label`
- `canonical_unit_hint`
- `negative_value_semantics`
- `formula_definition_json`
- `created_from_fact_id`
- `review_status`

`registry_status` 起步枚举：

- `provisional`
- `approved`
- `mapped_to_standard`
- `deprecated`
- `blacklisted`

设计重点：

- 标准指标与 custom 指标必须在同一个治理框架下。
- unknown label 允许生成 provisional custom metric。
- provisional metric 可以进入事实账本，但不能默认进入核心分析、比率计算、TTM、P5 主 dataset 或 Turtle 主输出。
- approved 或 mapped_to_standard 之后，才能进入稳定消费路径。

### 4.7 P5 And Export Layer

负责上层 dataset 与导出快照。

现有表可保留：

- `manifests`
- `manifest_entries`
- `extracted_artifacts`
- `dataset_artifacts`
- `turtle_export_artifacts`
- `extracted_review_surfaces`
- `dataset_review_surfaces`
- `turtle_export_review_surfaces`
- `dataset_lineage_records`
- `recompute_runs`

需要调整语义：

- `extracted_artifacts` 是 extraction run / fact set 的快照，不是基础事实唯一来源。
- `dataset_artifacts` 从 canonical / derived facts 组装。
- `turtle_export_artifacts` 从 dataset artifact 映射。
- `recompute_runs` 应引用 `extraction_run_id`、`fact_set_id`、`dataset_id` 中至少一个稳定对象。

## 5. 灵活字段升级路径

### 5.1 问题

财报字段天然不稳定：

- 不同市场披露标签不同
- 同一指标中英文名称不同
- 行业专有字段会出现
- 管理层口径和会计口径可能并存
- 主表和附注可能同时披露相似数字

如果所有未知字段都塞进 `extensions_json`，短期灵活，长期不可治理。

### 5.2 推荐生命周期

未知字段进入系统时：

1. 先尝试匹配标准 metric。
2. 匹配失败时生成 provisional custom metric。
3. 执行 shadow merge，查找潜在标准指标或已存在 custom metric。
4. provisional fact 进入事实账本。
5. review 决策把 custom metric 转为：
   - `approved`
   - `mapped_to_standard`
   - `deprecated`
   - `blacklisted`
6. 后续 recompute 根据 registry 状态重新决定消费路径。

### 5.3 消费规则

默认规则：

- `standard`: 可进入 canonical、derived、P5、Turtle。
- `approved custom`: 可进入指定 scope 的 canonical / dataset，是否进入 Turtle 由 export contract 决定。
- `mapped_to_standard`: 归并到标准 metric 后消费。
- `provisional`: 仅进入事实账本和 review surface，不进入核心分析主输出。
- `deprecated`: 历史可查，不再新增消费。
- `blacklisted`: 不进入 canonical 消费路径。

### 5.4 Shadow Merge 数据

`metric_shadow_merge_candidates` 应记录：

- source provisional metric
- target candidate metric
- hard filter 结果
- text similarity
- context similarity
- unit compatibility
- magnitude compatibility
- final merge score
- decision threshold
- reviewer override

这样后续 custom metric 的合并不是一次性人工判断，而是可审计、可重放的治理流程。

## 6. Recompute 与版本策略

数据库设计必须让重算有明确粒度。

### 6.1 触发来源

重算触发可以来自：

- source PDF hash changed
- parser version changed
- pipeline version changed
- metric registry version changed
- metric mapping version changed
- validation policy changed
- reviewer changed custom metric decision

### 6.2 推荐粒度

起步支持：

- `document_rerun`: 重新解析整份文档
- `extraction_rerun`: 重新生成三大表和 candidate facts
- `canonical_rerun`: 重新 resolve canonical facts
- `derived_rerun`: 重新计算 derived facts
- `dataset_rerun`: 重新生成 P5 dataset
- `export_rerun`: 重新生成 Turtle export

### 6.3 Recompute Run 记录

`recompute_runs` 应记录：

- `run_id`
- `reason`
- `trigger_kind`
- `source_object_type`
- `source_object_id`
- `target_scope`
- `input_versions_json`
- `output_versions_json`
- `diff_summary_json`
- `status`
- `created_at`

## 7. 与现有 P5 Storage 的关系

当前 P5 storage 不需要推倒重来。

推荐调整方式：

1. 保留当前 P5 artifact repository 和数据库表。
2. 新增核心 DB 层，先让基础抽取结果进入事实账本。
3. 改造 P5 runner，让默认路径从 fact ledger 读取 canonical / derived facts。
4. 保留 real-PDF seed E2E，作为补料和端到端 smoke，不作为默认 P5 closeout。
5. 将 `extracted_artifacts.payload_json` 定位为回放快照，而不是唯一查询源。

这能避免当前已经收口的 P5 功能被大改打散，同时把后续数据库路线拉回正确位置。

## 8. 推荐实施阶段

### 8.1 DB-P1: Core Extraction Persistence

目标：

- 建立 source registry、documents、extraction_runs。
- 建立 statement_tables。
- 建立 fact_sets、candidate_facts、canonical_facts、derived_facts。
- 建立 evidence 和 validation 的最小 durable model。

完成标准：

- 单份报告 pipeline 运行后，三大表和事实层可入库。
- P5 不需要重新从 PDF 抽取即可找到每年 canonical / derived facts。

### 8.2 DB-P2: P5 On Fact Ledger

目标：

- P5 dataset assembly 改为默认消费 fact ledger。
- P5 artifact 继续作为 dataset/export 快照。
- recompute run 能引用 fact set 和 dataset。

完成标准：

- persisted seed test 从数据库事实层组装 P5 dataset。
- real-PDF E2E 只作为慢速补充验证。

### 8.3 DB-P3: Metric Governance

目标：

- durable metric registry。
- custom metric lifecycle。
- shadow merge candidate。
- review decision。
- provisional consumption policy。

完成标准：

- unknown label 生成 provisional custom metric 后可审计。
- provisional metric 默认不进入 P5/Turtle 主输出。
- approved / mapped_to_standard 后可通过 recompute 进入稳定路径。

### 8.4 DB-P4: Query, Audit, And API Foundation

目标：

- 提供按 issuer/year/metric/statement_type 查询事实。
- 提供 evidence drilldown。
- 提供 validation issue 和 review decision 查询。
- 为后续 HTTP API 做 repository 边界。

完成标准：

- 上层 agent 可以消费 canonical facts、derived facts、validation reports、evidence bundles。
- 上层 agent 不需要读取 raw artifact payload 才能完成常规查询。

## 9. 不建议的方案

### 9.1 继续扩 P5 Artifact JSON

短期最快，但会让基础抽取、三大表、事实账本和 custom metric 生命周期都被塞进 payload。

风险：

- 查询困难
- 审计困难
- 重算粒度粗
- provisional metric 难治理
- 后续 API 会反向依赖 JSON 形状

### 9.2 一次性完整关系化所有 PDF 细节

结构最完整，但当前阶段成本过高。

风险：

- 在 table cell、document block、debug trace 上消耗过多时间
- schema 过早锁死
- 影响 post-P5 数据库主线推进

### 9.3 把数据库职责放回 `report/`

不推荐。

`report/` 应保持为报告下载和 PDF 注册工具。业务持久化应属于 `financial-report-analysis`，否则 extraction、fact ledger、metric governance、P5 dataset 会跨项目割裂。

## 10. 待确认问题

后续进入正式 implementation plan 前，需要确认：

1. 第一版 DB 是否仍坚持 SQLite-first，Postgres-compatible。
2. `statement_table_cells` 第一版是否完整关系化，还是先 payload 化。
3. P5 DB 测试是否从 `extracted_artifacts` 快照迁移到 `fact_sets`。
4. provisional custom metric 是否绝对禁止进入 P5 主输出，还是允许显式 flag 放行。
5. review decision 是否第一版只做 repository/API，还是需要人工交互界面。

## 11. 推荐结论

推荐采用：

> 新增核心事实账本层，P5 保持为上层快照层。

这条路线兼顾短期和长期：

- 不推翻已完成的 P5 收口。
- 补齐基础抽取业务的数据库底座。
- 让三大表、事实、证据、校验成为可查询的一等对象。
- 为灵活字段和 custom metric 生命周期预留治理空间。
- 让后续 P5、Turtle、API、review、recompute 都建立在同一套事实账本之上。

