# 财报分析 Document Ledger And Extraction-Run Persistence 设计

> **状态:** Draft for review
> **日期:** 2026-04-24
> **阶段:** Post-P5 Durable Storage Follow-up
> **范围类型:** 深层持久化子阶段

## 1. 目标

把当前已经建表但尚未真正接线的 `document / extraction-run / statement-table / fact-ledger` 层，从“schema 存在”推进到“可以承接真实 pipeline 对象”。

当前 durable storage baseline 主要服务于：

- report / manifest / artifact
- review / lineage / recompute
- historical ingestion

但更深一层的基础抽取对象还没有真正成为 durable first-class entities。

## 2. 非目标

本阶段不包含：

- broad query dashboard
- whole-document LLM assessment
- 重新设计 canonical fact contract
- 把所有 raw parser payload 完整关系化

## 3. 当前状态

数据库 schema 中已经存在或开始存在的对象包括：

- `report_files`
- `documents`
- `document_versions`
- `extraction_runs`
- `statement_tables`
- `statement_table_rows`
- `statement_table_columns`
- `fact_sets`
- `candidate_facts`
- `canonical_facts`
- `derived_facts`
- `fact_lineage`
- `validation_reports`
- `validation_issues`

但当前问题是：

- 这些表更多是 schema baseline，而不是已经接到主 pipeline 的 durable source of truth
- 真实 code path 仍主要围绕 artifact payload 在运行

## 4. 核心问题

### 4.1 Document Identity

要回答：

- `report`、`report_file`、`document`、`document_version` 之间如何稳定分层
- 一份 PDF 被重新下载、重新解析、重新抽取时，哪些 identity 应变化，哪些不应变化

### 4.2 Extraction Run Identity

要回答：

- `pipeline_version`
- `registry_version`
- `parser version`
- `quality gate`
- run status

这些如何与 document version 绑定。

### 4.3 Statement / Fact Ledger Persistence

要回答：

- 哪些 table/row/column 对象需要 durable row-level identity
- 哪些完整 payload 仍应保留在 JSON / object snapshot
- candidate / canonical / derived facts 如何 durable 化而不打乱当前 pipeline contract

## 5. 设计原则

- fact ledger 优先于 dataset snapshot
- 关系索引与 payload snapshot 混合，不追求 day-one 全量关系化
- 只把高价值、高稳定引用对象关系化
- 继续保持 deterministic-first

## 6. 推荐顺序

1. document / document_version / extraction_run identity 接线
2. statement table identity 接线
3. fact set / candidate / canonical / derived 最小 durable mapping
4. validation / quality gate persistence

## 7. 完成标准

本子阶段完成时，应满足：

- 一份 PDF 的 document / extraction-run 生命周期可持久化追踪
- statement tables 不再只存在于 artifact payload
- fact ledger 有最小 durable representation
- 后续 query / audit / recompute 可以引用更深层对象，而不只引用 artifact snapshot
