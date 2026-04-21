# Financial Report Analysis Cross-Statement Conflict Governance Design

## 1. Goal

This design defines the conflict-governance layer needed after broader
three-statement metric coverage is introduced.

The objective is to ensure that broader registry coverage does not degrade the
quality of canonical facts by allowing summary tables, ratio rows, or
secondary disclosures to outrank main-statement facts.

## 2. Why This Step Exists

As the supported metric set expands, conflict risk rises in four places:

- main statements versus key-metrics tables
- main rows versus ratio/growth rows
- primary disclosures versus management summaries
- overlapping aliases with different provenance quality

Existing main-table preference is a strong start, but broader coverage needs a
more explicit design boundary around conflict handling.

## 3. In Scope

This step is in scope for:

- statement-aware source ranking
- summary/growth/ratio suppression where broader aliases create collisions
- provenance-aware candidate and canonical promotion
- conflict-resolution behavior for overlapping metric families

## 4. Out Of Scope

This step is out of scope for:

- redesigning the full canonical ranking model from scratch
- derived fact synthesis
- cross-document consolidation logic

## 5. Main Risks

### 5.1 Over-Correction

Conflict handling must not become so aggressive that it suppresses legitimate
main-statement facts that happen to have weaker titles or noisier labels.

### 5.2 Provenance Drift

If wider coverage is resolved only by ranking heuristics, fact provenance may
stop reflecting the actual semantic source. This design must keep provenance
explicit and stable.

## 6. Verification Strategy

This step should verify:

- summary-table rows do not outrank main-statement rows
- ratio and growth rows are not promoted into core fact metrics
- provenance remains correct when table semantics affect metric selection
- broader metric support does not regress existing covered facts

## 7. Deliverable Definition

This design is complete when:

- broader three-statement coverage does not materially worsen false-positive
  promotion
- main-statement preference remains stable on supported sample sets
- fact-level provenance remains aligned with the semantic path actually used
