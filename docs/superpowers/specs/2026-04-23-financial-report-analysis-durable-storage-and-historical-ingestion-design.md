# 财报分析 Durable Storage 与历年入库设计

> **状态:** Draft for review
> **日期:** 2026-04-23
> **阶段:** Post-P5 Durable Storage Foundation
> **范围类型:** 持久化与系统能力升级

## 0. 当前实现状态

截至当前分支状态，这条 durable storage 大线已经不再处于纯 brainstorming 阶段。

已经完成并有代码/测试支撑的 baseline 包括：

- storage-bound contract freeze
- SQLite-first durable core models
- JSON / DB repository parity for extracted / dataset / turtle export
- historical ingestion 最小 registry
- review / lineage / recompute 的最小 durable persistence
- focused parity integration

因此，这份文档现在更适合作为 **umbrella spec**，而不是继续直接承载下一轮实现细节。

更准确的状态判断应为：

- `Storage Contract Freeze`: completed baseline
- `Durable Storage Foundation`: completed baseline
- `Historical Ingestion Registry`: completed minimal baseline
- `Storage-backed Query / Audit`: next
- `Document Ledger / Extraction-Run Deep Persistence`: next

## 1. 目标

本阶段不是单纯把 JSON repository 替换成数据库。

本阶段要同时完成两件事：

1. 承接已经在 post-P5 阶段稳定下来的 `review / lineage / recompute` contract
2. 补齐当前系统在 JSON 模式下难以继续扩展的持久化能力，尤其是：
   - 历年报告入库
   - issuer / fiscal year / report registry
   - artifact durable storage
   - query / review / audit 的数据底座

一句话说：

> 这是 `financial-report-analysis` 从“本地 artifact 可跑”走向“历年数据可管理、可查询、可重算”的阶段。

## 2. 非目标

本阶段不包含：

- 新字段 coverage phase
- whole-document LLM assessment 主体实现
- LLM 参与 recompute 裁决
- 广义 API 设计一次做满
- 在 schema 尚未稳定前过早做复杂工作流编排

## 3. 为什么现在要做

当前系统已经具备：

- extracted artifact
- dataset artifact
- Turtle export artifact
- review surface
- lineage surface
- deterministic recompute contract

但仍然缺少真正的系统级持久化能力：

- 没有 durable 的 issuer / report registry
- 历年 annual report 仍主要依赖 manifest 和本地路径组织
- artifact 之间的关系虽然已有 contract，但还不是数据库中的一等实体
- query / audit / recompute 还没有 durable basis

如果后面要持续做：

- 历年数据入库
- 批量重跑
- review 工作流
- API / query surface

那么 durable storage 已经不是“可选优化”，而是系统能力前置。

## 4. 设计原则

### 4.1 Contract First

数据库层应承接既有 contract，而不是重写 contract。

优先承接：

- extracted artifact contract
- dataset artifact contract
- Turtle export contract
- review surface contract
- lineage contract
- recompute plan / result / diff summary contract

### 4.2 Historical Ingestion Is First-Class

数据库阶段必须把历年数据入库视为核心能力，而不是附带脚本。

至少要能稳定管理：

- issuer
- report
- fiscal year
- report type
- source
- artifact generation state

### 4.3 Repository Boundary Must Survive

即使底层从 JSON 切到数据库，上层业务规则也不应被数据库实现细节污染。

需要保留清晰边界：

- artifact persistence
- review surface generation
- lineage generation
- recompute orchestration

### 4.4 Deterministic Core Stays Deterministic

数据库只负责承接与查询，不改变：

- extraction 主路径
- deterministic recompute core
- source precedence
- review / lineage 的语义边界

### 4.5 SQLite First, Postgres Compatible

本阶段的默认数据库选型应明确为：

- ORM / schema layer: `SQLAlchemy`
- database engine: `SQLite-first`

原因是当前阶段的主要目标仍是：

- 跑通 durable schema
- 跑通 JSON / DB repository parity
- 跑通 historical ingestion registry
- 让 review / lineage / recompute 获得最小 durable basis

这些目标更依赖 contract 稳定，而不是更重的数据库能力。`SQLite` 更适合当前阶段的：

- 本地开发
- focused parity tests
- seed historical dataset ingestion
- 单机重算与 review workflow 验证

但 schema / repository abstraction 必须保持 **Postgres-compatible**。这意味着：

- 不引入 SQLite-only 的业务 contract
- 不让上层接口依赖文件路径型数据库特性
- 不把 migration discipline 推迟到数据库切换之后

只有在出现以下信号时，才应把默认执行环境从 `SQLite-first` 升级为 `Postgres-first`：

- 多进程或多人并发写入成为常态
- storage-backed API / service mode 成为主路径
- query / audit workload 明显超出单机 SQLite 的舒适范围
- recompute orchestration 开始需要更强的并发与隔离语义

## 5. 核心对象

### 5.1 Registry Layer

至少应有 durable 的：

- `issuer`
- `report`
- `report_file`
- `manifest`
- `manifest_entry`

### 5.2 Artifact Layer

至少应有 durable 的：

- `extracted_artifact`
- `dataset_artifact`
- `turtle_export_artifact`

这些对象应保留：

- identity
- version
- created_at
- source linkage
- status

### 5.3 Review Layer

至少应有 durable 的：

- extracted review surface
- dataset review surface
- turtle export review surface

重点不是一开始就做复杂 approval，而是让 review 结果不再只存在于临时 JSON 和日志里。

### 5.4 Lineage Layer

至少应有 durable 的：

- artifact lineage links
- dataset row lineage
- export row lineage

### 5.5 Recompute Layer

至少应有 durable 的：

- recompute plan
- recompute execution record
- recompute diff summary

## 6. 历年入库能力

本阶段必须显式承接历年 annual report ingestion。

最小能力包括：

- 按 issuer + fiscal year + report type 建立唯一 report identity
- 把本地 PDF 路径和 report record 关联起来
- 区分“已发现报告”“已入库”“已生成 extracted artifact”“已生成 dataset/export”
- 支持后续按 issuer / year 查询历史覆盖状态

本阶段不要求自动下载器编排做满，但 durable storage 必须能够承接来自下载器或 manifest 的报告记录。

## 7. 推荐分层

### 7.1 Phase A: Storage Contract Freeze

目标：

- 确认数据库前必须稳定的 review / lineage / recompute contract
- 明确哪些对象是一等 durable entities

### 7.2 Phase B: Durable Storage Foundation

目标：

- 建立 issuer / report / artifact durable model
- 提供 database-backed repository
- 保持 JSON repository 可短期并存

### 7.3 Phase C: Historical Ingestion And Query Foundation

目标：

- 把历年 annual report 组织进 durable registry
- 提供基础 query / audit / recompute lookup 能力

### 7.4 建议拆成子 Spec

从当前实现状态继续往前推进时，不建议再直接从这份 umbrella spec 写一个新的“大一统 implementation plan”。

更稳的拆法是：

1. `Storage Core And Repository Parity`
   - 角色：已实现 baseline
   - 范围：durable core models、JSON / DB repository parity、最小 review / lineage / recompute persistence

2. `Storage-Backed Query And Audit`
   - 角色：下一阶段执行 spec
   - 范围：按 issuer / fiscal year / artifact / run id 的查询面、review / audit lookup、query-oriented repository surface

3. `Document Ledger And Extraction-Run Persistence`
   - 角色：下一阶段执行 spec
   - 范围：`report_files`、`documents`、`document_versions`、`extraction_runs`、statement-table / fact-ledger 深层对象如何从“建表存在”推进到“真实接线”

现有 [2026-04-23-financial-report-analysis-core-database-architecture-planning.md](/Users/keli/source/report-collector/docs/superpowers/specs/2026-04-23-financial-report-analysis-core-database-architecture-planning.md) 更适合作为第 3 类工作的分析底稿，而不是下一轮直接执行的总 spec。

## 8. 与 LLM 的关系

whole-document LLM assessment 仍然后置。

数据库阶段最多只需要：

- 给 assessment artifact 预留扩展位置

不应先做：

- 全流程 LLM 插件化接口
- LLM 主导的 review / recompute

## 9. Definition Of Done

作为 umbrella spec，本阶段的总体完成应满足：

- review / lineage / recompute contract 已能被 durable storage 直接承接
- issuer / report / fiscal year / artifact 已有稳定 durable model
- 历年 annual report 可以入库并关联到 artifact
- query / review / recompute 已有数据库层基础支撑
- JSON 模式不再是整个系统跑通的唯一方式

## 10. 一句话结论

数据库重构既是 contract 承接阶段，也是系统能力升级阶段；
它要解决的不只是“怎么存”，还包括“怎么把历年报告、artifact、review、lineage、recompute 组织成一个真正可运行的系统”。
当前默认路径应为：`SQLAlchemy + SQLite-first`, with a Postgres-compatible contract boundary.
