# 财报分析 Turtle P2A 营运资本核心字段设计

## 1. 目标

本设计定义 Turtle 投资输入覆盖路线的 Phase 2A。

Phase 2A 的目标不是一次性补齐所有营运资本、债务和递延税字段，而是先把最常用、最适合由资产负债表或明确附注明细支撑的营运资本核心字段打通。

本阶段应交付一个可被 Turtle 下游消费的最小营运资本输入层，用于支持：

- 真实现金收入还原的基础输入
- 经营性负债和应收质量观察
- 后续 debt / deferred tax / parent-scope 阶段的稳定前置语义

## 2. 战略定位

Phase 2A 面向更广泛的 CN/HK 年报家族，但不承诺当前阶段通吃所有财报格式。

本阶段要覆盖两类 HK 英文年报形态：

- 标准 statement-row path：目标字段直接出现在资产负债表主表行中。
- note/disclosure supplement path：目标字段不完整出现在主表中，需要从附注明细表补充。

后续新增样本时，应优先扩展：

- table structure recovery
- normalized table semantics
- metric mapping registry
- gated semantic locator

不应通过 issuer-specific extraction branches 为单家公司硬写分支。

## 3. 字段范围

本阶段只覆盖 7 个营运资本字段：

- `accounts_receiv`
- `notes_receiv`
- `oth_receiv`
- `contract_liab`
- `adv_receipts`
- `acct_payable`
- `notes_payable`

这些字段的默认语义为：

- statement type: `balance_sheet`
- value shape: `point_in_time`
- value type: `amount`
- unit expectation: `currency_amount`
- preferred scope: consolidated statement

## 4. 明确不做

本阶段不纳入：

- `contract_assets`
- `st_borr`
- `lt_borr`
- `bond_payable`
- `non_cur_liab_due_1y`
- `defer_tax_assets`
- `defer_tax_liab`
- 母公司口径资产负债表
- 账龄、坏账准备、信用损失等附注深挖
- 从合并大项中自由推断未独立披露字段
- 让 LLM 直接生成 canonical facts

Debt 和 deferred tax 应进入 P2B，不与 P2A 混做。

## 5. 样本锚点

### 5.1 CN Anchor

主锚点：

- `report/downloads/cn_stocks/601919/annual/2025_年度报告.pdf`

参考样本：

- `report/downloads/cn_stocks/600519/annual/2024_年度报告.pdf`
- `report/downloads/cn_stocks/688008/annual/2025_年度报告.pdf`

CN 样本用于验证中文标准资产负债表行，例如：

- `应收票据`
- `应收账款`
- `其他应收款`
- `合同负债`
- `预收款项`
- `应付账款`
- `应付票据`

### 5.2 HK Anchor A: Statement Row Path

主锚点：

- `report/downloads/hk_stocks/02498/annual/2022_annual_en.pdf`

该样本用于验证英文主表逐行路径，例如：

- `Notes receivable`
- `Accounts receivable`
- `Other receivables`
- `Notes payable`
- `Accounts payable`
- `Payments received in advance`
- `Contract liabilities`

### 5.3 HK Anchor B: Note / Disclosure Supplement Path

主锚点：

- `report/downloads/hk_stocks/09987/annual/2025_annual_en.pdf`

该样本用于验证英文 note/disclosure 补充路径。当前已观察到的相关披露包括：

- `Accounts receivable, net`
- `Accounts Payable and Other Current Liabilities`
- `Accounts payable`
- `Contract liabilities`

该样本不应被强制要求产出没有独立披露的字段。如果 `notes_receiv` 或 `notes_payable` 没有可追踪的独立来源，应输出 absent / not surfaced，而不是推断近似值。

## 6. 主数据流

P2A 的目标链路为：

`pdf -> structure recovery -> normalized table semantics -> metric mapping registry -> candidate facts -> canonical facts -> API`

对于 HK note/disclosure path，允许增加一个补充定位层：

`structured table path -> note/disclosure table path -> gated semantic locator -> candidate facts -> canonical resolver`

其中：

- structure recovery 负责恢复表格、行、列、单位、币种和局部上下文。
- normalized table semantics 负责将表结构转成稳定的 row/column/table 语义。
- metric mapping registry 负责把稳定语义映射到标准 metric id。
- candidate/canonical resolver 继续负责事实裁决、冲突处理和最终输出。
- semantic locator 只在结构化路径缺失或语义不确定时辅助定位，不替代解析、映射和裁决。

### 6.1 Source Precedence

P2A 的事实来源优先级必须固定，不允许依赖当前 resolver 的隐式启发式偶然决定。

优先级为：

1. primary statement-row path
2. deterministic note/disclosure row path
3. Ollama-assisted note/disclosure locator path

note/disclosure path 只补充当前文档中尚未由 statement-row path 产出的 P2A metric，不覆盖已有 statement-row fact。

Ollama-assisted locator 只补充当前文档中尚未由 deterministic path 产出的 P2A metric，不覆盖 deterministic note/disclosure fact。

如果未来需要让 note fact 覆盖 statement fact，必须进入单独的 conflict-governance 任务，本阶段不做。

## 7. Ollama Semantic Locator 边界

本阶段允许使用 Ollama fallback，但只作为 gated semantic locator。

允许它做：

- 判断一段 note/table 是否可能对应目标字段。
- 在结构化路径未找到时，定位候选页、候选标题或候选行。
- 返回受限 JSON：
  - `metric_id`
  - `matched_label`
  - `source_text_span`
  - `confidence`
  - `reason`
  - `fallback_reason`

不允许它做：

- 直接从全文自由抽取最终数值。
- 自由换算单位或币种。
- 推断没有独立披露的字段。
- 直接生成 canonical facts。
- 绕过 candidate/canonical resolver。

Ollama 的输出必须带 provenance，例如：

- `semantic_source = "ollama_fallback"`
- `fallback_reason = "missing_statement_row"` 或 `ambiguous_note_label`
- `semantic_confidence`

默认执行策略仍然是 deterministic-first。Ollama 只在明确触发条件下运行，不是默认主路径。

Ollama locator 的触发条件必须同时满足：

- 当前文档是 HK 英文年报。
- deterministic statement-row path 和 deterministic note/disclosure path 都没有产出该目标 metric。
- 当前文本块位于明确的 note/disclosure 标题或表格上下文中，例如 `Accounts Payable and Other Current Liabilities`、`Accounts Receivable, net` 或 `Contract Liabilities`。
- 当前文本块包含可解析的局部行或表格片段，而不是 MD&A、risk factors、普通叙述段落或全文搜索命中。

禁止仅凭 `accounts receivable`、`contract liabilities` 等泛词在全文中触发 locator。

每个文档必须有 disclosure-locator 调用预算。默认预算应很小，例如 3 次。明确写成配置语义时，应等价于 `default budget: 3 calls per document`。预算耗尽后必须继续使用 deterministic 结果，而不是继续调用 Ollama。

## 8. 缺失字段语义

本阶段需要显式区分三种状态：

- `present`: 样本中存在可追踪来源，且进入 candidate/canonical。
- `absent`: 样本中明确没有独立披露。
- `not_surfaced`: 当前结构或语义层尚未能稳定恢复，不能当作字段不存在。

这一区分对 `09987 2025` 尤其重要。它不能为了凑齐 7 个字段而 hallucinate，也不能把结构层未恢复误报成业务字段不存在。

缺失状态应进入可测试 metadata，而不是只通过 candidate omission 表达。推荐字段为：

- `document_metadata["working_capital_missing_status"]`

其值为 `metric_id -> status` 映射，例如：

- `notes_receiv: "absent"`
- `notes_payable: "absent"`
- `adv_receipts: "not_surfaced"`

## 9. 验收标准

### 9.1 Candidate 层

在支持样本中，真实存在且有可追踪来源的 7 个字段应进入 `candidate_facts`。

最低要求：

- CN `601919 2025` 能覆盖中文标准行路径。
- HK `02498 2022` 能覆盖英文 statement-row path。
- HK `09987 2025` 能覆盖 note/disclosure path 中明确披露的字段。

### 9.2 Canonical 层

对于来源明确、statement scope 清晰、period/value shape 正确的字段，应进入 canonical/key-fact 输出。

本阶段不要求每个样本都输出全部 7 个字段。验收应按样本真实披露情况判断。

### 9.3 Negative Controls

本阶段必须避免以下误映射：

- `accounts receivable financing` 不应映射为 `accounts_receiv`。
- `long-term receivables` 不应映射为 `accounts_receiv` 或 `oth_receiv`。
- `employee compensation payable` 不应映射为 `acct_payable`。
- `taxes payable` 不应映射为 `acct_payable`。
- `bonds payable` 不应映射为 `notes_payable`。
- cash-flow adjustment rows such as `Changes in accounts receivable` 不应映射为 balance-sheet point-in-time facts。

### 9.4 Real PDF 回归

真实 PDF 回归应分层运行：

- 默认收口测试优先使用 deterministic real-PDF subset。
- Ollama 测试单独标记，并限制调用预算。
- 不应默认跑全量 real-PDF + Ollama 矩阵。

对于 `09987 2025`，应至少验证：

- 能定位 `Accounts receivable, net`。
- 能定位 `Accounts payable`。
- 能定位 `Contract liabilities`。
- 不能把未独立披露的 `notes_receiv` / `notes_payable` 编造成事实。

## 10. 实现边界建议

后续 implementation plan 应拆成两段：

### Phase A: Deterministic Working-Capital Path

目标：

- 扩展 registry 和 deterministic label normalization。
- 支持 CN 和 HK statement-row path。
- 添加 negative controls。
- 让 `601919 2025` 和 `02498 2022` 形成稳定候选事实。

### Phase B: HK Note / Disclosure Supplement Path

目标：

- 支持 `09987 2025` 的 note/disclosure 定位。
- 接入 gated semantic locator。
- 保持数值抽取和 canonical 裁决仍由结构化链路负责。
- 明确 absent / not_surfaced 状态。

Phase A 和 Phase B 都属于 P2A，但应在实现计划中分开验收，避免把 note path 的难度污染到标准 statement-row path。

## 11. 完成定义

P2A 视为完成，当：

- 7 个营运资本字段在 registry / normalization / fact builder 中有明确语义。
- CN `601919 2025` 的标准资产负债表路径稳定。
- HK `02498 2022` 的英文 statement-row path 稳定。
- HK `09987 2025` 的 note/disclosure path 能产出真实存在字段，且不 hallucinate 缺失字段。
- Ollama 只作为 gated semantic locator 使用，并带 provenance。
- 现有 Phase 1 Turtle investor inputs 和三大表高价值指标不回退。
