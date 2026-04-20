# Ollama Real-Report Probe And Promotion Design

## Goal

Before resuming the previous implementation plan's Task 6 target regressions, add a real-report evaluation layer for the limited Ollama semantic fallback.

This phase should answer two questions:

1. Can the current local Ollama fallback handle the seven target financial fields on realistic annual-report row labels?
2. Which of those cases are stable enough to promote into hard integration regressions?

## Scope

In scope:

- Real Ollama evaluation against representative annual-report row labels
- Coverage for the seven target fields:
  - `revenue`
  - `operating_profit`
  - `net_profit`
  - `operating_cash_flow`
  - `cash`
  - `total_assets`
  - `total_liabilities`
- A small set of negative controls such as:
  - `Revenue growth`
  - `Deferred revenue`
  - `Net assets`
  - selected ratio or margin labels
- A promotion step that upgrades only the most stable cases into hard regressions

Out of scope:

- Requiring all seven target fields to become hard CI gates immediately
- Expanding Ollama fallback beyond row-label normalization and table-kind disambiguation
- Replacing deterministic extraction, registry mapping, or canonical resolution with LLM output

## Positioning

This work is not a new extraction path. It is an evaluation-and-promotion layer for the existing limited semantic fallback.

The purpose is to make fallback quality visible on realistic report labels without turning model variance into the single blocking condition for continuing Task 6.

## Sample Strategy

### Primary Sources

Use annual-report labels drawn from:

- CN annual primary anchor:
  - `601919/annual/2024_年度报告.pdf`
- CN annual reference set:
  - `600519/annual/2024_年度报告.pdf`
  - `600519/annual/2025_年度报告.pdf`
  - `601919/annual/2025_年度报告.pdf`
  - `688008/annual/2024_年度报告.pdf`
  - `688008/annual/2025_年度报告.pdf`
- HK annual anchors:
  - `02498/annual/2022_annual_en.pdf`
  - `06862/annual/2024_annual_en.pdf`
  - `09987/annual/2024_annual_en.pdf`

### Probe Set

The evaluation set should include:

- At least one positive case for each of the seven target fields
- At least one negative control for each major confusion family:
  - growth/rate labels
  - deferred/contract liability style labels
  - equity/net-assets style labels
  - margin/ratio style labels

The probe set may contain normalized label snippets derived from real reports rather than dynamically extracting fresh labels from PDFs during test execution.

## Test Layers

### 1. Evaluation Layer

Create or extend a real-Ollama evaluation test that:

- uses the local Ollama endpoint
- runs the probe dataset against the live fallback service
- records expected label, actual label, and confidence
- verifies that every target field has at least one realistic probe case

This layer exists to measure capability and surface weak spots. It is not intended to become a brittle all-green gate for every probe.

### 2. Promotion Layer

Select a smaller subset of probe cases for hard regression tests:

- 2-4 stable positive cases
- 1-2 stable negative controls

These promoted cases must:

- pass reliably on the local supported model
- exercise real fallback behavior
- remain narrow enough to avoid flakiness

## Promotion Criteria

A probe case is eligible for promotion when:

- it has a clear expected outcome
- it has passed repeatedly on the supported local model
- it represents a meaningful business distinction
- it is not overly dependent on one issuer-specific wording quirk

The promotion set should prefer semantically representative labels over issuer-specific edge phrasing.

## Verification Expectations

This phase is complete when:

1. the seven target fields are all represented in the real-report evaluation dataset
2. the evaluation run produces a clear picture of stable vs unstable cases
3. a small promotion set has been added as hard integration regressions
4. promoted regressions pass on the supported local Ollama model

## Exit Condition For Returning To Task 6

Task 6 may resume after:

- the evaluation dataset covers all seven target fields
- the promotion set is established and passing
- fallback behavior is no longer judged only by smoke tests

This phase does not require every real-report probe to become a hard gate. It requires enough validated signal to continue Task 6 with informed confidence.
