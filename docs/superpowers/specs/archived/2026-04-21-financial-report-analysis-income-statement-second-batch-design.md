# Financial Report Analysis Income Statement Second Batch Design

## 1. Goal

This design defines the next income-statement expansion step after the
completed core metric path for:

- `revenue`
- `operating_cost`
- `operating_profit`
- `net_profit`

The objective is to extend that path with one additional high-value metric
that materially improves statement usefulness without broadening the semantic
surface too aggressively.

## 2. Primary Scope

This step is primarily in scope for:

- `gross_profit`

This step may also prepare the normalization surface for:

- `adjusted_net_profit`

but `adjusted_net_profit` is not a primary completion dependency for this
design.

## 3. Why This Step Exists

The income statement is currently the strongest statement path in the system.
That makes it the lowest-risk place to deepen coverage before broader
three-statement expansion introduces more ownership and cross-statement
ambiguity.

`gross_profit` is the best next metric because it is:

- highly valuable to downstream analysis
- semantically close to already supported income-statement metrics
- a useful test of stricter summary/ratio suppression

## 4. In Scope

This step is in scope for:

- extending registry aliases for `gross_profit`
- strengthening deterministic row-label normalization for realistic CN/HK
  gross-profit label families
- ensuring `gross_profit` can travel through:
  - candidate facts
  - canonical facts
  - API `key_facts`
- blocking common false positives such as margin rows and summary rows

## 5. Representative Label Families

The following label families should be treated as the starting deterministic
coverage target for this tranche.

### 5.1 CN Representative Labels

- `营业毛利`
- `毛利润`
- `毛利`

### 5.2 HK / English Representative Labels

- `gross profit`
- `gross profit for the period`
- `gross profit attributable to operations`

These are representative targets, not permission to add broad profit aliases
indiscriminately. Labels that are clearly ratio-oriented or summary-oriented
should still be excluded.

## 6. Out Of Scope

This step is out of scope for:

- broad profitability-ratio support
- wide adjusted-profit taxonomy support
- direct support for `gross_margin` as a fact metric
- note-table profit derivation

## 7. Main Risks

### 7.1 Gross Margin Interference

The most important risk is confusing:

- `gross profit`

with:

- `gross margin`
- margin change rows
- profitability summaries

This design should preserve strict deterministic gating so ratio rows are not
promoted into fact metrics.

### 7.2 Summary Table Override

As aliases widen, management-summary tables may compete with the main income
statement. The existing main-table-first behavior must remain stable.

## 8. Verification Strategy

This step should verify:

- registry coverage for CN and HK aliases
- deterministic normalization coverage
- candidate-to-canonical promotion
- API `key_facts` visibility
- non-regression against summary/growth/ratio interference
- the shared sample matrix defined in the umbrella three-statement design, with
  emphasis on the CN annual primary anchor, the HK annual anchors, and the CN
  annual reference set

This tranche may include minimal ranking or gating adjustments if they are
required to keep `gross_profit` from being displaced by summary or ratio
tables. Larger cross-statement policy consolidation remains in the dedicated
conflict-governance tranche.

## 9. Deliverable Definition

This design is complete when:

- `gross_profit` is stably extracted from supported income-statement samples
- `gross_margin` and similar ratio rows are not promoted as `gross_profit`
- current income-statement core metrics do not regress
