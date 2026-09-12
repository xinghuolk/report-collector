# HK00001 Remaining Main Statement Metrics Design

## 背景

上一轮 HK.00001 2025 年报修复已经证明双币种主报表可以从 page text 恢复出
deterministic statement rows，并已覆盖 `revenue`、`total_profit`、`cash`、
`fix_assets`、`goodwill` 等字段。但最终 review 指出原计划目标仍未达成：
`operating_cost`、`total_assets`、`operating_cash_flow` 等 Turtle 核心字段在禁用
fallback 的 availability 中仍未稳定露出。

本轮不是重做双币种结构恢复，也不是扩大到完整 Turtle 32 字段覆盖。目标是对 HK.00001
剩余主报表关键字段做 focused pass，把每个缺口明确归类并修到 deterministic 主路径。

## 目标

在 HK.00001 2025 年报上，禁用 semantic fallback 时，以下字段中真实存在于主报表的
字段必须从 deterministic `table_semantics` candidate facts 产出：

- `operating_cost`
- `total_assets`
- `operating_cash_flow`

同时诊断并尽量纳入以下相邻主表字段：

- `operating_profit`
- `total_liabilities`
- `c_paid_for_taxes`

如果某个字段仍不能产出，必须给出明确状态：`structure_recovery_gap`、
`semantic_normalization_gap`、`metric_mapping_gap`、`fact_filter_gap`、`absent` 或
`out_of_scope`。不能只用 availability report 中的 omission 代表字段不存在。

## 非目标

- 不引入 issuer-specific 分支，例如不能按 `stock_code == "00001"` 写逻辑。
- 不让 Ollama fallback 参与 HK.00001 主报表字段验收。
- 不扩展到附注、债务、现金健康度、营运资本或文本型 review artifact。
- 不调整 canonical promotion、review workflow、DB schema 或 API contract。
- 不把 US$ 展示列作为 Turtle 指标值。

## 当前诊断假设

已有结构回归说明以下行标签已经从真实 PDF 主表中恢复：

- income statement: `cost of inventories sold`
- balance sheet: `fixed assets`、`total assets less current liabilities`
- cash flow statement:
  `cash generated from operating activities before interest expenses, other finance costs, tax paid, and changes in working capital`
  以及 `tax paid`

剩余字段缺口更可能分布在三个位置：

1. `metric_mapping_gap`：例如 HK `cost of inventories sold` 没有映射到
   `operating_cost`。
2. `semantic_normalization_gap` 或 `fact_filter_gap`：例如现金流主表的
   “cash generated before interest/tax/working capital” 不是最终 operating cash flow，
   需要避免误映射；真正的 operating cash flow 可能在同页汇总行、续页行或当前被过滤。
3. `structure_recovery_gap`：例如 `total assets` 或 `net cash generated from operating activities`
   行存在于 page text，但没有形成可绑定 HK$ value cells 的 deterministic row。

## 设计

### 1. Deterministic E2E 报告模式

`scripts/run-real-pdf-e2e-evaluation.sh` 增加 deterministic/no-fallback 报告模式。
该模式不替代 slow path E2E，而是额外生成一个可复现的 focused availability report。

新增环境变量：

- `FRA_E2E_DETERMINISTIC_ONLY`
  - 默认 `false`
  - 设为 `true` 时，availability report 阶段以 `FRA_SEMANTIC_FALLBACK_ENABLED=false`
    调用 `scripts/report_metric_availability.py`
- `FRA_E2E_EXPECTED_METRIC_IDS`
  - 逗号分隔
  - 为空时沿用 turtle investment 32 字段
  - 本轮验证使用
    `revenue,operating_cost,operating_profit,total_assets,total_liabilities,cash,operating_cash_flow,c_paid_for_taxes`

输出文件命名：

- 默认 report 保持现状：`HK_00001_2025_annual_metric_availability.md`
- deterministic-only report 使用：
  `HK_00001_2025_annual_deterministic_metric_availability.md`
- summary 文件同步使用：
  `HK_00001_2025_annual_deterministic_summary.txt`

### 2. 字段缺口诊断顺序

每个目标字段按固定顺序诊断：

1. structure row：真实 PDF parsed/normalized tables 中是否有对应 raw label 和 HK$ value。
2. table semantics：row label 是否归一成可稳定匹配的 normalized label，statement/table kind 是否正确。
3. metric mapping：`MetricMappingRegistry` 是否命中目标 metric，period scope 是否匹配。
4. fact builder/filter：candidate fact 是否生成，是否被 summary/ratio/noise filter 错误过滤。
5. availability：禁用 fallback 的 report 是否 present，source 是否 `table_semantics`，semantic source 是否 `deterministic`。

### 3. 字段映射边界

允许的 deterministic 映射：

- `cost of inventories sold` -> `operating_cost`
  - 仅限 income statement。
  - 保留负数值。
- `total assets` -> `total_assets`
  - 仅限 balance sheet point-in-time。
  - 不把 `total assets less current liabilities` 映射为 `total_assets`。
- `tax paid` -> `c_paid_for_taxes`
  - 仅限 cash flow statement duration。
  - 保留负数值。

需要谨慎处理的现金流：

- `cash generated from operating activities before interest expenses, other finance costs, tax paid, and changes in working capital`
  不是最终 `operating_cash_flow`，不能为了通过测试直接映射。
- 只有能证明 label 表达最终经营活动现金流净额，例如
  `net cash generated from operating activities`，才映射到 `operating_cash_flow`。
- 如果 HK.00001 2025 主报表没有最终经营活动现金流净额行稳定露出，本轮应记录为
  `not_surfaced`，而不是做近似映射。

### 4. 回归测试策略

新增或更新测试必须覆盖两类行为：

- Positive：HK.00001 2025 真实 PDF 中真实存在且可稳定映射的字段，在禁用 fallback 时
  deterministic present。
- Negative：近似但非最终口径的现金流行不能映射成 `operating_cash_flow`；
  `total assets less current liabilities` 不能映射成 `total_assets`。

测试不能依赖 Ollama、网络或 DB。真实 PDF integration 可以使用现有
`report/downloads/hk_stocks/00001/annual/2025_annual_en.pdf` fixture。

## 验收标准

本轮完成时必须满足：

- `scripts/run-real-pdf-e2e-evaluation.sh --dry-run` 显示 deterministic-only 输出路径。
- deterministic-only report 可通过脚本复现，不再依赖手工 `/tmp` 命令。
- 禁用 fallback 的 focused availability 至少让 `revenue`、`operating_cost`、`cash`、
  `total_assets` 中真实存在字段 deterministic present。
- `operating_cash_flow` 如果不能 deterministic present，必须有测试或文档说明它是
  `not_surfaced`，且没有用 “before interest/tax/working capital” 近似行误映射。
- `c_paid_for_taxes` 如果从 `tax paid` 行产出，必须来自 cash flow statement deterministic source。
- HK.00001 结构回归和既有 HK anchors 不回退。

## 风险

- `operating_cash_flow` 可能需要进一步结构恢复，而不是 alias 增补。若主表最终净额行没有稳定露出，
  应先记录 `not_surfaced`，不要用中间行替代。
- `total_assets` 可能被 `total assets less current liabilities` 干扰，必须用 negative control 压住。
- E2E 脚本目前自定义 `FRA_E2E_PDF_PATH` 只影响存在性检查和 availability report，pytest E2E
  仍按 stock/year/filename 找样本。本轮不强制重构全部 E2E fixture resolution，但必须在脚本文档中
  明确该限制，避免误导。

## 自检

- 无 issuer-specific 实现要求。
- 验收以 deterministic/no-fallback 为主，slow path 只证明 fallback 可用。
- 字段范围限于 HK.00001 主报表剩余核心字段。
- 每个未产出字段必须分类，避免把 omission 当作 absence。
