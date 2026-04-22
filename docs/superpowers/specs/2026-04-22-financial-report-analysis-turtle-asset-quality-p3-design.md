# 财报分析 Turtle 资产质量输入 P3 设计

> **Status:** Draft for implementation planning
> **Phase:** Turtle Investment Input Coverage - Phase 3
> **Scope Type:** Narrow phase spec

## 1. 背景

`financial-report-analysis` 已完成：

- Phase 1 的 Turtle core investor inputs
- Phase 2A 的 working capital core
- Phase 2B 的 debt inputs core

到当前为止，Turtle 路线已经把利润表、现金流量表和资产负债表中一批最关键的主路径输入打通，但还没有系统补齐“资产质量判断”所需的资产端字段。

本轮 P3 的目标不是泛化“更多资产字段”，而是先建立一条可被 Turtle 直接消费的资产质量输入层，并在此基础上受限引入少量 note-only 资产字段。

同时，本轮需要吸收新增文档 [new-report-sample-onboarding-and-field-variance-process.md](F:/source/git/report-collector/docs/architecture-analysis/new-report-sample-onboarding-and-field-variance-process.md) 的方法约束，避免新增样本时回到 issuer-specific 分支或样本补丁式开发。

## 2. 目标

本轮 P3 的目标是为 Turtle 的资产质量判断建立稳定、可追溯、可验证的输入层，优先支持：

- 现金储备质量判断
- 存货与营运资产质量判断
- 商誉/无形资产占比判断
- 主表缺口下的受限资产附注补充

本轮不追求一次性补齐所有资产端字段，也不提前进入 Phase 4 的母公司口径、受限资金、分红回购或资本化项目桥接。

## 3. 范围

### 3.1 本轮纳入的主字段

- `money_cap`
- `trad_asset`
- `inventories`
- `goodwill`
- `intang_assets`

### 3.2 本轮允许纳入的 note-only 补充字段

- `contract_assets`
- `other_non_current_assets`

这两个字段只允许作为“资产质量补洞”进入本轮，不得借机扩展为广义 notes bridge。

### 3.3 本轮明确不纳入

- 母公司口径资产字段
- 分红、回购、受限资金
- 资本化项目、资本化利息
- `assets_held_for_sale`
- 多年序列
- Phase 4 的 notes bridge 主题

## 4. 样本锚点

本轮固定使用以下真实样本锚点：

### 4.1 CN 主锚点

- `report/downloads/cn_stocks/601919/annual/2025_年度报告.pdf`

用途：

- 验证中文资产负债表的 deterministic statement-row path

### 4.2 HK statement-row 锚点

- `report/downloads/hk_stocks/02498/annual/2022_annual_en.pdf`

用途：

- 验证英文年报主表中的资产端字段 deterministic mapping

### 4.3 HK mixed-structure 锚点

- `report/downloads/hk_stocks/09987/annual/2025_annual_en.pdf`

用途：

- 验证主表不完整时，受限 note/disclosure supplement path 对资产字段的补充能力

`09987` 仍然不是公司特例，而是代表“主表不完整、附注补充更重要”的英文年报输入家族。

## 5. Onboarding 与失败归类前置章节

本轮 P3 必须显式吸收新增样本接入流程文档中的治理要求。

### 5.1 样本登记最小字段

每个新锚点或新增样本至少应记录：

- `sample_id`
- `market`
- `language`
- `issuer_code`
- `report_year`
- `report_type`
- `pdf_path`
- `expected_report_family`
- `target_phase`
- `target_metric_ids`
- `known_special_shape`

本轮 P3 不要求先引入数据库或新配置系统，但要求这些字段至少落在一个可审阅的文档化 artifact 中，而不是只留在临时终端记录里。

### 5.2 缺失状态

本轮至少区分：

- `present`
- `absent`
- `not_surfaced`
- `out_of_scope`

不得只通过 candidate omission 表达缺失。

对于 note-only 字段，缺失状态必须按“逐 metric、逐锚点”显式记录，而不是只写一个笼统结论。

### 5.3 失败归类

本轮新样本接入与修复时，必须优先按以下类型归类：

- `structure_recovery_gap`
- `semantic_normalization_gap`
- `metric_mapping_gap`
- `note_disclosure_supplement_gap`
- `absent`
- `not_surfaced`
- `out_of_scope`

归类的目的不是增加流程负担，而是约束修复顺序：

- 先修 structure / semantics
- 再修 mapping
- 最后才进入 note/disclosure supplement 或 gated locator

## 6. 架构边界

本轮继续沿用既有结构化主链路：

`pdf -> structure recovery -> normalized table semantics -> metric mapping registry -> candidate facts -> canonical facts`

补充链路为：

`statement_row miss -> deterministic note/disclosure supplement -> gated semantic locator -> candidate facts`

### 6.1 Source precedence

必须显式保持以下优先级：

1. `statement_row`
2. `deterministic_note_disclosure`
3. `llm_locator_assisted_note_disclosure`

低优先级来源只补缺，不覆盖高优先级已存在事实。

### 6.2 Deterministic-first

P3 仍必须遵守：

1. structure recovery
2. deterministic table semantics
3. metric mapping registry
4. deterministic note/disclosure supplement
5. gated semantic locator

不要把新样本资产端差异直接推给 LLM。

### 6.3 Note-only 补充边界

本轮 note-only 补充只允许服务：

- `contract_assets`
- `other_non_current_assets`

并且只在以下条件下允许进入：

- statement-row path 没有产出目标资产字段
- 存在明确 note/disclosure title 或受限 table context
- 字段属于真实独立披露，而不是 narrative 猜测或 summary row 推导

不允许在本轮顺手纳入：

- 受限资金
- 分红/回购
- 母公司资产
- 资本化项目
- 复杂公司行为型附注

## 7. 语义口径

### 7.1 主字段语义

- `money_cap`
  - 明确指货币资金 / cash and cash equivalents / cash and bank balances 等主表现金储备口径
- `trad_asset`
  - 明确指交易性金融资产 / trading assets / held-for-trading financial assets
- `inventories`
  - 明确指存货 / inventories
- `goodwill`
  - 明确指商誉 / goodwill
- `intang_assets`
  - 明确指无形资产 / intangible assets

### 7.2 note-only 字段语义

- `contract_assets`
  - 只在主表缺失、但附注明确独立披露时补充
- `other_non_current_assets`
  - 只在结构和上下文足够清晰、且附注明确为目标字段时补充

这两个字段在本轮 P3 中不是主表 statement-row 覆盖目标。它们不应被纳入“默认 balance-sheet 主路径字段集合”，也不应因为主表上出现相似标签就自动扩展为普通 statement-row 字段。

### 7.3 Negative controls

本轮至少避免以下误吸：

- `restricted cash`
- `assets held for sale`
- `investment properties`
- `prepayments`
- `deferred tax assets`
- `right-of-use assets`
- `capitalized development costs`
- `summary asset rows`

其中：

- `restricted cash` 属于 Phase 4/notes bridge 主题，不应在本轮偷偷纳入 `money_cap`
- `deferred tax assets` 仍属于 Phase 2/扩展 debt-and-tax 以外范围，不应顺带混入 P3

## 8. Ollama Fallback 边界

本轮允许保留 gated semantic locator，但仍不是默认主路径。

可以做：

- 判断某个 note/disclosure row 是否更像 `contract_assets` 或 `other_non_current_assets`
- 在受限资产附注块中做语义定位

不可以做：

- 全文自由抽数
- 直接生成 canonical facts
- 直接替代表结构恢复或 deterministic mapping

只有在 deterministic note/disclosure supplement 仍无法稳定分类时，才允许触发 locator。

## 9. 验收标准

P3 视为完成，仅当以下条件同时满足：

- `money_cap / trad_asset / inventories / goodwill / intang_assets` 已进入稳定主路径
- `601919 2025` 能从 CN 资产负债表 deterministic 产出核心资产质量字段
- `02498 2022` 能从 HK statement-row path deterministic 产出核心资产质量字段
- `09987 2025` 在主表不充分时，可通过受限 note/disclosure supplement 补出真实独立披露的 `contract_assets` 或 `other_non_current_assets`，如果该样本真实存在
- `present / absent / not_surfaced / out_of_scope` 状态清楚
- note/disclosure path 只补缺，不覆盖 statement-row fact
- negative controls 不被误吸
- 不破坏 Phase 1、P2A、P2B 与既有 API-visible 链路

## 10. 建议实现顺序

建议按以下顺序展开 implementation plan：

1. 先补 5 个主字段的 deterministic statement-row path
2. 再补 `contract_assets / other_non_current_assets` 的受限 note/disclosure path
3. 最后才评估是否真的需要 bounded locator
4. 收尾时按 onboarding 文档的失败归类与缺失状态做 focused verification

## 11. 一句话收束

P3 这轮只做“资产质量第一批字段 + 少量 note-only 资产补充”的稳定输入层，不提前进入 Phase 4 的 notes bridge 或母公司口径主题。
