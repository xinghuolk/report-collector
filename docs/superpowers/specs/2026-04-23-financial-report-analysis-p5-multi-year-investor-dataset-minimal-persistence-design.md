# 财报分析 P5 多年投资数据集与最小持久化设计

> **状态:** Draft for review
> **日期:** 2026-04-23
> **阶段:** Turtle Phase 5 - Multi-Year Investor Dataset
> **范围类型:** 数据集组装与最小持久化

## 1. 目标

P5 的目标是把 P4C/P4D/P4E 已经收口的抽取能力，组装成 Turtle 可以稳定消费的多年投资分析输入数据集。

第一版 P5 不应继续变成字段覆盖 phase。它应聚焦于 3-5 年已支持事实的组装、缺失状态保留、质量标记、版本标识和 Turtle 导出形状。

这份设计同时补齐 unified roadmap 中明确指出的 storage 缺口：在多年抽取继续扩张前，项目需要一个最小持久化层，用来保存输入清单、单份报告分析 artifact 和组装后的数据集 artifact。

## 2. 与 `report/` 的边界

`report/` 只保留为下载器和 PDF 注册工具。

P5 可以使用 `report/` 把年报下载到以下目录：

- `report/downloads/cn_stocks/<stock_code>/annual/`
- `report/downloads/hk_stocks/<stock_code>/annual/`

但 P5 不应依赖 `report` 作为业务持久化层。`report/src/reports.db` 和它的提取缓存属于下载器运行状态，不属于 `financial-report-analysis` 的事实库。

`financial-report-analysis` 负责：

- P5 输入 manifest
- 单份报告的 extracted analysis artifact
- 多年数据集 artifact
- 数据集质量与缺失状态 contract

## 3. P5 V1 输入边界

P5 V1 使用显式输入，不做自动报告发现。

输入是一个 manifest，列出 seed dataset 使用的年报。第一版 seed 建议包含 3 个公司，每个公司 3-5 份年度报告。

每条 manifest entry 记录：

- `issuer_id`
- `market`
- `stock_code`
- `fiscal_year`
- `report_type`
- `pdf_path`
- `source`
- 可选 `company_name`
- 可选 `report_language`

P5 V1 的 seed dataset 只覆盖年度报告，`report_type` 固定为 `annual`。季度和半年报可以在后续 phase 加入，但不能和年度报告共用同一个 artifact id 规则。

自动按股票代码和年份范围搜索报告、下载编排、报告替换策略，均不属于 P5 V1。

## 4. 最小持久化模型

P5 V1 先使用当前项目内的 JSON 文件 artifact，不直接引入数据库。

推荐目录结构：

```text
financial-report-analysis/data/p5/
  manifests/
    p5_seed_3_issuers.json
  extracted/
    CN_601919_2025.json
    HK_02498_2022.json
  datasets/
    p5_seed_3_issuers_dataset.json
```

这个设计故意保持轻量：它提供可复现的本地状态，但不提前绑定 SQLite、PostgreSQL、迁移脚本或 recompute 调度。

实现时应明确 artifact repository 边界。后续如果改成数据库 repository，不应改变 dataset assembly 的业务规则。

## 5. 单份报告 Extracted Artifact

每条 manifest entry 对应一个 extracted artifact。生成方式是使用现有 `financial-report-analysis` pipeline 分析该 PDF，然后把结果落盘。

每个 artifact 包含：

- `artifact_version`
- `pipeline_version`
- `source_pdf_path`
- `document`
- `document_metadata`
- `candidate_facts`
- `canonical_facts`
- `derived_facts`
- `validation_report`
- `review_packets`
- `quality_gate`
- `missing_status`
- `created_at`

`missing_status` 应保留已有阶段产生的缺失状态 map，例如：

- `working_capital_missing_status`
- `debt_missing_status`
- `asset_missing_status`
- `cash_health_missing_status`

如果某个指标没有对应的 phase missing-status map，dataset 层可以把该指标标为 `unknown`，但不能静默当成 `absent`。

## 6. Dataset Artifact

组装后的 dataset artifact 包含：

- `dataset_id`
- `dataset_version`
- `created_at`
- `issuer_count`
- `periods`
- `metrics`
- `rows`
- `quality_summary`
- `source_artifacts`

每个数据行使用以下字段作为 key：

- `issuer_id`
- `market`
- `stock_code`
- `fiscal_year`
- `metric_id`
- `entity_scope`
- `period_scope`
- `statement_type`

每行保存：

- `value`
- `currency`
- `unit`
- `quality_status`
- `missing_status`
- `source_fact_id`
- `source_artifact_id`
- `evidence_bundle_id`

Dataset 必须同时保留时点值和期间值。不能把资产负债表时点值强行转成期间指标，也不能把合并口径和母公司口径混在同一个 row key 里。

## 7. 缺失与质量 Contract

P5 V1 使用以下 dataset-level missing status：

- `present`: 该 issuer/year/metric/scope 存在受支持事实
- `absent`: 相关 phase contract 已判定该指标缺失
- `not_surfaced`: 原始证据可能存在，但当前支持路径没有稳定产出事实
- `out_of_scope`: 当前数据集 contract 不覆盖该指标或口径
- `unknown`: source artifact 中没有可靠状态

`unknown` 在 V1 中允许作为显式过渡状态，但必须在 `quality_summary` 中可见。

Dataset quality 至少汇总：

- 按指标统计的缺失数量
- 按 issuer 统计的缺失数量
- source artifact 中的 unsupported / review-required 状态
- 重复事实冲突
- parent / consolidated 口径混淆风险

## 8. Turtle 导出形状

P5 V1 除内部标准化 dataset 外，还应生成 Turtle-facing export。

Turtle export 只做别名视图，把当前 canonical id 映射到 Turtle 字段名，例如：

- `operating_cost` -> `oper_cost`
- `operating_profit` -> `operate_profit`
- `net_profit` -> `n_income`
- `total_liabilities` -> `total_liab`
- `equity_attributable_to_owners` -> `total_hldr_eqy_exc_min_int`
- `operating_cash_flow` -> `n_cashflow_act`
- `investing_cash_flow` -> `n_cashflow_inv_act`
- `financing_cash_flow` -> `n_cash_flows_fnc_act`
- `cash` -> `money_cap`

Turtle export 是 adapter view，不应引入另一套 competing canonical metric registry。

## 9. 派生计算边界

P5 V1 可以组装已有 canonical facts 和 derived facts，但不应在 dataset 层新增投资计算。

P5 V1 允许：

- 年份对齐
- period / scope 校验
- missing / quality summary
- Turtle alias export

P5 V1 不包含：

- CAGR
- 平均 ROE
- DCF 输入
- FCF Yield
- 自动估值结论

这些应属于后续 Turtle analytics 层，除非另有独立 spec 把某个窄口径派生指标纳入本项目。

## 10. API 边界

P5 V1 起步阶段不需要公开 HTTP API。

第一版可以是 Python service 加 CLI / script-style entry point，流程为：

1. 读取 manifest
2. 检查缺失的 extracted artifacts
3. 写入单份报告 extracted artifacts
4. 组装 dataset artifact
5. 写入 Turtle export artifact

等 artifact contract 稳定后，再考虑公开 API。

## 11. 验证策略

默认验证保持窄范围：

1. manifest 解析和校验的 unit tests
2. JSON artifact repository round-trip unit tests
3. dataset row assembly 和 missing-status propagation unit tests
4. Turtle alias export unit tests
5. 使用现有本地 PDF fixture 的 focused integration tests

默认不跑大范围 real-PDF matrix，也不跑 live Ollama matrix。seed issuer 的真实样本验证应使用明确 node selection。

## 12. 非目标

P5 V1 不包含：

- 在 `financial-report-analysis` 内部编排下载器
- 按股票代码和年份范围自动发现报告
- 数据库迁移或 PostgreSQL schema
- recompute 调度
- 大型 review UI
- 新的广义 note / disclosure 抽取
- 超出 P4C/P4D/P4E 已完成 contract 的新增字段覆盖

## 13. 完成标准

P5 V1 完成时应满足：

- seed manifest 能指向 3 个 issuer、每个 3-5 份年度 PDF
- 单份报告 extracted artifacts 能持久化在 `financial-report-analysis`
- multi-year dataset artifact 能从 persisted artifacts 组装出来
- row 级和 summary 级都能看到 missing / quality 状态
- Turtle alias export 能生成，且不改变 canonical metric id
- focused unit tests 和 seed integration tests 通过
