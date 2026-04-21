# Financial Report Analysis Cash Flow Core Completion Design

## 1. Goal

This design defines the next cash-flow expansion step after the existing
support for:

- `operating_cash_flow`

The objective is to complete the three primary cash-flow sections so the
cash-flow statement has a usable closed loop at the same high-value level as
the other two core statements.

## 2. Primary Scope

This step is in scope for:

- `investing_cash_flow`
- `financing_cash_flow`

Together with `operating_cash_flow`, these metrics complete the main
cash-flow statement structure.

## 3. Why This Step Exists

Without investing and financing cash-flow coverage, the system still lacks a
complete main-section view of the cash-flow statement. Adding these two
metrics gives downstream consumers a materially more useful statement-level
result without requiring a broad sub-line cash-flow expansion.

## 4. In Scope

This step is in scope for:

- registry support for realistic CN/HK investing/financing cash-flow labels
- deterministic normalization for common row-label variants
- stable candidate, canonical, and API promotion
- suppression of summary and derived cash-flow rows

## 5. Representative Label Families

The following label families should be treated as the starting deterministic
coverage target for this tranche.

### 5.1 CN Representative Labels

- `投资活动产生的现金流量净额`
- `筹资活动产生的现金流量净额`

### 5.2 HK / English Representative Labels

- `net cash generated from investing activities`
- `net cash used in investing activities`
- `net cash generated from financing activities`
- `net cash used in financing activities`

These are representative targets, not permission to absorb subtotal rows, free
cash flow rows, or net-change-in-cash rows into the core metric set.

## 6. Out Of Scope

This step is out of scope for:

- free cash flow
- cash-flow ratio metrics
- sub-line investing or financing components
- liquidity note-table extraction

## 7. Main Risks

### 7.1 Net Change Interference

Cash-flow tables frequently include rows such as:

- net increase in cash and cash equivalents
- free cash flow
- subtotal cash-flow rows

These must not be mistaken for the target investing or financing sections.

### 7.2 Layout Variation

Cash-flow tables often vary more in phrasing and table layout than the income
statement. This design must still rely primarily on deterministic
normalization and registry coverage rather than bespoke parser logic.

## 8. Verification Strategy

This step should verify:

- registry coverage for investing/financing cash-flow aliases
- normalization coverage for CN/HK statement variants
- candidate-to-canonical promotion
- API `key_facts` visibility
- non-regression on `operating_cash_flow`
- the shared sample matrix defined in the umbrella three-statement design, with
  emphasis on the CN annual primary anchor, HK annual anchors, and the HK
  quarterly supplement

This tranche may include minimal ranking or gating adjustments if they are
required to prevent derived or summary cash-flow rows from outranking the
three primary statement sections. Wider policy consolidation still belongs to
the dedicated conflict-governance tranche.

## 9. Deliverable Definition

This design is complete when:

- `operating_cash_flow`, `investing_cash_flow`, and `financing_cash_flow`
  form a stable three-section cash-flow path
- summary or derived cash-flow rows are not promoted as target metrics
