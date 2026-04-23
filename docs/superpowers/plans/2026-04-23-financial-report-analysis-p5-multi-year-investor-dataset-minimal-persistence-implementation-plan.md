# P5 多年投资数据集与最小持久化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 P5 V1 的显式 manifest 输入、JSON artifact 持久化、单份报告预处理落盘、多年 dataset 组装和 Turtle alias export。

**Architecture:** 在 `financial_report_analysis.p5` 下新增独立子包，避免把 P5 持久化混入现有单报告 pipeline。`report/` 只作为外部下载器，P5 只读取 manifest 中的 `pdf_path`，并把分析结果落在 `financial-report-analysis/data/p5/` 下的 JSON artifact。dataset assembler 只消费 persisted extracted artifacts，不重复发现报告、不编排下载器、不新增字段覆盖。

**Tech Stack:** Python 3.10+, dataclasses, pathlib/json, existing `PdfIngestionAdapter`, existing `analyze_report`, pytest, Ruff.

---

## Scope Check

本计划只实现 P5 V1 的最小持久化和 dataset assembly。

明确不做：

- `report/` 下载器编排
- 股票代码 + 年份范围自动发现报告
- SQLite / PostgreSQL / migrations
- HTTP API
- CAGR / 平均 ROE / DCF / FCF Yield 等投资计算
- 新字段覆盖或广义 note/disclosure 扩张

## File Structure

- Create: `financial-report-analysis/src/financial_report_analysis/p5/__init__.py`
  - 导出 P5 V1 的公开入口。
- Create: `financial-report-analysis/src/financial_report_analysis/p5/models.py`
  - 定义 manifest、extracted artifact、dataset row、dataset artifact、Turtle export dataclasses 和校验错误。
- Create: `financial-report-analysis/src/financial_report_analysis/p5/manifest.py`
  - 负责读取、解析、校验 manifest JSON。
- Create: `financial-report-analysis/src/financial_report_analysis/p5/artifact_repository.py`
  - 负责 JSON artifact 路径规划、读写、原子写入和已存在 artifact 检查。
- Create: `financial-report-analysis/src/financial_report_analysis/p5/extraction.py`
  - 负责从 manifest entry 调用现有 ingestion + pipeline，生成 per-report extracted artifact。
- Create: `financial-report-analysis/src/financial_report_analysis/p5/dataset.py`
  - 负责从 extracted artifacts 组装 normalized multi-year dataset。
- Create: `financial-report-analysis/src/financial_report_analysis/p5/turtle_export.py`
  - 负责把 normalized dataset 转成 Turtle alias export。
- Create: `financial-report-analysis/src/financial_report_analysis/p5/runner.py`
  - 负责串起 manifest -> missing extraction artifacts -> dataset -> Turtle export。
- Modify: `financial-report-analysis/pyproject.toml`
  - 增加 `financial-report-analysis-p5` script entry point。
- Create: `financial-report-analysis/tests/unit/test_p5_manifest.py`
- Create: `financial-report-analysis/tests/unit/test_p5_artifact_repository.py`
- Create: `financial-report-analysis/tests/unit/test_p5_extraction.py`
- Create: `financial-report-analysis/tests/unit/test_p5_dataset.py`
- Create: `financial-report-analysis/tests/unit/test_p5_turtle_export.py`
- Create: `financial-report-analysis/tests/unit/test_p5_runner.py`
- Create: `financial-report-analysis/tests/integration/test_p5_seed_dataset.py`
- Create: `financial-report-analysis/tests/fixtures/p5_seed_manifest.json`
- Modify: `.gitignore`
  - 忽略 `financial-report-analysis/data/p5/extracted/` 和 `financial-report-analysis/data/p5/datasets/` 生成物，允许后续按需提交小型 manifest。

---

### Task 1: Manifest Contract And Validation

**Files:**

- Create: `financial-report-analysis/src/financial_report_analysis/p5/__init__.py`
- Create: `financial-report-analysis/src/financial_report_analysis/p5/models.py`
- Create: `financial-report-analysis/src/financial_report_analysis/p5/manifest.py`
- Create: `financial-report-analysis/tests/unit/test_p5_manifest.py`

- [ ] **Step 1: Write failing manifest tests**

Add `financial-report-analysis/tests/unit/test_p5_manifest.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from financial_report_analysis.p5.manifest import load_manifest
from financial_report_analysis.p5.models import P5ManifestValidationError


def test_load_manifest_accepts_three_issuer_seed(tmp_path: Path) -> None:
    pdf_a = tmp_path / "601919_2025.pdf"
    pdf_b = tmp_path / "02498_2022.pdf"
    pdf_c = tmp_path / "09987_2025.pdf"
    for path in (pdf_a, pdf_b, pdf_c):
        path.write_bytes(b"%PDF-1.4\n")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "p5_seed_3_issuers",
                "manifest_version": "1.0",
                "entries": [
                    {
                        "issuer_id": "CN_601919",
                        "market": "CN",
                        "stock_code": "601919",
                        "company_name": "中远海控",
                        "fiscal_year": 2025,
                        "report_type": "annual",
                        "pdf_path": str(pdf_a),
                        "source": "report",
                        "report_language": "zh",
                    },
                    {
                        "issuer_id": "HK_02498",
                        "market": "HK",
                        "stock_code": "02498",
                        "fiscal_year": 2022,
                        "report_type": "annual",
                        "pdf_path": str(pdf_b),
                        "source": "report",
                        "report_language": "en",
                    },
                    {
                        "issuer_id": "HK_09987",
                        "market": "HK",
                        "stock_code": "09987",
                        "fiscal_year": 2025,
                        "report_type": "annual",
                        "pdf_path": str(pdf_c),
                        "source": "report",
                        "report_language": "en",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manifest = load_manifest(manifest_path)

    assert manifest.manifest_id == "p5_seed_3_issuers"
    assert len(manifest.entries) == 3
    assert manifest.entries[0].artifact_id == "CN_601919_2025"
    assert manifest.entries[1].market == "HK"
    assert manifest.entries[2].pdf_path == pdf_c


def test_load_manifest_rejects_missing_pdf_path(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "bad",
                "manifest_version": "1.0",
                "entries": [
                    {
                        "issuer_id": "CN_601919",
                        "market": "CN",
                        "stock_code": "601919",
                        "fiscal_year": 2025,
                        "report_type": "annual",
                        "pdf_path": str(tmp_path / "missing.pdf"),
                        "source": "report",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(P5ManifestValidationError, match="pdf_path does not exist"):
        load_manifest(manifest_path)


def test_load_manifest_rejects_duplicate_entry_key(tmp_path: Path) -> None:
    pdf_path = tmp_path / "601919_2025.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    entry = {
        "issuer_id": "CN_601919",
        "market": "CN",
        "stock_code": "601919",
        "fiscal_year": 2025,
        "report_type": "annual",
        "pdf_path": str(pdf_path),
        "source": "report",
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "bad",
                "manifest_version": "1.0",
                "entries": [entry, dict(entry)],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(P5ManifestValidationError, match="duplicate manifest entry"):
        load_manifest(manifest_path)


def test_load_manifest_resolves_relative_pdf_path_from_pdf_root(tmp_path: Path) -> None:
    pdf_root = tmp_path / "repo"
    pdf_path = pdf_root / "report" / "downloads" / "cn_stocks" / "601919" / "annual" / "2025.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4\n")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "relative",
                "manifest_version": "1.0",
                "entries": [
                    {
                        "issuer_id": "CN_601919",
                        "market": "CN",
                        "stock_code": "601919",
                        "fiscal_year": 2025,
                        "report_type": "annual",
                        "pdf_path": "report/downloads/cn_stocks/601919/annual/2025.pdf",
                        "source": "report",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = load_manifest(manifest_path, pdf_root=pdf_root)

    assert manifest.entries[0].pdf_path == pdf_path
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_p5_manifest.py -q -o addopts=
```

Expected: fail because `financial_report_analysis.p5` does not exist.

- [ ] **Step 3: Add manifest models**

Create `financial-report-analysis/src/financial_report_analysis/p5/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Market = Literal["CN", "HK", "US"]
ReportType = Literal["annual", "semi_annual", "quarterly"]
MissingStatus = Literal["present", "absent", "not_surfaced", "out_of_scope", "unknown"]


class P5ManifestValidationError(ValueError):
    """Raised when a P5 manifest cannot be used safely."""


@dataclass(frozen=True, slots=True)
class P5ManifestEntry:
    issuer_id: str
    market: Market
    stock_code: str
    fiscal_year: int
    report_type: ReportType
    pdf_path: Path
    source: str
    company_name: str | None = None
    report_language: str | None = None

    @property
    def artifact_id(self) -> str:
        return f"{self.market}_{self.stock_code}_{self.fiscal_year}"

    @property
    def entry_key(self) -> tuple[str, int, str]:
        return (self.issuer_id, self.fiscal_year, self.report_type)


@dataclass(frozen=True, slots=True)
class P5Manifest:
    manifest_id: str
    manifest_version: str
    entries: tuple[P5ManifestEntry, ...]


@dataclass(frozen=True, slots=True)
class P5ExtractedArtifact:
    artifact_id: str
    artifact_version: str
    pipeline_version: str
    manifest_entry: P5ManifestEntry
    source_pdf_path: Path
    document: dict[str, Any]
    document_metadata: dict[str, Any]
    candidate_facts: tuple[dict[str, Any], ...]
    canonical_facts: tuple[dict[str, Any], ...]
    derived_facts: tuple[dict[str, Any], ...]
    validation_report: dict[str, Any]
    review_packets: tuple[dict[str, Any], ...]
    quality_gate: str
    missing_status: dict[str, dict[str, str]]
    created_at: str


@dataclass(frozen=True, slots=True)
class P5DatasetRow:
    issuer_id: str
    market: str
    stock_code: str
    fiscal_year: int
    metric_id: str
    entity_scope: str
    period_scope: str
    statement_type: str
    value: int | float | None
    currency: str | None
    unit: str | None
    quality_status: str | None
    missing_status: MissingStatus
    source_fact_id: str | None
    source_artifact_id: str
    evidence_bundle_id: str | None


@dataclass(frozen=True, slots=True)
class P5DatasetArtifact:
    dataset_id: str
    dataset_version: str
    created_at: str
    issuer_count: int
    periods: tuple[int, ...]
    metrics: tuple[str, ...]
    rows: tuple[P5DatasetRow, ...]
    quality_summary: dict[str, Any]
    source_artifacts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class P5TurtleExport:
    dataset_id: str
    dataset_version: str
    created_at: str
    rows: tuple[dict[str, Any], ...]
    alias_map: dict[str, str] = field(default_factory=dict)
```

Create `financial-report-analysis/src/financial_report_analysis/p5/__init__.py`:

```python
from financial_report_analysis.p5.manifest import load_manifest
from financial_report_analysis.p5.models import (
    P5DatasetArtifact,
    P5DatasetRow,
    P5ExtractedArtifact,
    P5Manifest,
    P5ManifestEntry,
    P5ManifestValidationError,
    P5TurtleExport,
)

__all__ = [
    "P5DatasetArtifact",
    "P5DatasetRow",
    "P5ExtractedArtifact",
    "P5Manifest",
    "P5ManifestEntry",
    "P5ManifestValidationError",
    "P5TurtleExport",
    "load_manifest",
]
```

- [ ] **Step 4: Add manifest loader**

Create `financial-report-analysis/src/financial_report_analysis/p5/manifest.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from financial_report_analysis.p5.models import (
    P5Manifest,
    P5ManifestEntry,
    P5ManifestValidationError,
)

_SUPPORTED_MARKETS = {"CN", "HK", "US"}
_SUPPORTED_REPORT_TYPES = {"annual", "semi_annual", "quarterly"}


def load_manifest(path: str | Path, *, pdf_root: str | Path | None = None) -> P5Manifest:
    manifest_path = Path(path)
    base_dir = Path(pdf_root) if pdf_root is not None else manifest_path.parent
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise P5ManifestValidationError("manifest root must be an object")

    manifest_id = _required_text(payload, "manifest_id")
    manifest_version = _required_text(payload, "manifest_version")
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise P5ManifestValidationError("entries must be a non-empty list")

    entries = tuple(_parse_entry(entry, base_dir=base_dir) for entry in raw_entries)
    seen: set[tuple[str, int, str]] = set()
    for entry in entries:
        if entry.entry_key in seen:
            raise P5ManifestValidationError(
                f"duplicate manifest entry: {entry.entry_key}"
            )
        seen.add(entry.entry_key)

    return P5Manifest(
        manifest_id=manifest_id,
        manifest_version=manifest_version,
        entries=entries,
    )


def _parse_entry(payload: Any, *, base_dir: Path) -> P5ManifestEntry:
    if not isinstance(payload, dict):
        raise P5ManifestValidationError("manifest entry must be an object")

    market = _required_text(payload, "market").upper()
    if market not in _SUPPORTED_MARKETS:
        raise P5ManifestValidationError(f"unsupported market: {market}")

    report_type = _required_text(payload, "report_type")
    if report_type not in _SUPPORTED_REPORT_TYPES:
        raise P5ManifestValidationError(f"unsupported report_type: {report_type}")

    fiscal_year = payload.get("fiscal_year")
    if not isinstance(fiscal_year, int) or fiscal_year < 1900:
        raise P5ManifestValidationError("fiscal_year must be an integer year")

    pdf_path = Path(_required_text(payload, "pdf_path")).expanduser()
    if not pdf_path.is_absolute():
        pdf_path = base_dir / pdf_path
    if not pdf_path.exists():
        raise P5ManifestValidationError(f"pdf_path does not exist: {pdf_path}")
    pdf_path = pdf_path.resolve()

    return P5ManifestEntry(
        issuer_id=_required_text(payload, "issuer_id"),
        market=market,  # type: ignore[arg-type]
        stock_code=_required_text(payload, "stock_code"),
        fiscal_year=fiscal_year,
        report_type=report_type,  # type: ignore[arg-type]
        pdf_path=pdf_path,
        source=_required_text(payload, "source"),
        company_name=_optional_text(payload, "company_name"),
        report_language=_optional_text(payload, "report_language"),
    )


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise P5ManifestValidationError(f"{key} must be a non-empty string")
    return value.strip()


def _optional_text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise P5ManifestValidationError(f"{key} must be a string when provided")
    normalized = value.strip()
    return normalized or None
```

- [ ] **Step 5: Run manifest tests**

Run:

```bash
uv run pytest tests/unit/test_p5_manifest.py -q -o addopts=
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/p5 financial-report-analysis/tests/unit/test_p5_manifest.py
git commit -m "feat: add p5 manifest contract"
```

---

### Task 2: JSON Artifact Repository

**Files:**

- Create: `financial-report-analysis/src/financial_report_analysis/p5/artifact_repository.py`
- Create: `financial-report-analysis/tests/unit/test_p5_artifact_repository.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing repository tests**

Add `financial-report-analysis/tests/unit/test_p5_artifact_repository.py`:

```python
from __future__ import annotations

from pathlib import Path

from financial_report_analysis.p5.artifact_repository import P5JsonArtifactRepository
from financial_report_analysis.p5.models import (
    P5DatasetArtifact,
    P5DatasetRow,
    P5ExtractedArtifact,
    P5ManifestEntry,
)


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
        company_name="中远海控",
        report_language="zh",
    )


def test_repository_round_trips_extracted_artifact(tmp_path: Path) -> None:
    repository = P5JsonArtifactRepository(tmp_path / "data" / "p5")
    entry = _entry(tmp_path)
    artifact = P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={"document_id": "doc-1"},
        document_metadata={"working_capital_missing_status": {"notes_receiv": "absent"}},
        candidate_facts=({"fact_id": "candidate-1"},),
        canonical_facts=({"fact_id": "canonical-1", "metric_id": "revenue"},),
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate="pass",
        missing_status={"working_capital_missing_status": {"notes_receiv": "absent"}},
        created_at="2026-04-23T00:00:00",
    )

    repository.save_extracted_artifact(artifact)
    loaded = repository.load_extracted_artifact("CN_601919_2025")

    assert loaded.artifact_id == "CN_601919_2025"
    assert loaded.manifest_entry.company_name == "中远海控"
    assert loaded.canonical_facts[0]["metric_id"] == "revenue"
    assert repository.extracted_artifact_exists("CN_601919_2025") is True


def test_repository_round_trips_dataset_artifact(tmp_path: Path) -> None:
    repository = P5JsonArtifactRepository(tmp_path / "data" / "p5")
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
                source_fact_id="canonical-1",
                source_artifact_id="CN_601919_2025",
                evidence_bundle_id="bundle-1",
            ),
        ),
        quality_summary={"missing_by_metric": {}, "unknown_count": 0},
        source_artifacts=("CN_601919_2025",),
    )

    repository.save_dataset_artifact(dataset)
    loaded = repository.load_dataset_artifact("p5_seed")

    assert loaded.dataset_id == "p5_seed"
    assert loaded.rows[0].metric_id == "revenue"
    assert loaded.rows[0].missing_status == "present"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_p5_artifact_repository.py -q -o addopts=
```

Expected: fail because `P5JsonArtifactRepository` does not exist.

- [ ] **Step 3: Implement JSON repository**

Create `financial-report-analysis/src/financial_report_analysis/p5/artifact_repository.py`:

```python
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from financial_report_analysis.p5.models import (
    P5DatasetArtifact,
    P5DatasetRow,
    P5ExtractedArtifact,
    P5ManifestEntry,
)


class P5JsonArtifactRepository:
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.extracted_dir = self.root_dir / "extracted"
        self.datasets_dir = self.root_dir / "datasets"

    def extracted_artifact_exists(self, artifact_id: str) -> bool:
        return self._extracted_path(artifact_id).exists()

    def save_extracted_artifact(self, artifact: P5ExtractedArtifact) -> Path:
        payload = _extracted_to_json(artifact)
        return self._write_json(self._extracted_path(artifact.artifact_id), payload)

    def load_extracted_artifact(self, artifact_id: str) -> P5ExtractedArtifact:
        payload = self._read_json(self._extracted_path(artifact_id))
        return _extracted_from_json(payload)

    def save_dataset_artifact(self, dataset: P5DatasetArtifact) -> Path:
        payload = _dataset_to_json(dataset)
        return self._write_json(self._dataset_path(dataset.dataset_id), payload)

    def load_dataset_artifact(self, dataset_id: str) -> P5DatasetArtifact:
        payload = self._read_json(self._dataset_path(dataset_id))
        return _dataset_from_json(payload)

    def _extracted_path(self, artifact_id: str) -> Path:
        return self.extracted_dir / f"{artifact_id}.json"

    def _dataset_path(self, dataset_id: str) -> Path:
        return self.datasets_dir / f"{dataset_id}.json"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(path)
        return path


def _entry_to_json(entry: P5ManifestEntry) -> dict[str, Any]:
    payload = asdict(entry)
    payload["pdf_path"] = str(entry.pdf_path)
    return payload


def _entry_from_json(payload: dict[str, Any]) -> P5ManifestEntry:
    return P5ManifestEntry(
        issuer_id=str(payload["issuer_id"]),
        market=str(payload["market"]),  # type: ignore[arg-type]
        stock_code=str(payload["stock_code"]),
        fiscal_year=int(payload["fiscal_year"]),
        report_type=str(payload["report_type"]),  # type: ignore[arg-type]
        pdf_path=Path(str(payload["pdf_path"])),
        source=str(payload["source"]),
        company_name=payload.get("company_name"),
        report_language=payload.get("report_language"),
    )


def _extracted_to_json(artifact: P5ExtractedArtifact) -> dict[str, Any]:
    payload = asdict(artifact)
    payload["manifest_entry"] = _entry_to_json(artifact.manifest_entry)
    payload["source_pdf_path"] = str(artifact.source_pdf_path)
    payload["candidate_facts"] = list(artifact.candidate_facts)
    payload["canonical_facts"] = list(artifact.canonical_facts)
    payload["derived_facts"] = list(artifact.derived_facts)
    payload["review_packets"] = list(artifact.review_packets)
    return payload


def _extracted_from_json(payload: dict[str, Any]) -> P5ExtractedArtifact:
    return P5ExtractedArtifact(
        artifact_id=str(payload["artifact_id"]),
        artifact_version=str(payload["artifact_version"]),
        pipeline_version=str(payload["pipeline_version"]),
        manifest_entry=_entry_from_json(payload["manifest_entry"]),
        source_pdf_path=Path(str(payload["source_pdf_path"])),
        document=dict(payload["document"]),
        document_metadata=dict(payload["document_metadata"]),
        candidate_facts=tuple(payload.get("candidate_facts", [])),
        canonical_facts=tuple(payload.get("canonical_facts", [])),
        derived_facts=tuple(payload.get("derived_facts", [])),
        validation_report=dict(payload["validation_report"]),
        review_packets=tuple(payload.get("review_packets", [])),
        quality_gate=str(payload["quality_gate"]),
        missing_status=dict(payload.get("missing_status", {})),
        created_at=str(payload["created_at"]),
    )


def _dataset_to_json(dataset: P5DatasetArtifact) -> dict[str, Any]:
    payload = asdict(dataset)
    payload["periods"] = list(dataset.periods)
    payload["metrics"] = list(dataset.metrics)
    payload["rows"] = [asdict(row) for row in dataset.rows]
    payload["source_artifacts"] = list(dataset.source_artifacts)
    return payload


def _dataset_from_json(payload: dict[str, Any]) -> P5DatasetArtifact:
    return P5DatasetArtifact(
        dataset_id=str(payload["dataset_id"]),
        dataset_version=str(payload["dataset_version"]),
        created_at=str(payload["created_at"]),
        issuer_count=int(payload["issuer_count"]),
        periods=tuple(int(period) for period in payload.get("periods", [])),
        metrics=tuple(str(metric) for metric in payload.get("metrics", [])),
        rows=tuple(P5DatasetRow(**row) for row in payload.get("rows", [])),
        quality_summary=dict(payload.get("quality_summary", {})),
        source_artifacts=tuple(str(item) for item in payload.get("source_artifacts", [])),
    )
```

- [ ] **Step 4: Ignore generated P5 artifacts**

Modify `.gitignore` and append:

```gitignore
# P5 generated local artifacts
financial-report-analysis/data/p5/extracted/
financial-report-analysis/data/p5/datasets/
```

- [ ] **Step 5: Run repository tests**

Run:

```bash
uv run pytest tests/unit/test_p5_artifact_repository.py -q -o addopts=
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add .gitignore financial-report-analysis/src/financial_report_analysis/p5/artifact_repository.py financial-report-analysis/tests/unit/test_p5_artifact_repository.py
git commit -m "feat: add p5 json artifact repository"
```

---

### Task 3: Per-Report Extracted Artifact Builder

**Files:**

- Create: `financial-report-analysis/src/financial_report_analysis/p5/extraction.py`
- Create: `financial-report-analysis/tests/unit/test_p5_extraction.py`

- [ ] **Step 1: Write failing extraction artifact tests**

Add `financial-report-analysis/tests/unit/test_p5_extraction.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from financial_report_analysis.p5.extraction import build_extracted_artifact
from financial_report_analysis.p5.models import P5ManifestEntry


@dataclass
class _FakeValidationReport:
    overall_status: str
    issues: tuple[str, ...]


@dataclass
class _FakePipelineResult:
    canonical_fact_set_id: str
    derived_fact_set_id: str
    validation_report_id: str
    quality_gate: str
    canonical_facts: list[dict[str, object]]
    derived_facts: list[dict[str, object]]
    validation_report: _FakeValidationReport
    review_packets: list[dict[str, object]]


class _FakeIngestionAdapter:
    def extract_candidate_facts(
        self,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
        market: str | None,
        min_confidence: float | None,
    ) -> dict[str, object]:
        assert pdf_url is None
        assert pdf_path is not None
        assert market == "CN"
        assert min_confidence is None
        return {
            "document_metadata": {
                "language": "zh",
                "working_capital_missing_status": {"notes_receiv": "absent"},
            },
            "candidate_facts": [{"fact_id": "candidate-1", "metric_id": "revenue"}],
        }


def test_build_extracted_artifact_uses_existing_pipeline(tmp_path: Path) -> None:
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
        company_name="中远海控",
        report_language="zh",
    )

    def fake_analyze_report(
        document_ref: dict[str, object],
        extracted_payload: dict[str, object],
    ) -> _FakePipelineResult:
        assert document_ref["document_id"] == str(pdf_path)
        assert extracted_payload["candidate_facts"]
        return _FakePipelineResult(
            canonical_fact_set_id="doc:canonical:v1",
            derived_fact_set_id="doc:derived:v1",
            validation_report_id="doc:validation:v1",
            quality_gate="pass",
            canonical_facts=[{"fact_id": "canonical-1", "metric_id": "revenue"}],
            derived_facts=[],
            validation_report=_FakeValidationReport(overall_status="ok", issues=()),
            review_packets=[],
        )

    artifact = build_extracted_artifact(
        entry,
        ingestion_adapter=_FakeIngestionAdapter(),
        analyze_report_func=fake_analyze_report,
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert artifact.artifact_id == "CN_601919_2025"
    assert artifact.pipeline_version == "p5-v1"
    assert artifact.document["market"] == "CN"
    assert artifact.document_metadata["language"] == "zh"
    assert artifact.candidate_facts[0]["fact_id"] == "candidate-1"
    assert artifact.canonical_facts[0]["metric_id"] == "revenue"
    assert artifact.validation_report == {"overall_status": "ok", "issues": ()}
    assert artifact.missing_status == {
        "working_capital_missing_status": {"notes_receiv": "absent"}
    }
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_p5_extraction.py -q -o addopts=
```

Expected: fail because `p5.extraction` does not exist.

- [ ] **Step 3: Implement extracted artifact builder**

Create `financial-report-analysis/src/financial_report_analysis/p5/extraction.py`:

```python
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Callable

from financial_report_analysis.ingestion import PdfIngestionAdapter
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.pipeline import analyze_report

P5_PIPELINE_VERSION = "p5-v1"
P5_ARTIFACT_VERSION = "1.0"

_MISSING_STATUS_KEYS = (
    "working_capital_missing_status",
    "debt_missing_status",
    "asset_missing_status",
    "cash_health_missing_status",
)


def build_extracted_artifact(
    entry: P5ManifestEntry,
    *,
    ingestion_adapter: Any | None = None,
    analyze_report_func: Callable[[dict[str, Any], dict[str, Any]], Any] = analyze_report,
    now_func: Callable[[], str] | None = None,
) -> P5ExtractedArtifact:
    adapter = ingestion_adapter or PdfIngestionAdapter()
    extracted_payload = adapter.extract_candidate_facts(
        pdf_path=str(entry.pdf_path),
        pdf_url=None,
        market=entry.market,
        min_confidence=None,
    )
    document_metadata = dict(extracted_payload.get("document_metadata", {}))
    document = {
        "document_id": str(entry.pdf_path),
        "pdf_path": str(entry.pdf_path),
        "market": entry.market,
        "stock_code": entry.stock_code,
        "issuer_id": entry.issuer_id,
        "fiscal_year": entry.fiscal_year,
        "report_type": entry.report_type,
        "company_name": entry.company_name,
        "language": document_metadata.get("language") or entry.report_language,
        "metadata": document_metadata,
    }
    pipeline_result = analyze_report_func(
        document_ref=document,
        extracted_payload=extracted_payload,
    )
    pipeline_data = _to_dict(pipeline_result)
    created_at = now_func() if now_func is not None else datetime.now().isoformat()

    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version=P5_ARTIFACT_VERSION,
        pipeline_version=P5_PIPELINE_VERSION,
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document=document,
        document_metadata=document_metadata,
        candidate_facts=tuple(extracted_payload.get("candidate_facts", [])),
        canonical_facts=tuple(_to_dict(fact) for fact in pipeline_data.get("canonical_facts", [])),
        derived_facts=tuple(_to_dict(fact) for fact in pipeline_data.get("derived_facts", [])),
        validation_report=_to_dict(pipeline_data.get("validation_report", {})),
        review_packets=tuple(_to_dict(packet) for packet in pipeline_data.get("review_packets", [])),
        quality_gate=str(pipeline_data.get("quality_gate", "review")),
        missing_status=_extract_missing_status(document_metadata),
        created_at=created_at,
    )


def _extract_missing_status(document_metadata: dict[str, Any]) -> dict[str, dict[str, str]]:
    statuses: dict[str, dict[str, str]] = {}
    for key in _MISSING_STATUS_KEYS:
        value = document_metadata.get(key)
        if isinstance(value, dict):
            statuses[key] = {str(metric): str(status) for metric, status in value.items()}
    return statuses


def _to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}
```

- [ ] **Step 4: Run extraction tests**

Run:

```bash
uv run pytest tests/unit/test_p5_extraction.py -q -o addopts=
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/extraction.py financial-report-analysis/tests/unit/test_p5_extraction.py
git commit -m "feat: persist p5 per-report extraction artifacts"
```

---

### Task 4: Multi-Year Dataset Assembly

**Files:**

- Create: `financial-report-analysis/src/financial_report_analysis/p5/dataset.py`
- Create: `financial-report-analysis/tests/unit/test_p5_dataset.py`

- [ ] **Step 1: Write failing dataset assembly tests**

Add `financial-report-analysis/tests/unit/test_p5_dataset.py`:

```python
from __future__ import annotations

from pathlib import Path

from financial_report_analysis.p5.dataset import assemble_dataset
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry


def _artifact(
    *,
    tmp_path: Path,
    fiscal_year: int,
    canonical_facts: tuple[dict[str, object], ...],
    missing_status: dict[str, dict[str, str]] | None = None,
    quality_gate: str = "pass",
) -> P5ExtractedArtifact:
    pdf_path = tmp_path / f"report_{fiscal_year}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=fiscal_year,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
    )
    return P5ExtractedArtifact(
        artifact_id=entry.artifact_id,
        artifact_version="1.0",
        pipeline_version="p5-v1",
        manifest_entry=entry,
        source_pdf_path=entry.pdf_path,
        document={"document_id": str(pdf_path)},
        document_metadata={},
        candidate_facts=(),
        canonical_facts=canonical_facts,
        derived_facts=(),
        validation_report={"overall_status": "ok", "issues": []},
        review_packets=(),
        quality_gate=quality_gate,
        missing_status=missing_status or {},
        created_at="2026-04-23T00:00:00",
    )


def test_assemble_dataset_emits_present_rows_from_canonical_facts(tmp_path: Path) -> None:
    artifact_2025 = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(
            {
                "fact_id": "fact-2025-revenue",
                "metric_id": "revenue",
                "statement_type": "income_statement",
                "entity_scope": "consolidated",
                "period_id": "2025FY",
                "numeric_value": 100.0,
                "currency": "CNY",
                "normalized_unit": "currency_amount",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-1",
                "extensions": {"period_scope": "duration"},
            },
        ),
    )
    artifact_2024 = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2024,
        canonical_facts=(
            {
                "fact_id": "fact-2024-cash",
                "metric_id": "cash",
                "statement_type": "balance_sheet",
                "entity_scope": "consolidated",
                "period_id": "2024FY",
                "numeric_value": 80.0,
                "currency": "CNY",
                "raw_unit": "CNY",
                "quality_status": "ok",
                "evidence_bundle_id": "bundle-2",
                "extensions": {"period_scope": "point_in_time"},
            },
        ),
    )

    dataset = assemble_dataset(
        dataset_id="p5_seed",
        artifacts=(artifact_2025, artifact_2024),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert dataset.dataset_id == "p5_seed"
    assert dataset.issuer_count == 1
    assert dataset.periods == (2024, 2025)
    assert dataset.metrics == ("cash", "revenue")
    assert len(dataset.rows) == 2
    revenue_row = next(row for row in dataset.rows if row.metric_id == "revenue")
    assert revenue_row.value == 100.0
    assert revenue_row.period_scope == "duration"
    assert revenue_row.missing_status == "present"
    cash_row = next(row for row in dataset.rows if row.metric_id == "cash")
    assert cash_row.period_scope == "point_in_time"


def test_assemble_dataset_surfaces_unknown_missing_summary(tmp_path: Path) -> None:
    artifact = _artifact(
        tmp_path=tmp_path,
        fiscal_year=2025,
        canonical_facts=(),
        missing_status={"asset_missing_status": {"goodwill": "not_surfaced"}},
        quality_gate="review",
    )

    dataset = assemble_dataset(
        dataset_id="p5_seed",
        artifacts=(artifact,),
        required_metric_ids=("goodwill", "revenue"),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert {row.metric_id: row.missing_status for row in dataset.rows} == {
        "goodwill": "not_surfaced",
        "revenue": "unknown",
    }
    assert dataset.quality_summary["unknown_count"] == 1
    assert dataset.quality_summary["review_required_artifacts"] == ["CN_601919_2025"]
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_p5_dataset.py -q -o addopts=
```

Expected: fail because `assemble_dataset` does not exist.

- [ ] **Step 3: Implement dataset assembler**

Create `financial-report-analysis/src/financial_report_analysis/p5/dataset.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from financial_report_analysis.p5.models import (
    MissingStatus,
    P5DatasetArtifact,
    P5DatasetRow,
    P5ExtractedArtifact,
)

P5_DATASET_VERSION = "1.0"


def assemble_dataset(
    *,
    dataset_id: str,
    artifacts: tuple[P5ExtractedArtifact, ...],
    required_metric_ids: tuple[str, ...] = (),
    now_func: Callable[[], str] | None = None,
) -> P5DatasetArtifact:
    created_at = now_func() if now_func is not None else datetime.now().isoformat()
    present_rows = [_row_from_fact(artifact, fact) for artifact in artifacts for fact in artifact.canonical_facts]
    missing_rows = _missing_rows(
        artifacts=artifacts,
        present_rows=tuple(present_rows),
        required_metric_ids=required_metric_ids,
    )
    rows = tuple(sorted([*present_rows, *missing_rows], key=_row_sort_key))
    periods = tuple(sorted({row.fiscal_year for row in rows}))
    metrics = tuple(sorted({row.metric_id for row in rows}))
    issuer_count = len({artifact.manifest_entry.issuer_id for artifact in artifacts})

    return P5DatasetArtifact(
        dataset_id=dataset_id,
        dataset_version=P5_DATASET_VERSION,
        created_at=created_at,
        issuer_count=issuer_count,
        periods=periods,
        metrics=metrics,
        rows=rows,
        quality_summary=_quality_summary(artifacts=artifacts, rows=rows),
        source_artifacts=tuple(sorted(artifact.artifact_id for artifact in artifacts)),
    )


def _row_from_fact(
    artifact: P5ExtractedArtifact,
    fact: dict[str, Any],
) -> P5DatasetRow:
    entry = artifact.manifest_entry
    extensions = fact.get("extensions")
    if not isinstance(extensions, dict):
        extensions = {}
    return P5DatasetRow(
        issuer_id=entry.issuer_id,
        market=entry.market,
        stock_code=entry.stock_code,
        fiscal_year=entry.fiscal_year,
        metric_id=str(fact["metric_id"]),
        entity_scope=str(fact.get("entity_scope", "unknown")),
        period_scope=str(extensions.get("period_scope", "unknown")),
        statement_type=str(fact.get("statement_type", "metrics")),
        value=_numeric_value(fact.get("numeric_value")),
        currency=_optional_string(fact.get("currency")),
        unit=_optional_string(fact.get("normalized_unit") or fact.get("raw_unit")),
        quality_status=_optional_string(fact.get("quality_status")),
        missing_status="present",
        source_fact_id=_optional_string(fact.get("fact_id")),
        source_artifact_id=artifact.artifact_id,
        evidence_bundle_id=_optional_string(fact.get("evidence_bundle_id")),
    )


def _missing_rows(
    *,
    artifacts: tuple[P5ExtractedArtifact, ...],
    present_rows: tuple[P5DatasetRow, ...],
    required_metric_ids: tuple[str, ...],
) -> list[P5DatasetRow]:
    present_keys = {
        (row.source_artifact_id, row.metric_id, row.entity_scope)
        for row in present_rows
    }
    rows: list[P5DatasetRow] = []
    for artifact in artifacts:
        entry = artifact.manifest_entry
        statuses = _flatten_missing_status(artifact.missing_status)
        for metric_id in sorted(set(required_metric_ids) | set(statuses)):
            if (artifact.artifact_id, metric_id, "consolidated") in present_keys:
                continue
            status = statuses.get(metric_id, "unknown")
            rows.append(
                P5DatasetRow(
                    issuer_id=entry.issuer_id,
                    market=entry.market,
                    stock_code=entry.stock_code,
                    fiscal_year=entry.fiscal_year,
                    metric_id=metric_id,
                    entity_scope="consolidated",
                    period_scope="unknown",
                    statement_type="metrics",
                    value=None,
                    currency=None,
                    unit=None,
                    quality_status=None,
                    missing_status=status,  # type: ignore[arg-type]
                    source_fact_id=None,
                    source_artifact_id=artifact.artifact_id,
                    evidence_bundle_id=None,
                )
            )
    return rows


def _flatten_missing_status(
    missing_status: dict[str, dict[str, str]],
) -> dict[str, MissingStatus]:
    flattened: dict[str, MissingStatus] = {}
    allowed = {"present", "absent", "not_surfaced", "out_of_scope", "unknown"}
    for status_map in missing_status.values():
        for metric_id, status in status_map.items():
            normalized = status if status in allowed else "unknown"
            flattened[metric_id] = normalized  # type: ignore[assignment]
    return flattened


def _quality_summary(
    *,
    artifacts: tuple[P5ExtractedArtifact, ...],
    rows: tuple[P5DatasetRow, ...],
) -> dict[str, Any]:
    missing_by_metric: dict[str, int] = {}
    missing_by_issuer: dict[str, int] = {}
    unknown_count = 0
    for row in rows:
        if row.missing_status == "present":
            continue
        missing_by_metric[row.metric_id] = missing_by_metric.get(row.metric_id, 0) + 1
        missing_by_issuer[row.issuer_id] = missing_by_issuer.get(row.issuer_id, 0) + 1
        if row.missing_status == "unknown":
            unknown_count += 1
    return {
        "missing_by_metric": missing_by_metric,
        "missing_by_issuer": missing_by_issuer,
        "unknown_count": unknown_count,
        "review_required_artifacts": sorted(
            artifact.artifact_id
            for artifact in artifacts
            if artifact.quality_gate != "pass"
        ),
        "duplicate_fact_conflicts": [],
        "scope_mismatch_warnings": [],
    }


def _row_sort_key(row: P5DatasetRow) -> tuple[object, ...]:
    return (
        row.issuer_id,
        row.fiscal_year,
        row.metric_id,
        row.entity_scope,
        row.period_scope,
        row.statement_type,
    )


def _numeric_value(value: object) -> int | float | None:
    if isinstance(value, (int, float)):
        return value
    return None


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
```

- [ ] **Step 4: Run dataset tests**

Run:

```bash
uv run pytest tests/unit/test_p5_dataset.py -q -o addopts=
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/dataset.py financial-report-analysis/tests/unit/test_p5_dataset.py
git commit -m "feat: assemble p5 multi-year dataset artifacts"
```

---

### Task 5: Turtle Alias Export

**Files:**

- Create: `financial-report-analysis/src/financial_report_analysis/p5/turtle_export.py`
- Create: `financial-report-analysis/tests/unit/test_p5_turtle_export.py`

- [ ] **Step 1: Write failing Turtle export tests**

Add `financial-report-analysis/tests/unit/test_p5_turtle_export.py`:

```python
from __future__ import annotations

from financial_report_analysis.p5.models import P5DatasetArtifact, P5DatasetRow
from financial_report_analysis.p5.turtle_export import build_turtle_export


def test_build_turtle_export_maps_canonical_ids_to_turtle_aliases() -> None:
    dataset = P5DatasetArtifact(
        dataset_id="p5_seed",
        dataset_version="1.0",
        created_at="2026-04-23T00:00:00",
        issuer_count=1,
        periods=(2025,),
        metrics=("cash", "operating_cash_flow", "revenue"),
        rows=(
            P5DatasetRow(
                issuer_id="CN_601919",
                market="CN",
                stock_code="601919",
                fiscal_year=2025,
                metric_id="cash",
                entity_scope="consolidated",
                period_scope="point_in_time",
                statement_type="balance_sheet",
                value=100.0,
                currency="CNY",
                unit="currency_amount",
                quality_status="ok",
                missing_status="present",
                source_fact_id="fact-cash",
                source_artifact_id="CN_601919_2025",
                evidence_bundle_id="bundle-cash",
            ),
            P5DatasetRow(
                issuer_id="CN_601919",
                market="CN",
                stock_code="601919",
                fiscal_year=2025,
                metric_id="operating_cash_flow",
                entity_scope="consolidated",
                period_scope="duration",
                statement_type="cash_flow_statement",
                value=80.0,
                currency="CNY",
                unit="currency_amount",
                quality_status="ok",
                missing_status="present",
                source_fact_id="fact-ocf",
                source_artifact_id="CN_601919_2025",
                evidence_bundle_id="bundle-ocf",
            ),
        ),
        quality_summary={},
        source_artifacts=("CN_601919_2025",),
    )

    export = build_turtle_export(dataset)

    assert export.dataset_id == "p5_seed"
    assert export.alias_map["cash"] == "money_cap"
    assert export.rows[0]["turtle_field"] == "money_cap"
    assert export.rows[1]["turtle_field"] == "n_cashflow_act"
    assert export.rows[0]["canonical_metric_id"] == "cash"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_p5_turtle_export.py -q -o addopts=
```

Expected: fail because `p5.turtle_export` does not exist.

- [ ] **Step 3: Implement Turtle export**

Create `financial-report-analysis/src/financial_report_analysis/p5/turtle_export.py`:

```python
from __future__ import annotations

from dataclasses import asdict

from financial_report_analysis.p5.models import P5DatasetArtifact, P5TurtleExport

TURTLE_ALIAS_MAP = {
    "operating_cost": "oper_cost",
    "operating_profit": "operate_profit",
    "net_profit": "n_income",
    "total_liabilities": "total_liab",
    "equity_attributable_to_owners": "total_hldr_eqy_exc_min_int",
    "operating_cash_flow": "n_cashflow_act",
    "investing_cash_flow": "n_cashflow_inv_act",
    "financing_cash_flow": "n_cash_flows_fnc_act",
    "cash": "money_cap",
}


def build_turtle_export(dataset: P5DatasetArtifact) -> P5TurtleExport:
    rows = []
    for row in dataset.rows:
        turtle_field = TURTLE_ALIAS_MAP.get(row.metric_id, row.metric_id)
        payload = asdict(row)
        payload["canonical_metric_id"] = row.metric_id
        payload["turtle_field"] = turtle_field
        rows.append(payload)
    return P5TurtleExport(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        created_at=dataset.created_at,
        rows=tuple(rows),
        alias_map=dict(TURTLE_ALIAS_MAP),
    )
```

- [ ] **Step 4: Run Turtle export tests**

Run:

```bash
uv run pytest tests/unit/test_p5_turtle_export.py -q -o addopts=
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/p5/turtle_export.py financial-report-analysis/tests/unit/test_p5_turtle_export.py
git commit -m "feat: add p5 turtle export adapter"
```

---

### Task 6: P5 Runner And CLI Entry Point

**Files:**

- Create: `financial-report-analysis/src/financial_report_analysis/p5/runner.py`
- Modify: `financial-report-analysis/pyproject.toml`
- Create: `financial-report-analysis/tests/unit/test_p5_runner.py`

- [ ] **Step 1: Write failing runner tests**

Add `financial-report-analysis/tests/unit/test_p5_runner.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.p5.runner import run_p5_dataset_build


def test_run_p5_dataset_build_reuses_existing_extracted_artifacts(tmp_path: Path) -> None:
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_id": "p5_seed",
                "manifest_version": "1.0",
                "entries": [
                    {
                        "issuer_id": "CN_601919",
                        "market": "CN",
                        "stock_code": "601919",
                        "fiscal_year": 2025,
                        "report_type": "annual",
                        "pdf_path": str(pdf_path),
                        "source": "report",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    artifact_root = tmp_path / "data" / "p5"
    entry = P5ManifestEntry(
        issuer_id="CN_601919",
        market="CN",
        stock_code="601919",
        fiscal_year=2025,
        report_type="annual",
        pdf_path=pdf_path,
        source="report",
    )

    calls = {"build": 0}

    def fake_builder(entry_arg: P5ManifestEntry) -> P5ExtractedArtifact:
        calls["build"] += 1
        return P5ExtractedArtifact(
            artifact_id=entry_arg.artifact_id,
            artifact_version="1.0",
            pipeline_version="p5-v1",
            manifest_entry=entry_arg,
            source_pdf_path=entry_arg.pdf_path,
            document={},
            document_metadata={},
            candidate_facts=(),
            canonical_facts=(
                {
                    "fact_id": "fact-1",
                    "metric_id": "revenue",
                    "statement_type": "income_statement",
                    "entity_scope": "consolidated",
                    "numeric_value": 100.0,
                    "currency": "CNY",
                    "extensions": {"period_scope": "duration"},
                },
            ),
            derived_facts=(),
            validation_report={"overall_status": "ok", "issues": []},
            review_packets=(),
            quality_gate="pass",
            missing_status={},
            created_at="2026-04-23T00:00:00",
        )

    first = run_p5_dataset_build(
        manifest_path=manifest_path,
        artifact_root=artifact_root,
        dataset_id="p5_seed",
        build_artifact_func=fake_builder,
        now_func=lambda: "2026-04-23T00:00:00",
    )
    second = run_p5_dataset_build(
        manifest_path=manifest_path,
        artifact_root=artifact_root,
        dataset_id="p5_seed",
        build_artifact_func=fake_builder,
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert calls["build"] == 1
    assert first.dataset_path.exists()
    assert first.turtle_export_path.exists()
    assert second.extracted_artifact_ids == ("CN_601919_2025",)
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_p5_runner.py -q -o addopts=
```

Expected: fail because `p5.runner` does not exist.

- [ ] **Step 3: Implement runner**

Create `financial-report-analysis/src/financial_report_analysis/p5/runner.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from pathlib import Path
from typing import Callable

from financial_report_analysis.p5.artifact_repository import (
    P5JsonArtifactRepository,
)
from financial_report_analysis.p5.dataset import assemble_dataset
from financial_report_analysis.p5.extraction import build_extracted_artifact
from financial_report_analysis.p5.manifest import load_manifest
from financial_report_analysis.p5.models import P5ExtractedArtifact, P5ManifestEntry
from financial_report_analysis.p5.turtle_export import build_turtle_export


@dataclass(frozen=True, slots=True)
class P5RunResult:
    manifest_id: str
    extracted_artifact_ids: tuple[str, ...]
    dataset_path: Path
    turtle_export_path: Path


def run_p5_dataset_build(
    *,
    manifest_path: str | Path,
    artifact_root: str | Path,
    dataset_id: str,
    pdf_root: str | Path | None = None,
    required_metric_ids: tuple[str, ...] = (),
    build_artifact_func: Callable[[P5ManifestEntry], P5ExtractedArtifact] = build_extracted_artifact,
    now_func: Callable[[], str] | None = None,
) -> P5RunResult:
    manifest = load_manifest(manifest_path, pdf_root=pdf_root)
    repository = P5JsonArtifactRepository(artifact_root)
    artifacts: list[P5ExtractedArtifact] = []
    for entry in manifest.entries:
        if repository.extracted_artifact_exists(entry.artifact_id):
            artifact = repository.load_extracted_artifact(entry.artifact_id)
        else:
            artifact = build_artifact_func(entry)
            repository.save_extracted_artifact(artifact)
        artifacts.append(artifact)

    dataset = assemble_dataset(
        dataset_id=dataset_id,
        artifacts=tuple(artifacts),
        required_metric_ids=required_metric_ids,
        now_func=now_func,
    )
    dataset_path = repository.save_dataset_artifact(dataset)
    turtle_export = build_turtle_export(dataset)
    turtle_export_path = repository.datasets_dir / f"{dataset_id}_turtle_export.json"
    turtle_export_path.parent.mkdir(parents=True, exist_ok=True)
    turtle_export_path.write_text(
        json.dumps(
            {
                "dataset_id": turtle_export.dataset_id,
                "dataset_version": turtle_export.dataset_version,
                "created_at": turtle_export.created_at,
                "rows": list(turtle_export.rows),
                "alias_map": turtle_export.alias_map,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return P5RunResult(
        manifest_id=manifest.manifest_id,
        extracted_artifact_ids=tuple(artifact.artifact_id for artifact in artifacts),
        dataset_path=dataset_path,
        turtle_export_path=turtle_export_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build P5 multi-year investor dataset")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact-root", default="data/p5")
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--pdf-root", default=None)
    args = parser.parse_args()
    result = run_p5_dataset_build(
        manifest_path=args.manifest,
        artifact_root=args.artifact_root,
        dataset_id=args.dataset_id,
        pdf_root=args.pdf_root,
    )
    print(
        json.dumps(
            {
                "manifest_id": result.manifest_id,
                "extracted_artifact_ids": list(result.extracted_artifact_ids),
                "dataset_path": str(result.dataset_path),
                "turtle_export_path": str(result.turtle_export_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
```

- [ ] **Step 4: Add script entry point**

Modify `financial-report-analysis/pyproject.toml`:

```toml
[project.scripts]
financial-report-analysis-api = "financial_report_analysis.api.app:main"
financial-report-analysis-p5 = "financial_report_analysis.p5.runner:main"
```

- [ ] **Step 5: Run runner tests**

Run:

```bash
uv run pytest tests/unit/test_p5_runner.py -q -o addopts=
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 6**

Run:

```bash
git add financial-report-analysis/pyproject.toml financial-report-analysis/src/financial_report_analysis/p5/runner.py financial-report-analysis/tests/unit/test_p5_runner.py
git commit -m "feat: add p5 dataset build runner"
```

---

### Task 7: Seed Manifest Fixture And Focused Integration

**Files:**

- Create: `financial-report-analysis/tests/fixtures/p5_seed_manifest.json`
- Create: `financial-report-analysis/tests/integration/test_p5_seed_dataset.py`

- [ ] **Step 1: Create seed manifest fixture using existing local samples**

Add `financial-report-analysis/tests/fixtures/p5_seed_manifest.json`.

Use paths relative to the repo root. Start with samples already used by the current regression suite:

```json
{
  "manifest_id": "p5_seed_existing_samples",
  "manifest_version": "1.0",
  "entries": [
    {
      "issuer_id": "CN_601919",
      "market": "CN",
      "stock_code": "601919",
      "company_name": "中远海控",
      "fiscal_year": 2025,
      "report_type": "annual",
      "pdf_path": "report/downloads/cn_stocks/601919/annual/2025_年度报告.pdf",
      "source": "report",
      "report_language": "zh"
    },
    {
      "issuer_id": "HK_02498",
      "market": "HK",
      "stock_code": "02498",
      "fiscal_year": 2022,
      "report_type": "annual",
      "pdf_path": "report/downloads/hk_stocks/02498/annual/2022_annual_en.pdf",
      "source": "report",
      "report_language": "en"
    },
    {
      "issuer_id": "HK_09987",
      "market": "HK",
      "stock_code": "09987",
      "fiscal_year": 2025,
      "report_type": "annual",
      "pdf_path": "report/downloads/hk_stocks/09987/annual/2025_annual_en.pdf",
      "source": "report",
      "report_language": "en"
    }
  ]
}
```

The fixture intentionally uses paths relative to the main `report-collector` repo root. The runner must pass `pdf_root` when loading this fixture.

- [ ] **Step 2: Write focused integration test**

Add `financial-report-analysis/tests/integration/test_p5_seed_dataset.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from financial_report_analysis.p5.runner import run_p5_dataset_build


ANALYSIS_ROOT = Path(__file__).resolve().parents[2]
WORKTREE_ROOT = Path(__file__).resolve().parents[3]
MAIN_REPO_ROOT = WORKTREE_ROOT.parent.parent
PDF_ROOT_CANDIDATES = (MAIN_REPO_ROOT, WORKTREE_ROOT)


def _sample_exists(relative_path: str) -> bool:
    for root in PDF_ROOT_CANDIDATES:
        if (root / relative_path).exists():
            return True
    return False


def _pdf_root_for_all(relative_paths: list[str]) -> Path | None:
    for root in PDF_ROOT_CANDIDATES:
        if all((root / relative_path).exists() for relative_path in relative_paths):
            return root
    return None


@pytest.mark.real_pdf
@pytest.mark.slow
def test_p5_seed_dataset_builds_from_existing_real_pdf_samples(tmp_path: Path) -> None:
    manifest_path = ANALYSIS_ROOT / "tests" / "fixtures" / "p5_seed_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    relative_paths = [entry["pdf_path"] for entry in payload["entries"]]
    missing = [
        relative_path
        for relative_path in relative_paths
        if not _sample_exists(relative_path)
    ]
    if missing:
        pytest.skip("seed PDF sample(s) not available: " + ", ".join(missing))
    pdf_root = _pdf_root_for_all(relative_paths)
    assert pdf_root is not None

    result = run_p5_dataset_build(
        manifest_path=manifest_path,
        artifact_root=tmp_path / "p5",
        dataset_id="p5_seed_existing_samples",
        pdf_root=pdf_root,
        required_metric_ids=("revenue", "cash", "operating_cash_flow"),
        now_func=lambda: "2026-04-23T00:00:00",
    )

    assert result.dataset_path.exists()
    assert result.turtle_export_path.exists()
    dataset_payload = json.loads(result.dataset_path.read_text(encoding="utf-8"))
    assert dataset_payload["dataset_id"] == "p5_seed_existing_samples"
    assert dataset_payload["issuer_count"] == 3
    assert dataset_payload["rows"]
    assert "quality_summary" in dataset_payload
```

- [ ] **Step 3: Run focused unit suite**

Run:

```bash
uv run pytest tests/unit/test_p5_manifest.py tests/unit/test_p5_artifact_repository.py tests/unit/test_p5_extraction.py tests/unit/test_p5_dataset.py tests/unit/test_p5_turtle_export.py tests/unit/test_p5_runner.py -q -o addopts=
```

Expected: all P5 unit tests pass.

- [ ] **Step 4: Run focused seed integration**

Run:

```bash
uv run pytest tests/integration/test_p5_seed_dataset.py -q -o addopts=
```

Expected: pass if local seed PDFs exist; otherwise skip with explicit missing sample list.

- [ ] **Step 5: Commit Task 7**

Run:

```bash
git add financial-report-analysis/tests/fixtures/p5_seed_manifest.json financial-report-analysis/tests/integration/test_p5_seed_dataset.py
git commit -m "test: add p5 seed dataset integration"
```

---

### Task 8: Public Exports, Ruff, And Closeout Verification

**Files:**

- Modify: `financial-report-analysis/tests/unit/test_public_exports.py`
- Verify: `financial-report-analysis/src/financial_report_analysis/p5/__init__.py`

- [ ] **Step 1: Add public export test for P5 package**

Append to `financial-report-analysis/tests/unit/test_public_exports.py`:

```python
def test_p5_public_exports_are_available() -> None:
    from financial_report_analysis.p5 import (
        P5DatasetArtifact,
        P5ExtractedArtifact,
        P5Manifest,
        P5ManifestEntry,
        load_manifest,
    )

    assert P5DatasetArtifact is not None
    assert P5ExtractedArtifact is not None
    assert P5Manifest is not None
    assert P5ManifestEntry is not None
    assert callable(load_manifest)
```

- [ ] **Step 2: Run public export test**

Run:

```bash
uv run pytest tests/unit/test_public_exports.py::test_p5_public_exports_are_available -q -o addopts=
```

Expected: pass. `financial-report-analysis/src/financial_report_analysis/p5/__init__.py` already exports these names from Task 1; if this test fails, correct that file before continuing.

- [ ] **Step 3: Run all P5 unit tests**

Run:

```bash
uv run pytest tests/unit/test_p5_manifest.py tests/unit/test_p5_artifact_repository.py tests/unit/test_p5_extraction.py tests/unit/test_p5_dataset.py tests/unit/test_p5_turtle_export.py tests/unit/test_p5_runner.py tests/unit/test_public_exports.py::test_p5_public_exports_are_available -q -o addopts=
```

Expected: all tests pass.

- [ ] **Step 4: Run focused P5 integration**

Run:

```bash
uv run pytest tests/integration/test_p5_seed_dataset.py -q -o addopts=
```

Expected: pass or explicit skip if seed PDFs are not present.

- [ ] **Step 5: Run Ruff**

Run:

```bash
uv run ruff check src tests
```

Expected: `All checks passed!`

- [ ] **Step 6: Commit closeout**

Run:

```bash
git add financial-report-analysis/src/financial_report_analysis/p5 financial-report-analysis/tests/unit/test_public_exports.py
git commit -m "test: close p5 minimal persistence verification"
```

## Final Verification Matrix

Before declaring P5 V1 implementation complete, run:

```bash
uv run pytest tests/unit/test_p5_manifest.py tests/unit/test_p5_artifact_repository.py tests/unit/test_p5_extraction.py tests/unit/test_p5_dataset.py tests/unit/test_p5_turtle_export.py tests/unit/test_p5_runner.py tests/unit/test_public_exports.py::test_p5_public_exports_are_available -q -o addopts=
uv run pytest tests/integration/test_p5_seed_dataset.py -q -o addopts=
uv run ruff check src tests
```

Do not run full `test_semantic_recovery_regressions.py` or live Ollama tests as part of default P5 closeout unless a later task explicitly changes semantic fallback behavior.

## Definition Of Done

P5 V1 is complete when:

- `financial_report_analysis.p5` exposes manifest, repository, extraction, dataset, Turtle export, and runner modules.
- JSON extracted artifacts and dataset artifacts can round-trip through `P5JsonArtifactRepository`.
- Existing single-report pipeline output can be persisted as per-report P5 extracted artifacts.
- Dataset rows preserve `issuer_id`, `fiscal_year`, `metric_id`, `entity_scope`, `period_scope`, `statement_type`, value, quality, missing status, and source lineage.
- Turtle export maps aliases without changing canonical metric IDs.
- Generated extracted/dataset artifacts are ignored by git.
- Focused P5 unit tests pass.
- Focused seed integration passes or skips only because local seed PDFs are missing.
- Ruff passes.
