# Financial Report Analysis Metric Governance Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 2 of metric governance so persisted provisional metric candidates can be listed, inspected, and annotated with lightweight mapping decisions through a dedicated API surface.

**Architecture:** Keep Phase 1 guardrails unchanged and build a separate read/write governance surface on top of persisted extracted artifacts. Use a lightweight SQLAlchemy-backed decision record plus a focused review service that assembles provisional review items from artifact payloads and hydrates the latest decision at read time.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy, pytest, existing `financial_report_analysis` storage repository and API runtime.

---

## File Structure

Create:

- `financial-report-analysis/tests/unit/test_metric_governance_review_service.py`
  - Unit coverage for provisional review item assembly and latest-decision annotation.
- `financial-report-analysis/tests/unit/test_metric_governance_decision_repository.py`
  - Unit coverage for DB decision persistence and latest-decision lookup.
- `financial-report-analysis/tests/integration/test_metric_governance_api.py`
  - End-to-end API contract coverage for list/detail/write flows.

Modify:

- `financial-report-analysis/src/financial_report_analysis/models/governance.py`
  - Add Phase 2 decision and review-item dataclasses.
- `financial-report-analysis/src/financial_report_analysis/models/__init__.py`
  - Export the new governance dataclasses.
- `financial-report-analysis/src/financial_report_analysis/storage/models.py`
  - Add `MetricGovernanceDecisionRecord`.
- `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
  - Add save/list/latest decision methods and read helpers for governance review.
- `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
  - Add request/response models for governance review list/detail/write.
- `financial-report-analysis/src/financial_report_analysis/api/routes.py`
  - Add governance review list/detail/write endpoints.
- `financial-report-analysis/src/financial_report_analysis/api/runtime.py`
  - Only if needed for typing helpers; avoid behavior changes.

Create or modify if the codebase benefits from a focused service file:

- `financial-report-analysis/src/financial_report_analysis/services/metric_governance_review.py`
  - Assemble provisional review items from persisted artifacts and annotate them
    with latest decisions.

Do not modify:

- `financial-report-analysis/src/financial_report_analysis/services/fact_normalizer.py`
- `financial-report-analysis/src/financial_report_analysis/services/conflict_resolver.py`
- `financial-report-analysis/src/financial_report_analysis/services/validation_service.py`
- `financial-report-analysis/src/financial_report_analysis/adapters/report_adapter.py`
- P5/Turtle assembly logic

## Task 1: Add Phase 2 Governance Domain Contracts

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/models/governance.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/models/__init__.py`
- Test: `financial-report-analysis/tests/unit/test_metric_governance_review_service.py`

- [ ] **Step 1: Write the failing contract tests**

Create `financial-report-analysis/tests/unit/test_metric_governance_review_service.py` with the contract-level tests first:

```python
from __future__ import annotations

from financial_report_analysis.models.governance import (
    MetricGovernanceDecision,
    MetricGovernanceDecisionAnnotation,
    MetricGovernanceReviewItem,
)


def test_review_item_exposes_latest_decision_annotation() -> None:
    decision = MetricGovernanceDecision(
        decision_id="decision-1",
        review_item_id="CN_601919_2025:candidate-1",
        artifact_id="CN_601919_2025",
        issuer_id="CN_601919",
        fiscal_year=2025,
        report_type="annual",
        metric_id="custom::cn::general::income-statement::root::contract-assets",
        raw_label="Contract assets",
        normalized_label="contract assets",
        statement_type="income_statement",
        evidence_bundle_id="bundle-1",
        decision_type="map_to_standard",
        target_metric_id="accounts_receiv",
        reason="maps to supported working capital metric",
        actor="reviewer@example.com",
        created_at="2026-04-27T12:00:00+00:00",
    )

    item = MetricGovernanceReviewItem(
        review_item_id="CN_601919_2025:candidate-1",
        artifact_id="CN_601919_2025",
        issuer_id="CN_601919",
        fiscal_year=2025,
        report_type="annual",
        metric_id=decision.metric_id,
        raw_label=decision.raw_label,
        normalized_label=decision.normalized_label,
        statement_type=decision.statement_type,
        candidate_value=125.0,
        period_label="FY2025",
        source_page=88,
        source_table_id="table-7",
        evidence_bundle_id="bundle-1",
        metric_governance={
            "registry_status": "provisional",
            "metric_namespace": "custom",
            "review_required": True,
            "auto_analysis_allowed": False,
            "governance_reason": "provisional_custom_metric",
        },
        latest_decision=MetricGovernanceDecisionAnnotation.from_decision(decision),
    )

    assert item.latest_decision is not None
    assert item.latest_decision.decision_type == "map_to_standard"
    assert item.latest_decision.target_metric_id == "accounts_receiv"


def test_decision_annotation_from_keep_provisional_omits_target_metric() -> None:
    decision = MetricGovernanceDecision(
        decision_id="decision-2",
        review_item_id="CN_601919_2025:candidate-2",
        artifact_id="CN_601919_2025",
        issuer_id="CN_601919",
        fiscal_year=2025,
        report_type="annual",
        metric_id="custom::cn::general::income-statement::root::loyalty-liabilities",
        raw_label="Customer loyalty liabilities",
        normalized_label="customer loyalty liabilities",
        statement_type="income_statement",
        evidence_bundle_id="bundle-2",
        decision_type="keep_provisional",
        target_metric_id=None,
        reason="not a supported standard metric",
        actor="reviewer@example.com",
        created_at="2026-04-27T12:05:00+00:00",
    )

    annotation = MetricGovernanceDecisionAnnotation.from_decision(decision)

    assert annotation.decision_type == "keep_provisional"
    assert annotation.target_metric_id is None
```

- [ ] **Step 2: Run the unit test and confirm failure**

Run:

```bash
cd /Users/keli/source/report-collector/financial-report-analysis
uv run pytest tests/unit/test_metric_governance_review_service.py -q
```

Expected: failure because `MetricGovernanceDecision`, `MetricGovernanceDecisionAnnotation`, and `MetricGovernanceReviewItem` do not exist yet.

- [ ] **Step 3: Add the minimal domain dataclasses**

Append these definitions to `financial-report-analysis/src/financial_report_analysis/models/governance.py`:

```python
MetricGovernanceDecisionType = Literal["keep_provisional", "map_to_standard"]


@dataclass(frozen=True, slots=True)
class MetricGovernanceDecision:
    decision_id: str
    review_item_id: str
    artifact_id: str
    issuer_id: str
    fiscal_year: int
    report_type: str
    metric_id: str
    raw_label: str
    normalized_label: str | None
    statement_type: str
    evidence_bundle_id: str | None
    decision_type: MetricGovernanceDecisionType
    target_metric_id: str | None
    reason: str
    actor: str
    created_at: str


@dataclass(frozen=True, slots=True)
class MetricGovernanceDecisionAnnotation:
    decision_type: MetricGovernanceDecisionType
    target_metric_id: str | None
    reason: str
    actor: str
    created_at: str

    @classmethod
    def from_decision(
        cls,
        decision: MetricGovernanceDecision,
    ) -> "MetricGovernanceDecisionAnnotation":
        return cls(
            decision_type=decision.decision_type,
            target_metric_id=decision.target_metric_id,
            reason=decision.reason,
            actor=decision.actor,
            created_at=decision.created_at,
        )


@dataclass(frozen=True, slots=True)
class MetricGovernanceReviewItem:
    review_item_id: str
    artifact_id: str
    issuer_id: str
    fiscal_year: int
    report_type: str
    metric_id: str
    raw_label: str
    normalized_label: str | None
    statement_type: str
    candidate_value: float | int | None
    period_label: str | None
    source_page: int | None
    source_table_id: str | None
    evidence_bundle_id: str | None
    metric_governance: dict[str, object]
    latest_decision: MetricGovernanceDecisionAnnotation | None = None
```

Add the new exports to `financial-report-analysis/src/financial_report_analysis/models/__init__.py`:

```python
from financial_report_analysis.models.governance import (
    MetricGovernanceDecision,
    MetricGovernanceDecisionAnnotation,
    MetricGovernanceDecisionType,
    MetricGovernanceReviewItem,
)
```

And add them to `__all__`:

```python
    "MetricGovernanceDecision",
    "MetricGovernanceDecisionAnnotation",
    "MetricGovernanceDecisionType",
    "MetricGovernanceReviewItem",
```

- [ ] **Step 4: Re-run the unit test**

Run:

```bash
cd /Users/keli/source/report-collector/financial-report-analysis
uv run pytest tests/unit/test_metric_governance_review_service.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/keli/source/report-collector
git add financial-report-analysis/src/financial_report_analysis/models/governance.py \
        financial-report-analysis/src/financial_report_analysis/models/__init__.py \
        financial-report-analysis/tests/unit/test_metric_governance_review_service.py
git commit -m "feat: add metric governance review contracts"
```

## Task 2: Add Lightweight Decision Persistence

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/storage/models.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Test: `financial-report-analysis/tests/unit/test_metric_governance_decision_repository.py`

- [ ] **Step 1: Write the failing repository tests**

Create `financial-report-analysis/tests/unit/test_metric_governance_decision_repository.py`:

```python
from __future__ import annotations

from pathlib import Path

from financial_report_analysis.models.governance import MetricGovernanceDecision
from financial_report_analysis.storage.database import create_sqlite_engine, initialize_database
from financial_report_analysis.storage.repositories import SqlAlchemyP5ArtifactRepository


def _decision(*, decision_id: str, review_item_id: str, decision_type: str) -> MetricGovernanceDecision:
    return MetricGovernanceDecision(
        decision_id=decision_id,
        review_item_id=review_item_id,
        artifact_id="CN_601919_2025",
        issuer_id="CN_601919",
        fiscal_year=2025,
        report_type="annual",
        metric_id="custom::cn::general::income-statement::root::contract-assets",
        raw_label="Contract assets",
        normalized_label="contract assets",
        statement_type="income_statement",
        evidence_bundle_id="bundle-1",
        decision_type=decision_type,  # type: ignore[arg-type]
        target_metric_id="accounts_receiv" if decision_type == "map_to_standard" else None,
        reason="review decision",
        actor="reviewer@example.com",
        created_at="2026-04-27T12:00:00+00:00",
    )


def test_repository_round_trips_metric_governance_decisions(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)

    decision = _decision(
        decision_id="decision-1",
        review_item_id="CN_601919_2025:candidate-1",
        decision_type="map_to_standard",
    )

    repository.save_metric_governance_decision(decision)

    loaded = repository.list_metric_governance_decisions(decision.review_item_id)
    assert loaded == (decision,)


def test_repository_returns_latest_decision_for_review_item(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "storage.db")
    initialize_database(engine)
    repository = SqlAlchemyP5ArtifactRepository(engine)
    review_item_id = "CN_601919_2025:candidate-1"

    first = _decision(
        decision_id="decision-1",
        review_item_id=review_item_id,
        decision_type="keep_provisional",
    )
    second = _decision(
        decision_id="decision-2",
        review_item_id=review_item_id,
        decision_type="map_to_standard",
    )

    repository.save_metric_governance_decision(first)
    repository.save_metric_governance_decision(second)

    latest = repository.load_latest_metric_governance_decision(review_item_id)

    assert latest is not None
    assert latest.decision_id == "decision-2"
    assert latest.decision_type == "map_to_standard"
```

- [ ] **Step 2: Run the repository tests and confirm failure**

Run:

```bash
cd /Users/keli/source/report-collector/financial-report-analysis
uv run pytest tests/unit/test_metric_governance_decision_repository.py -q
```

Expected: failure because the repository methods and storage table do not exist yet.

- [ ] **Step 3: Add the DB record and repository methods**

Add this record to `financial-report-analysis/src/financial_report_analysis/storage/models.py`:

```python
class MetricGovernanceDecisionRecord(Base):
    __tablename__ = "metric_governance_decisions"

    decision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    review_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    artifact_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    issuer_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    metric_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    raw_label: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_label: Mapped[str | None] = mapped_column(Text)
    statement_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_bundle_id: Mapped[str | None] = mapped_column(String(128))
    decision_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_metric_id: Mapped[str | None] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
```

Import `MetricGovernanceDecision` and `MetricGovernanceDecisionRecord` into
`financial-report-analysis/src/financial_report_analysis/storage/repositories.py`,
then add:

```python
    def save_metric_governance_decision(
        self,
        decision: MetricGovernanceDecision,
    ) -> str:
        with Session(self.engine) as session:
            record = MetricGovernanceDecisionRecord(
                decision_id=decision.decision_id,
                review_item_id=decision.review_item_id,
                artifact_id=decision.artifact_id,
                issuer_id=decision.issuer_id,
                fiscal_year=decision.fiscal_year,
                report_type=decision.report_type,
                metric_id=decision.metric_id,
                raw_label=decision.raw_label,
                normalized_label=decision.normalized_label,
                statement_type=decision.statement_type,
                evidence_bundle_id=decision.evidence_bundle_id,
                decision_type=decision.decision_type,
                target_metric_id=decision.target_metric_id,
                reason=decision.reason,
                actor=decision.actor,
                created_at=decision.created_at,
            )
            session.add(record)
            session.commit()
        return decision.decision_id

    def list_metric_governance_decisions(
        self,
        review_item_id: str,
    ) -> tuple[MetricGovernanceDecision, ...]:
        with Session(self.engine) as session:
            records = tuple(
                session.scalars(
                    select(MetricGovernanceDecisionRecord)
                    .where(MetricGovernanceDecisionRecord.review_item_id == review_item_id)
                    .order_by(
                        MetricGovernanceDecisionRecord.created_at,
                        MetricGovernanceDecisionRecord.decision_id,
                    )
                ).all()
            )
        return tuple(self._metric_governance_decision_from_record(record) for record in records)

    def load_latest_metric_governance_decision(
        self,
        review_item_id: str,
    ) -> MetricGovernanceDecision | None:
        decisions = self.list_metric_governance_decisions(review_item_id)
        return decisions[-1] if decisions else None

    @staticmethod
    def _metric_governance_decision_from_record(
        record: MetricGovernanceDecisionRecord,
    ) -> MetricGovernanceDecision:
        return MetricGovernanceDecision(
            decision_id=record.decision_id,
            review_item_id=record.review_item_id,
            artifact_id=record.artifact_id,
            issuer_id=record.issuer_id,
            fiscal_year=record.fiscal_year,
            report_type=record.report_type,
            metric_id=record.metric_id,
            raw_label=record.raw_label,
            normalized_label=record.normalized_label,
            statement_type=record.statement_type,
            evidence_bundle_id=record.evidence_bundle_id,
            decision_type=record.decision_type,  # type: ignore[arg-type]
            target_metric_id=record.target_metric_id,
            reason=record.reason,
            actor=record.actor,
            created_at=record.created_at,
        )
```

Keep the persistence semantics append-only:

- each write creates a new row;
- `decision_id` must be globally unique, for example `uuid4().hex`;
- repeated submissions for the same `review_item_id` are represented as later
  decision records rather than updates to an existing row;
- `load_latest_metric_governance_decision()` defines "latest" by
  `(created_at, decision_id)` ordering so same-timestamp inserts remain
  deterministic.

- [ ] **Step 4: Re-run the repository tests**

Run:

```bash
cd /Users/keli/source/report-collector/financial-report-analysis
uv run pytest tests/unit/test_metric_governance_decision_repository.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/keli/source/report-collector
git add financial-report-analysis/src/financial_report_analysis/storage/models.py \
        financial-report-analysis/src/financial_report_analysis/storage/repositories.py \
        financial-report-analysis/tests/unit/test_metric_governance_decision_repository.py
git commit -m "feat: persist metric governance review decisions"
```

## Task 3: Add the Review Assembly Service

**Files:**

- Create: `financial-report-analysis/src/financial_report_analysis/services/metric_governance_review.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Test: `financial-report-analysis/tests/unit/test_metric_governance_review_service.py`

- [ ] **Step 1: Expand the service test with provisional-item assembly**

Append these tests to `financial-report-analysis/tests/unit/test_metric_governance_review_service.py`:

```python
from pathlib import Path

from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.services.metric_governance_review import MetricGovernanceReviewService


def _entry(tmp_path: Path) -> P5ManifestEntry:
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    return P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
        company_name="测试公司",
        report_language="zh",
    )


def _artifact(entry: P5ManifestEntry) -> P5ExtractedArtifact:
    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={"document_id": str(entry.pdf_path), "pdf_path": str(entry.pdf_path)},
        document_metadata={},
        candidate_facts=(
            {
                "fact_id": "candidate-1",
                "metric_id": "custom::cn::general::income-statement::root::contract-assets",
                "raw_label": "Contract assets",
                "normalized_label": "contract assets",
                "statement_type": "income_statement",
                "value": 125.0,
                "evidence_bundle_id": "bundle-1",
                "extensions": {
                    "table_id": "table-7",
                    "page_number": 88,
                    "period_label": "FY2025",
                    "metric_governance": {
                        "registry_status": "provisional",
                        "metric_namespace": "custom",
                        "review_required": True,
                        "auto_analysis_allowed": False,
                        "governance_reason": "provisional_custom_metric",
                    },
                },
            },
            {
                "fact_id": "candidate-2",
                "metric_id": "revenue",
                "raw_label": "Revenue",
                "statement_type": "income_statement",
                "value": 500.0,
                "extensions": {
                    "metric_governance": {
                        "registry_status": "standard",
                        "metric_namespace": "standard",
                        "review_required": False,
                        "auto_analysis_allowed": True,
                        "governance_reason": "standard_metric",
                    },
                },
            },
        ),
        canonical_facts=(),
        derived_facts=(),
        validation_report={"overall_status": "review_required", "issues": []},
        review_packets=(),
        quality_gate="review",
        missing_status={},
        created_at="2026-04-27T12:00:00+00:00",
    )


class _StubRepository:
    def __init__(self, artifact: P5ExtractedArtifact, decision: MetricGovernanceDecision | None = None) -> None:
        self._artifact = artifact
        self._decision = decision

    def list_extracted_artifact_ids(self, issuer_id: str | None = None, fiscal_year: int | None = None) -> tuple[str, ...]:
        return (self._artifact.artifact_id,)

    def load_extracted_artifact(self, artifact_id: str) -> P5ExtractedArtifact:
        assert artifact_id == self._artifact.artifact_id
        return self._artifact

    def load_latest_metric_governance_decision(self, review_item_id: str) -> MetricGovernanceDecision | None:
        return self._decision


def test_service_lists_only_provisional_review_items(tmp_path: Path) -> None:
    artifact = _artifact(_entry(tmp_path))
    service = MetricGovernanceReviewService(_StubRepository(artifact))

    items = service.list_review_items(issuer_id="CN_601919")

    assert len(items) == 1
    assert items[0].metric_id.startswith("custom::")
    assert items[0].raw_label == "Contract assets"


def test_service_hydrates_latest_decision_annotation(tmp_path: Path) -> None:
    artifact = _artifact(_entry(tmp_path))
    decision = MetricGovernanceDecision(
        decision_id="decision-1",
        review_item_id=f"{artifact.artifact_id}:candidate-1",
        artifact_id=artifact.artifact_id,
        issuer_id="CN_601919",
        fiscal_year=2025,
        report_type="annual",
        metric_id="custom::cn::general::income-statement::root::contract-assets",
        raw_label="Contract assets",
        normalized_label="contract assets",
        statement_type="income_statement",
        evidence_bundle_id="bundle-1",
        decision_type="map_to_standard",
        target_metric_id="accounts_receiv",
        reason="maps to supported receivables field",
        actor="reviewer@example.com",
        created_at="2026-04-27T12:05:00+00:00",
    )
    service = MetricGovernanceReviewService(_StubRepository(artifact, decision))

    item = service.get_review_item(f"{artifact.artifact_id}:candidate-1")

    assert item is not None
    assert item.latest_decision is not None
    assert item.latest_decision.target_metric_id == "accounts_receiv"
```

- [ ] **Step 2: Run the service test and confirm failure**

Run:

```bash
cd /Users/keli/source/report-collector/financial-report-analysis
uv run pytest tests/unit/test_metric_governance_review_service.py -q
```

Expected: failure because `MetricGovernanceReviewService` does not exist.

- [ ] **Step 3: Implement the review service**

Create `financial-report-analysis/src/financial_report_analysis/services/metric_governance_review.py`:

```python
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol

from financial_report_analysis.models.governance import (
    MetricGovernanceDecisionAnnotation,
    MetricGovernanceReviewItem,
)
from financial_report_analysis.p5.models import P5ExtractedArtifact


class MetricGovernanceReviewRepository(Protocol):
    def list_extracted_artifact_ids(
        self,
        issuer_id: str | None = None,
        fiscal_year: int | None = None,
    ) -> tuple[str, ...]: ...

    def load_extracted_artifact(self, artifact_id: str) -> P5ExtractedArtifact: ...

    def load_latest_metric_governance_decision(
        self,
        review_item_id: str,
    ): ...


class MetricGovernanceReviewService:
    def __init__(self, repository: MetricGovernanceReviewRepository) -> None:
        self._repository = repository

    def list_review_items(
        self,
        *,
        issuer_id: str | None = None,
        fiscal_year: int | None = None,
    ) -> list[MetricGovernanceReviewItem]:
        items: list[MetricGovernanceReviewItem] = []
        for artifact_id in self._repository.list_extracted_artifact_ids(
            issuer_id=issuer_id,
            fiscal_year=fiscal_year,
        ):
            artifact = self._repository.load_extracted_artifact(artifact_id)
            items.extend(self._review_items_from_artifact(artifact))
        return items

    def get_review_item(self, review_item_id: str) -> MetricGovernanceReviewItem | None:
        artifact_id, _, _candidate_id = review_item_id.partition(":")
        artifact = self._repository.load_extracted_artifact(artifact_id)
        for item in self._review_items_from_artifact(artifact):
            if item.review_item_id == review_item_id:
                return item
        return None

    def _review_items_from_artifact(
        self,
        artifact: P5ExtractedArtifact,
    ) -> list[MetricGovernanceReviewItem]:
        items: list[MetricGovernanceReviewItem] = []
        for candidate in artifact.candidate_facts:
            extensions = _extensions(candidate)
            governance = _governance(extensions)
            if governance.get("registry_status") != "provisional":
                continue
            fact_id = str(candidate.get("fact_id", ""))
            review_item_id = f"{artifact.artifact_id}:{fact_id}"
            latest = self._repository.load_latest_metric_governance_decision(review_item_id)
            items.append(
                MetricGovernanceReviewItem(
                    review_item_id=review_item_id,
                    artifact_id=artifact.artifact_id,
                    issuer_id=artifact.manifest_entry.issuer_id,
                    fiscal_year=artifact.manifest_entry.fiscal_year,
                    report_type=artifact.manifest_entry.report_type,
                    metric_id=str(candidate.get("metric_id", "")),
                    raw_label=str(candidate.get("raw_label", "")),
                    normalized_label=_optional_text(candidate.get("normalized_label")),
                    statement_type=str(candidate.get("statement_type", "")),
                    candidate_value=candidate.get("value"),  # type: ignore[arg-type]
                    period_label=_optional_text(extensions.get("period_label")),
                    source_page=_optional_int(extensions.get("page_number")),
                    source_table_id=_optional_text(extensions.get("table_id")),
                    evidence_bundle_id=_optional_text(candidate.get("evidence_bundle_id")),
                    metric_governance=governance,
                    latest_decision=(
                        MetricGovernanceDecisionAnnotation.from_decision(latest)
                        if latest is not None
                        else None
                    ),
                )
            )
        return items


def _extensions(candidate: Mapping[str, object]) -> dict[str, object]:
    raw = candidate.get("extensions")
    return dict(raw) if isinstance(raw, dict) else {}


def _governance(extensions: Mapping[str, object]) -> dict[str, object]:
    raw = extensions.get("metric_governance")
    return dict(raw) if isinstance(raw, dict) else {}


def _optional_text(value: object) -> str | None:
    return str(value) if isinstance(value, str) and value.strip() else None


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int) else None
```

- [ ] **Step 4: Re-run the service tests**

Run:

```bash
cd /Users/keli/source/report-collector/financial-report-analysis
uv run pytest tests/unit/test_metric_governance_review_service.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/keli/source/report-collector
git add financial-report-analysis/src/financial_report_analysis/services/metric_governance_review.py \
        financial-report-analysis/tests/unit/test_metric_governance_review_service.py
git commit -m "feat: assemble metric governance review items"
```

## Task 4: Expose Phase 2 Governance API

**Files:**

- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Test: `financial-report-analysis/tests/integration/test_metric_governance_api.py`

- [ ] **Step 1: Write the failing API tests**

Create `financial-report-analysis/tests/integration/test_metric_governance_api.py`:

```python
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from financial_report_analysis.api.app import create_app
from financial_report_analysis.api.runtime import build_api_runtime
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.storage.historical_ingestion import HistoricalIngestionService


def _entry(tmp_path: Path) -> P5ManifestEntry:
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    return P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
        company_name="测试公司",
        report_language="zh",
    )


def _artifact(entry: P5ManifestEntry) -> P5ExtractedArtifact:
    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={"document_id": str(entry.pdf_path), "pdf_path": str(entry.pdf_path)},
        document_metadata={},
        candidate_facts=(
            {
                "fact_id": "candidate-1",
                "metric_id": "custom::cn::general::income-statement::root::contract-assets",
                "raw_label": "Contract assets",
                "normalized_label": "contract assets",
                "statement_type": "income_statement",
                "value": 125.0,
                "evidence_bundle_id": "bundle-1",
                "extensions": {
                    "table_id": "table-7",
                    "page_number": 88,
                    "period_label": "FY2025",
                    "metric_governance": {
                        "registry_status": "provisional",
                        "metric_namespace": "custom",
                        "review_required": True,
                        "auto_analysis_allowed": False,
                        "governance_reason": "provisional_custom_metric",
                    },
                },
            },
        ),
        canonical_facts=(),
        derived_facts=(),
        validation_report={"overall_status": "review_required", "issues": []},
        review_packets=(),
        quality_gate="review",
        missing_status={},
        created_at="2026-04-27T12:00:00+00:00",
    )


def test_metric_governance_review_list_and_write_flow(tmp_path: Path) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))

    list_response = client.get("/api/v1/metric-governance/review-items", params={"issuer_id": "CN_601919"})

    assert list_response.status_code == 200
    payload = list_response.json()
    assert len(payload["items"]) == 1
    review_item_id = payload["items"][0]["review_item_id"]

    write_response = client.post(
        "/api/v1/metric-governance/review-items/decision",
        json={
            "review_item_id": review_item_id,
            "decision_type": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "maps to supported receivables metric",
            "actor": "reviewer@example.com",
        },
    )

    assert write_response.status_code == 200
    assert write_response.json()["decision"]["decision_type"] == "map_to_standard"

    detail_response = client.get(f"/api/v1/metric-governance/review-items/{review_item_id}")

    assert detail_response.status_code == 200
    assert detail_response.json()["latest_decision"]["target_metric_id"] == "accounts_receiv"


def test_metric_governance_rejects_unknown_review_item(tmp_path: Path) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    client = TestClient(create_app(runtime=runtime))

    response = client.post(
        "/api/v1/metric-governance/review-items/decision",
        json={
            "review_item_id": "missing:item",
            "decision_type": "keep_provisional",
            "reason": "not enough evidence",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run the API tests and confirm failure**

Run:

```bash
cd /Users/keli/source/report-collector/financial-report-analysis
uv run pytest tests/integration/test_metric_governance_api.py -q
```

Expected: failure because the schemas and routes do not exist yet.

- [ ] **Step 3: Add schemas and routes**

Add the new Pydantic models to `financial-report-analysis/src/financial_report_analysis/api/schemas.py`:

```python
from typing import Literal


class MetricGovernanceDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_item_id: str
    decision_type: Literal["keep_provisional", "map_to_standard"]
    target_metric_id: str | None = None
    reason: str
    actor: str

    @model_validator(mode="after")
    def validate_decision_shape(self) -> "MetricGovernanceDecisionRequest":
        if self.decision_type == "map_to_standard" and not self.target_metric_id:
            raise ValueError(
                "target_metric_id is required for decision_type='map_to_standard'"
            )
        if (
            self.decision_type == "keep_provisional"
            and self.target_metric_id is not None
        ):
            raise ValueError(
                "target_metric_id is not allowed for decision_type='keep_provisional'"
            )
        return self


class MetricGovernanceDecisionAnnotationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_type: str
    target_metric_id: str | None = None
    reason: str
    actor: str
    created_at: str


class MetricGovernanceReviewItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_item_id: str
    artifact_id: str
    issuer_id: str
    fiscal_year: int
    report_type: str
    metric_id: str
    raw_label: str
    normalized_label: str | None = None
    statement_type: str
    candidate_value: int | float | None = None
    period_label: str | None = None
    source_page: int | None = None
    source_table_id: str | None = None
    evidence_bundle_id: str | None = None
    metric_governance: dict[str, Any]
    latest_decision: MetricGovernanceDecisionAnnotationResponse | None = None


class MetricGovernanceReviewListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MetricGovernanceReviewItemResponse]


class MetricGovernanceDecisionWriteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: MetricGovernanceDecisionAnnotationResponse
    review_item: MetricGovernanceReviewItemResponse
```

Add these routes to `financial-report-analysis/src/financial_report_analysis/api/routes.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

from financial_report_analysis.models.governance import MetricGovernanceDecision
from financial_report_analysis.registries.metric_mapping import load_metric_registry
from financial_report_analysis.services.metric_governance_review import MetricGovernanceReviewService
```

```python
@router.get(
    "/api/v1/metric-governance/review-items",
    response_model=MetricGovernanceReviewListResponse,
)
def list_metric_governance_review_items(
    request: Request,
    issuer_id: str | None = None,
    fiscal_year: int | None = None,
) -> MetricGovernanceReviewListResponse:
    repository = _require_storage_repository(request)
    service = MetricGovernanceReviewService(repository)
    items = service.list_review_items(issuer_id=issuer_id, fiscal_year=fiscal_year)
    return MetricGovernanceReviewListResponse(
        items=[_metric_governance_item_to_response(item) for item in items]
    )


@router.get(
    "/api/v1/metric-governance/review-items/{review_item_id}",
    response_model=MetricGovernanceReviewItemResponse,
)
def get_metric_governance_review_item(
    review_item_id: str,
    request: Request,
) -> MetricGovernanceReviewItemResponse:
    repository = _require_storage_repository(request)
    service = MetricGovernanceReviewService(repository)
    item = service.get_review_item(review_item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review item not found")
    return _metric_governance_item_to_response(item)


@router.post(
    "/api/v1/metric-governance/review-items/decision",
    response_model=MetricGovernanceDecisionWriteResponse,
)
def write_metric_governance_decision(
    payload: MetricGovernanceDecisionRequest,
    request: Request,
) -> MetricGovernanceDecisionWriteResponse:
    repository = _require_storage_repository(request)
    service = MetricGovernanceReviewService(repository)
    item = service.get_review_item(payload.review_item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review item not found")
    if payload.decision_type == "map_to_standard":
        target_metric_id = payload.target_metric_id or ""
        mapping_registry = load_metric_registry()
        if mapping_registry.get_metric_definition(target_metric_id) is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="target_metric_id must be a supported standard metric",
            )
    decision = MetricGovernanceDecision(
        decision_id=uuid4().hex,
        review_item_id=item.review_item_id,
        artifact_id=item.artifact_id,
        issuer_id=item.issuer_id,
        fiscal_year=item.fiscal_year,
        report_type=item.report_type,
        metric_id=item.metric_id,
        raw_label=item.raw_label,
        normalized_label=item.normalized_label,
        statement_type=item.statement_type,
        evidence_bundle_id=item.evidence_bundle_id,
        decision_type=payload.decision_type,  # type: ignore[arg-type]
        target_metric_id=payload.target_metric_id,
        reason=payload.reason,
        actor=payload.actor,
        created_at=datetime.now(UTC).isoformat(),
    )
    repository.save_metric_governance_decision(decision)
    refreshed = service.get_review_item(item.review_item_id)
    assert refreshed is not None
    return MetricGovernanceDecisionWriteResponse(
        decision=_metric_governance_annotation_to_response(refreshed.latest_decision),
        review_item=_metric_governance_item_to_response(refreshed),
    )
```

Add the two private response builders near the other `_..._to_response` helpers:

```python
def _metric_governance_annotation_to_response(
    annotation,
) -> MetricGovernanceDecisionAnnotationResponse:
    assert annotation is not None
    return MetricGovernanceDecisionAnnotationResponse(
        decision_type=annotation.decision_type,
        target_metric_id=annotation.target_metric_id,
        reason=annotation.reason,
        actor=annotation.actor,
        created_at=annotation.created_at,
    )


def _metric_governance_item_to_response(
    item,
) -> MetricGovernanceReviewItemResponse:
    return MetricGovernanceReviewItemResponse(
        review_item_id=item.review_item_id,
        artifact_id=item.artifact_id,
        issuer_id=item.issuer_id,
        fiscal_year=item.fiscal_year,
        report_type=item.report_type,
        metric_id=item.metric_id,
        raw_label=item.raw_label,
        normalized_label=item.normalized_label,
        statement_type=item.statement_type,
        candidate_value=item.candidate_value,
        period_label=item.period_label,
        source_page=item.source_page,
        source_table_id=item.source_table_id,
        evidence_bundle_id=item.evidence_bundle_id,
        metric_governance=item.metric_governance,
        latest_decision=(
            _metric_governance_annotation_to_response(item.latest_decision)
            if item.latest_decision is not None
            else None
        ),
    )
```

- [ ] **Step 4: Run the focused API tests**

Run:

```bash
cd /Users/keli/source/report-collector/financial-report-analysis
uv run pytest tests/integration/test_metric_governance_api.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Run the closeout verification for Phase 2 surface**

Run:

```bash
cd /Users/keli/source/report-collector/financial-report-analysis
uv run pytest \
  tests/unit/test_metric_governance_review_service.py \
  tests/unit/test_metric_governance_decision_repository.py \
  tests/integration/test_metric_governance_api.py \
  tests/unit/test_fact_pipeline.py -q
uv run ruff check src/financial_report_analysis/api/routes.py \
  src/financial_report_analysis/api/schemas.py \
  src/financial_report_analysis/services/metric_governance_review.py \
  src/financial_report_analysis/storage/models.py \
  src/financial_report_analysis/storage/repositories.py \
  tests/unit/test_metric_governance_review_service.py \
  tests/unit/test_metric_governance_decision_repository.py \
  tests/integration/test_metric_governance_api.py
```

Expected:

- all focused tests pass;
- `tests/unit/test_fact_pipeline.py` stays green, proving Phase 1 guardrails still hold;
- Ruff reports `All checks passed`.

- [ ] **Step 6: Commit**

```bash
cd /Users/keli/source/report-collector
git add financial-report-analysis/src/financial_report_analysis/api/schemas.py \
        financial-report-analysis/src/financial_report_analysis/api/routes.py \
        financial-report-analysis/src/financial_report_analysis/storage/repositories.py \
        financial-report-analysis/tests/integration/test_metric_governance_api.py
git commit -m "feat: add metric governance phase2 review api"
```

## Self-Review Checklist

- Spec coverage:
  - review list/detail surface -> Task 3 and Task 4
  - lightweight DB-backed decision record -> Task 2
  - latest-decision annotation -> Task 1 and Task 3
  - separate API from extract -> Task 4
  - Phase 1 guardrails unchanged -> Task 4 verification
- Placeholder scan:
  - no `TODO` / `TBD`
  - each task includes file paths, test commands, and concrete code
- Type consistency:
  - review item id format is consistently `artifact_id:fact_id`
  - decision types stay limited to `keep_provisional` and `map_to_standard`
  - target metric validation uses `load_metric_registry().get_metric_definition()`
    rather than inventing a new registry API
  - decision persistence is append-only and uses unique ids instead of
    route-time timestamp collisions
