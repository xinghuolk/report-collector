# 财报分析 Post-P5 利润增强最小切片设计

> **状态:** Active design
> **日期:** 2026-04-28
> **范围类型:** Turtle post-P5 focused enhancement
> **上游基线:** P5 multi-year dataset、storage-backed read surfaces、metric governance Phase 1-4B、downstream hardening、DB-backed recompute boundary 和 explicit JSON-to-DB sync bridge 已完成

## 1. 目的

当前系统已经完成 Turtle 结构化财报事实 baseline。下一阶段不应重启旧 P4/P5
coverage phase，也不应在没有明确产品 workflow 需求时新增 async job/recompute
基础设施。

本阶段选择一个 post-P5 focused enhancement：利润增强最小字段族。目标是让现有
deterministic statement-row 主路径覆盖更细的利润质量字段，并继续让这些字段自然进入
canonical facts、P5 dataset、Turtle export、review、lineage 和 storage-backed read
surfaces。

本阶段新增或增强的目标字段是：

- `selling_general_administrative`
- `fv_value_chg_gain`
- `non_oper_income`
- `non_oper_exp`

`gross_profit` 已经在当前代码中具备 registry、semantics、canonical/key facts 和 API
回归覆盖，因此本阶段只把它作为回归保护，不重复作为新增字段。

## 2. 为什么不是 HTTP-triggered recompute/job boundary

路线图在 explicit JSON-to-DB sync bridge 完成后，把 HTTP-triggered recompute/job
boundary evaluation 列为后续候选。但架构分析同时明确：只有出现产品 workflow
requirement 时，才应评估 job status、locking、idempotency 和 async boundary。

当前没有新的产品需求要求用户通过 HTTP 触发 heavy recompute，也没有自动补齐、retry、
approval workflow 或 product artifact lifecycle 的约束。因此现在启动 job/recompute
基础设施会扩大平台面，收益低于字段增强。

利润增强最小切片更符合当前路线图：

- 来自 Turtle v0.15 gap 文档的第一优先级；
- 贴近现有 income statement table semantics；
- 不需要新增 workflow、UI、async job 或 DB-native executor；
- 能直接改善毛利率、费用率、非经常性收益和利润质量判断；
- 可以继续复用已经完成的 governance/source-precedence/downstream guardrails。

## 3. 非目标

本阶段不做：

- HTTP-triggered recompute execution。
- async job queue、job status table、locking 或 workflow lifecycle。
- DB-native recompute executor。
- whole-document LLM assessment 或 diff review。
- 附注/公告桥接字段，例如 DPS、回购、资本化研发、资本化利息、账龄/坏账。
- 现金流增强字段，例如 `stock_based_compensation`、`change_in_receivables`。
- 资产负债增强字段，例如 `total_cur_assets`、`defer_tax_assets`。
- 把单独的 CN `销售费用` 与 `管理费用` 静默求和为 SG&A。
- 让 Ollama 生成 values、canonical facts 或扩大 fallback output space。

## 4. 当前基线

已经存在：

- `gross_profit` 的 table semantics、metric mapping、normalizer standard list 和
  canonical/key facts 回归。
- `rd_exp`、`invest_income`、`asset_disp_income` 等 P4E 字段。
- downstream governance policy：non-consumable facts 不进入 P5 dataset/Turtle。
- P5 dataset 与 Turtle export 是 dataset-driven，不绕过 canonical facts。
- storage-backed dataset/audit/recompute/sync read surfaces。

当前缺口：

- `selling_general_administrative` 缺少明确 direct-row mapping。
- `fv_value_chg_gain` 缺少 income statement direct-row mapping。
- `non_oper_income` 与 `non_oper_exp` 缺少受限 mapping。
- SG&A 的 CN 单项费用场景容易被错误合并，需要在第一阶段 fail closed。
- `other income`、`other expenses`、fair-value balance sheet/note rows 等容易误吸，需要
  negative controls。

## 5. 设计原则

### 5.1 Statement-row first

本阶段只承接 income statement 中可明确定位的 direct rows。字段应从 table semantics
归一化进入 metric mapping registry，再进入 candidate/canonical facts。

### 5.2 SG&A direct-combined only

`selling_general_administrative` 只匹配直接合并口径，例如：

- `selling, general and administrative expenses`
- `selling and administrative expenses`
- `selling and distribution expenses and administrative expenses`
- `销售及行政开支`
- `销售及分销开支及行政开支`

本阶段不把以下单独行映射为 `selling_general_administrative`：

- `selling expenses`
- `distribution expenses`
- `administrative expenses`
- `销售费用`
- `管理费用`

原因是单独费用行需要 component facts 和 derived sum 规则；如果现在直接映射到 SG&A，
同一报表里多行会通过 conflict resolver 互相竞争，造成静默少算。

### 5.3 非经常性项目 fail closed

`non_oper_income` 和 `non_oper_exp` 只匹配明确的 non-operating 语义：

- CN：`营业外收入`、`营业外支出`
- HK/EN：`non-operating income`、`non-operating expenses`

本阶段不把 `other income`、`other gains and losses`、`other expenses` 直接映射到
non-operating。它们在 HK/IFRS 报表中可能属于经营性其他收入或费用，不能无审阅进入
Turtle 利润质量字段。

### 5.4 公允价值变动只取利润表 direct row

`fv_value_chg_gain` 只匹配 income statement 中表达损益影响的 direct rows：

- `公允价值变动收益`
- `fair value change gain`
- `fair value gains and losses`
- `net fair value gains on financial assets`
- `fair value changes of financial instruments`

本阶段不从 balance sheet、note detail 或金融资产公允价值层级表抽取该字段。

### 5.5 继续复用现有治理

新增字段如果作为 standard metrics 被 deterministic mapping 支持，应附带 standard
metric governance metadata，并允许进入 downstream consumption。未知或 unsupported
labels 继续走 provisional/custom review surface，不能静默进入 P5/Turtle。

## 6. 核心组件

### 6.1 Metric mapping registry

在 `financial_report_analysis/registries/metric_mapping.py` 增加四个
`MetricMappingDefinition`：

- `selling_general_administrative`
- `fv_value_chg_gain`
- `non_oper_income`
- `non_oper_exp`

这些定义都限定：

- `statement_type="income_statement"`
- `allowed_table_kinds=("income_statement",)`
- `period_scope="duration"`
- `value_type="amount"`
- `unit_expectation="currency_amount"`
- `sign_rule="allow_negative"`

### 6.2 Table semantics normalization

在 `financial_report_analysis/ingestion/table_semantics.py` 增加受限 label aliases。
同时增加 negative controls，确保：

- `gross margin` 仍不映射为 `gross_profit`；
- `selling expenses` / `administrative expenses` 不映射为 combined SG&A；
- `other income` 不映射为 `non_oper_income`；
- balance sheet 的 fair-value rows 不会因 table kind 进入目标字段。

### 6.3 Fact normalizer standard metrics

在 `financial_report_analysis/services/fact_normalizer.py` 的标准字段列表中加入这四个
metric 的受限 raw labels，确保它们在 standard path 上带有 standard governance
metadata，而不是变成 provisional custom metrics。

### 6.4 P5 dataset 与 Turtle export

不新增专门的 P5 dataset assembly 逻辑。只要新增 canonical facts 是 consumable standard
facts，现有 `assemble_dataset(...)` 会生成 `present` rows，`build_turtle_export(...)`
会按 metric id 透传到 `turtle_field`。

需要增加测试锁定：

- 新字段能从 extracted artifact 进入 P5 dataset。
- 新字段能从 P5 dataset 进入 Turtle export。
- 被 governance policy 阻断的同名字段仍不会进入 dataset/Turtle。

### 6.5 Storage/API

本阶段不新增 API route 或 storage table。现有 storage-backed read surfaces 会通过
persisted extracted artifact、dataset、Turtle 和 audit surface 读回新增字段。

## 7. 数据流

```text
income statement table row
-> normalize_table_semantics
-> MetricMappingRegistry.match
-> TableFactBuilder candidate fact
-> FactNormalizer standard governance metadata
-> ConflictResolver canonical fact
-> ReportAdapter key facts / blocked items
-> P5 assemble_dataset
-> Turtle export
-> optional storage-backed bundle
```

## 8. 错误处理与边界

- 不匹配的 labels 保持 provisional/custom 或不进入目标字段。
- 单独 SG&A component rows 不被自动汇总。
- HK broad `other income` 不被当作 `non_oper_income`。
- table kind 不是 income statement 时，metric mapping registry 必须返回 `None`。
- fallback output space 不在本阶段扩大；如果现有 fallback 遇到这些 labels，仍不能生成
  value 或 canonical fact。

## 9. 测试策略

最小回归集：

- `test_metric_mapping_registry.py`：四个新字段的 CN/HK direct aliases 和 table-kind
  negative controls。
- `test_table_semantics.py`：受限 label normalization 和 SG&A/non-operating negative
  controls。
- `test_fact_pipeline.py`：新字段进入 canonical facts，并带 standard governance metadata。
- `test_p5_dataset.py` 或 `test_p5_turtle_export.py`：新字段进入 dataset/Turtle export。
- `test_analysis_api.py`：至少一个 HTTP extract fixture 能把目标字段暴露到 key facts 或
  canonical surface。

## 10. 验收标准

本阶段完成时应满足：

- 四个目标字段都有 deterministic mapping registry coverage。
- 四个目标字段在 income statement direct-row 场景下能进入 canonical facts。
- 四个目标字段不会绕过 downstream governance guardrails。
- `gross_profit` 既有行为不回退。
- SG&A 单独组件行不会被错误归并成 combined SG&A。
- `other income` 不会被错误归并成 non-operating income。
- P5 dataset 和 Turtle export 能消费新增 standard facts。
- 不新增 HTTP recompute/job/product workflow surface。

## 11. 后续方向

完成利润增强后，下一轮按路线图再二选一：

- 继续 Turtle post-P5 字段线：资产负债增强最小切片。
- 如果出现明确产品 workflow 需求，再启动 HTTP-triggered recompute/job boundary
  evaluation。
