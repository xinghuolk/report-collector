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

Downstream governance hardening 也已完成：

- P5 dataset 通过共享 policy helper 过滤 non-consumable canonical facts；
- dataset `quality_summary` 记录 governance blocked count、metric、reason 和 source
  fact ids；
- Turtle export 继续只消费 dataset rows，不绕过 dataset governance；
- 3-5Y availability 在 present 判定前检查同一 governance policy；
- 缺失或 malformed governance metadata 默认 fail closed。

Lifecycle recompute audit persistence 也已完成：

- recompute run 可以持久化 lifecycle recompute audit snapshot；
- recompute run read surface 和 dataset audit view/API 可以读回该 snapshot；
- dataset audit view 读取 persisted snapshot，不重新推断 live lifecycle state；
- 旧 recompute run 没有 snapshot 时保持 `null`；
- malformed lifecycle audit payload 会 fail fast。

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
- P5 dataset 和 availability 现在也会在下游消费前显式执行 governance policy。

剩余风险：

- DB-backed recompute boundary/readiness contract 已明确：当前仍是 JSON-first
  canonical executor，DB-native recompute unsupported。后续风险转为 JSON-first
  recompute 结果如何显式同步到 DB read surface。
- 如果新增 post-P5 字段，仍需要先走 sample-onboarding diagnosis，避免绕过当前
  governance/source precedence gates。

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

1. **Explicit JSON-to-DB sync bridge。**
   DB-backed recompute boundary/readiness contract 已明确：当前仍是 JSON-first
   canonical executor，DB-native recompute unsupported。下一步如果产品需要让
   JSON-first recompute 结果稳定进入 DB read surface，应设计 explicit JSON-to-DB
   sync bridge，包括 input hashes、before/after artifact references、overwrite
   semantics 和 partial failure recovery。

2. **One-field post-P5 onboarding slice。**
   从 gap list 中选择一个字段族，先执行 sample-onboarding diagnosis，再决定
   是否扩展 deterministic semantics、registry mappings 或 review surfaces。

3. **Whole-document LLM assessment/diff review。**
   只作为 review/gap-detection artifact，不直接产出 canonical facts，也不参与
   deterministic recompute 裁决。

## 不应该马上做的事

- 不要在未检查 governance 和 source precedence gates 前启动宽泛新字段 phase。
- 不要让 Ollama 产出 values 或 canonical facts。
- 不要从 raw labels 或 fuzzy matching 推断 lifecycle impact。
- 不要在没有具体 workflow product requirement 的情况下新增 async workflow/job
  基础设施。
- 不要在没有 explicit candidate links 和 audit 的情况下，把 Phase 2 review
  decisions 当作 lifecycle decisions。
