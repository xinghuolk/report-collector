# Metric Governance Phase 4A Workflow API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose Phase 3 metric lifecycle state and lifecycle writes through the existing metric-governance review item API.

**Architecture:** Keep the review item as the workflow anchor. Add lifecycle response schemas, hydrate review item responses from `MetricLifecycleService.load_state_by_review_item`, and add two review-item-scoped write endpoints that create explicit candidate links before lifecycle decisions. Do not change recompute, canonical facts, P5 dataset rows, Turtle export, extraction, Ollama, or semantic fallback behavior.

**Tech Stack:** Python 3, FastAPI, Pydantic, SQLAlchemy-backed `SqlAlchemyP5ArtifactRepository`, pytest, Ruff.

---

## File Structure

- Modify `financial-report-analysis/src/financial_report_analysis/api/schemas.py`: add lifecycle request/response Pydantic models and add `lifecycle_state` to `MetricGovernanceReviewItemResponse`.
- Modify `financial-report-analysis/src/financial_report_analysis/api/routes.py`: convert lifecycle dataclasses to API responses, hydrate review responses, derive lifecycle concept identity from review items, and add lifecycle entry/decision endpoints.
- Modify `financial-report-analysis/tests/integration/test_metric_governance_api.py`: add end-to-end API tests for no-state response, lifecycle entry/link creation, lifecycle decisions, errors, and Phase 2 separation.
- No changes to P5 builders, recompute executors, Turtle exporters, extraction pipeline, Ollama clients, or semantic fallback modules.

## Task 1: Lifecycle API Schemas

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Test: `financial-report-analysis/tests/integration/test_metric_governance_api.py`

- [ ] **Step 1: Write failing assertions for explicit no-state lifecycle state**

Add these assertions to `test_metric_governance_review_list_and_write_flow` after `payload = list_response.json()`:

```python
    assert payload["items"][0]["lifecycle_state"] == {
        "entry": None,
        "latest_decision": None,
        "candidate_link": None,
        "decision_history": [],
    }
```

Add this assertion after `detail_response.status_code == 200`:

```python
    assert detail_response.json()["lifecycle_state"] == {
        "entry": None,
        "latest_decision": None,
        "candidate_link": None,
        "decision_history": [],
    }
```

- [ ] **Step 2: Run the focused integration test and verify it fails**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_metric_governance_api.py::test_metric_governance_review_list_and_write_flow -q
```

Expected: FAIL with a `KeyError: 'lifecycle_state'` or Pydantic response validation error showing the field is not present.

- [ ] **Step 3: Add lifecycle schema models**

In `financial-report-analysis/src/financial_report_analysis/api/schemas.py`, insert these models after `MetricGovernanceDecisionAnnotationResponse`:

```python
class MetricLifecycleConceptIdentityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issuer_id: str
    metric_id: str
    raw_label: str
    normalized_label: str | None = None
    statement_type: str
    accounting_standard: str
    industry_slug: str
    parent_metric_id: str | None = None


class MetricLifecycleEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lifecycle_entry_id: str
    concept: MetricLifecycleConceptIdentityResponse
    current_status: str
    mapped_standard_metric_id: str | None = None
    created_at: str
    updated_at: str
    created_by: str | None = None


class MetricLifecycleDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    lifecycle_entry_id: str
    action: str
    previous_status: str
    new_status: str
    target_metric_id: str | None = None
    actor: str
    reason: str
    evidence_bundle_id: str | None = None
    source_review_item_id: str | None = None
    source_artifact_id: str | None = None
    created_at: str
    effective_at: str


class MetricLifecycleCandidateLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_link_id: str
    lifecycle_entry_id: str
    review_item_id: str
    artifact_id: str
    issuer_id: str
    fiscal_year: int
    report_type: str
    candidate_metric_id: str
    raw_label: str
    normalized_label: str | None = None
    statement_type: str
    evidence_bundle_id: str | None = None
    created_at: str
    created_by: str | None = None


class MetricLifecycleStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry: MetricLifecycleEntryResponse | None = None
    latest_decision: MetricLifecycleDecisionResponse | None = None
    candidate_link: MetricLifecycleCandidateLinkResponse | None = None
    decision_history: list[MetricLifecycleDecisionResponse] = Field(
        default_factory=list,
    )


class MetricLifecycleEntryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str

    @model_validator(mode="after")
    def validate_actor(self) -> "MetricLifecycleEntryRequest":
        if not self.actor.strip():
            raise ValueError("actor is required")
        return self


class MetricLifecycleEntryWriteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_item: "MetricGovernanceReviewItemResponse"


class MetricLifecycleDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal[
        "approve_custom",
        "map_to_standard",
        "deprecate",
        "blacklist",
    ]
    target_metric_id: str | None = None
    reason: str
    actor: str
    effective_at: str | None = None

    @model_validator(mode="after")
    def validate_decision_shape(self) -> "MetricLifecycleDecisionRequest":
        if not self.actor.strip():
            raise ValueError("actor is required")
        if not self.reason.strip():
            raise ValueError("reason is required")
        if self.action == "map_to_standard" and not self.target_metric_id:
            raise ValueError(
                "target_metric_id is required for action='map_to_standard'"
            )
        if self.action != "map_to_standard" and self.target_metric_id is not None:
            raise ValueError(
                "target_metric_id is only allowed for action='map_to_standard'"
            )
        return self


class MetricLifecycleDecisionWriteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: MetricLifecycleDecisionResponse
    review_item: "MetricGovernanceReviewItemResponse"
```

Then add this field to `MetricGovernanceReviewItemResponse`:

```python
    lifecycle_state: MetricLifecycleStateResponse
```

- [ ] **Step 4: Update route imports and response helper to return no-state**

In `financial-report-analysis/src/financial_report_analysis/api/routes.py`, import `MetricLifecycleState` from `financial_report_analysis.models`:

```python
    MetricLifecycleState,
```

Import these schemas from `financial_report_analysis.api.schemas`:

```python
    MetricLifecycleCandidateLinkResponse,
    MetricLifecycleConceptIdentityResponse,
    MetricLifecycleDecisionResponse,
    MetricLifecycleDecisionRequest,
    MetricLifecycleDecisionWriteResponse,
    MetricLifecycleEntryRequest,
    MetricLifecycleEntryResponse,
    MetricLifecycleEntryWriteResponse,
    MetricLifecycleStateResponse,
```

Change `_metric_governance_review_item_to_response` signature to accept optional lifecycle state:

```python
def _metric_governance_review_item_to_response(
    item: MetricGovernanceReviewItem,
    lifecycle_state: MetricLifecycleState | None = None,
) -> MetricGovernanceReviewItemResponse:
```

Add this argument in the returned `MetricGovernanceReviewItemResponse`:

```python
        lifecycle_state=_metric_lifecycle_state_to_response(
            lifecycle_state
            or MetricLifecycleState(
                entry=None,
                latest_decision=None,
                candidate_link=None,
                decision_history=(),
            )
        ),
```

Add this helper below `_metric_governance_review_item_to_response`:

```python
def _metric_lifecycle_state_to_response(
    state: MetricLifecycleState,
) -> MetricLifecycleStateResponse:
    return MetricLifecycleStateResponse(
        entry=None,
        latest_decision=None,
        candidate_link=None,
        decision_history=[],
    )
```

- [ ] **Step 5: Run the focused test and verify it passes**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_metric_governance_api.py::test_metric_governance_review_list_and_write_flow -q
```

Expected: PASS.

- [ ] **Step 6: Commit schema baseline**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/api/schemas.py financial-report-analysis/src/financial_report_analysis/api/routes.py financial-report-analysis/tests/integration/test_metric_governance_api.py
git commit -m "feat: expose metric lifecycle state schema"
```

## Task 2: Review Response Lifecycle Hydration

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Modify: `financial-report-analysis/tests/integration/test_metric_governance_api.py`

- [ ] **Step 1: Add an integration test proving Phase 2 decisions do not create lifecycle state**

Add this test to `financial-report-analysis/tests/integration/test_metric_governance_api.py`:

```python
def test_metric_governance_phase2_decision_does_not_create_lifecycle_state(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))

    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )

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

    detail_response = client.get(
        f"/api/v1/metric-governance/review-items/{review_item_id}",
    )

    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["latest_decision"]["target_metric_id"] == "accounts_receiv"
    assert payload["lifecycle_state"] == {
        "entry": None,
        "latest_decision": None,
        "candidate_link": None,
        "decision_history": [],
    }
```

- [ ] **Step 2: Run the new test and verify it passes with the no-state baseline**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_metric_governance_api.py::test_metric_governance_phase2_decision_does_not_create_lifecycle_state -q
```

Expected: PASS.

- [ ] **Step 3: Implement lifecycle state conversion helpers**

In `financial-report-analysis/src/financial_report_analysis/api/routes.py`, expand model imports:

```python
    MetricLifecycleCandidateLink,
    MetricLifecycleConceptIdentity,
    MetricLifecycleDecision,
    MetricLifecycleEntry,
```

Replace `_metric_lifecycle_state_to_response` with:

```python
def _metric_lifecycle_state_to_response(
    state: MetricLifecycleState,
) -> MetricLifecycleStateResponse:
    return MetricLifecycleStateResponse(
        entry=(
            _metric_lifecycle_entry_to_response(state.entry)
            if state.entry is not None
            else None
        ),
        latest_decision=(
            _metric_lifecycle_decision_to_response(state.latest_decision)
            if state.latest_decision is not None
            else None
        ),
        candidate_link=(
            _metric_lifecycle_candidate_link_to_response(state.candidate_link)
            if state.candidate_link is not None
            else None
        ),
        decision_history=[
            _metric_lifecycle_decision_to_response(decision)
            for decision in state.decision_history
        ],
    )


def _metric_lifecycle_concept_to_response(
    concept: MetricLifecycleConceptIdentity,
) -> MetricLifecycleConceptIdentityResponse:
    return MetricLifecycleConceptIdentityResponse(
        issuer_id=concept.issuer_id,
        metric_id=concept.metric_id,
        raw_label=concept.raw_label,
        normalized_label=concept.normalized_label,
        statement_type=concept.statement_type,
        accounting_standard=concept.accounting_standard,
        industry_slug=concept.industry_slug,
        parent_metric_id=concept.parent_metric_id,
    )


def _metric_lifecycle_entry_to_response(
    entry: MetricLifecycleEntry,
) -> MetricLifecycleEntryResponse:
    return MetricLifecycleEntryResponse(
        lifecycle_entry_id=entry.lifecycle_entry_id,
        concept=_metric_lifecycle_concept_to_response(entry.concept),
        current_status=entry.current_status,
        mapped_standard_metric_id=entry.mapped_standard_metric_id,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        created_by=entry.created_by,
    )


def _metric_lifecycle_decision_to_response(
    decision: MetricLifecycleDecision,
) -> MetricLifecycleDecisionResponse:
    return MetricLifecycleDecisionResponse(
        decision_id=decision.decision_id,
        lifecycle_entry_id=decision.lifecycle_entry_id,
        action=decision.action,
        previous_status=decision.previous_status,
        new_status=decision.new_status,
        target_metric_id=decision.target_metric_id,
        actor=decision.actor,
        reason=decision.reason,
        evidence_bundle_id=decision.evidence_bundle_id,
        source_review_item_id=decision.source_review_item_id,
        source_artifact_id=decision.source_artifact_id,
        created_at=decision.created_at,
        effective_at=decision.effective_at,
    )


def _metric_lifecycle_candidate_link_to_response(
    link: MetricLifecycleCandidateLink,
) -> MetricLifecycleCandidateLinkResponse:
    return MetricLifecycleCandidateLinkResponse(
        candidate_link_id=link.candidate_link_id,
        lifecycle_entry_id=link.lifecycle_entry_id,
        review_item_id=link.review_item_id,
        artifact_id=link.artifact_id,
        issuer_id=link.issuer_id,
        fiscal_year=link.fiscal_year,
        report_type=link.report_type,
        candidate_metric_id=link.candidate_metric_id,
        raw_label=link.raw_label,
        normalized_label=link.normalized_label,
        statement_type=link.statement_type,
        evidence_bundle_id=link.evidence_bundle_id,
        created_at=link.created_at,
        created_by=link.created_by,
    )
```

- [ ] **Step 4: Hydrate list/detail/write responses from `MetricLifecycleService`**

In `financial-report-analysis/src/financial_report_analysis/api/routes.py`, import:

```python
from financial_report_analysis.services.metric_lifecycle import MetricLifecycleService
```

In `list_metric_governance_review_items`, add:

```python
    lifecycle_service = MetricLifecycleService(repository)
```

Replace the response list with:

```python
        items=[
            _metric_governance_review_item_to_response(
                item,
                lifecycle_service.load_state_by_review_item(item.review_item_id),
            )
            for item in items
        ],
```

In `get_metric_governance_review_item`, add:

```python
    lifecycle_service = MetricLifecycleService(repository)
```

Return:

```python
    return _metric_governance_review_item_to_response(
        item,
        lifecycle_service.load_state_by_review_item(item.review_item_id),
    )
```

In `write_metric_governance_decision`, add:

```python
    lifecycle_service = MetricLifecycleService(repository)
```

Return the refreshed review item with:

```python
        review_item=_metric_governance_review_item_to_response(
            refreshed_item,
            lifecycle_service.load_state_by_review_item(refreshed_item.review_item_id),
        ),
```

- [ ] **Step 5: Run the focused API tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_metric_governance_api.py -q
```

Expected: all tests in the file PASS.

- [ ] **Step 6: Commit lifecycle hydration**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/api/routes.py financial-report-analysis/tests/integration/test_metric_governance_api.py
git commit -m "feat: hydrate metric review lifecycle state"
```

## Task 3: Lifecycle Entry And Candidate Link Endpoint

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Modify: `financial-report-analysis/tests/integration/test_metric_governance_api.py`

- [ ] **Step 1: Add lifecycle-entry happy-path and idempotency test**

Add this test:

```python
def test_metric_governance_lifecycle_entry_endpoint_creates_linked_state(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )

    first_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )
    second_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_state = first_response.json()["review_item"]["lifecycle_state"]
    second_state = second_response.json()["review_item"]["lifecycle_state"]
    assert first_state["entry"]["lifecycle_entry_id"] == (
        second_state["entry"]["lifecycle_entry_id"]
    )
    assert first_state["entry"]["current_status"] == "provisional"
    assert first_state["entry"]["concept"]["accounting_standard"] == "cn"
    assert first_state["entry"]["concept"]["industry_slug"] == "general"
    assert first_state["entry"]["concept"]["parent_metric_id"] is None
    assert first_state["candidate_link"]["review_item_id"] == review_item_id
    assert first_state["candidate_link"]["evidence_bundle_id"] == "bundle-1"

    detail_response = client.get(
        f"/api/v1/metric-governance/review-items/{review_item_id}",
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["lifecycle_state"]["entry"]["lifecycle_entry_id"] == (
        first_state["entry"]["lifecycle_entry_id"]
    )
```

- [ ] **Step 2: Add lifecycle-entry malformed custom metric fallback test**

Add this helper:

```python
def _artifact_with_malformed_custom_metric(
    entry: P5ManifestEntry,
) -> P5ExtractedArtifact:
    base = _artifact(entry)
    malformed = dict(base.candidate_facts[0])
    malformed["metric_id"] = "custom_accounts_receivable"
    return P5ExtractedArtifact(
        artifact_id=base.artifact_id,
        artifact_version=base.artifact_version,
        pipeline_version=base.pipeline_version,
        manifest_entry=base.manifest_entry,
        source_pdf_path=base.source_pdf_path,
        document=base.document,
        document_metadata=base.document_metadata,
        candidate_facts=(malformed, base.candidate_facts[1]),
        canonical_facts=base.canonical_facts,
        derived_facts=base.derived_facts,
        validation_report=base.validation_report,
        review_packets=base.review_packets,
        quality_gate=base.quality_gate,
        missing_status=base.missing_status,
        created_at=base.created_at,
    )
```

Add this test:

```python
def test_metric_governance_lifecycle_entry_uses_legacy_custom_defaults(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact_with_malformed_custom_metric(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )

    response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )

    assert response.status_code == 200
    concept = response.json()["review_item"]["lifecycle_state"]["entry"]["concept"]
    assert concept["accounting_standard"] == "OTHER"
    assert concept["industry_slug"] == "general"
    assert concept["parent_metric_id"] is None
```

- [ ] **Step 3: Add lifecycle-entry error tests**

Add this test:

```python
def test_metric_governance_lifecycle_entry_rejects_missing_review_item(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    client = TestClient(create_app(runtime=runtime))

    response = client.post(
        "/api/v1/metric-governance/review-items/missing:item/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )

    assert response.status_code == 404
```

Add this test:

```python
def test_metric_governance_lifecycle_entry_rejects_non_provisional_review_item(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))
    review_item_id = build_review_item_id(artifact.artifact_id, "candidate-2")

    response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "review item is not provisional"
```

Add this test:

```python
def test_metric_governance_lifecycle_entry_rejects_blank_actor(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )

    response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "   "},
    )

    assert response.status_code == 422
```

Add this test:

```python
def test_metric_governance_lifecycle_entry_requires_storage_runtime() -> None:
    client = TestClient(create_app(runtime=build_api_runtime(None)))

    response = client.post(
        "/api/v1/metric-governance/review-items/missing:item/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "storage repository is not configured"
```

- [ ] **Step 4: Run new endpoint tests and verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_metric_governance_api.py -q
```

Expected: FAIL for lifecycle-entry tests with HTTP 405 or 404 because the endpoint does not exist.

- [ ] **Step 5: Implement concept derivation and candidate link helpers**

In `financial-report-analysis/src/financial_report_analysis/api/routes.py`, add imports:

```python
from financial_report_analysis.models import (
    MetricLifecycleCandidateLink,
    MetricLifecycleConceptIdentity,
)
from financial_report_analysis.services.metric_lifecycle import MetricLifecycleError
```

If these model imports already exist from Task 2, do not duplicate them.

Add helper functions near the metric-governance helpers:

```python
def _metric_lifecycle_concept_from_review_item(
    item: MetricGovernanceReviewItem,
) -> MetricLifecycleConceptIdentity:
    accounting_standard, industry_slug, parent_metric_id = (
        _parse_custom_metric_identity(item.metric_id)
    )
    return MetricLifecycleConceptIdentity(
        issuer_id=item.issuer_id,
        metric_id=item.metric_id,
        raw_label=item.raw_label,
        normalized_label=item.normalized_label,
        statement_type=item.statement_type,
        accounting_standard=accounting_standard,
        industry_slug=industry_slug,
        parent_metric_id=parent_metric_id,
    )


def _parse_custom_metric_identity(metric_id: str) -> tuple[str, str, str | None]:
    parts = metric_id.split("::")
    if len(parts) >= 6 and parts[0] == "custom":
        parent_metric_id = parts[4] if parts[4] != "root" else None
        return parts[1], parts[2], parent_metric_id
    return "OTHER", "general", None


def _metric_lifecycle_candidate_link_from_review_item(
    item: MetricGovernanceReviewItem,
    lifecycle_entry_id: str,
    *,
    actor: str,
) -> MetricLifecycleCandidateLink:
    timestamp = datetime.now(UTC).isoformat()
    return MetricLifecycleCandidateLink(
        candidate_link_id=f"metric-lifecycle-candidate-link:{uuid4().hex}",
        lifecycle_entry_id=lifecycle_entry_id,
        review_item_id=item.review_item_id,
        artifact_id=item.artifact_id,
        issuer_id=item.issuer_id,
        fiscal_year=item.fiscal_year,
        report_type=item.report_type,
        candidate_metric_id=item.metric_id,
        raw_label=item.raw_label,
        normalized_label=item.normalized_label,
        statement_type=item.statement_type,
        evidence_bundle_id=item.evidence_bundle_id,
        created_at=timestamp,
        created_by=actor,
    )
```

- [ ] **Step 6: Implement lifecycle-entry endpoint**

In `financial-report-analysis/src/financial_report_analysis/api/routes.py`, add this endpoint before the legacy Phase 2 decision endpoint:

```python
@router.post(
    "/api/v1/metric-governance/review-items/{review_item_id:path}/lifecycle-entry",
    response_model=MetricLifecycleEntryWriteResponse,
)
def create_metric_governance_lifecycle_entry(
    review_item_id: str,
    entry_request: MetricLifecycleEntryRequest,
    request: Request,
) -> MetricLifecycleEntryWriteResponse:
    repository = _require_storage_repository(request)
    review_service = MetricGovernanceReviewService(repository)
    if not review_service.review_item_exists(review_item_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"missing metric governance review item: {review_item_id}",
        )
    if not review_service.review_item_is_provisional(review_item_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="review item is not provisional",
        )
    item = _load_metric_governance_review_item_or_404(review_service, review_item_id)
    lifecycle_service = MetricLifecycleService(repository)
    try:
        entry = lifecycle_service.create_or_load_entry(
            concept=_metric_lifecycle_concept_from_review_item(item),
            actor=entry_request.actor,
        )
        lifecycle_service.link_candidate(
            _metric_lifecycle_candidate_link_from_review_item(
                item,
                entry.lifecycle_entry_id,
                actor=entry_request.actor,
            )
        )
    except MetricLifecycleError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    refreshed_item = _load_metric_governance_review_item_or_404(
        review_service,
        review_item_id,
    )
    return MetricLifecycleEntryWriteResponse(
        review_item=_metric_governance_review_item_to_response(
            refreshed_item,
            lifecycle_service.load_state_by_review_item(review_item_id),
        )
    )
```

- [ ] **Step 7: Run lifecycle-entry tests**

Run:

```bash
cd financial-report-analysis
uv run pytest \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_entry_endpoint_creates_linked_state \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_entry_uses_legacy_custom_defaults \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_entry_rejects_missing_review_item \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_entry_rejects_non_provisional_review_item \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_entry_rejects_blank_actor \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_entry_requires_storage_runtime \
  -q
```

Expected: PASS.

- [ ] **Step 8: Commit lifecycle-entry endpoint**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/api/routes.py financial-report-analysis/tests/integration/test_metric_governance_api.py
git commit -m "feat: add metric lifecycle entry review endpoint"
```

## Task 4: Lifecycle Decision Endpoint

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Modify: `financial-report-analysis/tests/integration/test_metric_governance_api.py`

- [ ] **Step 1: Add lifecycle-decision happy-path test**

Add this test:

```python
def test_metric_governance_lifecycle_decision_endpoint_records_mapping(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )
    entry_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )
    assert entry_response.status_code == 200

    decision_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "Matches the supported receivables metric.",
            "actor": "reviewer@example.com",
            "effective_at": "2026-04-27T10:03:00+00:00",
        },
    )

    assert decision_response.status_code == 200
    payload = decision_response.json()
    assert payload["decision"]["action"] == "map_to_standard"
    assert payload["decision"]["previous_status"] == "provisional"
    assert payload["decision"]["new_status"] == "mapped_to_standard"
    assert payload["decision"]["target_metric_id"] == "accounts_receiv"
    assert payload["decision"]["evidence_bundle_id"] == "bundle-1"
    assert payload["decision"]["source_review_item_id"] == review_item_id
    assert payload["decision"]["source_artifact_id"] == artifact.artifact_id
    state = payload["review_item"]["lifecycle_state"]
    assert state["entry"]["current_status"] == "mapped_to_standard"
    assert state["entry"]["mapped_standard_metric_id"] == "accounts_receiv"
    assert state["latest_decision"]["action"] == "map_to_standard"
    assert len(state["decision_history"]) == 1
```

- [ ] **Step 2: Add lifecycle-decision error tests**

Add this test:

```python
def test_metric_governance_lifecycle_decision_rejects_missing_review_item(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    client = TestClient(create_app(runtime=runtime))

    response = client.post(
        "/api/v1/metric-governance/review-items/missing:item/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "Missing review item.",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 404
```

Add this test:

```python
def test_metric_governance_lifecycle_decision_rejects_non_provisional_review_item(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))
    review_item_id = build_review_item_id(artifact.artifact_id, "candidate-2")

    response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "Standard candidates are not lifecycle review items.",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "review item is not provisional"
```

Add this test:

```python
def test_metric_governance_lifecycle_decision_requires_candidate_link(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )

    response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "Matches the supported receivables metric.",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "lifecycle candidate link is required"
```

Add this test:

```python
def test_metric_governance_lifecycle_decision_rejects_target_for_non_mapping_action(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )
    entry_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )
    assert entry_response.status_code == 200

    response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision",
        json={
            "action": "approve_custom",
            "target_metric_id": "accounts_receiv",
            "reason": "Keep as custom metric.",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 422
```

Add this test:

```python
def test_metric_governance_lifecycle_decision_rejects_blank_actor_and_reason(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )
    entry_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )
    assert entry_response.status_code == 200

    blank_actor_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "Valid reason.",
            "actor": "   ",
        },
    )
    blank_reason_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "   ",
            "actor": "reviewer@example.com",
        },
    )

    assert blank_actor_response.status_code == 422
    assert blank_reason_response.status_code == 422
```

Add this test:

```python
def test_metric_governance_lifecycle_decision_requires_storage_runtime() -> None:
    client = TestClient(create_app(runtime=build_api_runtime(None)))

    response = client.post(
        "/api/v1/metric-governance/review-items/missing:item/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "accounts_receiv",
            "reason": "Missing storage runtime.",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "storage repository is not configured"
```

Add this test:

```python
def test_metric_governance_lifecycle_decision_rejects_unknown_standard_target(
    tmp_path: Path,
) -> None:
    runtime = build_api_runtime(tmp_path / "storage.db")
    entry = _entry(tmp_path)
    artifact = _artifact(entry)
    assert runtime.storage_repository is not None
    assert runtime.historical_ingestion_service is not None
    runtime.historical_ingestion_service.register_report(entry)
    runtime.storage_repository.save_extracted_artifact(artifact)
    client = TestClient(create_app(runtime=runtime))
    review_item_id = build_review_item_id(
        artifact.artifact_id,
        "/tmp/report.pdf:candidate:1",
    )
    entry_response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-entry",
        json={"actor": "reviewer@example.com"},
    )
    assert entry_response.status_code == 200

    response = client.post(
        f"/api/v1/metric-governance/review-items/{review_item_id}/lifecycle-decision",
        json={
            "action": "map_to_standard",
            "target_metric_id": "custom::bad",
            "reason": "Unsupported target.",
            "actor": "reviewer@example.com",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "target_metric_id must be a supported standard metric"
    )
```

- [ ] **Step 3: Run lifecycle-decision tests and verify they fail**

Run:

```bash
cd financial-report-analysis
uv run pytest \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_endpoint_records_mapping \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_rejects_missing_review_item \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_rejects_non_provisional_review_item \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_requires_candidate_link \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_rejects_target_for_non_mapping_action \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_rejects_blank_actor_and_reason \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_requires_storage_runtime \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_rejects_unknown_standard_target \
  -q
```

Expected: FAIL for missing lifecycle-decision endpoint or validation behavior.

- [ ] **Step 4: Implement lifecycle-decision endpoint**

In `financial-report-analysis/src/financial_report_analysis/api/routes.py`, add this endpoint after the lifecycle-entry endpoint:

```python
@router.post(
    "/api/v1/metric-governance/review-items/{review_item_id:path}/lifecycle-decision",
    response_model=MetricLifecycleDecisionWriteResponse,
)
def write_metric_governance_lifecycle_decision(
    review_item_id: str,
    decision_request: MetricLifecycleDecisionRequest,
    request: Request,
) -> MetricLifecycleDecisionWriteResponse:
    repository = _require_storage_repository(request)
    review_service = MetricGovernanceReviewService(repository)
    if not review_service.review_item_exists(review_item_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"missing metric governance review item: {review_item_id}",
        )
    if not review_service.review_item_is_provisional(review_item_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="review item is not provisional",
        )
    item = _load_metric_governance_review_item_or_404(review_service, review_item_id)
    lifecycle_service = MetricLifecycleService(repository)
    state = lifecycle_service.load_state_by_review_item(review_item_id)
    if state.candidate_link is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="lifecycle candidate link is required",
        )
    try:
        decision = lifecycle_service.record_decision(
            lifecycle_entry_id=state.candidate_link.lifecycle_entry_id,
            action=decision_request.action,
            actor=decision_request.actor,
            reason=decision_request.reason,
            target_metric_id=decision_request.target_metric_id,
            evidence_bundle_id=item.evidence_bundle_id,
            source_review_item_id=item.review_item_id,
            source_artifact_id=item.artifact_id,
            effective_at=decision_request.effective_at,
        )
    except MetricLifecycleError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    refreshed_item = _load_metric_governance_review_item_or_404(
        review_service,
        review_item_id,
    )
    return MetricLifecycleDecisionWriteResponse(
        decision=_metric_lifecycle_decision_to_response(decision),
        review_item=_metric_governance_review_item_to_response(
            refreshed_item,
            lifecycle_service.load_state_by_review_item(review_item_id),
        ),
    )
```

- [ ] **Step 5: Run lifecycle-decision tests**

Run:

```bash
cd financial-report-analysis
uv run pytest \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_endpoint_records_mapping \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_rejects_missing_review_item \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_rejects_non_provisional_review_item \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_requires_candidate_link \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_rejects_target_for_non_mapping_action \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_rejects_blank_actor_and_reason \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_requires_storage_runtime \
  tests/integration/test_metric_governance_api.py::test_metric_governance_lifecycle_decision_rejects_unknown_standard_target \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit lifecycle-decision endpoint**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/api/routes.py financial-report-analysis/tests/integration/test_metric_governance_api.py
git commit -m "feat: add metric lifecycle decision review endpoint"
```

## Task 5: Full Verification And Guardrails

**Files:**
- Modify only if verification exposes a bug in P4A files:
  `financial-report-analysis/src/financial_report_analysis/api/schemas.py`,
  `financial-report-analysis/src/financial_report_analysis/api/routes.py`,
  `financial-report-analysis/tests/integration/test_metric_governance_api.py`

- [ ] **Step 1: Run metric governance API integration tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/integration/test_metric_governance_api.py -q
```

Expected: PASS.

- [ ] **Step 2: Run lifecycle and governance unit regression tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_metric_lifecycle.py tests/unit/test_metric_lifecycle_repository.py tests/unit/test_metric_lifecycle_service.py tests/unit/test_metric_governance_decision_repository.py tests/unit/test_metric_governance_review_service.py tests/unit/test_public_exports.py -q
```

Expected: PASS.

- [ ] **Step 3: Run no-output-change guardrail tests**

Run:

```bash
cd financial-report-analysis
uv run pytest tests/unit/test_storage_models.py tests/unit/test_storage_repository.py tests/unit/test_p5_recompute.py tests/unit/test_fact_pipeline.py::test_analyze_report_blocks_provisional_custom_metric_from_canonical_facts tests/unit/test_fact_pipeline.py::test_provisional_custom_quarterly_candidates_do_not_produce_ttm_facts tests/unit/test_report_adapter.py::test_report_adapter_excludes_non_auto_analysis_facts_from_key_facts tests/unit/test_report_adapter.py::test_report_adapter_does_not_expose_extensions_in_ttm_facts -q
```

Expected: PASS.

- [ ] **Step 4: Run Ruff**

Run:

```bash
cd financial-report-analysis
uv run ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 5: Fix only P4A defects found by verification**

If a command fails, inspect the failing assertion or lint location and change only P4A files. Re-run the exact failing command until it passes, then re-run Steps 1-4.

- [ ] **Step 6: Final commit for verification fixes if needed**

If Step 5 changed files, run:

```bash
git add financial-report-analysis/src/financial_report_analysis/api/schemas.py financial-report-analysis/src/financial_report_analysis/api/routes.py financial-report-analysis/tests/integration/test_metric_governance_api.py
git commit -m "fix: stabilize metric lifecycle review api"
```

If Step 5 changed no files, do not create an empty commit.

## Self-Review

- Spec coverage: response embedding is covered by Tasks 1-2; lifecycle entry/link endpoint, blank actor validation, and storage-runtime errors are covered by Task 3; lifecycle decision endpoint, missing/non-provisional review item errors, blank actor/reason validation, missing link errors, and storage-runtime errors are covered by Task 4; no-output-change guardrails are covered by Task 5.
- Placeholder scan: no placeholder work remains; every task includes concrete files, code, commands, and expected results.
- Type consistency: plan uses Phase 3 dataclass names and Pydantic response names consistently: `MetricLifecycleState`, `MetricLifecycleEntryResponse`, `MetricLifecycleDecisionRequest`, `MetricLifecycleDecisionWriteResponse`, and `MetricLifecycleEntryWriteResponse`.
