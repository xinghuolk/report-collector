# 财报分析设计文档

## 1. 背景

当前财报提取主要围绕字段级正则和文档特例规则展开，这带来了三个结构性问题：

- 提取错误率高，尤其集中在期间、单位和表格对齐上
- 可追溯性弱，很难解释某个数字来自哪里
- 可维护性差，修复逻辑不断堆积在面向单文档的 extractor 中

新目标不应再是“PDF 字段提取器”，而应是一个可被多个项目复用的财报分析能力，包括 `/home/like/mycode/finanice/TradingAgents-CN` 这类调用方。

## 2. 目标

构建一个以独立 HTTP API 为主形态、并保留可嵌入 app factory 的财报理解与分析能力。

该能力需要支持：

- A 股与港股财报
- 年报、中报、季报
- 带证据与校验结果的标准财务事实
- TTM 派生数据
- 可回放、可审计、可复用的分析归档结果

该能力不应以 MCP 作为主要集成形式。

## 3. 第一阶段非目标

第一阶段不覆盖：

- 招股书、临时公告、投资者 PPT、业绩快报等文档
- 以 RAG 为主链路的核心数字抽取架构
- 继续在单一大型 extractor 文件中堆市场特例逻辑

后续可以为解释与证据检索引入 RAG，但它不应承担高精度财务事实抽取的主链路。

## 4. 交付形态

推荐交付方式：

1. `financial-report-analysis` 作为独立分析服务，对外暴露稳定 HTTP API
2. 同时保留 Python 包与 app factory，供服务内部复用和宿主进程嵌入启动
3. 包内部通过可复用 skills/components 编排流水线

优先于以下方案：

- 以 MCP 作为主接口
- 以 Codex 风格 `SKILL.md` 运行时产物作为生产集成形态
- 让整个仓库直接依赖一个“大而全”的服务实现

原因：

- `/home/like/mycode/finanice/TradingAgents-CN` 与 `report/` 都需要稳定、可独立演进的跨项目契约
- HTTP contract 比跨仓库 Python import 更容易部署、测试、版本治理与权限隔离
- 保留包内 app factory 可以兼顾本地联调、单进程嵌入和未来组合部署
- 核心领域逻辑仍保留在包内，不会因为引入 HTTP 层而倒灌回旧 extractor

## 5. 推荐架构

目标系统应设计为围绕“财务事实账本”构建的独立分析服务，服务内部复用同一套领域包。

端到端主流程：

`document -> document_blocks -> candidate_facts -> normalized_facts -> canonical_facts -> derived_facts -> analysis_snapshot`

事实层职责划分：

- `candidate_facts`：抽取器输出；允许脏、重复、冲突、不完整
- `normalized_facts`：完成 metric、period、unit、currency、scope、comparison-axis 归一化，但尚未做冲突裁决
- `canonical_facts`：经过裁决与校验后的主事实，是账本级事实来源

推荐内部层次：

1. 文档接入
2. 文档标准化
3. 候选事实抽取
4. 事实归一化
5. 冲突裁决与校验
6. 派生事实生成
7. 分析生成
8. 存储与查询

对外集成层次：

1. `financial-report-analysis` 独立 FastAPI 服务
2. `report/` 作为 forwarding client 暴露兼容入口
3. `TradingAgents-CN` 推荐直连分析服务，不强制经过 `report/`

系统应把“事实账本”而非“字段提取”作为中心抽象。

## 6. Skill 化组件模型

可复用的 skills/components 应按跨文档认知能力组织，而不是按字段组织。

证据应通过一层可复用的 evidence layer 表达，而不是分散为各对象上的临时字段。

### 6.1 高优先级可复用 skills

- `classify_document_type`
- `parse_financial_table`
- `stitch_cross_page_table`
- `normalize_metric`
- `parse_period`
- `parse_unit_currency`
- `detect_entity_scope`
- `detect_comparison_axis`
- `build_fact`
- `resolve_conflicts`
- `validate_facts`
- `derive_ttm`
- `render_analysis_units`

### 6.2 反模式

不要设计类似以下组件：

- `extract_revenue_from_pdf`
- `extract_balance_sheet_from_cn_annual_report`
- `parse_hk_09987_report`

这些本质上是 extractor 特例逻辑，不是可复用 skill。

## 7. 市场与报告范围

第一阶段支持范围：

- 市场：A 股、港股
- 报告类型：年报、中报、季报
- 输出：财务事实、证据、校验结果、TTM、分析快照

第一阶段需要容忍 A 股与港股报告中的术语差异，包括单位写法、报表名称和双语披露差异。

港股语言策略：

- 第一阶段仅接入英文版港股财报作为主输入
- 后续阶段再补充繁体中文版作为可选辅助来源
- 在补充繁中支持前，港股主账本与核心数字分析以英文披露为准

期间模型必须支持：

- 全年
- 半年累计
- 季度累计
- 单季度披露值或单季度派生值
- 资产负债表时点值

## 8. TTM 设计

第一阶段必须支持 TTM。

设计决策：

- 将 TTM 存为派生后的标准事实
- 分析阶段也支持动态重算
- 必须持久化公式、来源期间、计算版本和校验状态

因此 TTM 同时具备两种角色：

- 可查询、可归档的事实
- 可重算的派生指标

TTM 最低血缘字段：

- `is_derived = true`
- `derivation_type = "ttm"`
- `derivation_formula`
- `source_fact_ids`
- `derivation_version`
- `validation_status`

## 9. 单位策略

单位处理是系统级策略，不是 extractor 局部细节。

全局单位约定：

| 数据阶段 | 单位规则 | 说明 |
| --- | --- | --- |
| Phase 1 `data_pack_market.md` | `{报表币种}百万` | 市场数据输出，币种取决于报表币种 |
| Phase 2 `data_pack_report.md` | 报表原始披露单位 | 来源于财报表头或文档说明，例如 `RMB'000`、`万元`、`百万` |
| Phase 3 最终分析 | `人民币亿元` | 面向阅读的统一展示单位 |

核心原则：

`原始披露单位 != 规范计算单位 != 展示单位`

`规范计算单位` 只服务于内部计算一致性，不应被视为面向用户的展示单位。

每个事实在适用时都应保留这三层表达。

最小单位相关字段：

- `value_raw`
- `raw_unit`
- `raw_currency`
- `normalized_value`
- `normalized_unit`
- `normalized_currency`
- `presentation_value`
- `presentation_unit`
- `currency_conversion_basis`
- `unit_conversion_formula`

单位策略必须同时适用于：

- 原始财报事实
- 市场数据包事实
- TTM 等派生事实
- 最终分析展示

## 10. 核心数据对象

### 10.1 DocumentBlock

标准化后的文档块输出：

- `block_id`
- `document_id`
- `page_no`
- `bbox`
- `block_type`
- `text`
- `structured_repr`
- `table_cells`
- `reading_order`

### 10.2 BaseFact

核心事实 schema 需要表达语义、来源和单位上下文：

- `fact_id`
- `metric`
- `metric_label_raw`
- `statement_type`
- `entity_scope`
- `comparison_axis`
- `value`
- `value_raw`
- `currency`
- `scale`
- `period_id`
- `source_block_id`
- `source_page`
- `evidence_span`
- `confidence`
- `extractor`

### 10.3 Canonical Fact

Canonical facts 是经过冲突裁决与校验后的主事实：

- `canonical_fact_id`
- `selected_source_fact_ids`
- `resolution_reason`
- `validation_flags`
- `quality_score`

### 10.4 Derived Fact

用于 TTM 及其他计算得出的事实：

- `derived_fact_id`
- `derivation_type`
- `derivation_formula`
- `source_fact_ids`
- `derivation_version`
- `validation_status`

### 10.5 Analysis Snapshot

归档后的分析输出：

- `analysis_id`
- `document_id`
- `canonical_fact_set_version`
- `derived_fact_set_version`
- `analysis_version`
- `presentation_unit_policy_version`
- `summary`
- `risk_points`
- `variance_explanations`

## 11. 存储模型

系统必须归档的不只是最终 JSON。

建议持久化以下对象：

1. `raw_document`
2. `document_blocks`
3. `candidate_facts`
4. `normalized_facts`
5. `canonical_facts`
6. `derived_facts`
7. `validation_report`
8. `analysis_snapshot`
9. `run_metadata`

`run_metadata` 应至少包括：

- pipeline version
- model version
- rule version
- unit policy version
- derivation version
- execution timestamp

## 12. 分析规则

分析层应拆成两部分：

### 12.1 确定性分析

- 同比、环比计算
- 利润率、杠杆率等比率
- 现金流质量检查
- 单季度差分
- TTM 生成
- 比率与异常检测

### 12.2 解释性分析

- 波动原因解释
- 管理层讨论抽取
- 风险摘要
- 可疑事实的复核提示

基于 LLM 的解释必须消费 canonical 或 derived facts，而不是直接把原始 chunk 当作数字主来源。

## 13. 集成策略

推荐的下游集成方式：

### 13.1 主路径

独立 HTTP API：

- 适合 `TradingAgents-CN` 与 `report/` 共享同一份跨项目契约
- 更利于服务化部署、版本治理和调用权限隔离
- 允许 `report/` 作为 forwarding client 存在，而不承载分析核心实现

### 13.2 可选路径

嵌入式 app factory：

- 用于必须同进程承载的宿主环境
- 用于本地联调或组合部署
- 不能替代独立 HTTP API 作为主集成契约

## 14. 建议的包结构

推荐目录结构：

```text
financial_report_analysis/
  models/
  skills/
  pipeline/
  unit_policy/
  storage/
  analysis/
  adapters/
  api/
```

各目录职责：

- `models/`：定义数据契约
- `skills/`：放可复用领域能力
- `pipeline/`：编排端到端执行流程
- `unit_policy/`：统一管理单位与币种转换策略
- `storage/`：负责归档与读取
- `analysis/`：负责确定性分析与解释性分析
- `adapters/`：对外暴露受控结果适配
- `api/`：对外暴露 HTTP app、routes 与 schemas

## 15. 迁移方向

推荐迁移路径：

1. 保留现有 downloader 与基础 PDF 输入链路
2. 在当前 extractor 旁边构建新包
3. 新文档逐步走新事实账本流水线
4. 仅在必要处保留兼容输出
5. 在建立信心后逐步下线旧 extractor 逻辑

不应继续在 `report/src/pdf_parser/content_extractor.py` 中堆新逻辑。

## 16. 下一步待定问题

以下内容应在实现规划阶段最终确定：

- 新包在当前仓库中的具体落点
- 持久化 schema 与数据库选型
- 跨市场计算时的规范计算单位
- Phase 3 统一展示到 `人民币亿元` 时的汇率策略
- 第一阶段优先支持的核心指标集合
- 是否对所有可推导单季度值都进行持久化

## 17. 结论摘要

推荐方向：

- 先留在当前仓库中推进
- 但从代码组织上设计成独立 analysis service + 包内领域实现
- 主集成方式使用独立 HTTP API
- 以财务事实账本为中心
- 把单位策略和 TTM 作为一等能力
- 按认知能力拆 skills，而不是按字段拆 extractor

该设计既服务当前财报处理，也服务未来被 `TradingAgents-CN`、`report/` 等调用方通过统一 HTTP contract 复用。
