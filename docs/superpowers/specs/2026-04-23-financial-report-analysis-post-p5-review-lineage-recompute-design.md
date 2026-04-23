# 财报分析 Post-P5 Review、Lineage 与 Deterministic Recompute 设计

> **状态:** Draft for review
> **日期:** 2026-04-23
> **阶段:** Post-P5 Foundation
> **范围类型:** 基础设施阶段设计

## 1. 背景

截至当前分支状态，`financial-report-analysis` 已完成并收口：

- P1 `Core Investor Inputs`
- P2A `Working Capital Inputs`
- P2B `Debt Inputs`
- P3 `Asset Quality Inputs`
- P4A `Parent Scope / Notes Conflict Governance`
- P4B `Cash-Health Notes Bridge`
- P4C `Investor Core Statement Gaps`
- P4D `Parent Scope And Notes Follow-up`
- P4E `Investor Earnings Quality And Capex Follow-up`
- P5 `Multi-Year Investor Dataset And Minimal Persistence`

这意味着项目已经具备：

- 单份 PDF 的 extracted artifact
- 多年 dataset artifact
- Turtle-facing export artifact
- 基于 JSON repository 的最小持久化

但当前仍缺一层 post-P5 基础设施：

- 如何审阅当前 artifact 是否可信
- 如何回答某条 dataset row 来自哪份 PDF、哪版 pipeline、哪组 extracted artifacts
- 当 manifest / pipeline / contract 变化后，如何稳定重算目标 artifact
- 如何在未来接入更强的 review 能力，而不把主链路重新变成不可控的黑盒

因此，本阶段不再继续扩字段，而是转向：

**review surface + artifact lineage + deterministic recompute contract**

## 2. 目标

本阶段目标是为现有 P5 产物补齐一层可审、可追、可重算的基础设施。

具体包括：

1. 为 extracted artifact、dataset artifact、Turtle export 定义稳定的 review surface
2. 为 artifact 之间的来源关系定义清晰的 lineage contract
3. 为重算建立 deterministic contract，而不是临时脚本式重跑
4. 保持当前 JSON repository 可继续承担第一版实现
5. 为未来的 whole-document LLM assessment 预留扩展挂点，但不让它进入当前主逻辑

一句话收束：

> 这轮不是为了“多存一些东西”，而是为了让当前已有结果真正变成可审计、可追溯、可重算的正式资产。

## 3. 非目标

本阶段不包含：

- 新的 Turtle coverage phase
- 新的主表或附注字段扩张
- 广义数据库重构
- 公共 HTTP API 设计与实现
- LLM 直接参与 recompute 决策
- LLM 直接改写 canonical facts
- 把整份 PDF 的自由抽取重新变成第二套主抽取系统

## 4. 架构定位

Post-P5 基础设施应建立在当前 artifact 链条之上：

```text
manifest
-> extracted artifacts
-> dataset artifact
-> turtle export
```

本阶段新增的不是另一条抽取链，而是围绕这条链补以下能力：

```text
review surface
-> lineage surface
-> recompute contract
```

默认顺序应为：

1. 先把当前 artifact 变成可 review 的对象
2. 再把 artifact 之间的依赖关系明确表达出来
3. 再让 recompute 成为一个明确 contract，而不是“重新跑一遍脚本”

## 5. Review Surface

### 5.1 Review 关注对象

本阶段应把以下对象视为可 review 单元：

- 单份 `P5ExtractedArtifact`
- 单份 `P5DatasetArtifact`
- 单份 `P5TurtleExport`

### 5.2 Review surface 的最小内容

每个 review surface 至少应暴露：

- artifact identity
- artifact version
- pipeline version
- source PDF / manifest entry / dataset source artifacts
- quality gate / validation / missing status 摘要
- review-required signals
- duplicate conflicts / scope mismatch / missing summary

### 5.3 Review surface 的边界

Review surface 的职责是：

- 让人或 agent 能看清当前 artifact 是否值得信任
- 让后续 recompute / diff / approval 有稳定输入

它不负责：

- 重新抽取 facts
- 自动裁决 canonical truth
- 直接提供面向外部用户的公共 API

## 6. Lineage Contract

### 6.1 需要回答的问题

lineage contract 至少要能回答：

- 这条 dataset row 来自哪个 `source_artifact_id`
- 对应哪份 `source_pdf_path`
- 对应哪版 `pipeline_version`
- 由哪个 manifest entry 引入
- 由哪个 dataset artifact 组装出来

### 6.2 最小 lineage 单元

本阶段先不追求复杂 graph 存储，而是定义清晰的逻辑链：

`manifest entry -> extracted artifact -> dataset row -> turtle export row`

每一级都应能向上追溯：

- manifest identity
- artifact identity
- source fact identity
- evidence bundle identity（若存在）

### 6.3 Lineage 的用途

lineage 不是装饰字段。它直接服务：

- review
- recompute target selection
- diff reporting
- 未来 storage / query / audit 扩展

## 7. Deterministic Recompute Contract

### 7.1 核心原则

recompute 必须保持 deterministic-first。

重算的结果应由以下输入唯一决定：

- manifest
- source PDF 集合
- extracted artifact contract
- dataset assembly rules
- Turtle export rules
- artifact / pipeline / dataset version

### 7.2 本阶段的 recompute 关注点

本阶段不要求完整调度平台，而是先明确：

- 重算的输入对象
- 重算的输出对象
- 重算前后如何比较版本与差异
- 哪些变化应触发 extracted 重算
- 哪些变化只需 dataset / export 重组

### 7.3 典型触发条件

应至少区分：

- manifest 改变
- source PDF 改变
- extracted artifact contract 改变
- pipeline version 改变
- dataset assembly contract 改变
- export alias / export shape 改变

### 7.4 本阶段不做

本阶段不做：

- 复杂任务编排器
- 分布式调度
- 自动裁决哪次重算“更真”

## 8. Storage 边界

本阶段默认继续建立在 JSON artifact repository 之上。

理由是：

- 当前主要缺口是 review / lineage / recompute contract，不是存储技术选型
- 现有 JSON artifact 已经足够支撑第一版最小闭环
- 提前抽象数据库层容易产生暂时无人消费的空接口

因此默认策略是：

- 先在当前 repository 之上补 review / lineage / recompute 结构
- 只有当 query / audit / concurrency / durability 需求形成稳定压力后，再推进更重的 storage abstraction

## 9. 与 LLM 的关系

### 9.1 当前阶段立场

LLM 不进入当前 deterministic recompute 主逻辑。

它不能：

- 直接决定 recompute 是否正确
- 直接修改 canonical facts
- 成为第二套事实来源

### 9.2 允许的 future extension

未来可以在本阶段之上扩展：

`whole-document LLM assessment`

它的合理定位是：

- 读整份 PDF
- 形成受限的 assessment / comparison artifact
- 与系统 extracted/dataset artifact 做 diff
- 辅助 review、差异摘要与优先级判断

### 9.3 边界声明

这种 LLM 能力只能是：

- review assist
- diff summary
- coverage gap hint

不能是：

- recompute authority
- canonical truth source

## 10. 推荐切分

本阶段建议拆成三个连续子目标：

### 10.1 Review-first

先补可审阅 surface，让现有 artifact 真正可读、可检查、可摘要。

### 10.2 Lineage-next

再补 artifact 间追溯关系，让 dataset 与 export 不再只是孤立 JSON。

### 10.3 Recompute-last

最后建立 deterministic recompute contract，明确哪些变更触发哪一层重算。

## 11. Definition Of Done

本阶段完成时，应满足：

- current extracted / dataset / export artifacts 都有稳定 review surface
- dataset row 可追溯到 extracted artifact 与 source PDF
- 变更类型与 recompute 目标之间有清晰 deterministic contract
- 当前 JSON repository 足以支撑第一版 review / lineage / recompute
- future whole-document LLM assessment 已被写成明确扩展方向，但不阻塞当前阶段

## 12. 一句话结论

Post-P5 的下一步不该继续补字段，而应先把：

**review、lineage、deterministic recompute**

做成正式基础设施；只有这样，后续字段扩展、query surface、storage 升级和 LLM 对照评估才有稳定落点。
