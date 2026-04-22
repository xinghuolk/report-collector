# 财报分析架构差距盘点

> **状态:** 分析记录
> **日期:** 2026-04-22
> **范围:** 对比历史文档意图与当前代码现状，重点覆盖扩展字段、HTTP API、skills/components、存储、血缘与重算。

## 1. 目的

本文记录当前对 `financial-report-analysis` 的架构差距盘点。

这次盘点主要是为了保留前面回看历史 plan / spec 时发现的问题，尤其是以下方向：

- 灵活扩展字段设计
- HTTP API 与 `report/` forwarding 边界
- skills/components 拆分方式
- storage、lineage、recompute 的设计预期

本文不是 implementation plan。它应作为后续判断是否需要创建“扩展字段治理”或“API/query surface 扩展”专项计划时的参考。

## 2. 已回看的关键文档

### 2.1 核心架构设计

- `docs/superpowers/specs/2026-04-18-financial-report-analysis-design.md`
  - 定义 `financial-report-analysis` 是独立 analysis service。
  - 定义 `report/` 只作为 forwarding client。
  - 引入以事实账本为中心的主流程：
    `document -> document_blocks -> candidate_facts -> normalized_facts ->
    canonical_facts -> derived_facts -> analysis_snapshot`。
  - 提出 reusable skills/components 应按跨文档认知能力组织，而不是按单个字段抽取组织。

### 2.2 数据模型与灵活字段

- `docs/superpowers/specs/2026-04-18-financial-report-analysis-data-model-design.md`
  - 定义标准 metric 库 + 受控 custom metric registry。
  - 定义 registry 状态：
    `provisional | approved | mapped_to_standard | deprecated | blacklisted`。
  - 定义 shadow merge、review status、lineage、storage、versioning、recompute 等预期。
  - 明确说明 provisional custom metric 可以进入事实账本，但在 approved 之前不能进入核心分析、比率计算或 TTM。

### 2.3 集成边界

- `docs/superpowers/specs/2026-04-18-financial-report-analysis-integration-design.md`
  - 定义稳定 HTTP contract：
    - `POST /api/v1/analysis/extract`
    - `GET /health`
  - 定义 `report/` 的 `/extract/analysis` 是 forwarding path。
  - 规定上层 agent 应消费 canonical facts、derived facts、analysis snapshots、validation reports、evidence bundles。
  - 规定上层 agent 不应直接消费 candidate facts、raw block payloads、prompt/completion dumps、provisional custom metrics 或未校验核心数字。

### 2.4 初始实施计划

- `docs/superpowers/plans/2026-04-18-financial-report-analysis-implementation-plan.md`
  - 规划独立 `financial-report-analysis/` 子项目。
  - 按 `models`、`registries`、`services`、`pipeline`、`adapters`、`api`、`storage` 组织包结构。
  - 包含早期 `MetricRegistry` 任务：标准 metric 命中、自定义 metric provisional 注册、shadow merge。
  - 包含独立 API 与 `report/` forwarding 的专门任务。

### 2.5 表格语义与 canonical 设计

- `docs/superpowers/specs/2026-04-19-financial-report-analysis-table-semantic-canonical-design.md`
  - 引入表格语义主路径：
    `pdf -> raw table blocks -> parsed tables -> normalized table semantics ->
    metric mapping registry -> candidate facts -> canonical facts`。
  - 定义 `load_metric_registry(source=None)` 作为稳定 loader 边界。
  - 第一版不实现外部 YAML、JSON 或数据库 registry source，但先保留未来迁移边界。

## 3. 当前代码现状

### 3.1 HTTP API 与 Forwarding

当前代码已经有预期中的独立 API surface：

- `financial-report-analysis/src/financial_report_analysis/api/routes.py`
  - `GET /health`
  - `POST /api/v1/analysis/extract`
- `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
  - `AnalysisExtractRequest`
  - `AnalysisExtractResponse`

当前 `report/` forwarding 也已经存在：

- `report/src/api/routes/extract.py`
  - `POST /extract/analysis`
- `report/src/handlers/pdf_handler.py`
  - `extract_financial_report_analysis()` 通过 `aiohttp` 做 HTTP 转发。
- `report/src/config.py`
  - `ANALYSIS_SERVICE_BASE_URL`
  - `ANALYSIS_EXTRACT_PATH = "/api/v1/analysis/extract"`

判断：

- service 边界基本按文档落地。
- API 仍然很窄：extract + health。
- 还没有面向 facts、validation reports、provisional metrics、analysis snapshots 的独立 read / query / export / review API。

### 3.2 灵活扩展字段

当前代码仍保留早期的灵活 metric registry：

- `financial-report-analysis/src/financial_report_analysis/registries/metric_registry.py`
  - `MetricRegistry`
  - `MetricRegistryEntry`
  - `StandardMetric`
  - `resolve_metric()`
  - 使用 `custom::...` 生成 custom metric ID
  - 对未知 label 返回 `registry_status="provisional"`

当前测试覆盖了第一步：

- `financial-report-analysis/tests/unit/test_metric_registry.py`
  - 验证标准 metric 命中。
  - 验证 provisional custom metric 创建。
  - 验证 custom ID 会随 statement / parent metric 不同而稳定区分。

当前主表格路径主要使用另一套 mapping registry：

- `financial-report-analysis/src/financial_report_analysis/registries/metric_mapping.py`
  - `MetricMappingDefinition`
  - `MetricMappingRegistry`
  - `load_metric_registry(source=None)`
  - 对非 `None` external source 抛出 `NotImplementedError`

判断：

- 灵活扩展字段的第一步已经存在：未知 label 可以生成 provisional custom metric ID。
- 但 data-model design 中的完整 lifecycle 尚未实现。
- 当前没有 durable registry record、review workflow、shadow-merge score、duplicate candidate list，也没有 approved / mapped / deprecated / blacklisted 状态流转机制。
- 当前命名存在潜在混淆：
  - `MetricRegistry` 表示 raw-label 标准/自定义 metric identity resolution。
  - `MetricMappingRegistry` 表示 table-semantics-to-supported-metric mapping。
  - `load_metric_registry()` 当前加载的是 mapping registry，不是 custom metric registry。

### 3.3 Candidate / Canonical / Derived Facts

当前代码实现了三层 fact 结构：

- `financial-report-analysis/src/financial_report_analysis/models/facts.py`
  - `CandidateFact`
  - `CanonicalFact`
  - `DerivedFact`
  - 共享 `extensions` 字段

当前 pipeline 保留了预期中的粗粒度流程：

- `financial-report-analysis/src/financial_report_analysis/pipeline.py`
  - 从 ingestion payload 构造 candidate facts。
  - normalize candidates。
  - resolve canonical facts。
  - derive TTM facts。
  - validate canonical and derived facts。

判断：

- 基础 fact model 与早期设计一致。
- `extensions` 已经被实际用于语义 provenance，例如：
  - `semantic_source`
  - `semantic_confidence`
  - `fallback_reason`
  - `unit_semantic_source`
  - `currency_semantic_source`
- fact model 还没有强制执行 custom metric lifecycle 规则。

### 3.4 Quality Gate 与 Provisional Metrics

integration design 要求：

- `quality_gate=pass` 不应依赖 provisional custom metrics。
- 核心分析不能消费 provisional custom metrics。
- 如果核心分析必须依赖 provisional custom metrics，应根据严重程度进入 fail 或 review。

当前代码：

- `ReportAdapter` 会选择 key facts，并把 validation status 映射到 `pass`、`review` 或 `fail`。
- `ReportAdapter` 不检查 `registry_status`、custom metric namespace 或 provisional metric metadata。
- `ValidationService` 检查高层 lineage 和数量一致性，但没有看到 provisional metric policy。

判断：

- quality gate 概念已经实现。
- custom/provisional-specific gate policy 尚未实现。
- 这是一个实质性差距，因为 integration design 明确把 provisional custom metrics 排除在自动核心分析之外。

### 3.5 Skills / Components

核心设计曾提出 reusable skills/components，例如：

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

当前代码没有物理 `skills/` 目录。这些能力分散在：

- `ingestion/`
- `services/`
- `registries/`
- `semantic_fallback/`
- `unit_policy.py`
- `pipeline.py`

判断：

- 这不一定是功能问题。
- 设计原则保留下来了，但物理目录没有保留。
- 如果后续需要可复用能力地图，应把旧 skill list 映射到当前模块，而不是没有明确收益地重新引入一个 `skills/` package。

### 3.6 Storage / Lineage / Recompute

data model design 预期：

- relational-first storage
- 大型、易变、可回放 payload 放 object storage
- registry、lineage、version 是一等结构
- document block 和 table 索引
- fact set versions
- lineage link tables
- recompute 粒度：
  - `document_rerun`
  - `stage_rerun`
  - `analysis_rerun`
  - 未来 `selective_recompute`

当前代码有：

- `financial-report-analysis/src/financial_report_analysis/storage/artifacts.py`
  - fact set ID helpers
  - validation report artifact
  - evidence bundle record
- `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
  - in-memory evidence repository
  - 显式 bundle-item link model

判断：

- evidence bundle link-table 概念已有内存态表达。
- 没有 PostgreSQL schema 或实现。
- 没有 object-storage 实现。
- 没有 document block / table 关系型索引。
- 没有 durable fact-set version store。
- 没有 recompute API 或 stage-level recompute orchestration。

## 4. 差距总结

### 4.1 已实现或基本实现

- 独立 FastAPI service 边界。
- `report/` HTTP forwarding 边界。
- 基础 extract response envelope。
- Candidate / canonical / derived fact classes。
- 基础 pipeline flow。
- 内置 metric mapping registry。
- 最小 provisional custom metric ID 生成。
- `extensions` 中的 semantic provenance。
- in-memory evidence bundle link representation。

### 4.2 部分实现

- 灵活扩展字段。
  - provisional ID generation 已存在。
  - lifecycle、review、shadow merge、consumption policy 缺失。
- Registry externalization。
  - loader boundary 已存在。
  - YAML / JSON / database source loading 尚未实现。
- Skills/components。
  - 能力分散在现有模块中。
  - 没有显式 component map 或物理 `skills/` package。
- Quality gate。
  - 通用 gate 已存在。
  - provisional-metric-specific gate policy 缺失。

### 4.3 尚未实现

- Custom metric review/export surface。
- Durable custom metric registry。
- Shadow merge scoring and duplicate tracking。
- Approved / mapped / deprecated / blacklisted registry transitions。
- 面向 fact sets、validation reports、evidence、custom metric review 的 HTTP query/read endpoints。
- PostgreSQL-backed fact/evidence/lineage storage。
- 面向 PDF、OCR、完整 cell matrix、prompt/completion dump、replay bundle 的 object storage。
- Selective recompute。

## 5. 具体问题点

### 5.1 Registry 边界混淆

`MetricRegistry` 和 `MetricMappingRegistry` 解决的是两个不同问题，但当前公开 loader 名 `load_metric_registry()` 指向的是 mapping registry。

风险：

- 后续 custom metric 工作可能扩错 registry。
- 新贡献者可能把 table mapping 误认为完整 custom metric lifecycle。

建议澄清：

- 在扩展 custom metric governance 前，先明确命名和职责。
- 可以考虑使用类似名称：
  - `MetricIdentityRegistry`：负责 standard/custom metric identity。
  - `MetricMappingRegistry`：负责 table-semantics mapping。

### 5.2 Provisional Metrics 可存在但缺少治理

代码可以生成 provisional custom metric ID，但 pipeline 没有明显执行文档里的消费规则。

风险：

- 如果 ingestion path 提供了 provisional metric，它可能静默进入 canonical facts、key facts 或 analysis output。
- `quality_gate` 可能无法反映对 provisional metrics 的依赖。

建议澄清：

- 显式传播 `registry_status` metadata。
- 必要时增加 `unsupported_custom_metric` validation issue。
- 确保 `ReportAdapter` 和 quality gate 会从自动核心分析中排除或阻断 provisional metrics。

### 5.3 API 仍是 Extract-Only

当前 API 是很窄的 extract envelope。它符合早期交付边界，但不支持 custom metric review 或 durable query 用例。

风险：

- 扩展字段治理没有 user-facing 或 agent-facing workflow。
- review candidates 可能只能停留在 pipeline outputs 或 logs 中。

建议澄清：

- 后续单独设计 query/review API，不要把所有能力继续塞进 `/api/v1/analysis/extract`。
- 候选 endpoint 可以包括：
  - 按 document/run 列出 provisional metrics。
  - 查看 provisional metrics 的 evidence。
  - 标记 provisional metrics 为 approved、mapped、deprecated 或 blacklisted。
  - 导出 candidate review packet。

### 5.4 Storage 设计领先于代码

文档预期 durable relational/object storage。当前代码仍是 memory-first。

风险：

- lineage、audit、replay、recompute 难以做扎实。
- custom metric lifecycle 没有 durable registry state 就很难健壮。

建议澄清：

- 把 storage 视为完整 custom metric governance 的前置条件之一。
- 最小第一步可以仍然是 file-backed 或 SQLite/PostgreSQL-lite，但应保留关系型概念：
  - registry rows
  - fact sets
  - lineage links
  - evidence bundle links

### 5.5 Skills 是原则，不是当前模块边界

旧文档中的 `skills/components` 说法没有体现为目录结构。

风险：

- 阅读旧 plan 时容易误以为还有一层未实现的 `skills/` package。
- 但现在强行新建 `skills/` package 可能只会制造迁移成本。

建议澄清：

- 如有需要，创建一份 component map：
  - old skill name
  - current module
  - current maturity
  - known gap

## 6. 推荐后续顺序

### Step 1: 先明确 Registry 角色

写一份小设计说明，或在本文基础上继续补充，明确：

- metric identity registry
- metric mapping registry
- custom metric lifecycle registry

这个动作应发生在继续增加扩展字段行为之前。

### Step 2: 增加 Provisional Metric Governance

最小有用行为：

- 将 `registry_status` 传播到 candidate / canonical metadata。
- 对 provisional custom metrics 增加 validation issue 或 blocked item。
- 确保 provisional metrics 不进入 `key_facts`、ratios、TTM 或自动核心分析。

### Step 3: 增加 Review Surface

先做窄：

- 不做完整 UI。
- 不做大而全 query API。
- 一个 provisional metric candidates 的 review/export surface 就足够。

可选第一版交付形态：

- 内部 service function。
- CLI helper。
- 或单个只读 HTTP endpoint。

### Step 4: 决定 Registry Persistence

不要过早外置整个 metric mapping registry。

更合理的顺序：

1. 先持久化 custom metric registry records。
2. 持久化 review status 和 mapping decisions。
3. 再考虑是否外置 deterministic mapping definitions。

### Step 5: 再回到 Storage And Recompute

等 custom metric governance 有真实使用场景后，再围绕最小对象集引入 durable storage：

- registry rows
- pipeline runs
- fact sets
- evidence bundle links
- validation issues

之后再回看 `stage_rerun` 和 `selective_recompute`。

## 7. 当前最实际的下一步决策

最值得进入 implementation planning 的目标是：

**Extension Metric Governance Phase 1**

建议窄范围：

- 澄清 registry roles。
- 传播 custom/provisional metadata。
- 阻止 provisional metrics 进入 key facts 和自动分析。
- 暴露可 review 的 provisional metric candidates。
- 不把 table extraction 和 Turtle 字段扩展混进本阶段。

这样可以把早期“灵活扩展字段”设计从半落地状态推进成一个受控、可测试的能力，同时不打断当前 Turtle 字段抽取路线。
