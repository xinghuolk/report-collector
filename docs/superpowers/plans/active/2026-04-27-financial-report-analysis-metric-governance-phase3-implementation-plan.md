# Financial Report Analysis Metric Governance Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Phase 3 durable metric lifecycle registry with concept-level lifecycle entries, append-only decisions, explicit candidate links, and deterministic internal reads.

**Architecture:** Keep Phase 3 internal. Add domain contracts under `models/governance.py`, storage records and repository methods in the existing SQLAlchemy repository, and a focused lifecycle service under `services/`. Phase 2 review decisions remain review annotations only; lifecycle reads must never synthesize state from `metric_governance_decisions`.

**Tech Stack:** Python 3.12, dataclasses, SQLAlchemy ORM, pytest, Ruff, existing `financial_report_analysis` package patterns.

---

## File Structure

Create:

- `financial-report-analysis/src/financial_report_analysis/services/metric_lifecycle.py`
  - Service and validation layer for lifecycle entries, decisions, links, and deterministic reads.
- `financial-report-analysis/tests/unit/test_metric_lifecycle.py`
  - Domain contract and export tests.
- `financial-report-analysis/tests/unit/test_metric_lifecycle_repository.py`
  - SQLAlchemy repository round-trip and deterministic ordering tests.
- `financial-report-analysis/tests/unit/test_metric_lifecycle_service.py`
  - Service validation, no-state, target validation, and Phase 2 no-fallback tests.

Modify:

- `financial-report-analysis/src/financial_report_analysis/models/governance.py`
  - Add lifecycle types and dataclasses.
- `financial-report-analysis/src/financial_report_analysis/models/__init__.py`
  - Publicly export lifecycle contracts.
- `financial-report-analysis/src/financial_report_analysis/storage/models.py`
  - Add lifecycle entry, decision, and candidate link tables.
- `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
  - Add lifecycle repository methods and record converters.
- `financial-report-analysis/tests/unit/test_public_exports.py`
  - Assert public lifecycle contracts are exported.

Do not modify:

- extraction behavior;
- canonical promotion behavior;
- P5 dataset or Turtle output behavior;
- `/api/v1/metric-governance/*` API contracts;
- Ollama or semantic fallback behavior.

## Shared Naming Contract

Use these names consistently across all tasks:

```python
MetricLifecycleStatus = Literal[
    "provisional",
    "approved_custom",
    "mapped_to_standard",
    "deprecated",
    "blacklisted",
]

MetricLifecycleAction = Literal[
    "approve_custom",
    "map_to_standard",
    "deprecate",
    "blacklist",
]
```

Use these status transitions:

```python
ACTION_STATUS_MAP = {
    "approve_custom": "approved_custom",
    "map_to_standard": "mapped_to_standard",
    "deprecate": "deprecated",
    "blacklist": "blacklisted",
}
```

Use stable latest-decision ordering:

```text
effective_at desc, created_at desc, decision_id desc
```

Use stable history ordering:

```text
effective_at asc, created_at asc, decision_id asc
```

## Task 1: Add Lifecycle Domain Contracts

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/models/governance.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/models/__init__.py`
- Modify: `financial-report-analysis/tests/unit/test_public_exports.py`
- Create: `financial-report-analysis/tests/unit/test_metric_lifecycle.py`

- [ ] **Step 1: Write failing domain tests**

Create `financial-report-analysis/tests/unit/test_metric_lifecycle.py`:

```python
from __future__ import annotations

from financial_report_analysis.models import (
    MetricLifecycleCandidateLink,
    MetricLifecycleConceptIdentity,
    MetricLifecycleDecision,
    MetricLifecycleEntry,
    MetricLifecycleState,
)


def _identity() -> MetricLifecycleConceptIdentity:
    return MetricLifecycleConceptIdentity(
        issuer_id="HK_09987",
        metric_id="custom::ifrs::ecommerce::balance-sheet::root::customer-deposits",
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type="balance_sheet",
        accounting_standard="IFRS",
        industry_slug="ecommerce",
        parent_metric_id=None,
    )


def test_lifecycle_entry_keeps_concept_identity_and_status() -> None:
    entry = MetricLifecycleEntry(
        lifecycle_entry_id="lifecycle:001",
        concept=_identity(),
        current_status="provisional",
        mapped_standard_metric_id=None,
        created_at="2026-04-27T10:00:00+00:00",
        updated_at="2026-04-27T10:00:00+00:00",
        created_by="reviewer@example.com",
    )

    assert entry.concept.issuer_id == "HK_09987"
    assert entry.current_status == "provisional"
    assert entry.mapped_standard_metric_id is None


def test_lifecycle_decision_records_transition_and_evidence() -> None:
    decision = MetricLifecycleDecision(
        decision_id="decision:001",
        lifecycle_entry_id="lifecycle:001",
        action="map_to_standard",
        previous_status="provisional",
        new_status="mapped_to_standard",
        target_metric_id="accounts_receiv",
        actor="reviewer@example.com",
        reason="Matches standard accounts receivable.",
        evidence_bundle_id="bundle:001",
        source_review_item_id="review:001",
        source_artifact_id="artifact:001",
        created_at="2026-04-27T10:01:00+00:00",
        effective_at="2026-04-27T10:01:00+00:00",
    )

    assert decision.action == "map_to_standard"
    assert decision.previous_status == "provisional"
    assert decision.new_status == "mapped_to_standard"
    assert decision.target_metric_id == "accounts_receiv"


def test_candidate_link_bridges_review_item_to_lifecycle_entry() -> None:
    link = MetricLifecycleCandidateLink(
        candidate_link_id="link:001",
        lifecycle_entry_id="lifecycle:001",
        review_item_id="review:001",
        artifact_id="artifact:001",
        issuer_id="HK_09987",
        fiscal_year=2025,
        report_type="annual",
        candidate_metric_id="custom::ifrs::ecommerce::balance-sheet::root::customer-deposits",
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type="balance_sheet",
        evidence_bundle_id="bundle:001",
        created_at="2026-04-27T10:02:00+00:00",
        created_by="reviewer@example.com",
    )

    assert link.review_item_id == "review:001"
    assert link.lifecycle_entry_id == "lifecycle:001"


def test_lifecycle_state_can_represent_missing_state() -> None:
    state = MetricLifecycleState(
        entry=None,
        latest_decision=None,
        candidate_link=None,
        decision_history=(),
    )

    assert state.entry is None
    assert state.latest_decision is None
    assert state.decision_history == ()
```

- [ ] **Step 2: Run failing domain tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle.py -q
```

Expected: fail because lifecycle types are not exported.

- [ ] **Step 3: Add lifecycle dataclasses**

Modify `financial-report-analysis/src/financial_report_analysis/models/governance.py`.
Add imports and dataclasses near existing metric-governance review models:

```python
MetricLifecycleStatus = Literal[
    "provisional",
    "approved_custom",
    "mapped_to_standard",
    "deprecated",
    "blacklisted",
]
MetricLifecycleAction = Literal[
    "approve_custom",
    "map_to_standard",
    "deprecate",
    "blacklist",
]


@dataclass(frozen=True, slots=True)
class MetricLifecycleConceptIdentity:
    issuer_id: str
    metric_id: str
    raw_label: str
    normalized_label: str | None
    statement_type: str
    accounting_standard: str
    industry_slug: str
    parent_metric_id: str | None


@dataclass(frozen=True, slots=True)
class MetricLifecycleEntry:
    lifecycle_entry_id: str
    concept: MetricLifecycleConceptIdentity
    current_status: MetricLifecycleStatus
    mapped_standard_metric_id: str | None
    created_at: str
    updated_at: str
    created_by: str | None = None


@dataclass(frozen=True, slots=True)
class MetricLifecycleDecision:
    decision_id: str
    lifecycle_entry_id: str
    action: MetricLifecycleAction
    previous_status: MetricLifecycleStatus
    new_status: MetricLifecycleStatus
    target_metric_id: str | None
    actor: str
    reason: str
    evidence_bundle_id: str | None
    source_review_item_id: str | None
    source_artifact_id: str | None
    created_at: str
    effective_at: str


@dataclass(frozen=True, slots=True)
class MetricLifecycleCandidateLink:
    candidate_link_id: str
    lifecycle_entry_id: str
    review_item_id: str
    artifact_id: str
    issuer_id: str
    fiscal_year: int
    report_type: str
    candidate_metric_id: str
    raw_label: str
    normalized_label: str | None
    statement_type: str
    evidence_bundle_id: str | None
    created_at: str
    created_by: str | None = None


@dataclass(frozen=True, slots=True)
class MetricLifecycleState:
    entry: MetricLifecycleEntry | None
    latest_decision: MetricLifecycleDecision | None
    candidate_link: MetricLifecycleCandidateLink | None
    decision_history: tuple[MetricLifecycleDecision, ...]
```

- [ ] **Step 4: Export lifecycle contracts**

Modify `financial-report-analysis/src/financial_report_analysis/models/__init__.py`.
Import and add to `__all__`:

```python
MetricLifecycleAction,
MetricLifecycleCandidateLink,
MetricLifecycleConceptIdentity,
MetricLifecycleDecision,
MetricLifecycleEntry,
MetricLifecycleState,
MetricLifecycleStatus,
```

- [ ] **Step 5: Add public export assertions**

Modify `financial-report-analysis/tests/unit/test_public_exports.py`.
Add to `test_table_semantic_models_are_publicly_exported` or create a focused
test:

```python
def test_metric_lifecycle_models_are_publicly_exported() -> None:
    assert models.MetricLifecycleConceptIdentity is not None
    assert models.MetricLifecycleEntry is not None
    assert models.MetricLifecycleDecision is not None
    assert models.MetricLifecycleCandidateLink is not None
    assert models.MetricLifecycleState is not None
```

- [ ] **Step 6: Run tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle.py tests/unit/test_public_exports.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/models/governance.py \
  financial-report-analysis/src/financial_report_analysis/models/__init__.py \
  financial-report-analysis/tests/unit/test_metric_lifecycle.py \
  financial-report-analysis/tests/unit/test_public_exports.py
git commit -m "feat: add metric lifecycle domain contracts"
```

## Task 2: Add Lifecycle Storage And Repository Methods

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/storage/models.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Create: `financial-report-analysis/tests/unit/test_metric_lifecycle_repository.py`

- [ ] **Step 1: Write failing repository tests**

Create `financial-report-analysis/tests/unit/test_metric_lifecycle_repository.py`:

```python
from __future__ import annotations

from financial_report_analysis.models import (
    MetricLifecycleCandidateLink,
    MetricLifecycleConceptIdentity,
    MetricLifecycleDecision,
    MetricLifecycleEntry,
)
from financial_report_analysis.storage.database import (
    create_sqlite_engine,
    initialize_database,
)
from financial_report_analysis.storage.repositories import SqlAlchemyP5ArtifactRepository


def _concept() -> MetricLifecycleConceptIdentity:
    return MetricLifecycleConceptIdentity(
        issuer_id="HK_09987",
        metric_id="custom::ifrs::ecommerce::balance-sheet::root::customer-deposits",
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type="balance_sheet",
        accounting_standard="IFRS",
        industry_slug="ecommerce",
        parent_metric_id=None,
    )


def _entry(entry_id: str = "lifecycle:001") -> MetricLifecycleEntry:
    return MetricLifecycleEntry(
        lifecycle_entry_id=entry_id,
        concept=_concept(),
        current_status="provisional",
        mapped_standard_metric_id=None,
        created_at="2026-04-27T10:00:00+00:00",
        updated_at="2026-04-27T10:00:00+00:00",
        created_by="reviewer@example.com",
    )


def _decision(
    decision_id: str,
    *,
    effective_at: str = "2026-04-27T10:01:00+00:00",
    created_at: str = "2026-04-27T10:01:00+00:00",
) -> MetricLifecycleDecision:
    return MetricLifecycleDecision(
        decision_id=decision_id,
        lifecycle_entry_id="lifecycle:001",
        action="map_to_standard",
        previous_status="provisional",
        new_status="mapped_to_standard",
        target_metric_id="accounts_receiv",
        actor="reviewer@example.com",
        reason="Matches standard accounts receivable.",
        evidence_bundle_id="bundle:001",
        source_review_item_id="review:001",
        source_artifact_id="artifact:001",
        created_at=created_at,
        effective_at=effective_at,
    )


def _link(link_id: str = "link:001") -> MetricLifecycleCandidateLink:
    return MetricLifecycleCandidateLink(
        candidate_link_id=link_id,
        lifecycle_entry_id="lifecycle:001",
        review_item_id="review:001",
        artifact_id="artifact:001",
        issuer_id="HK_09987",
        fiscal_year=2025,
        report_type="annual",
        candidate_metric_id=_concept().metric_id,
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type="balance_sheet",
        evidence_bundle_id="bundle:001",
        created_at="2026-04-27T10:02:00+00:00",
        created_by="reviewer@example.com",
    )


def _repository(tmp_path):
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    return SqlAlchemyP5ArtifactRepository(engine)


def test_repository_round_trips_lifecycle_entry_by_id_and_concept(tmp_path) -> None:
    repository = _repository(tmp_path)
    entry = _entry()

    assert repository.save_metric_lifecycle_entry(entry) == entry.lifecycle_entry_id
    assert repository.load_metric_lifecycle_entry(entry.lifecycle_entry_id) == entry
    assert repository.load_metric_lifecycle_entry_by_concept(_concept()) == entry
    assert repository.load_metric_lifecycle_entry("missing") is None


def test_repository_round_trips_lifecycle_candidate_link(tmp_path) -> None:
    repository = _repository(tmp_path)
    entry = _entry()
    link = _link()

    repository.save_metric_lifecycle_entry(entry)
    assert repository.save_metric_lifecycle_candidate_link(link) == link.candidate_link_id

    assert repository.load_metric_lifecycle_candidate_link("review:001") == link
    assert repository.list_metric_lifecycle_candidate_links(entry.lifecycle_entry_id) == (link,)
    assert repository.load_metric_lifecycle_candidate_link("missing") is None


def test_repository_orders_lifecycle_decisions_deterministically(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.save_metric_lifecycle_entry(_entry())
    earlier = _decision("decision:001", effective_at="2026-04-27T10:00:00+00:00")
    same_effective_lower_created = _decision(
        "decision:002",
        effective_at="2026-04-27T10:05:00+00:00",
        created_at="2026-04-27T10:05:00+00:00",
    )
    latest_by_id = _decision(
        "decision:003",
        effective_at="2026-04-27T10:05:00+00:00",
        created_at="2026-04-27T10:05:00+00:00",
    )

    repository.save_metric_lifecycle_decision(latest_by_id)
    repository.save_metric_lifecycle_decision(earlier)
    repository.save_metric_lifecycle_decision(same_effective_lower_created)

    assert repository.list_metric_lifecycle_decisions("lifecycle:001") == (
        earlier,
        same_effective_lower_created,
        latest_by_id,
    )
    assert repository.load_latest_metric_lifecycle_decision("lifecycle:001") == latest_by_id
```

- [ ] **Step 2: Run failing repository tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle_repository.py -q
```

Expected: fail because storage records and repository methods do not exist.

- [ ] **Step 3: Add SQLAlchemy records**

Modify `financial-report-analysis/src/financial_report_analysis/storage/models.py`.
Add records after `MetricGovernanceDecisionRecord`:

```python
class MetricLifecycleEntryRecord(Base):
    __tablename__ = "metric_lifecycle_entries"
    __table_args__ = (
        UniqueConstraint(
            "issuer_id",
            "metric_id",
            "statement_type",
            "accounting_standard",
            "industry_slug",
            "parent_metric_id",
            name="uq_metric_lifecycle_entries_concept",
        ),
    )

    lifecycle_entry_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    issuer_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    metric_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    raw_label: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_label: Mapped[str | None] = mapped_column(String(255))
    statement_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    accounting_standard: Mapped[str] = mapped_column(String(32), nullable=False)
    industry_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_metric_id: Mapped[str | None] = mapped_column(String(128), index=True)
    current_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    mapped_standard_metric_id: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(128))
```

Also add:

```python
class MetricLifecycleDecisionRecord(Base):
    __tablename__ = "metric_lifecycle_decisions"

    decision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    lifecycle_entry_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("metric_lifecycle_entries.lifecycle_entry_id"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_metric_id: Mapped[str | None] = mapped_column(String(128), index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_bundle_id: Mapped[str | None] = mapped_column(String(128), index=True)
    source_review_item_id: Mapped[str | None] = mapped_column(String(128), index=True)
    source_artifact_id: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    effective_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
```

Also add:

```python
class MetricLifecycleCandidateLinkRecord(Base):
    __tablename__ = "metric_lifecycle_candidate_links"
    __table_args__ = (
        UniqueConstraint(
            "review_item_id",
            name="uq_metric_lifecycle_candidate_links_review_item",
        ),
    )

    candidate_link_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    lifecycle_entry_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("metric_lifecycle_entries.lifecycle_entry_id"),
        nullable=False,
        index=True,
    )
    review_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    artifact_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    issuer_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    candidate_metric_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    raw_label: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_label: Mapped[str | None] = mapped_column(String(255))
    statement_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evidence_bundle_id: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(128))
```

- [ ] **Step 4: Add repository imports and methods**

Modify `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`.
Import lifecycle domain classes and storage records.

Add methods on `SqlAlchemyP5ArtifactRepository` near existing
`save_metric_governance_decision`:

```python
def save_metric_lifecycle_entry(self, entry: MetricLifecycleEntry) -> str: ...
def load_metric_lifecycle_entry(self, lifecycle_entry_id: str) -> MetricLifecycleEntry | None: ...
def load_metric_lifecycle_entry_by_concept(
    self, concept: MetricLifecycleConceptIdentity
) -> MetricLifecycleEntry | None: ...
def save_metric_lifecycle_decision(self, decision: MetricLifecycleDecision) -> str: ...
def list_metric_lifecycle_decisions(
    self, lifecycle_entry_id: str
) -> tuple[MetricLifecycleDecision, ...]: ...
def load_latest_metric_lifecycle_decision(
    self, lifecycle_entry_id: str
) -> MetricLifecycleDecision | None: ...
def save_metric_lifecycle_candidate_link(
    self, link: MetricLifecycleCandidateLink
) -> str: ...
def load_metric_lifecycle_candidate_link(
    self, review_item_id: str
) -> MetricLifecycleCandidateLink | None: ...
def list_metric_lifecycle_candidate_links(
    self, lifecycle_entry_id: str
) -> tuple[MetricLifecycleCandidateLink, ...]: ...
```

Use SQLAlchemy `select(...)`, `Session(self.engine)`, and converter helpers
matching the existing `MetricGovernanceDecisionRecord` pattern.

When saving an entry, use `session.merge(record)` so repeated upserts update the
current denormalized state.

Decision history ordering must be:

```python
.order_by(
    MetricLifecycleDecisionRecord.effective_at,
    MetricLifecycleDecisionRecord.created_at,
    MetricLifecycleDecisionRecord.decision_id,
)
```

Latest ordering must be:

```python
.order_by(
    MetricLifecycleDecisionRecord.effective_at.desc(),
    MetricLifecycleDecisionRecord.created_at.desc(),
    MetricLifecycleDecisionRecord.decision_id.desc(),
)
```

- [ ] **Step 5: Run repository tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle_repository.py -q
```

Expected: pass.

- [ ] **Step 6: Run storage model smoke tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_storage_models.py tests/unit/test_metric_governance_decision_repository.py tests/unit/test_metric_lifecycle_repository.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/storage/models.py \
  financial-report-analysis/src/financial_report_analysis/storage/repositories.py \
  financial-report-analysis/tests/unit/test_metric_lifecycle_repository.py
git commit -m "feat: persist metric lifecycle registry"
```

## Task 3: Add Lifecycle Service And Validation

**Files:**

- Create: `financial-report-analysis/src/financial_report_analysis/services/metric_lifecycle.py`
- Create: `financial-report-analysis/tests/unit/test_metric_lifecycle_service.py`

- [ ] **Step 1: Write failing service tests**

Create `financial-report-analysis/tests/unit/test_metric_lifecycle_service.py`:

```python
from __future__ import annotations

from dataclasses import replace

import pytest

from financial_report_analysis.models import (
    MetricGovernanceDecision,
    MetricLifecycleCandidateLink,
    MetricLifecycleConceptIdentity,
    MetricLifecycleDecision,
    MetricLifecycleEntry,
)
from financial_report_analysis.registries import load_metric_registry
from financial_report_analysis.services.metric_lifecycle import (
    MetricLifecycleError,
    MetricLifecycleService,
)


class _Repository:
    def __init__(self) -> None:
        self.entries: dict[str, MetricLifecycleEntry] = {}
        self.decisions: dict[str, list[MetricLifecycleDecision]] = {}
        self.links: dict[str, MetricLifecycleCandidateLink] = {}
        self.phase2_decision: MetricGovernanceDecision | None = None

    def save_metric_lifecycle_entry(self, entry: MetricLifecycleEntry) -> str:
        self.entries[entry.lifecycle_entry_id] = entry
        return entry.lifecycle_entry_id

    def load_metric_lifecycle_entry(self, lifecycle_entry_id: str) -> MetricLifecycleEntry | None:
        return self.entries.get(lifecycle_entry_id)

    def load_metric_lifecycle_entry_by_concept(
        self, concept: MetricLifecycleConceptIdentity
    ) -> MetricLifecycleEntry | None:
        for entry in self.entries.values():
            if entry.concept == concept:
                return entry
        return None

    def save_metric_lifecycle_decision(self, decision: MetricLifecycleDecision) -> str:
        self.decisions.setdefault(decision.lifecycle_entry_id, []).append(decision)
        return decision.decision_id

    def list_metric_lifecycle_decisions(
        self, lifecycle_entry_id: str
    ) -> tuple[MetricLifecycleDecision, ...]:
        return tuple(
            sorted(
                self.decisions.get(lifecycle_entry_id, []),
                key=lambda item: (item.effective_at, item.created_at, item.decision_id),
            )
        )

    def load_latest_metric_lifecycle_decision(
        self, lifecycle_entry_id: str
    ) -> MetricLifecycleDecision | None:
        decisions = self.list_metric_lifecycle_decisions(lifecycle_entry_id)
        return decisions[-1] if decisions else None

    def save_metric_lifecycle_candidate_link(
        self, link: MetricLifecycleCandidateLink
    ) -> str:
        self.links[link.review_item_id] = link
        return link.candidate_link_id

    def load_metric_lifecycle_candidate_link(
        self, review_item_id: str
    ) -> MetricLifecycleCandidateLink | None:
        return self.links.get(review_item_id)

    def list_metric_lifecycle_candidate_links(
        self, lifecycle_entry_id: str
    ) -> tuple[MetricLifecycleCandidateLink, ...]:
        return tuple(
            link
            for link in self.links.values()
            if link.lifecycle_entry_id == lifecycle_entry_id
        )

    def load_latest_metric_governance_decision(self, review_item_id: str):
        return self.phase2_decision


def _concept() -> MetricLifecycleConceptIdentity:
    return MetricLifecycleConceptIdentity(
        issuer_id="HK_09987",
        metric_id="custom::ifrs::ecommerce::balance-sheet::root::customer-deposits",
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type="balance_sheet",
        accounting_standard="IFRS",
        industry_slug="ecommerce",
        parent_metric_id=None,
    )


def _entry() -> MetricLifecycleEntry:
    return MetricLifecycleEntry(
        lifecycle_entry_id="lifecycle:001",
        concept=_concept(),
        current_status="provisional",
        mapped_standard_metric_id=None,
        created_at="2026-04-27T10:00:00+00:00",
        updated_at="2026-04-27T10:00:00+00:00",
        created_by="reviewer@example.com",
    )


def _link() -> MetricLifecycleCandidateLink:
    return MetricLifecycleCandidateLink(
        candidate_link_id="link:001",
        lifecycle_entry_id="lifecycle:001",
        review_item_id="review:001",
        artifact_id="artifact:001",
        issuer_id="HK_09987",
        fiscal_year=2025,
        report_type="annual",
        candidate_metric_id=_concept().metric_id,
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type="balance_sheet",
        evidence_bundle_id="bundle:001",
        created_at="2026-04-27T10:02:00+00:00",
        created_by="reviewer@example.com",
    )


def test_service_records_lifecycle_decision_and_updates_entry_state() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())

    decision = service.record_decision(
        lifecycle_entry_id="lifecycle:001",
        action="approve_custom",
        actor="reviewer@example.com",
        reason="Valid custom metric.",
        evidence_bundle_id="bundle:001",
        source_review_item_id="review:001",
        source_artifact_id="artifact:001",
        created_at="2026-04-27T10:03:00+00:00",
        effective_at="2026-04-27T10:03:00+00:00",
    )

    assert decision.previous_status == "provisional"
    assert decision.new_status == "approved_custom"
    assert repository.entries["lifecycle:001"].current_status == "approved_custom"


def test_service_validates_map_to_standard_target() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())

    decision = service.record_decision(
        lifecycle_entry_id="lifecycle:001",
        action="map_to_standard",
        target_metric_id="accounts_receiv",
        actor="reviewer@example.com",
        reason="Maps to receivables.",
        evidence_bundle_id="bundle:001",
        source_review_item_id="review:001",
        source_artifact_id="artifact:001",
        created_at="2026-04-27T10:03:00+00:00",
        effective_at="2026-04-27T10:03:00+00:00",
    )

    assert decision.new_status == "mapped_to_standard"
    assert repository.entries["lifecycle:001"].mapped_standard_metric_id == "accounts_receiv"


def test_service_rejects_invalid_target_and_wrong_target_shape() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())

    with pytest.raises(MetricLifecycleError, match="target_metric_id is required"):
        service.record_decision(
            lifecycle_entry_id="lifecycle:001",
            action="map_to_standard",
            actor="reviewer@example.com",
            reason="Missing target.",
            evidence_bundle_id="bundle:001",
            created_at="2026-04-27T10:03:00+00:00",
            effective_at="2026-04-27T10:03:00+00:00",
        )

    with pytest.raises(MetricLifecycleError, match="target_metric_id is not allowed"):
        service.record_decision(
            lifecycle_entry_id="lifecycle:001",
            action="approve_custom",
            target_metric_id="accounts_receiv",
            actor="reviewer@example.com",
            reason="Wrong shape.",
            evidence_bundle_id="bundle:001",
            created_at="2026-04-27T10:03:00+00:00",
            effective_at="2026-04-27T10:03:00+00:00",
        )

    with pytest.raises(MetricLifecycleError, match="supported standard metric"):
        service.record_decision(
            lifecycle_entry_id="lifecycle:001",
            action="map_to_standard",
            target_metric_id="custom_metric",
            actor="reviewer@example.com",
            reason="Unsupported target.",
            evidence_bundle_id="bundle:001",
            created_at="2026-04-27T10:03:00+00:00",
            effective_at="2026-04-27T10:03:00+00:00",
        )


def test_service_reads_state_by_concept_and_candidate_link() -> None:
    repository = _Repository()
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())
    repository.save_metric_lifecycle_entry(_entry())
    repository.save_metric_lifecycle_candidate_link(_link())

    state_by_concept = service.load_state_by_concept(_concept())
    state_by_review = service.load_state_by_review_item("review:001")

    assert state_by_concept.entry is not None
    assert state_by_review.entry == state_by_concept.entry
    assert state_by_review.candidate_link is not None


def test_phase2_decision_alone_does_not_create_lifecycle_state() -> None:
    repository = _Repository()
    repository.phase2_decision = MetricGovernanceDecision(
        decision_id="phase2:001",
        review_item_id="review:001",
        artifact_id="artifact:001",
        issuer_id="HK_09987",
        fiscal_year=2025,
        report_type="annual",
        metric_id=_concept().metric_id,
        raw_label="Customer deposits",
        normalized_label="customer deposits",
        statement_type="balance_sheet",
        evidence_bundle_id="bundle:001",
        decision_type="map_to_standard",
        target_metric_id="accounts_receiv",
        reason="Advisory only.",
        actor="reviewer@example.com",
        created_at="2026-04-27T10:00:00+00:00",
    )
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())

    assert service.load_state_by_review_item("review:001").entry is None
    assert service.load_state_by_concept(_concept()).entry is None
```

- [ ] **Step 2: Run failing service tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle_service.py -q
```

Expected: fail because `services.metric_lifecycle` does not exist.

- [ ] **Step 3: Implement lifecycle service**

Create `financial-report-analysis/src/financial_report_analysis/services/metric_lifecycle.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from financial_report_analysis.models import (
    MetricLifecycleAction,
    MetricLifecycleCandidateLink,
    MetricLifecycleConceptIdentity,
    MetricLifecycleDecision,
    MetricLifecycleEntry,
    MetricLifecycleState,
    MetricLifecycleStatus,
)
from financial_report_analysis.registries import MetricMappingRegistry, load_metric_registry

_ACTION_STATUS: dict[MetricLifecycleAction, MetricLifecycleStatus] = {
    "approve_custom": "approved_custom",
    "map_to_standard": "mapped_to_standard",
    "deprecate": "deprecated",
    "blacklist": "blacklisted",
}


class MetricLifecycleError(ValueError):
    pass


class MetricLifecycleRepository(Protocol):
    def save_metric_lifecycle_entry(self, entry: MetricLifecycleEntry) -> str: ...
    def load_metric_lifecycle_entry(self, lifecycle_entry_id: str) -> MetricLifecycleEntry | None: ...
    def load_metric_lifecycle_entry_by_concept(
        self, concept: MetricLifecycleConceptIdentity
    ) -> MetricLifecycleEntry | None: ...
    def save_metric_lifecycle_decision(self, decision: MetricLifecycleDecision) -> str: ...
    def list_metric_lifecycle_decisions(
        self, lifecycle_entry_id: str
    ) -> tuple[MetricLifecycleDecision, ...]: ...
    def load_latest_metric_lifecycle_decision(
        self, lifecycle_entry_id: str
    ) -> MetricLifecycleDecision | None: ...
    def save_metric_lifecycle_candidate_link(
        self, link: MetricLifecycleCandidateLink
    ) -> str: ...
    def load_metric_lifecycle_candidate_link(
        self, review_item_id: str
    ) -> MetricLifecycleCandidateLink | None: ...
    def list_metric_lifecycle_candidate_links(
        self, lifecycle_entry_id: str
    ) -> tuple[MetricLifecycleCandidateLink, ...]: ...


class MetricLifecycleService:
    def __init__(
        self,
        repository: MetricLifecycleRepository,
        *,
        metric_registry: MetricMappingRegistry | None = None,
    ) -> None:
        self._repository = repository
        self._metric_registry = metric_registry or load_metric_registry()

    def create_or_load_entry(
        self,
        *,
        concept: MetricLifecycleConceptIdentity,
        actor: str | None,
        created_at: str | None = None,
    ) -> MetricLifecycleEntry:
        existing = self._repository.load_metric_lifecycle_entry_by_concept(concept)
        if existing is not None:
            return existing
        timestamp = created_at or _utc_now()
        entry = MetricLifecycleEntry(
            lifecycle_entry_id=f"metric-lifecycle:{uuid4().hex}",
            concept=concept,
            current_status="provisional",
            mapped_standard_metric_id=None,
            created_at=timestamp,
            updated_at=timestamp,
            created_by=actor,
        )
        self._repository.save_metric_lifecycle_entry(entry)
        return entry

    def link_candidate(self, link: MetricLifecycleCandidateLink) -> str:
        if self._repository.load_metric_lifecycle_entry(link.lifecycle_entry_id) is None:
            raise MetricLifecycleError("lifecycle entry does not exist")
        return self._repository.save_metric_lifecycle_candidate_link(link)

    def record_decision(
        self,
        *,
        lifecycle_entry_id: str,
        action: MetricLifecycleAction,
        actor: str,
        reason: str,
        target_metric_id: str | None = None,
        evidence_bundle_id: str | None = None,
        source_review_item_id: str | None = None,
        source_artifact_id: str | None = None,
        created_at: str | None = None,
        effective_at: str | None = None,
    ) -> MetricLifecycleDecision:
        entry = self._repository.load_metric_lifecycle_entry(lifecycle_entry_id)
        if entry is None:
            raise MetricLifecycleError("lifecycle entry does not exist")
        self._validate_decision_shape(
            action=action,
            target_metric_id=target_metric_id,
            actor=actor,
            reason=reason,
            evidence_bundle_id=evidence_bundle_id,
            source_review_item_id=source_review_item_id,
        )
        timestamp = created_at or _utc_now()
        effective = effective_at or timestamp
        new_status = _ACTION_STATUS[action]
        decision = MetricLifecycleDecision(
            decision_id=f"metric-lifecycle-decision:{uuid4().hex}",
            lifecycle_entry_id=lifecycle_entry_id,
            action=action,
            previous_status=entry.current_status,
            new_status=new_status,
            target_metric_id=target_metric_id,
            actor=actor,
            reason=reason,
            evidence_bundle_id=evidence_bundle_id,
            source_review_item_id=source_review_item_id,
            source_artifact_id=source_artifact_id,
            created_at=timestamp,
            effective_at=effective,
        )
        self._repository.save_metric_lifecycle_decision(decision)
        self._repository.save_metric_lifecycle_entry(
            MetricLifecycleEntry(
                lifecycle_entry_id=entry.lifecycle_entry_id,
                concept=entry.concept,
                current_status=new_status,
                mapped_standard_metric_id=(
                    target_metric_id if new_status == "mapped_to_standard" else None
                ),
                created_at=entry.created_at,
                updated_at=timestamp,
                created_by=entry.created_by,
            )
        )
        return decision

    def load_state_by_concept(
        self,
        concept: MetricLifecycleConceptIdentity,
    ) -> MetricLifecycleState:
        entry = self._repository.load_metric_lifecycle_entry_by_concept(concept)
        return self._state_for_entry(entry, candidate_link=None)

    def load_state_by_review_item(self, review_item_id: str) -> MetricLifecycleState:
        link = self._repository.load_metric_lifecycle_candidate_link(review_item_id)
        if link is None:
            return MetricLifecycleState(
                entry=None,
                latest_decision=None,
                candidate_link=None,
                decision_history=(),
            )
        entry = self._repository.load_metric_lifecycle_entry(link.lifecycle_entry_id)
        return self._state_for_entry(entry, candidate_link=link)

    def _state_for_entry(
        self,
        entry: MetricLifecycleEntry | None,
        *,
        candidate_link: MetricLifecycleCandidateLink | None,
    ) -> MetricLifecycleState:
        if entry is None:
            return MetricLifecycleState(
                entry=None,
                latest_decision=None,
                candidate_link=candidate_link,
                decision_history=(),
            )
        history = self._repository.list_metric_lifecycle_decisions(
            entry.lifecycle_entry_id
        )
        latest = self._repository.load_latest_metric_lifecycle_decision(
            entry.lifecycle_entry_id
        )
        return MetricLifecycleState(
            entry=entry,
            latest_decision=latest,
            candidate_link=candidate_link,
            decision_history=history,
        )

    def _validate_decision_shape(
        self,
        *,
        action: MetricLifecycleAction,
        target_metric_id: str | None,
        actor: str,
        reason: str,
        evidence_bundle_id: str | None,
        source_review_item_id: str | None,
    ) -> None:
        if not actor.strip():
            raise MetricLifecycleError("actor is required")
        if not reason.strip():
            raise MetricLifecycleError("reason is required")
        if evidence_bundle_id is None and source_review_item_id is None:
            raise MetricLifecycleError("evidence_bundle_id or source_review_item_id is required")
        if action == "map_to_standard":
            if target_metric_id is None:
                raise MetricLifecycleError("target_metric_id is required")
            if self._metric_registry.get_metric_definition(target_metric_id) is None:
                raise MetricLifecycleError("target_metric_id must be a supported standard metric")
            return
        if target_metric_id is not None:
            raise MetricLifecycleError("target_metric_id is not allowed")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
```

- [ ] **Step 4: Run service tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle_service.py -q
```

Expected: pass.

- [ ] **Step 5: Run domain/repository/service tests together**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle.py tests/unit/test_metric_lifecycle_repository.py tests/unit/test_metric_lifecycle_service.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/services/metric_lifecycle.py \
  financial-report-analysis/tests/unit/test_metric_lifecycle_service.py
git commit -m "feat: add metric lifecycle service"
```

## Task 4: Prove Phase 2 Decisions Do Not Become Lifecycle State

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_metric_lifecycle_service.py`

This task is a guardrail task. It should not add external API behavior.

- [ ] **Step 1: Add explicit no-backfill regression**

Append this test to
`financial-report-analysis/tests/unit/test_metric_lifecycle_service.py`:

```python
def test_candidate_link_is_required_even_when_concept_identity_matches_phase2_decision() -> None:
    repository = _Repository()
    entry = _entry()
    repository.save_metric_lifecycle_entry(entry)
    repository.phase2_decision = MetricGovernanceDecision(
        decision_id="phase2:001",
        review_item_id="review:001",
        artifact_id="artifact:001",
        issuer_id="HK_09987",
        fiscal_year=2025,
        report_type="annual",
        metric_id=entry.concept.metric_id,
        raw_label=entry.concept.raw_label,
        normalized_label=entry.concept.normalized_label,
        statement_type=entry.concept.statement_type,
        evidence_bundle_id="bundle:001",
        decision_type="map_to_standard",
        target_metric_id="accounts_receiv",
        reason="Advisory only.",
        actor="reviewer@example.com",
        created_at="2026-04-27T10:00:00+00:00",
    )
    service = MetricLifecycleService(repository, metric_registry=load_metric_registry())

    state = service.load_state_by_review_item("review:001")

    assert state.entry is None
    assert service.load_state_by_concept(entry.concept).entry == entry
```

- [ ] **Step 2: Run the focused test**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle_service.py::test_candidate_link_is_required_even_when_concept_identity_matches_phase2_decision -q
```

Expected: pass. If it fails, fix `MetricLifecycleService.load_state_by_review_item`
so it only resolves via `load_metric_lifecycle_candidate_link`.

- [ ] **Step 3: Run lifecycle service tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle_service.py -q
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add financial-report-analysis/tests/unit/test_metric_lifecycle_service.py
git commit -m "test: guard metric lifecycle against phase2 decision fallback"
```

## Task 5: Close-Out Regression And Lint

**Files:**

- Modify only files needed to fix issues discovered by verification.

- [ ] **Step 1: Run Phase 3 focused tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle.py \
  tests/unit/test_metric_lifecycle_repository.py \
  tests/unit/test_metric_lifecycle_service.py \
  tests/unit/test_metric_governance_decision_repository.py \
  tests/unit/test_metric_governance_review_service.py \
  tests/unit/test_public_exports.py -q
```

Expected: pass.

- [ ] **Step 2: Run storage and P5 no-behavior-change tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_storage_models.py \
  tests/unit/test_storage_repository.py \
  tests/unit/test_p5_recompute.py \
  tests/unit/test_fact_pipeline.py::test_fact_pipeline_blocks_provisional_custom_metrics_from_canonical_promotion \
  tests/unit/test_fact_pipeline.py::test_report_adapter_excludes_provisional_custom_metrics_from_key_facts \
  tests/unit/test_fact_pipeline.py::test_report_adapter_does_not_build_ttm_from_provisional_custom_metrics -q
```

Expected: pass. These tests prove Phase 1 guardrails and P5 recompute behavior
remain stable.

- [ ] **Step 3: Run Ruff**

Run:

```bash
cd financial-report-analysis
uv run ruff check src/financial_report_analysis/models/governance.py \
  src/financial_report_analysis/models/__init__.py \
  src/financial_report_analysis/services/metric_lifecycle.py \
  src/financial_report_analysis/storage/models.py \
  src/financial_report_analysis/storage/repositories.py \
  tests/unit/test_metric_lifecycle.py \
  tests/unit/test_metric_lifecycle_repository.py \
  tests/unit/test_metric_lifecycle_service.py \
  tests/unit/test_public_exports.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Fix verification failures narrowly**

If a focused test or Ruff fails, fix only the Phase 3 files touched by this
plan unless the failure proves an existing contract has to be updated. Do not
change extraction, fallback, P5 output, Turtle output, or public API behavior.

- [ ] **Step 5: Commit verification fixes if any**

If Step 4 changed files:

```bash
git add <changed-files>
git commit -m "fix: stabilize metric lifecycle phase3"
```

If Step 4 did not change files, do not create an empty commit.

## Final Review Checklist

- [ ] `MetricLifecycleEntry`, `MetricLifecycleDecision`, and
  `MetricLifecycleCandidateLink` exist and are exported.
- [ ] SQLAlchemy storage can persist and read lifecycle entries, decisions, and
  candidate links.
- [ ] Lifecycle service validates all four actions.
- [ ] `map_to_standard` accepts only supported standard metric ids.
- [ ] Latest lifecycle state ordering is deterministic by `effective_at`,
  `created_at`, then `decision_id`.
- [ ] Phase 2 `metric_governance_decisions` are never used as lifecycle state.
- [ ] No external lifecycle API was added.
- [ ] No recompute, P5 dataset, Turtle, extraction, Ollama, or semantic fallback
  behavior changed.

## Execution Handoff

Recommended execution mode: `superpowers:subagent-driven-development`.

Use one fresh implementer subagent per task. After each task:

1. run the task's focused verification;
2. dispatch a spec-compliance reviewer;
3. dispatch a code-quality reviewer;
4. fix review findings before moving to the next task.
