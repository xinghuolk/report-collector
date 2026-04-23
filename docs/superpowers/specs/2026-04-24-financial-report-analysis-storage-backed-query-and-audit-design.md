# 财报分析 Storage-Backed Query And Audit 设计

> **状态:** Draft for review
> **日期:** 2026-04-24
> **阶段:** Post-P5 Durable Storage Follow-up
> **范围类型:** 查询与审计子阶段

## 1. 目标

在已完成的 durable storage core baseline 之上，补齐最小可用的 storage-backed query / audit surface。

这阶段不再解决：

- durable core schema 是否存在
- JSON / DB repository 是否能 round-trip
- historical ingestion 是否能最小入库

这些都已经有 baseline。

这阶段真正要解决的是：

- 如何按 `issuer / fiscal year / report_type` 查询历史覆盖状态
- 如何按 `artifact_id / dataset_id / run_id` 查询 persisted review / lineage / recompute 结果
- 如何给后续 API、audit 和人工 review 提供稳定 lookup surface

## 2. 非目标

本阶段不包含：

- broad HTTP API
- dashboard / BI 风格聚合层
- Postgres migration
- whole-document LLM assessment
- 新字段 coverage

## 3. 当前基线

当前已经有：

- `SqlAlchemyP5ArtifactRepository`
- `HistoricalIngestionService`
- persisted review surfaces
- persisted lineage records
- persisted recompute results

但还缺：

- query-oriented repository methods 的系统化定义
- issuer/year/report coverage lookup
- recompute / review / lineage 的一致查询入口
- audit-oriented read model

## 4. 推荐范围

### 4.1 Report Coverage Query

至少支持：

- 按 `issuer_id` 列出 available fiscal years
- 按 `issuer_id + fiscal_year + report_type` 查询 report 注册状态
- 查询 report-level artifact 是否已生成：
  - extracted

这里要明确区分两类对象：

- `report` / `extracted artifact` 是单报告粒度
- `dataset artifact` / `turtle export` 是多 issuer 聚合粒度

因此，本阶段的 coverage query 不应把 `dataset` / `turtle export` 直接伪装成 report-level availability。
如果后续确实需要回答“某个 report 是否已被某个 dataset 覆盖”，那应作为 dataset-side 派生判断，而不是 report registry 的基础状态字段。

### 4.2 Persisted Surface Query

至少支持：

- 按 `artifact_id` 查询 extracted review surface
- 按 `dataset_id` 查询 dataset review surface
- 按 `dataset_id` 查询 turtle export review surface
- 按 `dataset_id` / `source_artifact_id` 查询 lineage
- 按 `run_id` 查询 recompute result

这一层应优先承接当前已存在的 durable repository baseline。也就是说：

- repository baseline 若已经使用 `load_*` 命名，应继续沿用
- 如果后续需要 `get_*` 风格的更上层 read service，可作为 wrapper 引入
- 但本阶段不应为了 query spec 再重命名已经稳定的 persistence API

### 4.3 Audit Read Model

第一阶段只做 read model，不做 decision workflow。

至少能回答：

- 某个 dataset 由哪些 source artifacts 构成
- 某个 source artifact 对应哪份 PDF
- 某次 recompute 是因为什么 reason 触发
- 某个 dataset 当前有哪些 persisted review signals

## 5. 设计原则

- query surface 只读优先
- 不新造 review / lineage / recompute 业务 contract
- repository query methods 优先于临时 SQL 片段散落在服务层
- 保持 SQLite-first，同时避免写出 SQLite-only 语义

## 6. 完成标准

本子阶段完成时，应满足：

- issuer/year/report coverage 有稳定查询面
- review / lineage / recompute persisted records 有统一读取入口
- 后续 API / audit 工作不需要重新发明 query contract
