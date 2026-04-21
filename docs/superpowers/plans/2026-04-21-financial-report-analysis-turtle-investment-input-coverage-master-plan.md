# 财报分析面向 Turtle 投资输入覆盖计划总纲

> **For agentic workers:** This is a master plan. Do not implement the whole document at once. Expand one phase into a dedicated spec and implementation plan before coding.

**Goal:** 把 `financial-report-analysis` 从“面向三大表高价值指标的抽取底座”，逐步推进为“可为 Turtle 投资框架稳定提供财报输入数据”的分析数据底座。

**Positioning:** 本总纲不是一个直接执行到底的大 implementation plan，而是一个阶段化路线图。每个 phase 完成后，都应先收口，再决定是否进入下一 phase。默认不并行推进多个高风险 phase。

**Primary Downstream Consumer:** `/Users/keli/source/Turtle_investment_framework/docs/龟龟投资_穿透回报与估值分析_财报取数清单.md`

**Planning Principle:** 先补 Turtle 最核心、最常用、最可由主表稳定提取的字段，再逐步进入营运资本细项、债务结构、母公司口径、附注桥接和多年序列一致性。不要一开始就把附注、公司行为和多口径时序揉成一个 phase。

---

## 1. 为什么需要这份总纲

当前 `financial-report-analysis` 已经具备：

- 三大主表结构恢复
- deterministic normalization + bounded fallback
- candidate -> canonical -> API 主链路
- 一小组高价值指标的稳定抽取

但对于 Turtle 投资框架来说，当前覆盖仍然明显不足。

Turtle 的核心计算不仅依赖：

- 营收
- 净利润
- 经营现金流
- 现金
- 总资产/总负债/权益

还依赖大量更细的分析型字段，例如：

- 归母净利润
- EPS
- 财务费用
- 所得税费用
- 借款类负债
- 资本开支
- 折旧摊销
- 应收/预收/应付细项
- 已付股息
- 母公司现金
- 分红方案与受限资金等附注信息

因此，下一步不应只沿着“三大表高价值指标”继续扩一点点，而应形成一条面向 Turtle 输入覆盖的独立路线。

---

## 2. 总体目标

本总纲的最终目标不是“抽到更多字段”，而是逐步达到以下状态：

1. 能稳定提供 Turtle 最核心的财报主表输入
2. 能支持 Turtle 的现金质量、资本配置、债务与分配能力分析
3. 能逐步桥接母公司口径与附注中的关键补充信息
4. 能输出 3-5 年可计算、可校验、可追溯的投资分析输入数据集

---

## 3. 范围边界

### 3.1 本路线纳入范围

- 三大主表中的 Turtle 核心分析字段
- 母公司资产负债表中的关键上游限制字段
- 与分红、回购、受限资金、资本化项目有关的高价值附注桥接
- 面向 Turtle 的多年序列数据一致性与导出 schema

### 3.2 本路线暂不纳入范围

- 一次性覆盖 Tushare 全量字段字典
- 非财报类公告的广泛抽取
- 行情/市值/PE/PB/无风险利率等外部市场数据接入
- 复杂 note-table 全量结构化解析
- 所有公司行为事件的一次性自动化穿透

---

## 4. 分阶段路线

本路线建议拆为五个 phase。

## Phase 1：Core Investor Inputs

**目标：** 先补齐 Turtle 最核心、最常被直接消费、最适合由主表稳定抽取的输入字段。

**建议优先字段**

- 利润表：
  - `n_income_attr_p`
  - `basic_eps`
  - `finance_exp`
  - `total_profit`
  - `income_tax`
  - `minority_gain`
- 现金流量表：
  - `c_pay_acq_const_fiolta`
  - `depr_fa_coga_dpba`
  - `amort_intang_assets`
  - `lt_amort_deferred_exp`
  - `c_pay_dist_dpcp_int_exp`

**直接支撑的 Turtle 计算**

- Owner Earnings
- D&A / Capex 基线
- EPS / 股利支付率交叉校验
- DCF 的最小可用输入

**收口标准**

- Turtle 最关键的一组主表输入能在主样本上稳定提取
- 不破坏当前三大表高价值指标链路
- candidate / canonical / API contract 保持稳定

---

## Phase 2：Working Capital And Debt Inputs

**目标：** 补齐真实现金收入、经营现金支出、债务结构和 WACC/EV 相关的营运资本与有息负债字段。

**建议优先字段**

- 资产负债表：
  - `accounts_receiv`
  - `notes_receiv`
  - `oth_receiv`
  - `contract_liab`
  - `adv_receipts`
  - `acct_payable`
  - `notes_payable`
  - `st_borr`
  - `lt_borr`
  - `bond_payable`
  - `non_cur_liab_due_1y`
  - `defer_tax_assets`
  - `defer_tax_liab`

**直接支撑的 Turtle 计算**

- 真实现金收入还原
- 经营性现金支出还原
- WACC / EV / 净负债口径估值

**收口标准**

- 现金收入和债务相关的核心字段可稳定形成同口径输入
- 不把非主表、摘要表和附注零散数据误吸成主口径事实

---

## Phase 3：Asset Quality And Capital Allocation Inputs

**目标：** 补齐资产质量、资本配置与资本开支去伪分析所需的资产端字段。

**建议优先字段**

- `money_cap`
- `trad_asset`
- `inventories`
- `lt_eqt_invest`
- `fix_assets`
- `intang_assets`
- `goodwill`
- `cip`
- `minority_int`

**直接支撑的 Turtle 计算**

- 现金储备质量
- 商誉/总资产
- 资本开支质量
- 对外投资与内生投入区分

**收口标准**

- 资产质量与资本配置的关键字段可稳定输出
- `cash` 等泛化口径逐步细化为 Turtle 可消费口径

---

## Phase 4：Parent Scope And Notes Bridge

**目标：** 开始进入 Turtle 分析真正拉开差距的部分，即母公司口径和高价值附注桥接。

**建议优先范围**

- 母公司资产负债表关键字段：
  - 母公司 `money_cap`
  - 母公司 `lt_eqt_invest`
  - 母公司借款类负债
  - 母公司总资产、总负债、权益
- 附注桥接：
  - DPS / 分红方案
  - 回购/注销
  - 受限资金
  - 定存/理财/高流动性金融资产
  - 投资收益拆分
  - 资产处置收益拆分
  - 资本化研发
  - 资本化利息
  - 子公司现金归集限制

**直接支撑的 Turtle 计算**

- 分配能力与上游障碍判断
- DDM / 支付率分析
- 现金质量增强版
- 非经常性现金流入识别

**收口标准**

- 至少能桥接 Turtle 最高频使用的少数几类附注信息
- 母公司口径与合并口径不混淆

---

## Phase 5：Multi-Year Investor Dataset

**目标：** 从“能抽单年字段”升级到“能为 Turtle 输出多年、可计算、可校验的数据集”。

**建议交付物**

- 3-5 年三大表关键字段序列
- 母公司资产负债表 3-5 年关键字段序列
- 关键附注桥接字段序列
- 面向 Turtle 的导出 schema
- 质量标记与缺失标记

**直接支撑的 Turtle 计算**

- 5 年营收 CAGR
- 5 年净利润 CAGR
- 5 年平均 ROE
- 3 年平均支付率
- 多年 DCF / 反向估值 / FCF Yield

**收口标准**

- 能稳定产出 Turtle 可消费的多年输入数据集
- 时点值 / 期间值 / 合并 / 母公司口径保持一致

---

## 5. 默认执行顺序

建议严格按以下顺序推进：

1. Phase 1：Core Investor Inputs
2. Phase 2：Working Capital And Debt Inputs
3. Phase 3：Asset Quality And Capital Allocation Inputs
4. Phase 4：Parent Scope And Notes Bridge
5. Phase 5：Multi-Year Investor Dataset
6. Post-Phase Closure：Ollama Semantic Fallback Coverage Closure

原因：

- Phase 1 与当前项目距离最近，收益最大、风险最低
- Phase 2/3 仍主要依赖三大主表，可沿用现有抽取架构
- Phase 4 开始才进入高歧义的母公司/附注桥接
- Phase 5 应建立在前四阶段字段口径已经基本稳定的前提下
- Ollama fallback coverage 应在 Turtle 主字段口径稳定后统一收口，避免每个字段阶段都被动扩 prompt、allowed outputs 和 probe 阈值

---

## 5.1 Post-Phase Closure：Ollama Semantic Fallback Coverage Closure

本总纲完成后，应单独安排一轮 Ollama semantic fallback coverage 收口，而不是把它塞进任一单个字段 phase 的完成条件。

这轮 closure 的目标是统一评估：

- 哪些 Turtle 字段仍只应由 deterministic registry / normalization 支撑
- 哪些字段需要进入 Ollama row-label fallback 的 supported outputs
- 哪些真实财报 label family 需要加入 promoted probe
- 当前 prompt、accuracy threshold、fallback budget 是否仍适合扩展后的 Turtle 字段集合

至少应覆盖：

- Phase 1 的 investor inputs，如 `basic_eps`、`finance_exp`、`total_profit`、`income_tax`、`minority_gain`、Capex、D&A、已付股息现金流
- Phase 2/3 中最终确认需要 fallback 辅助的 working-capital、debt、asset-quality 字段
- 明确 negative controls，如 adjusted EPS、non-GAAP EPS、growth、margin、ratio、summary rows、secondary management rows

边界：

- 这不是回到 LLM 主抽取路径
- 不要求 Ollama 直接产出 canonical facts
- 不替代 structure recovery、deterministic normalization、registry、candidate/canonical resolution
- 只做 gated semantic fallback 的覆盖、准确率和性能收口

---

## 6. 推荐文档策略

本总纲之后，不建议一次性把五个 phase 的子 spec 全部写完。

建议流程：

1. 先完成本 master plan
2. 先写 **Phase 1 的子 spec**
3. 再写 **Phase 1 的 implementation plan**
4. Phase 1 实现并收口后，再决定是否进入 Phase 2

这样做的原因是：

- Turtle 所需字段很多，但当前底座对不同字段类型的适配难度差异很大
- 过早把附注桥接和多年序列细节写死，会增加返工概率
- Phase 1 的结果会影响后续字段命名、registry 设计和导出 schema

---

## 7. 一句话收口标准

本总纲本身视为完成，当以下条件满足时：

- 路线分期清晰
- 每个 phase 的目标、边界、优先字段、收口标准明确
- 后续可以直接从 Phase 1 展开子 spec 和 implementation plan

本总纲不要求立即开始编码，但要求后续阶段能够顺着它稳定推进。
