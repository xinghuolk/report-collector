# 财报分析 Turtle 有息负债输入 P2B 设计

> **Status:** Draft for implementation planning
> **Phase:** Turtle Investment Input Coverage - Phase 2B
> **Scope Type:** Narrow phase spec

## 1. 背景

`financial-report-analysis` 已完成：

- Phase 1 的 Turtle core investor inputs
- Phase 2A 的 working capital core

当前下一步最自然的推进方向，不是跳到 Phase 3，也不是提前做统一 Ollama closure，而是继续完成 Phase 2 中尚未覆盖的 debt inputs。

本轮聚焦 Turtle 最直接依赖、且最适合从资产负债表与受限附注补充路径稳定抽取的核心有息负债字段。

## 2. 目标

本轮目标是为 Turtle 投资框架建立稳定、可追溯、可验证的有息负债输入层，优先支持：

- 净负债口径
- EV / WACC 的基础负债输入
- 流动 / 非流动有息负债拆分

本轮不追求“覆盖所有负债相关字段”，而是先把最小可用的 debt input path 做稳。

## 3. 范围

### 3.1 本轮纳入的 4 个核心字段

- `st_borr`
- `lt_borr`
- `bond_payable`
- `non_cur_liab_due_1y`

### 3.2 本轮明确不纳入

- `defer_tax_assets`
- `defer_tax_liab`
- 租赁负债、可转债、衍生负债等扩展 debt family
- 母公司口径 debt
- 多年序列
- 净负债、EV、WACC 的派生计算
- debt summary row 的拆分推导

## 4. 样本锚点

本轮固定使用以下真实样本锚点：

### 4.1 CN 主锚点

- `report/downloads/cn_stocks/601919/annual/2025_年度报告.pdf`

用途：

- 验证中文资产负债表中的 deterministic statement-row debt path

### 4.2 HK statement-row 锚点

- `report/downloads/hk_stocks/02498/annual/2022_annual_en.pdf`

用途：

- 验证英文年报主表 debt rows 的 deterministic mapping

### 4.3 HK mixed-structure 锚点

- `report/downloads/hk_stocks/09987/annual/2025_annual_en.pdf`

用途：

- 验证另一类英文年报形态
- 当主表 debt 信息不充分时，允许走受限 note/disclosure supplement path

`09987` 不是公司特例样本，而是代表“主表不完整、附注补充更重要”的英文年报输入家族。

## 5. 架构定位

本轮继续沿用既有的结构化主路径：

`pdf -> parsed balance-sheet tables -> normalized table semantics -> debt metric mapping -> candidate facts -> canonical facts`

补充路径为：

`statement-row miss -> deterministic note/disclosure supplement -> gated semantic locator -> candidate facts`

边界如下：

- `statement-row path` 是默认主路径
- `deterministic note/disclosure supplement` 只补缺，不覆盖主表已稳定产出的事实
- Ollama semantic locator 只做语义定位，不直接生成数值事实或 canonical facts

## 6. 4 个字段的最小语义定义

### 6.1 `st_borr`

明确指短期借款 / short-term borrowings / short-term bank loans 等一年内到期且本身就是短期融资的有息负债。

### 6.2 `lt_borr`

明确指长期借款 / long-term borrowings / long-term bank loans，不包含一年内到期部分。

### 6.3 `bond_payable`

明确指应付债券 / bonds payable / corporate bonds / debt-financing notes。

### 6.4 `non_cur_liab_due_1y`

明确指一年内到期的非流动负债。只有在报表或附注中被独立披露时才允许产出。

### 6.5 统一口径原则

- 这 4 个字段都是“报表已独立披露口径”
- 本轮不做跨字段重算
- 不从总借款反推子项
- 不从 narrative 文本猜测拆分

## 7. Deterministic Mapping 规则

### 7.1 主表优先

只要主资产负债表中存在明确 debt row，应优先从该行构建 candidate facts。

### 7.2 附注只补缺

仅在以下情况允许使用 deterministic note/disclosure supplement：

- statement-row path 没有产出目标 debt metric
- 主表只有聚合 row，无法稳定映射到 4 个字段之一
- `09987 2025` 这类英文年报中，目标字段主要出现在附注 debt disclosure block

### 7.3 Source precedence

必须显式保持以下优先级：

- `statement_row`
- `deterministic_note_disclosure`
- `llm_locator_assisted_note_disclosure`

低优先级来源只能补缺，不能覆盖高优先级来源已存在的 debt fact。

## 8. Ollama Fallback 边界

本轮允许继续使用 gated semantic fallback，但必须维持受限边界。

### 8.1 可以做什么

- 判断某个 disclosure row 更像哪一个 debt metric
- 判断某个 row 是否属于 4 个目标字段之一
- 返回受限语义结果，如：
  - `metric_id`
  - `matched_label`
  - `source_text_span`
  - `semantic_source`
  - `semantic_confidence`
  - `fallback_reason`

### 8.2 不可以做什么

- 直接自由抽数
- 自由做单位传播
- 直接生成 canonical facts
- 因为样本复杂就把全文交给模型兜底

### 8.3 触发条件

只在以下情况允许触发 semantic locator：

- deterministic row mapping 结果是 `unknown`
- 同一 row 命中多个 debt metric 候选且无法稳定判别
- `09987` 类 note block 中存在明显 debt-like row，但 deterministic label family 仍无法归类

## 9. Negative Controls

以下语义本轮必须避免误吸：

- `lease liabilities`
- `accounts payable`
- `notes payable`
- `contract liabilities`
- `convertible preferred shares`
- `redeemable shares`
- `derivative liabilities`
- “总负债”“有息负债合计”“借款及其他负债”等 summary rows

特别约束：

- `current portion of long-term debt` 如果独立披露，应优先归到 `non_cur_liab_due_1y`
- 不能把它误吸成 `st_borr`

## 10. 验收标准

P2B 视为完成，仅当以下条件同时满足：

- 4 个 debt metrics 已进入 registry，并带有明确的 balance-sheet / point-in-time 语义
- `601919 2025` 能从 CN 资产负债表 deterministic 产出核心 debt candidate facts
- `02498 2022` 能从 HK statement-row path deterministic 产出核心 debt candidate facts
- `09987 2025` 在主表不充分时，可通过受限 note/disclosure supplement 补出真实存在的 debt facts
- `non_cur_liab_due_1y` 只有在独立披露时才产出
- negative controls 不被误吸成 4 个核心 debt metrics
- Ollama locator 仍是 bounded / gated / provenance-carrying 的补充能力
- 不破坏 P2A working capital、Phase 1 investor inputs 与现有高价值指标链路

## 11. 实现顺序建议

建议按以下顺序展开 implementation plan：

1. 先补 registry / deterministic row semantics
2. 再补 statement-row candidate coverage
3. 再补 `09987` note/disclosure supplement path
4. 最后再扩 bounded debt semantic locator
5. 收尾时做 focused verification，而不是默认跑全量 real-PDF / 全量 Ollama

## 12. 一句话收束

P2B 这轮只做“4 个核心有息负债字段的稳定输入层”，不做 debt 分析全家桶，也不提前进入递延税、母公司口径、派生净债务或多年序列。
