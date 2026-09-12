# 财报分析 Durable Storage 与历年入库前置阶段 Brainstorming

> **状态:** Brainstorming draft
> **日期:** 2026-04-23
> **阶段:** Post-P5 Foundation Follow-up
> **范围类型:** 数据库重构前置条件与系统能力边界

## 1. 目的

这份文档用来回答两个紧密相关的问题：

1. 在 `financial-report-analysis` 进入数据库重构之前，`review / lineage / recompute` 这一层到底要先补到什么程度？
2. 数据库重构阶段除了“承接这些 contract”，还需要新增哪些系统级能力？

当前项目已经有：

- extracted artifact
- dataset artifact
- Turtle export
- JSON repository

但如果直接进入数据库重构，风险是把还没稳定的 contract 一起固化进 schema，后面又要边改业务边改持久化。

因此这份 brainstorming 的目标不是直接设计数据库表，而是先定义：

- 哪些 contract 必须先稳定
- 哪些能力只要“够数据库承接”就可以
- 哪些增强项不该阻塞 durable storage 阶段
- 数据库阶段本身要解决哪些 JSON repository 难以继续承担的系统问题

## 2. 背景判断

截至当前阶段，P5 和 post-P5 已经证明：

- 多年 dataset 的最小持久化是可行的
- review surface 已经有最小可用版本
- lineage 已经不是空白
- recompute 已经从“重跑脚本”演进成有 target-selection / diff summary 的 contract

但这还不等于已经适合立刻做数据库重构。

数据库阶段真正需要的不是“功能初步可跑”，而是：

- 上层对象边界清楚
- 关键 identity 清楚
- review / lineage / recompute 的输入输出 shape 足够稳定

## 3. 一句话结论

数据库重构不应作为 `review / lineage / recompute` 的替代品，而应作为它们的承接层，同时补齐当前 JSON 方案难以继续支撑的系统能力。

更准确的顺序应是：

```text
P5 minimal persistence
-> post-P5 review surface
-> post-P5 lineage contract
-> post-P5 deterministic recompute contract
-> durable storage and historical-ingestion foundation
-> whole-document LLM assessment extension
```

这里的 durable storage 阶段不只是“把 JSON 改成数据库”，还应同时承接：

- 历年 annual report 入库
- issuer / fiscal year / report registry
- artifact 持久化与可查询化
- recompute / review / audit 的 durable basis

## 4. 本阶段要先稳定什么

### 4.1 Review Surface Contract

进入数据库阶段前，至少要稳定：

- extracted review surface 的 identity / version / provenance / review-required signals
- dataset review surface 的 source artifacts / quality summary / conflict summary
- Turtle export review surface 的 source linkage / missing summary / review-required summary

这里的关键不是“字段越多越好”，而是：

- review object 的 identity 是稳定的
- review object 的来源可以追溯
- review object 的 summary 结构不会频繁重写

### 4.2 Lineage Contract

数据库阶段前，至少要稳定：

- manifest entry -> extracted artifact
- extracted artifact -> dataset row
- dataset row -> turtle export row

以及每一层最少需要的 identity：

- manifest identity
- artifact identity
- source fact identity
- evidence bundle identity
- dataset / export row linkage

如果这些 identity 还在频繁改名或改语义，数据库 schema 也会不稳定。

### 4.3 Deterministic Recompute Contract

数据库阶段前，至少要稳定：

- recompute plan 的 target-selection 规则
- change reason -> rebuild target 的 deterministic mapping
- diff summary 的最小 shape
- 只重组 dataset/export 和重建 extracted artifacts 的边界

数据库阶段不应负责“发明 recompute 规则”，而应复用这层 contract。

## 5. 什么叫“足够进入数据库阶段”

我会把进入 durable storage 阶段的门槛定义成：

### 5.1 Contract Gate

以下对象已经有稳定 shape：

- `P5ExtractedArtifact`
- `P5DatasetArtifact`
- `P5TurtleExport`
- extracted / dataset / export review surfaces
- lineage records
- recompute plan / recompute result / diff summary

### 5.2 Behavior Gate

以下行为已经能稳定验证：

- review surface 不依赖临时日志输出
- lineage 查询不依赖 ad-hoc 解析 JSON 内容
- recompute 的 target-selection 不是“默认全量重跑”
- diff summary 不会被 `created_at` 这类波动字段污染

### 5.3 Persistence Boundary Gate

已经能回答：

- 哪些对象应持久化为一等实体
- 哪些对象只是派生 surface
- 哪些对象可以在数据库中做物化，哪些只需按需生成

## 6. 数据库阶段不该先做什么

进入 durable storage 之前，不建议先做：

- 把 JSON repository 全面替换成数据库实现，但上层 contract 仍在频繁变化
- 提前设计大量 query API，而 review / lineage / recompute 语义还不稳定
- 把 LLM assessment 一起塞进数据库阶段
- 为了数据库表设计去回推业务对象命名

## 7. 推荐的数据库阶段承接对象与系统能力

如果下一阶段开始 durable storage，我建议优先承接这些对象：

### 7.1 第一层：核心 artifact

- manifest records
- extracted artifacts
- dataset artifacts
- turtle export artifacts

### 7.2 历年入库与报告组织

- issuer registry
- report registry
- fiscal year / report type / source tracking
- 入库状态、解析状态、重算状态
- manifest 与 report registry 的关系

### 7.3 第二层：review / lineage / recompute

- extracted review surfaces
- dataset review surfaces
- turtle export review surfaces
- lineage links
- recompute plans
- recompute results
- diff summaries

### 7.4 第三层：后续再扩

- query indexes
- audit trails
- durable review decisions
- approval / suppression workflow

## 8. 与 LLM 的关系

这份前置阶段 brainstorming 里，`LLM whole-document assessment` 仍然明确后置。

理由很简单：

- 它不是数据库阶段的前置条件
- 它不是 recompute authority
- 它更像建立在 durable storage 之上的 review assist 扩展

因此，数据库阶段最多只需要给未来的 assessment artifact 预留挂点，不应先做整套 LLM 插件化接口。

## 9. 推荐切分

如果把这条线拆阶段，我会建议：

### 9.1 阶段 A：Post-P5 Foundation Closeout

目标：

- 把 `review / lineage / recompute` 补到数据库可承接状态
- 继续使用 JSON repository
- 不直接改底层 storage

### 9.2 阶段 B：Durable Storage And Historical Ingestion Foundation

目标：

- 引入数据库 repository
- 保持上层 artifact / review / lineage / recompute contract 不变
- 把 issuer / report / fiscal year / artifact 组织进 durable model
- 让 JSON 与数据库实现短期并存或可对照迁移

### 9.3 阶段 C：Storage-backed Query And Audit

目标：

- 增加 query / review / audit surface
- 开始利用数据库的索引与关系能力

## 10. 当前最合理的下一步

如果现在要继续推进，我不建议直接跳到 implementation plan。

我建议先做一轮更窄的收口：

1. 列出 post-P5 仍未完成的 `review / lineage / recompute` contract 项
2. 区分“数据库前必须完成”与“数据库后可增强”
3. 明确数据库阶段除 contract 承接外要新增的系统能力，尤其是历年数据入库与 report registry
4. 只在这之后再起 durable storage design / implementation plan

## 11. 非目标

这份 brainstorming 不做：

- 具体数据库选型拍板
- 具体表结构设计
- migration plan 细节
- whole-document LLM assessment 方案
- 新字段覆盖 phase

## 12. 一句话总结

数据库重构应该承接一个已经稳定的 `review / lineage / recompute` contract；
如果 contract 还没稳定，就先收口 contract，而不是先重写 storage。
