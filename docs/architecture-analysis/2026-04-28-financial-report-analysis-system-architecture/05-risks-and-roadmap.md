# 风险、边界与路线

## 事实来源

顶层路线图是：

`docs/superpowers/specs/active/2026-04-22-financial-report-analysis-unified-roadmap.md`

Metric governance umbrella 是：

`docs/superpowers/specs/active/2026-04-25-financial-report-analysis-metric-governance-umbrella-design.md`

当前实现已经超过 umbrella 中“只有 Phase 1 是 immediate target”的原始说明。
Metric governance Phase 1 到 Phase 4B 现在已经存在于代码和测试中。阅读文档时
应结合这段实现历史。

## 当前已完成基线

路线图现在将 DB-backed 3-5Y data provider baseline 视为已完成：

- 单年 PDF extraction 可以被持久化；
- extracted artifact、dataset、Turtle、review 和 lineage surfaces 可以读回；
- 3-5Y availability/data view 可以报告 persisted facts、missing states、
  coverage explanation 和 lineage；
- read paths 不触发 extraction、recompute、dataset build 或 Turtle build。

Metric governance 也已完成 Phase 1-4B 切片：

- registry metadata 和 provisional guardrails；
- metric governance review surface；
- durable lifecycle registry；
- lifecycle workflow API；
- recompute audit 和 dry-run；
- controlled consumption 和 provenance。

## 暂停门槛

路线图定义了五类 pause gates：

- Foundation：issuer-specific branches、不稳定 row-value binding、薄弱的
  period/unit/currency recovery。
- Governance：provisional/custom facts 影响自动输出、registry roles 不清晰、
  unsupported metric identities 缺少 review。
- Fallback：不受控的 Ollama calls、未测试就扩大 output space、fallback 返回
  values 或 canonical facts。
- Source precedence：note/summary/parent facts 在没有明确策略时覆盖 primary
  statement 或 consolidated facts。
- API/Persistence：重要 decisions 只存在 logs 中、缺少 review surfaces、正确性
  已依赖 recompute/audit 但模型未表达。

## 主要正确性风险

核心 silent-pollution 风险仍然是：

```text
unknown or unsupported field
-> provisional/custom identity
-> canonical promotion
-> key facts / derived facts / Turtle export
-> downstream treats the value as stable
```

当前 guardrails 已经降低该风险：

- `FactNormalizer` 附加 metric governance metadata。
- `ConflictResolver` 阻断 provisional custom canonical promotion。
- `ReportAdapter` 排除 `auto_analysis_allowed=false`。
- Lifecycle-controlled output changes 必须通过显式 audit 和 recompute。

剩余风险：

- P5 dataset、Turtle export 和 availability 大体信任 canonical facts。如果 polluted
  canonical fact 通过其他路径进入 artifact，这些下游 consumers 仍可能将其视为
  present。

## 语义兜底边界

允许的 fallback 角色：

- table kind disambiguation；
- 在 supported labels closed set 中做 row-label choice；
- currency/unit ambiguity；
- 在 target metrics 中做 note/disclosure locator。

禁止的 fallback 角色：

- 创建 lifecycle states；
- approve provisional custom metrics；
- map custom metrics to standard metrics；
- 直接生成 canonical facts；
- override governance policy；
- 决定 recompute correctness。

当前代码通过 `semantic_fallback/config.py`、`semantic_fallback/models.py` 和
`semantic_fallback/service.py` 遵循 bounded pattern。

## 后续范围

除非出现具体业务目标，否则以下内容应保持 future scope：

- 3-5Y job/workflow state；
- automatic report acquisition/backfill/retry/rebuild；
- product artifact lifecycle；
- full approval workflow state machine；
- UI；
- whole-document LLM assessment/diff review；
- 更广泛的 object-storage/Postgres 产品化。

## 建议的后续切片

1. **Active docs reconciliation。**
   更新 active roadmap/umbrella 状态，使其明确反映 metric governance Phase
   1-4B 已实现，同时 approval workflow/UI/async jobs 仍是 future scope。

2. **Downstream governance hardening。**
   在 P5 dataset、Turtle export 和 availability 中增加显式 governance
   assertions 或 filters，避免完全依赖 upstream canonical purity。

3. **Lifecycle recompute audit persistence。**
   持久化 audit snapshots 或 run-level metadata，说明哪些 lifecycle decisions
   影响了某次 dataset/Turtle output。

4. **DB-backed recompute boundary。**
   明确 recompute 是继续 JSON-first 并显式 DB sync，还是变成 DB-native。避免
   长期保留两条含糊的 recompute paths。

5. **One-field post-P5 onboarding slice。**
   从 gap list 中选择一个字段族，先执行 sample-onboarding diagnosis，再决定
   是否扩展 deterministic semantics、registry mappings 或 review surfaces。

## 不应该马上做的事

- 不要在未检查 governance 和 source precedence gates 前启动宽泛新字段 phase。
- 不要让 Ollama 产出 values 或 canonical facts。
- 不要从 raw labels 或 fuzzy matching 推断 lifecycle impact。
- 不要在没有具体 workflow product requirement 的情况下新增 async workflow/job
  基础设施。
- 不要在没有 explicit candidate links 和 audit 的情况下，把 Phase 2 review
  decisions 当作 lifecycle decisions。
