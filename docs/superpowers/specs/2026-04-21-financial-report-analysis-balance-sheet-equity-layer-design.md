# Financial Report Analysis Balance Sheet Equity Layer Design

## 1. Goal

This design defines the next balance-sheet expansion step after the completed
baseline support for:

- `cash`
- `total_assets`
- `total_liabilities`

The objective is to add the smallest meaningful equity-aware layer while
keeping point-in-time semantics, ownership semantics, and provenance stable.

## 2. Primary Scope

This step is in scope for:

- `equity`
- `equity_attributable_to_owners`

These two metrics are enough to prove the system can move beyond low-ambiguity
balance-sheet totals without drifting into a full equity taxonomy project.

## 3. Why This Step Exists

The balance sheet currently has only low-ambiguity totals. The next useful
step is not broad asset/liability detail, but ownership-sensitive equity
coverage.

This is the first place where the system must explicitly distinguish:

- total equity
- attributable equity
- consolidated versus parent-only disclosures

That makes this step strategically important even though it stays narrow.

## 4. In Scope

This step is in scope for:

- registry support for CN/HK equity label families
- deterministic normalization of ownership-aware equity labels
- point-in-time and statement-aware gating
- stable provenance through candidate, canonical, and API layers

## 5. Representative Label Families

The following label families should be treated as the starting deterministic
coverage target for this tranche.

### 5.1 CN Representative Labels

- `所有者权益合计`
- `股东权益合计`
- `归属于母公司股东权益`
- `归属于母公司所有者权益`

### 5.2 HK / English Representative Labels

- `total equity`
- `total shareholders' equity`
- `equity attributable to owners of the parent`
- `equity attributable to equity holders of the company`

These are representative targets, not justification for broad lexical
expansion into book value, per-share net asset, or ratio-style labels.

## 6. Out Of Scope

This step is out of scope for:

- book value
- per-share net asset metrics
- broad parent-only balance-sheet coverage
- wide working-capital expansion
- equity-change-statement extraction

## 7. Main Risks

### 7.1 Ownership Ambiguity

The main risk is conflating:

- total equity
- equity attributable to owners
- parent-company-only equity

This design should prefer narrower deterministic mappings over broad lexical
coverage that lowers precision.

### 7.2 Summary and Ratio Interference

Rows such as:

- net asset per share
- equity ratio
- shareholder return summaries

must not be promoted into core balance-sheet facts.

## 8. Verification Strategy

This step should verify:

- registry coverage for selected CN/HK equity aliases
- normalization and gating for ownership-aware labels
- candidate/canonical/API provenance stability
- non-regression on existing `cash`, `total_assets`, `total_liabilities`
- the shared sample matrix defined in the umbrella three-statement design, with
  emphasis on the CN annual primary anchor and the HK annual anchors that
  expose attributable-ownership labels

This tranche may include minimal ranking or gating adjustments if they are
required to prevent summary rows, parent-only rows, or weaker secondary tables
from outranking the intended balance-sheet facts. Wider policy consolidation
still belongs to the dedicated conflict-governance tranche.

## 9. Deliverable Definition

This design is complete when:

- `equity` and `equity_attributable_to_owners` are stable on supported sample
  sets
- ownership drift is materially controlled
- balance-sheet totals do not regress
