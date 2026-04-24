# Financial Report Analysis Turtle Core Investor Inputs Design

## 1. Goal

This design defines Phase 1 of the Turtle investment input coverage roadmap.

The purpose of this phase is to extend `financial-report-analysis` from
"three-statement high-value metrics" into a first investor-oriented input
layer that can support the most essential Turtle calculations without yet
entering broad working-capital detail, note-table parsing, or parent-company
bridge logic.

This phase should focus on the smallest field set that materially improves the
practical usefulness of the extracted financial dataset for:

- owner earnings
- DCF baseline inputs
- dividend payout cross-checks
- basic profitability and capital-allocation interpretation

## 2. Why This Step Exists

The current system is already close to a usable statement-level extraction
layer, but Turtle calculations still cannot run on top of it in a stable way.

The biggest blockers are not broad note-table coverage or parent-company
complexity yet. The biggest blockers are a small group of core investor fields
that still sit just outside the current high-value metric set.

These missing fields include:

- attributable profit
- EPS
- finance and tax anchors
- depreciation and amortization
- capital expenditure
- paid-dividend cash outflow

Without them, Turtle can only approximate the business economics. With them,
the framework can begin to compute more meaningful investor-facing measures
before the harder phases begin.

## 3. In Scope

This phase is in scope for the following fields.

### 3.1 Income Statement

- `n_income_attr_p`
- `basic_eps`
- `finance_exp`
- `total_profit`
- `income_tax`
- `minority_gain`

### 3.2 Cash Flow Statement

- `c_pay_acq_const_fiolta`
- `depr_fa_coga_dpba`
- `amort_intang_assets`
- `lt_amort_deferred_exp`
- `c_pay_dist_dpcp_int_exp`

### 3.3 Field-Model Constraints

This phase should not treat every selected field as the same kind of fact.

The baseline modeling expectations should be:

- amount-like statement rows:
  - `n_income_attr_p`
  - `finance_exp`
  - `total_profit`
  - `income_tax`
  - `minority_gain`
  - `c_pay_acq_const_fiolta`
  - `depr_fa_coga_dpba`
  - `amort_intang_assets`
  - `lt_amort_deferred_exp`
  - `c_pay_dist_dpcp_int_exp`
- per-share field:
  - `basic_eps`

For `basic_eps`, this phase should assume:

- `value_type = per_share`
- `unit_expectation = per_share_amount`
- the preferred source is the primary income statement
- `key_metrics` or per-share summary blocks may be used only if the semantic
  path and provenance remain explicit and they do not outrank a valid primary
  income-statement source

This constraint exists to avoid forcing EPS into the same semantic bucket as
currency-amount statement facts.

## 4. Out Of Scope

This phase is explicitly out of scope for:

- broad working-capital fields such as receivables, payables, and contract
  liabilities
- debt-structure fields such as short-term and long-term borrowing
- parent-company balance-sheet extraction
- note-table and note-paragraph bridge logic
- DPS extraction from dividend plans
- buyback and cancellation bridge logic
- multi-year dataset export design

## 5. Why These Fields Come First

These fields are the best Phase-1 target because they satisfy four conditions:

- they are heavily used by Turtle downstream calculations
- they mostly live in primary financial statements
- they are materially more important than many broader detail fields
- they can be added without forcing early entry into the highest-ambiguity
  note-bridge problems

This makes them the highest-leverage next step.

## 6. Target Downstream Use Cases

This phase should directly improve the quality of:

### 6.1 Owner Earnings

By adding:

- `n_income_attr_p`
- `depr_fa_coga_dpba`
- `amort_intang_assets`
- `lt_amort_deferred_exp`
- `c_pay_acq_const_fiolta`

### 6.2 Dividend And Distribution Interpretation

By adding:

- `c_pay_dist_dpcp_int_exp`
- `n_income_attr_p`
- `basic_eps`

### 6.3 DCF Baseline Inputs

By adding:

- `c_pay_acq_const_fiolta`
- `depr_fa_coga_dpba`
- `amort_intang_assets`
- `lt_amort_deferred_exp`
- `finance_exp`
- `income_tax`
- `total_profit`

## 7. Representative Label Families

The following label families should be treated as the starting deterministic
coverage target for this phase.

### 7.1 CN Representative Labels

- `归属于母公司股东的净利润`
- `归属于上市公司股东的净利润`
- `基本每股收益`
- `财务费用`
- `利润总额`
- `所得税费用`
- `少数股东损益`
- `购建固定资产、无形资产和其他长期资产支付的现金`
- `固定资产折旧`
- `无形资产摊销`
- `长期待摊费用摊销`
- `分配股利、利润或偿付利息支付的现金`

### 7.2 HK / English Representative Labels

- `profit attributable to owners of the parent`
- `profit attributable to equity holders of the company`
- `basic earnings per share`
- `finance costs`
- `profit before tax`
- `income tax expense`
- `profit attributable to non-controlling interests`
- `payments for acquisition of property, plant and equipment`
- `depreciation of property, plant and equipment`
- `amortisation of intangible assets`
- `amortisation of long-term deferred expenses`
- `dividends paid`

These are representative targets, not a reason to add unbounded aliases.
Fields that are clearly summary-only, note-only, ratio-style, or secondary
management-disclosure rows should still be excluded.

## 8. Main Risks

### 8.1 Profit Attribution Ambiguity

The phase must distinguish:

- total net profit
- attributable net profit
- minority-interest profit

This is especially important because Turtle calculations use attributable
profit directly.

### 8.2 Cash-Flow Detail Collisions

Cash-flow detail rows can be noisier than the current main cash-flow section
metrics. This phase must avoid confusing:

- capital expenditure
- dividends paid
- other financing cash outflows
- subtotal or narrative disclosure rows

### 8.3 EPS Surface Drift

The design should prioritize:

- basic EPS

without accidentally mixing in:

- diluted EPS
- adjusted EPS
- non-GAAP EPS

## 9. Deterministic-First Constraints

This phase should continue to follow the same priority order:

`structure recovery -> deterministic normalization -> registry match -> candidate facts -> canonical facts -> API`

That means:

- new coverage should come primarily from deterministic normalization and
  registry support
- semantic fallback may assist ambiguous local cases, but must not become the
  default mechanism for these new fields
- statement-aware gating and provenance must remain explicit

## 10. Verification Strategy

This phase should verify:

- registry coverage for the selected Phase-1 fields
- deterministic normalization for representative CN/HK labels
- candidate-to-canonical promotion where applicable
- API visibility for fields that belong in high-value outputs
- non-regression on the existing high-value metric set
- the shared CN/HK anchor and reference matrix already used in the current
  financial-report-analysis roadmap

The field-layer expectations for this phase should be:

- must reach candidate:
  - `n_income_attr_p`
  - `basic_eps`
  - `finance_exp`
  - `total_profit`
  - `income_tax`
  - `minority_gain`
  - `c_pay_acq_const_fiolta`
  - `depr_fa_coga_dpba`
  - `amort_intang_assets`
  - `lt_amort_deferred_exp`
  - `c_pay_dist_dpcp_int_exp`
- must reach canonical:
  - `n_income_attr_p`
  - `basic_eps`
  - `finance_exp`
  - `total_profit`
  - `income_tax`
  - `minority_gain`
- API-visible requirement:
  - `n_income_attr_p`
  - `basic_eps`

The remaining cash-flow detail fields may stay candidate-visible in this phase
if their provenance is stable and they are consumable by downstream Turtle
logic through the extracted fact set.

### 10.1 Field-to-Sample Expectations

The phrase `supported sample set` should not mean that every field must appear
in every sample. The minimum phase expectations should be:

- `n_income_attr_p`, `finance_exp`, `total_profit`, `income_tax`:
  - expected on the CN annual primary anchor
  - expected on HK annual anchors
  - expected on at least part of the CN annual reference set
- `basic_eps`:
  - expected on the CN annual primary anchor
  - expected on HK annual anchors
  - not required on every quarterly or reduced-disclosure sample
- `minority_gain`:
  - expected where minority-interest presentation is explicit
  - not required on every sample if the issuer does not expose a meaningful
    minority-interest line
- `c_pay_acq_const_fiolta`, `depr_fa_coga_dpba`, `amort_intang_assets`,
  `lt_amort_deferred_exp`, `c_pay_dist_dpcp_int_exp`:
  - expected primarily on annual-report samples
  - not required on every quarterly supplement

Review and implementation should use these minimum expectations rather than
implicitly assuming full-matrix presence for every Phase-1 field.

This phase may include minimal ranking or gating adjustments if required to
keep new fields from being displaced by summary or non-primary disclosures.
Broader cross-statement policy consolidation should still remain in the
dedicated conflict-governance line.

## 11. Deliverable Definition

This design is complete when:

- the selected Phase-1 fields are stably extracted on the supported sample set
- attributable profit, basic EPS, D&A, Capex, and paid-dividend cash outflow
  have stable statement-aware semantics
- the candidate/canonical/API layer expectations defined above are met
- the existing high-value metric set does not regress
- candidate/canonical/API contracts remain stable

## 12. What Should Come Next

If this phase succeeds, the next default move should be:

- Phase 2: Working Capital And Debt Inputs

That is the next highest-leverage phase for Turtle because it supports:

- real cash revenue reconstruction
- debt-aware valuation
- working-capital quality interpretation

Ollama semantic fallback coverage for the new Turtle fields is intentionally
not a Phase-1 closure requirement. This phase is deterministic-first, and many
of the selected fields are expected to be handled by structure recovery,
normalization, and registry matching rather than live fallback.

After the Turtle master-plan phases establish the stable field set and
deterministic semantics, a separate Ollama semantic fallback coverage closure
should evaluate whether to expand:

- supported row-label fallback outputs
- prompt allowed labels and negative controls
- promoted real-report probe cases
- accuracy thresholds and fallback budgets

That closure should cover the final Turtle field set in one pass instead of
expanding Ollama probes piecemeal during each deterministic field phase.
