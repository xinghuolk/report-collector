# Post-P5 Review、Lineage 与 Deterministic Recompute Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为当前 P5 extracted artifact、dataset artifact 与 Turtle export 补齐 review surface、lineage surface 和 deterministic recompute contract，而不引入数据库或新的主抽取路径。

**Architecture:** 继续复用现有 `financial_report_analysis.p5` JSON artifact repository，把 review 和 lineage 先做成派生 surface，再在此基础上增加 deterministic recompute CLI / service。当前阶段不让 LLM 进入主裁决链，只为未来 whole-document assessment 预留扩展点。

**Tech Stack:** Python 3.12, dataclasses, existing P5 JSON artifacts, pytest, Ruff

---

## File Structure

### Existing files to modify

- `financial-report-analysis/src/financial_report_analysis/p5/__init__.py`
  - 暴露新的 public review / lineage / recompute 入口。
- `financial-report-analysis/src/financial_report_analysis/p5/models.py`
  - 增加 post-P5 review/lineage/recompute 所需 dataclass 模型。
- `financial-report-analysis/src/financial_report_analysis/p5/artifact_repository.py`
  - 如有必要，为 review/recompute 读取增加最小辅助方法；不重做 repository 抽象。
- `financial-report-analysis/src/financial_report_analysis/p5/runner.py`
  - 复用现有 P5 流程，为 recompute 复跑与 review surface 生成提供稳定入口。
- `financial-report-analysis/tests/unit/test_public_exports.py`
  - 锁住新的 public API surface。

### New files to create

- `financial-report-analysis/src/financial_report_analysis/p5/review.py`
  - 从 extracted / dataset / turtle export 派生 review surface。
- `financial-report-analysis/src/financial_report_analysis/p5/lineage.py`
  - 定义并生成 artifact lineage / row lineage surface。
- `financial-report-analysis/src/financial_report_analysis/p5/recompute.py`
  - 定义 deterministic recompute contract 与 CLI / service entry。
- `financial-report-analysis/tests/unit/test_p5_review.py`
  - review surface 单元测试。
- `financial-report-analysis/tests/unit/test_p5_lineage.py`
  - lineage surface 单元测试。
- `financial-report-analysis/tests/unit/test_p5_recompute.py`
  - recompute contract 单元测试。
- `financial-report-analysis/tests/integration/test_p5_recompute_review_flow.py`
  - focused integration：从 persisted P5 artifacts 生成 review / lineage，并执行 deterministic recompute。

### Responsibility split

- `models.py` 只定义数据形状，不放业务逻辑。
- `review.py` 只做 review surface 生成与摘要，不负责 recompute。
- `lineage.py` 只回答追溯关系，不负责 review formatting。
- `recompute.py` 只负责判定重算目标、执行重算和生成 diff summary，不承担字段抽取逻辑。

## Task 1: Add Post-P5 Models

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/models.py`
- Test: `financial-report-analysis/tests/unit/test_p5_review.py`

- [ ] **Step 1: Write the failing test for review and lineage dataclasses**

Append to `financial-report-analysis/tests/unit/test_p5_review.py`:

```python
from financial_report_analysis.p5.models import (
    P5ArtifactLineage,
    P5DatasetReviewSurface,
    P5ExtractedReviewSurface,
    P5RecomputePlan,
)


def test_post_p5_models_capture_minimum_contract() -> None:
    extracted = P5ExtractedReviewSurface(
        artifact_id="CN_601919_2025",
        artifact_version="1.0",
        pipeline_version="p5-v1",
        source_pdf_path="report/downloads/cn_stocks/601919/annual/2025_年度报告.pdf",
        manifest_entry_key=("CN_601919", 2025, "annual"),
        quality_gate="pass",
        review_issue_count=0,
        missing_status_groups=("working_capital_missing_status",),
    )
    dataset = P5DatasetReviewSurface(
        dataset_id="p5_seed",
        dataset_version="1.0",
        issuer_count=1,
        period_count=1,
        source_artifact_ids=("CN_601919_2025",),
        present_row_count=10,
        missing_row_count=2,
        review_required_artifact_ids=(),
    )
    lineage = P5ArtifactLineage(
        dataset_id="p5_seed",
        source_artifact_id="CN_601919_2025",
        source_pdf_path="report/downloads/cn_stocks/601919/annual/2025_年度报告.pdf",
        pipeline_version="p5-v1",
        source_fact_id="fact-1",
        evidence_bundle_id="bundle-1",
    )
    recompute_plan = P5RecomputePlan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        target_artifact_ids=("CN_601919_2025",),
        rebuild_dataset=True,
        rebuild_turtle_export=True,
        reason="pipeline_version_changed",
    )

    assert extracted.artifact_id == "CN_601919_2025"
    assert dataset.present_row_count == 10
    assert lineage.source_fact_id == "fact-1"
    assert recompute_plan.rebuild_dataset is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/unit/test_p5_review.py::test_post_p5_models_capture_minimum_contract -q -o addopts=
```

Expected: FAIL with import error or undefined names for the new dataclasses.

- [ ] **Step 3: Add minimal post-P5 dataclasses**

Update `financial-report-analysis/src/financial_report_analysis/p5/models.py` with:

```python
@dataclass(frozen=True, slots=True)
class P5ExtractedReviewSurface:
    artifact_id: str
    artifact_version: str
    pipeline_version: str
    source_pdf_path: str
    manifest_entry_key: tuple[str, int, str]
    quality_gate: str
    review_issue_count: int
    missing_status_groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class P5DatasetReviewSurface:
    dataset_id: str
    dataset_version: str
    issuer_count: int
    period_count: int
    source_artifact_ids: tuple[str, ...]
    present_row_count: int
    missing_row_count: int
    review_required_artifact_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class P5ArtifactLineage:
    dataset_id: str
    source_artifact_id: str
    source_pdf_path: str
    pipeline_version: str
    source_fact_id: str | None
    evidence_bundle_id: str | None


@dataclass(frozen=True, slots=True)
class P5RecomputePlan:
    manifest_id: str
    dataset_id: str
    target_artifact_ids: tuple[str, ...]
    rebuild_dataset: bool
    rebuild_turtle_export: bool
    reason: str
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/unit/test_p5_review.py::test_post_p5_models_capture_minimum_contract -q -o addopts=
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/models.py financial-report-analysis/tests/unit/test_p5_review.py
git commit -m "feat: add post-p5 review and lineage models"
```

## Task 2: Build Extracted And Dataset Review Surfaces

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/p5/review.py`
- Test: `financial-report-analysis/tests/unit/test_p5_review.py`

- [ ] **Step 1: Write the failing test for review surface builders**

Append to `financial-report-analysis/tests/unit/test_p5_review.py`:

```python
from financial_report_analysis.p5.review import (
    build_dataset_review_surface,
    build_extracted_review_surface,
)


def test_build_extracted_review_surface_counts_review_signals(tmp_path):
    from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry

    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
    )
    artifact = P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=pdf_path,
        document={"document_id": str(pdf_path), "pdf_path": str(pdf_path)},
        document_metadata={"working_capital_missing_status": {"notes_receiv": "absent"}},
        candidate_facts=(),
        canonical_facts=(),
        derived_facts=(),
        validation_report={"overall_status": "review", "issues": [{"code": "scope_conflict"}]},
        review_packets=({"metric_id": "cash", "conflict_state": "review_required"},),
        quality_gate="review",
        missing_status={"working_capital_missing_status": {"notes_receiv": "absent"}},
        created_at="2026-04-23T00:00:00",
    )

    surface = build_extracted_review_surface(artifact)

    assert surface.artifact_id == "CN_601919_2025"
    assert surface.review_issue_count == 1
    assert surface.quality_gate == "review"
    assert surface.missing_status_groups == ("working_capital_missing_status",)


def test_build_dataset_review_surface_uses_quality_summary(tmp_path):
    from financial_report_analysis.p5.models import P5DatasetArtifact

    dataset = P5DatasetArtifact(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00",
        issuer_count=2,
        periods=(2024, 2025),
        metrics=("cash", "revenue"),
        rows=(),
        quality_summary={
            "present_row_count": 12,
            "missing_row_count": 3,
            "review_required_artifacts": ["CN_601919_2025"],
        },
        source_artifacts=("CN_600519_2025", "CN_601919_2025"),
    )

    surface = build_dataset_review_surface(dataset)

    assert surface.dataset_id == "p5_seed"
    assert surface.period_count == 2
    assert surface.present_row_count == 12
    assert surface.review_required_artifact_ids == ("CN_601919_2025",)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/unit/test_p5_review.py::test_build_extracted_review_surface_counts_review_signals tests/unit/test_p5_review.py::test_build_dataset_review_surface_uses_quality_summary -q -o addopts=
```

Expected: FAIL with missing `financial_report_analysis.p5.review`.

- [ ] **Step 3: Implement minimal review builders**

Create `financial-report-analysis/src/financial_report_analysis/p5/review.py`:

```python
from __future__ import annotations

from financial_report_analysis.p5.models import (
    P5DatasetArtifact,
    P5DatasetReviewSurface,
    P5ExtractedArtifact,
    P5ExtractedReviewSurface,
)


def build_extracted_review_surface(
    artifact: P5ExtractedArtifact,
) -> P5ExtractedReviewSurface:
    return P5ExtractedReviewSurface(
        artifact_id=artifact.artifact_id,
        artifact_version=artifact.artifact_version,
        pipeline_version=artifact.pipeline_version,
        source_pdf_path=str(artifact.source_pdf_path),
        manifest_entry_key=artifact.manifest_entry.entry_key,
        quality_gate=artifact.quality_gate,
        review_issue_count=len(artifact.validation_report.get("issues", [])),
        missing_status_groups=tuple(sorted(artifact.missing_status)),
    )


def build_dataset_review_surface(
    dataset: P5DatasetArtifact,
) -> P5DatasetReviewSurface:
    quality_summary = dataset.quality_summary
    return P5DatasetReviewSurface(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        issuer_count=dataset.issuer_count,
        period_count=len(dataset.periods),
        source_artifact_ids=dataset.source_artifacts,
        present_row_count=int(quality_summary.get("present_row_count", 0)),
        missing_row_count=int(quality_summary.get("missing_row_count", 0)),
        review_required_artifact_ids=tuple(
            quality_summary.get("review_required_artifacts", [])
        ),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/test_p5_review.py -q -o addopts=
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/review.py financial-report-analysis/tests/unit/test_p5_review.py
git commit -m "feat: add post-p5 review surfaces"
```

## Task 3: Add Dataset And Export Lineage Surface

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/p5/lineage.py`
- Test: `financial-report-analysis/tests/unit/test_p5_lineage.py`

- [ ] **Step 1: Write the failing test for lineage generation**

Create `financial-report-analysis/tests/unit/test_p5_lineage.py`:

```python
from financial_report_analysis.p5.lineage import build_dataset_lineage
from financial_report_analysis.p5.models import P5DatasetArtifact, P5DatasetRow, P5ExtractedArtifact, P5ManifestEntry


def test_build_dataset_lineage_links_rows_back_to_artifacts(tmp_path):
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
    )
    artifact = P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=pdf_path,
        document={"document_id": str(pdf_path), "pdf_path": str(pdf_path)},
        document_metadata={},
        candidate_facts=(),
        canonical_facts=(),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={},
        created_at="2026-04-23T00:00:00",
    )
    dataset = P5DatasetArtifact(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00",
        issuer_count=1,
        periods=(2025,),
        metrics=("revenue",),
        rows=(
            P5DatasetRow(
                issuer_id="CN_601919",
                market="CN",
                stock_code="601919",
                fiscal_year=2025,
                metric_id="revenue",
                entity_scope="consolidated",
                period_scope="duration",
                statement_type="income_statement",
                value=100.0,
                currency="CNY",
                unit="currency_amount",
                quality_status="ok",
                missing_status="present",
                source_fact_id="fact-1",
                source_artifact_id="CN_601919_2025",
                evidence_bundle_id="bundle-1",
            ),
        ),
        quality_summary={},
        source_artifacts=("CN_601919_2025",),
    )

    lineage = build_dataset_lineage(dataset=dataset, extracted_artifacts=(artifact,))

    assert len(lineage) == 1
    assert lineage[0].dataset_id == "p5_seed"
    assert lineage[0].source_pdf_path == str(pdf_path)
    assert lineage[0].source_fact_id == "fact-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/unit/test_p5_lineage.py -q -o addopts=
```

Expected: FAIL with missing lineage module.

- [ ] **Step 3: Implement minimal lineage builder**

Create `financial-report-analysis/src/financial_report_analysis/p5/lineage.py`:

```python
from __future__ import annotations

from financial_report_analysis.p5.models import (
    P5ArtifactLineage,
    P5DatasetArtifact,
    P5ExtractedArtifact,
)


def build_dataset_lineage(
    *,
    dataset: P5DatasetArtifact,
    extracted_artifacts: tuple[P5ExtractedArtifact, ...],
) -> tuple[P5ArtifactLineage, ...]:
    artifacts_by_id = {
        artifact.artifact_id: artifact for artifact in extracted_artifacts
    }
    lineage: list[P5ArtifactLineage] = []
    for row in dataset.rows:
        artifact = artifacts_by_id.get(row.source_artifact_id)
        if artifact is None:
            continue
        lineage.append(
            P5ArtifactLineage(
                dataset_id=dataset.dataset_id,
                source_artifact_id=row.source_artifact_id,
                source_pdf_path=str(artifact.source_pdf_path),
                pipeline_version=artifact.pipeline_version,
                source_fact_id=row.source_fact_id,
                evidence_bundle_id=row.evidence_bundle_id,
            )
        )
    return tuple(lineage)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/unit/test_p5_lineage.py -q -o addopts=
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/lineage.py financial-report-analysis/tests/unit/test_p5_lineage.py
git commit -m "feat: add post-p5 lineage surface"
```

## Task 4: Add Deterministic Recompute Contract

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/p5/recompute.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/runner.py`
- Test: `financial-report-analysis/tests/unit/test_p5_recompute.py`

- [ ] **Step 1: Write the failing test for recompute planning and execution**

Create `financial-report-analysis/tests/unit/test_p5_recompute.py`:

```python
import json
from pathlib import Path

from financial_report_analysis.p5.recompute import (
    build_recompute_plan,
    execute_recompute_plan,
)


def test_build_recompute_plan_marks_dataset_and_export_rebuild_when_pipeline_changes():
    plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=("CN_600519_2025", "CN_601919_2025"),
        reason="pipeline_version_changed",
    )

    assert plan.target_artifact_ids == ("CN_600519_2025", "CN_601919_2025")
    assert plan.rebuild_dataset is True
    assert plan.rebuild_turtle_export is True


def test_execute_recompute_plan_reuses_runner_entry_point(tmp_path: Path):
    calls = {}

    def fake_run_p5_dataset_build(**kwargs):
        calls.update(kwargs)
        return type(
            "Result",
            (),
            {
                "manifest_id": "p5_seed",
                "extracted_artifact_ids": ("CN_600519_2025",),
                "dataset_path": tmp_path / "p5_seed.json",
                "turtle_export_path": tmp_path / "p5_seed_turtle_export.json",
            },
        )()

    plan = build_recompute_plan(
        manifest_id="p5_seed",
        dataset_id="p5_seed",
        extracted_artifact_ids=("CN_600519_2025",),
        reason="pipeline_version_changed",
    )

    result = execute_recompute_plan(
        plan=plan,
        manifest_path=tmp_path / "manifest.json",
        artifact_root=tmp_path / "data" / "p5",
        pdf_root=tmp_path,
        run_p5_dataset_build_func=fake_run_p5_dataset_build,
    )

    assert calls["dataset_id"] == "p5_seed"
    assert result.dataset_path.name == "p5_seed.json"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/unit/test_p5_recompute.py -q -o addopts=
```

Expected: FAIL with missing recompute module.

- [ ] **Step 3: Implement minimal recompute module**

Create `financial-report-analysis/src/financial_report_analysis/p5/recompute.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Callable

from financial_report_analysis.p5.models import P5RecomputePlan
from financial_report_analysis.p5.runner import P5RunResult, run_p5_dataset_build


def build_recompute_plan(
    *,
    manifest_id: str,
    dataset_id: str,
    extracted_artifact_ids: tuple[str, ...],
    reason: str,
) -> P5RecomputePlan:
    return P5RecomputePlan(
        manifest_id=manifest_id,
        dataset_id=dataset_id,
        target_artifact_ids=tuple(sorted(extracted_artifact_ids)),
        rebuild_dataset=True,
        rebuild_turtle_export=True,
        reason=reason,
    )


def execute_recompute_plan(
    *,
    plan: P5RecomputePlan,
    manifest_path: str | Path,
    artifact_root: str | Path,
    pdf_root: str | Path | None,
    run_p5_dataset_build_func: Callable[..., P5RunResult] = run_p5_dataset_build,
) -> P5RunResult:
    return run_p5_dataset_build_func(
        manifest_path=manifest_path,
        artifact_root=artifact_root,
        dataset_id=plan.dataset_id,
        pdf_root=pdf_root,
    )
```

- [ ] **Step 4: Add runner helper hook only if needed by tests**

If `financial-report-analysis/src/financial_report_analysis/p5/runner.py` needs a narrow helper to expose deterministic recompute inputs, add only the minimum helper:

```python
def build_recompute_inputs(
    *,
    manifest_path: str | Path,
    artifact_root: str | Path,
    dataset_id: str,
    pdf_root: str | Path | None = None,
) -> dict[str, object]:
    return {
        "manifest_path": manifest_path,
        "artifact_root": artifact_root,
        "dataset_id": dataset_id,
        "pdf_root": pdf_root,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/test_p5_recompute.py -q -o addopts=
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/recompute.py financial-report-analysis/src/financial_report_analysis/p5/runner.py financial-report-analysis/tests/unit/test_p5_recompute.py
git commit -m "feat: add deterministic p5 recompute contract"
```

## Task 5: Wire Public Exports And Focused Integration

**Files:**
- Modify: `financial-report-analysis/src/financial_report_analysis/p5/__init__.py`
- Modify: `financial-report-analysis/tests/unit/test_public_exports.py`
- Create: `financial-report-analysis/tests/integration/test_p5_recompute_review_flow.py`

- [ ] **Step 1: Write the failing public export and integration tests**

Append to `financial-report-analysis/tests/unit/test_public_exports.py`:

```python
def test_post_p5_public_exports_are_available() -> None:
    from financial_report_analysis.p5 import (
        build_dataset_lineage,
        build_dataset_review_surface,
        build_extracted_review_surface,
        build_recompute_plan,
        execute_recompute_plan,
    )

    assert callable(build_extracted_review_surface)
    assert callable(build_dataset_review_surface)
    assert callable(build_dataset_lineage)
    assert callable(build_recompute_plan)
    assert callable(execute_recompute_plan)
```

Create `financial-report-analysis/tests/integration/test_p5_recompute_review_flow.py`:

```python
from pathlib import Path

from financial_report_analysis.p5.lineage import build_dataset_lineage
from financial_report_analysis.p5.review import (
    build_dataset_review_surface,
    build_extracted_review_surface,
)
from financial_report_analysis.p5.recompute import (
    build_recompute_plan,
    execute_recompute_plan,
)
from financial_report_analysis.p5.runner import run_p5_dataset_build


def test_p5_recompute_review_flow_uses_persisted_artifacts(
    tmp_path: Path,
) -> None:
    manifest_path = (
        Path(__file__).resolve().parents[1] / "fixtures" / "p5_seed_manifest.json"
    )
    pdf_root = Path(__file__).resolve().parents[3]

    initial = run_p5_dataset_build(
        manifest_path=manifest_path,
        artifact_root=tmp_path / "p5",
        dataset_id="p5_seed_review_flow",
        pdf_root=pdf_root,
        required_metric_ids=("revenue", "cash", "operating_cash_flow"),
        now_func=lambda: "2026-04-23T00:00:00",
    )
    plan = build_recompute_plan(
        manifest_id="p5_seed_3_issuers_2_years",
        dataset_id="p5_seed_review_flow",
        extracted_artifact_ids=initial.extracted_artifact_ids,
        reason="manual_review_check",
    )
    recomputed = execute_recompute_plan(
        plan=plan,
        manifest_path=manifest_path,
        artifact_root=tmp_path / "p5",
        pdf_root=pdf_root,
    )

    assert recomputed.dataset_path.exists()
    assert recomputed.turtle_export_path.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/test_public_exports.py::test_post_p5_public_exports_are_available tests/integration/test_p5_recompute_review_flow.py -q -o addopts=
```

Expected: FAIL due to missing public exports and/or missing integration file behavior.

- [ ] **Step 3: Export new public entry points**

Update `financial-report-analysis/src/financial_report_analysis/p5/__init__.py`:

```python
from financial_report_analysis.p5.lineage import build_dataset_lineage
from financial_report_analysis.p5.manifest import load_manifest
from financial_report_analysis.p5.recompute import (
    build_recompute_plan,
    execute_recompute_plan,
)
from financial_report_analysis.p5.review import (
    build_dataset_review_surface,
    build_extracted_review_surface,
)

__all__ = [
    "P5DatasetArtifact",
    "P5DatasetRow",
    "P5ExtractedArtifact",
    "P5Manifest",
    "P5ManifestEntry",
    "P5ManifestValidationError",
    "P5TurtleExport",
    "build_dataset_lineage",
    "build_dataset_review_surface",
    "build_extracted_review_surface",
    "build_recompute_plan",
    "execute_recompute_plan",
    "load_manifest",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/unit/test_p5_review.py tests/unit/test_p5_lineage.py tests/unit/test_p5_recompute.py tests/unit/test_public_exports.py::test_post_p5_public_exports_are_available tests/integration/test_p5_recompute_review_flow.py -q -o addopts=
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/__init__.py financial-report-analysis/tests/unit/test_public_exports.py financial-report-analysis/tests/integration/test_p5_recompute_review_flow.py
git commit -m "feat: add post-p5 review and recompute surfaces"
```

## Task 6: Full Focused Verification And Plan Closeout

**Files:**
- Verify: `financial-report-analysis/src/financial_report_analysis/p5/*.py`
- Verify: `financial-report-analysis/tests/unit/test_p5_review.py`
- Verify: `financial-report-analysis/tests/unit/test_p5_lineage.py`
- Verify: `financial-report-analysis/tests/unit/test_p5_recompute.py`
- Verify: `financial-report-analysis/tests/integration/test_p5_recompute_review_flow.py`

- [ ] **Step 1: Run focused post-P5 unit suite**

Run:

```bash
uv run pytest tests/unit/test_p5_manifest.py tests/unit/test_p5_artifact_repository.py tests/unit/test_p5_extraction.py tests/unit/test_p5_dataset.py tests/unit/test_p5_turtle_export.py tests/unit/test_p5_runner.py tests/unit/test_p5_review.py tests/unit/test_p5_lineage.py tests/unit/test_p5_recompute.py tests/unit/test_public_exports.py::test_p5_public_exports_are_available tests/unit/test_public_exports.py::test_post_p5_public_exports_are_available -q -o addopts=
```

Expected: all tests pass.

- [ ] **Step 2: Run focused integration suite**

Run:

```bash
uv run pytest tests/integration/test_p5_seed_dataset.py tests/integration/test_p5_recompute_review_flow.py -q -o addopts=
```

Expected: all tests pass, or `test_p5_seed_dataset.py` explicitly skips only when local seed PDFs are not available.

- [ ] **Step 3: Run Ruff**

Run:

```bash
uv run ruff check src tests
```

Expected: `All checks passed!`

- [ ] **Step 4: Update plan closure note if needed**

If this plan gains a closure note section during execution, append a short summary like:

```markdown
## Closure Note

- Review surface 已落地为 extracted / dataset 派生对象。
- Lineage contract 已能把 dataset row 追溯回 source artifact 与 source PDF。
- Recompute 先保持 deterministic-first，基于当前 P5 runner 复用。
- LLM whole-document assessment 仍保留为 future extension。
```

- [ ] **Step 5: Commit closeout**

```bash
git add financial-report-analysis/src/financial_report_analysis/p5 financial-report-analysis/tests/unit/test_p5_review.py financial-report-analysis/tests/unit/test_p5_lineage.py financial-report-analysis/tests/unit/test_p5_recompute.py financial-report-analysis/tests/integration/test_p5_recompute_review_flow.py financial-report-analysis/tests/unit/test_public_exports.py docs/superpowers/plans/2026-04-23-financial-report-analysis-post-p5-review-lineage-recompute-implementation-plan.md
git commit -m "feat: close post-p5 review and recompute foundation"
```

## Self-Review

### Spec coverage

- `review surface` -> Task 1, Task 2, Task 5
- `artifact lineage contract` -> Task 1, Task 3, Task 5
- `deterministic recompute contract` -> Task 1, Task 4, Task 5
- `JSON repository remains sufficient` -> all tasks stay inside current `p5` package and repository, no DB work introduced
- `LLM whole-document assessment remains future extension` -> no task implements it; it stays out of scope by design

### Placeholder scan

- No `TBD` / `TODO`
- Every code step includes concrete code
- Every verification step includes exact commands and expected outcome

### Type consistency

- New model names used consistently:
  - `P5ExtractedReviewSurface`
  - `P5DatasetReviewSurface`
  - `P5ArtifactLineage`
  - `P5RecomputePlan`
- New public functions used consistently:
  - `build_extracted_review_surface`
  - `build_dataset_review_surface`
  - `build_dataset_lineage`
  - `build_recompute_plan`
  - `execute_recompute_plan`
