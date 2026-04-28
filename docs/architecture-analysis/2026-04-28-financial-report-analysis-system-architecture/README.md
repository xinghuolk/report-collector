# 财报分析系统架构分析

> 日期：2026-04-28
> 范围：Metric Governance Phase 4B、downstream governance hardening 和
> lifecycle recompute audit persistence 完成后的当前系统架构分析

本目录汇总当前 `financial-report-analysis` 的系统架构。分析依据包括：
active 统一路线图、metric governance umbrella、当前代码实现，以及最新
downstream governance / lifecycle audit persistence 实现结果。

## 文档索引

- [01-system-overview.md](01-system-overview.md)：高层架构、模块边界、
  当前完成状态。
- [02-extraction-data-flow.md](02-extraction-data-flow.md)：PDF 到事实、
  validation、P5 dataset、Turtle export 的数据流。
- [03-metric-governance.md](03-metric-governance.md)：确定性映射、
  metric identity 治理、lifecycle registry、review API、controlled
  consumption。
- [04-storage-api-recompute.md](04-storage-api-recompute.md)：JSON/DB
  repository、API runtime、review surface、lineage、recompute。
- [05-risks-and-roadmap.md](05-risks-and-roadmap.md)：pause gates、正确性
  风险、fallback 边界、future scope、建议的后续最小切片。

## 当前状态

系统已经越过原始 pre-P5 字段覆盖阶段。当前 active baseline 包括：

- table-driven extraction 和 canonical fact assembly；
- P5 dataset 与 Turtle export 生成；
- storage-backed API runtime 和 DB persistence；
- review、lineage、recompute，以及 3-5Y availability/read surfaces；
- metric governance Phase 1 到 Phase 4B；
- downstream governance hardening；
- lifecycle recompute audit snapshot persistence 和 read surfaces。

当前架构坚持 deterministic-first。LLM/Ollama fallback 只允许作为受限语义
辅助，不能创建 canonical facts、lifecycle decisions 或 recompute decisions。

## 顶层流程

```text
PDF
-> table structure recovery / semantic normalization
-> deterministic metric mapping and candidate facts
-> fact normalization and governance metadata
-> conflict resolution and canonical facts
-> derivation, validation, review packets
-> persisted extracted artifact
-> P5 dataset / Turtle export / API read surfaces
-> review, lineage, recompute, persisted lifecycle audit, and availability surfaces
```

## 当前架构边界

系统已经具备受控、可 review 的事实消费能力，但还不是完整 workflow product
平台。除非出现新的明确业务目标，以下内容仍应保持在 future scope：

- async job orchestration；
- automatic report acquisition / backfill / retry；
- full approval workflow state machine；
- UI；
- whole-document LLM assessment 作为生产裁决来源；
- 超出当前 SQLite/JSON baseline 的 Postgres/object-storage 产品化。
