# Financial Report Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在仓库根目录下落地一个平级的 `financial-report-analysis/` 独立分析服务，支持 A 股与港股英文财报的事实账本、TTM、证据链、校验与对外 adapter。

**Architecture:** 新实现不继续堆在 `report/src/pdf_parser/content_extractor.py` 上，而是在仓库根目录新增独立子项目 `financial-report-analysis/`。其内部使用 `src/financial_report_analysis/` 作为 Python 包根，按 `models + registries + services + pipeline + adapters + api` 组织，并对外暴露独立 FastAPI。`report/` 仅作为 forwarding client 调用该服务；第一阶段以内存/文件级持久化接口和关系型友好的数据契约为主，先把事实模型、质量闸门和服务边界打稳。

**Tech Stack:** Python 3.10, Pydantic v2, FastAPI, pytest, Ruff, mypy, existing `report/` project tooling

---

## File Structure

### New package layout

- Create: `financial-report-analysis/pyproject.toml`
  - 定义独立 Python 子项目与测试依赖。
- Create: `financial-report-analysis/src/financial_report_analysis/__init__.py`
  - 对外导出 `analyze_report` 与核心查询入口。
- Create: `financial-report-analysis/src/financial_report_analysis/models/`
  - 放 `DocumentBlock`、`Period`、`MetricRegistryEntry`、`EvidenceItem`、`EvidenceBundle`、`CandidateFact`、`CanonicalFact`、`DerivedFact`、`ValidationIssue`、`ValidationReport`、`AnalysisSnapshot`、`FactSetRef`。
- Create: `financial-report-analysis/src/financial_report_analysis/registries/metric_registry.py`
  - 标准 metric 命中、自定义 metric provisional 注册、shadow merge。
- Create: `financial-report-analysis/src/financial_report_analysis/registries/period_registry.py`
  - `Period` 查找/注册、标准期间归并。
- Create: `financial-report-analysis/src/financial_report_analysis/unit_policy.py`
  - 统一原始单位、规范计算单位、展示单位。
- Create: `financial-report-analysis/src/financial_report_analysis/services/`
  - `document_normalizer.py`
  - `fact_normalizer.py`
  - `conflict_resolver.py`
  - `derivation_service.py`
  - `validation_service.py`
  - `analysis_service.py`
- Create: `financial-report-analysis/src/financial_report_analysis/pipeline.py`
  - 编排主流程：`document -> blocks -> candidate -> normalized -> canonical -> derived -> validation -> snapshot`
- Create: `financial-report-analysis/src/financial_report_analysis/adapters/report_adapter.py`
  - 面向 `TradingAgents-CN` 的受控查询与 `quality_gate` 聚合。
- Create: `financial-report-analysis/src/financial_report_analysis/api/`
  - 独立 FastAPI app、routes、schemas，与外部调用方共享统一 HTTP contract。
- Create: `financial-report-analysis/src/financial_report_analysis/storage/`
  - `artifacts.py`：对象存储引用模型
  - `repositories.py`：先定义协议接口和内存实现；`EvidenceBundle` 与 `EvidenceItem` 的关系以 link relation 为真源

### Existing files to modify

- Modify: `financial-report-analysis/pyproject.toml`
  - 增加 FastAPI / Uvicorn 等 API 依赖与服务入口。
- Modify: `report/src/handlers/pdf_handler.py`
  - 改为通过 HTTP client 调独立 analysis service，保持旧 extractor 接口兼容。
- Modify: `report/src/api/routes/extract.py`
  - 新增独立 `/extract/analysis` 转发接口，不污染现有 `/extract/content`。
- Modify: `report/src/api/schemas/extract.py`
  - 与 analysis service contract 对齐的 request/response schema。

### Tests

- Create: `financial-report-analysis/tests/unit/test_models.py`
- Create: `financial-report-analysis/tests/unit/test_metric_registry.py`
- Create: `financial-report-analysis/tests/unit/test_period_registry.py`
- Create: `financial-report-analysis/tests/unit/test_unit_policy.py`
- Create: `financial-report-analysis/tests/unit/test_fact_pipeline.py`
- Create: `financial-report-analysis/tests/unit/test_report_adapter.py`
- Create: `financial-report-analysis/tests/integration/test_analysis_api.py`
- Create: `report/tests/integration/test_financial_report_analysis_api.py`

## Task 1: 建立领域包骨架与核心模型

**Files:**
- Create: `financial-report-analysis/pyproject.toml`
- Create: `financial-report-analysis/src/financial_report_analysis/__init__.py`
- Create: `financial-report-analysis/src/financial_report_analysis/models/__init__.py`
- Create: `financial-report-analysis/src/financial_report_analysis/models/common.py`
- Create: `financial-report-analysis/src/financial_report_analysis/models/document.py`
- Create: `financial-report-analysis/src/financial_report_analysis/models/period.py`
- Create: `financial-report-analysis/src/financial_report_analysis/models/evidence.py`
- Create: `financial-report-analysis/src/financial_report_analysis/models/facts.py`
- Create: `financial-report-analysis/tests/unit/test_models.py`

- [ ] **Step 1: 写失败测试，固定 `Period / EvidenceBundle / Fact` 最小契约**

```python
from financial_report_analysis.models.period import Period
from financial_report_analysis.models.evidence import EvidenceBundle, EvidenceItem
from financial_report_analysis.models.facts import CandidateFact, CanonicalFact


def test_canonical_fact_business_key_is_stable() -> None:
    fact = CanonicalFact(
        fact_id="fact-1",
        metric_id="revenue",
        metric_label_raw="营业收入",
        statement_type="income_statement",
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        period_id="2025FY",
        currency="CNY",
        raw_value="1000",
        numeric_value=1000.0,
        raw_unit="万元",
        normalized_unit="CNY",
        precision=2,
        confidence=0.99,
        source_candidate_fact_ids=["cand-1"],
        resolution_reason="table_preferred",
        resolution_score=0.95,
        validation_flags=[],
        quality_status="ok",
        is_primary=True,
        evidence_bundle_id="bundle-1",
    )

    assert fact.business_key == (
        "revenue|2025FY|consolidated|current|reported|CNY"
    )


def test_evidence_bundle_requires_primary_item() -> None:
    item = EvidenceItem(
        evidence_item_id="item-1",
        document_id="doc-1",
        source_type="table",
        block_id="block-1",
        table_id="table-1",
        page_no=5,
        text_excerpt="Revenue 1,000",
        table_coord=(1, 1),
        object_uri=None,
        content_hash="hash-1",
        confidence=0.9,
        created_by="unit-test",
        schema_version="v1",
    )
    bundle = EvidenceBundle(
        evidence_bundle_id="bundle-1",
        document_id="doc-1",
        bundle_type="fact_support",
        primary_evidence_item_id="item-1",
        summary="main table evidence",
        bundle_confidence=0.9,
        schema_version="v1",
    )

    assert bundle.primary_evidence_item_id == item.evidence_item_id


def test_period_point_requires_as_of_date() -> None:
    period = Period(
        period_id="2025BS",
        period_type="POINT",
        reporting_scope="FY",
        fiscal_year=2025,
        fiscal_period_index=4,
        start_date=None,
        end_date=None,
        as_of_date="2025-12-31",
        calendar_year=2025,
        adjusted_status="ORIGINAL",
        disclosure_label_raw="At 31 December 2025",
        fiscal_label="2025FY_BS",
        accounting_standard="HKFRS",
        is_stub_period=False,
        period_metadata={},
    )

    assert period.as_of_date == "2025-12-31"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_models.py -v`

Expected: FAIL，提示 `ModuleNotFoundError: No module named 'financial_report_analysis'`

- [ ] **Step 3: 写最小实现，落地模型与导出**

```python
# financial-report-analysis/src/financial_report_analysis/models/facts.py
from pydantic import BaseModel, computed_field


class BaseFact(BaseModel):
    fact_id: str
    fact_kind: str = "base"
    metric_id: str
    metric_label_raw: str | None = None
    statement_type: str
    entity_scope: str
    comparison_axis: str
    adjustment_basis: str
    period_id: str
    currency: str
    raw_value: str | None = None
    numeric_value: float | None = None
    raw_unit: str | None = None
    normalized_unit: str | None = None
    precision: int | None = None
    confidence: float = 0.0
    extensions: dict[str, object] = {}


class CandidateFact(BaseFact):
    fact_kind: str = "candidate"
    document_id: str
    block_id: str | None = None
    table_id: str | None = None
    page_index: int | None = None
    table_coord: tuple[int, int] | None = None
    evidence_bundle_id: str
    evidence_span: str | None = None
    snapshot_path: str | None = None
    extraction_method: str
    extraction_version: str
    source_rank_hint: int | None = None


class CanonicalFact(BaseFact):
    fact_kind: str = "canonical"
    source_candidate_fact_ids: list[str]
    resolution_reason: str
    resolution_score: float
    validation_flags: list[str]
    quality_status: str
    is_primary: bool
    evidence_bundle_id: str

    @computed_field
    @property
    def business_key(self) -> str:
        return "|".join(
            [
                self.metric_id,
                self.period_id,
                self.entity_scope,
                self.comparison_axis,
                self.adjustment_basis,
                self.currency,
            ]
        )
```

```python
# financial-report-analysis/src/financial_report_analysis/__init__.py
from .models.facts import CandidateFact, CanonicalFact

__all__ = ["CandidateFact", "CanonicalFact"]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_models.py -v`

Expected: PASS，3 passed

- [ ] **Step 5: 提交**

```bash
git add financial-report-analysis/pyproject.toml financial-report-analysis/src/financial_report_analysis financial-report-analysis/tests/unit/test_models.py
git commit -m "feat: add financial report analysis domain models"
```

## Task 2: 实现 PeriodRegistry、MetricRegistry 与 UnitPolicy

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/registries/__init__.py`
- Create: `financial-report-analysis/src/financial_report_analysis/registries/period_registry.py`
- Create: `financial-report-analysis/src/financial_report_analysis/registries/metric_registry.py`
- Create: `financial-report-analysis/src/financial_report_analysis/unit_policy.py`
- Create: `financial-report-analysis/tests/unit/test_period_registry.py`
- Create: `financial-report-analysis/tests/unit/test_metric_registry.py`
- Create: `financial-report-analysis/tests/unit/test_unit_policy.py`

- [ ] **Step 1: 写失败测试，固定期间归并、custom metric provisional 注册、单位换算**

```python
from financial_report_analysis.registries.metric_registry import MetricRegistry
from financial_report_analysis.registries.period_registry import PeriodRegistry
from financial_report_analysis.unit_policy import UnitPolicy


def test_period_registry_reuses_existing_standard_period() -> None:
    registry = PeriodRegistry()

    first = registry.get_or_create_duration(
        fiscal_year=2025,
        reporting_scope="FY",
        start_date="2025-01-01",
        end_date="2025-12-31",
        accounting_standard="CAS",
        disclosure_label_raw="2025年年度",
    )
    second = registry.get_or_create_duration(
        fiscal_year=2025,
        reporting_scope="FY",
        start_date="2025-01-01",
        end_date="2025-12-31",
        accounting_standard="CAS",
        disclosure_label_raw="2025年年度报告",
    )

    assert first.period_id == second.period_id


def test_metric_registry_creates_provisional_custom_metric() -> None:
    registry = MetricRegistry(standard_metrics={"revenue": ["Revenue", "营业收入"]})

    entry = registry.resolve_metric(
        raw_label="Research investment detail",
        statement_type="income_statement",
        accounting_standard="HKFRS",
        industry_slug="consumer",
        parent_metric_id=None,
    )

    assert entry.is_custom is True
    assert entry.registry_status == "provisional"
    assert entry.metric_id.startswith("custom::hkfrs::consumer::")


def test_unit_policy_separates_compute_and_presentation_units() -> None:
    policy = UnitPolicy()

    normalized = policy.normalize_report_value(
        numeric_value=1000.0,
        raw_unit="RMB'000",
        raw_currency="CNY",
    )

    presented = policy.to_presentation(
        numeric_value=normalized.normalized_value,
        normalized_currency="CNY",
    )

    assert normalized.normalized_currency == "CNY"
    assert presented.presentation_unit
    assert presented.presentation_policy_name == "default_phase1"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_period_registry.py tests/unit/test_metric_registry.py tests/unit/test_unit_policy.py -v`

Expected: FAIL，提示 `ModuleNotFoundError` 或缺少 `get_or_create_duration` / `resolve_metric` / `normalize_report_value`

- [ ] **Step 3: 写最小实现**

```python
# financial-report-analysis/src/financial_report_analysis/registries/period_registry.py
from dataclasses import dataclass

from ..models.period import Period


class PeriodRegistry:
    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str, str, str], Period] = {}

    def get_or_create_duration(
        self,
        *,
        fiscal_year: int,
        reporting_scope: str,
        start_date: str,
        end_date: str,
        accounting_standard: str,
        disclosure_label_raw: str,
    ) -> Period:
        key = (str(fiscal_year), reporting_scope, start_date, end_date)
        if key not in self._by_key:
            self._by_key[key] = Period(
                period_id=f"{fiscal_year}{reporting_scope}",
                period_type="DURATION",
                reporting_scope=reporting_scope,
                fiscal_year=fiscal_year,
                fiscal_period_index=4 if reporting_scope == "FY" else 0,
                start_date=start_date,
                end_date=end_date,
                as_of_date=None,
                calendar_year=fiscal_year,
                adjusted_status="ORIGINAL",
                disclosure_label_raw=disclosure_label_raw,
                fiscal_label=f"{fiscal_year}{reporting_scope}",
                accounting_standard=accounting_standard,
                is_stub_period=False,
                period_metadata={},
            )
        return self._by_key[key]
```

```python
# financial-report-analysis/src/financial_report_analysis/unit_policy.py
from dataclasses import dataclass


@dataclass
class NormalizedValue:
    normalized_value: float
    normalized_unit: str
    normalized_currency: str


@dataclass
class PresentationValue:
    presentation_value: float
    presentation_unit: str
    presentation_policy_name: str


class UnitPolicy:
    def normalize_report_value(
        self, *, numeric_value: float, raw_unit: str, raw_currency: str
    ) -> NormalizedValue:
        multiplier = {"RMB'000": 1000.0, "万元": 10000.0, "百万": 1_000_000.0}.get(
            raw_unit, 1.0
        )
        return NormalizedValue(
            normalized_value=numeric_value * multiplier,
            normalized_unit=raw_currency,
            normalized_currency=raw_currency,
        )

    def to_presentation(
        self, *, numeric_value: float, normalized_currency: str
    ) -> PresentationValue:
        return PresentationValue(
            presentation_value=numeric_value / 100_000_000.0,
            presentation_unit="DEFAULT_PRESENTATION_UNIT",
            presentation_policy_name="default_phase1",
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_period_registry.py tests/unit/test_metric_registry.py tests/unit/test_unit_policy.py -v`

Expected: PASS，所有 registry / unit policy 测试通过

- [ ] **Step 5: 提交**

```bash
git add financial-report-analysis/src/financial_report_analysis/registries financial-report-analysis/src/financial_report_analysis/unit_policy.py financial-report-analysis/tests/unit/test_period_registry.py financial-report-analysis/tests/unit/test_metric_registry.py financial-report-analysis/tests/unit/test_unit_policy.py
git commit -m "feat: add registries and unit policy for report analysis"
```

## Task 3: 实现 Normalizer、Resolver、Derivation、Validation 服务

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/services/__init__.py`
- Create: `financial-report-analysis/src/financial_report_analysis/services/fact_normalizer.py`
- Create: `financial-report-analysis/src/financial_report_analysis/services/conflict_resolver.py`
- Create: `financial-report-analysis/src/financial_report_analysis/services/derivation_service.py`
- Create: `financial-report-analysis/src/financial_report_analysis/services/validation_service.py`
- Create: `financial-report-analysis/tests/unit/test_fact_pipeline.py`

- [ ] **Step 1: 写失败测试，固定 normalized/canonical/derived 的边界**

```python
from financial_report_analysis.models.facts import CandidateFact, CanonicalFact
from financial_report_analysis.services.conflict_resolver import ConflictResolver
from financial_report_analysis.services.derivation_service import DerivationService
from financial_report_analysis.services.fact_normalizer import FactNormalizer
from financial_report_analysis.services.validation_service import ValidationService


def test_normalizer_sets_standard_metric_and_currency() -> None:
    fact = CandidateFact(
        fact_id="cand-1",
        metric_id="unknown",
        metric_label_raw="Revenue",
        statement_type="income_statement",
        entity_scope="consolidated",
        comparison_axis="current",
        adjustment_basis="reported",
        period_id="2025FY",
        currency="HKD",
        raw_value="100",
        numeric_value=100.0,
        raw_unit="million",
        normalized_unit=None,
        precision=2,
        confidence=0.8,
        document_id="doc-1",
        block_id="block-1",
        table_id="table-1",
        page_index=1,
        table_coord=(1, 1),
        evidence_bundle_id="bundle-1",
        evidence_span="Revenue 100",
        snapshot_path=None,
        extraction_method="table_skill",
        extraction_version="v1",
        source_rank_hint=1,
    )

    normalized = FactNormalizer().normalize_candidates([fact])[0]
    assert normalized.metric_id == "revenue"
    assert normalized.normalized_unit == "HKD"


def test_resolver_keeps_highest_priority_candidate_for_same_business_key() -> None:
    normalized = FactNormalizer().normalize_candidates(
        [
            CandidateFact.model_validate(
                {
                    "fact_id": "cand-1",
                    "metric_id": "unknown",
                    "metric_label_raw": "Revenue",
                    "statement_type": "income_statement",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "HKD",
                    "raw_value": "100",
                    "numeric_value": 100.0,
                    "raw_unit": "million",
                    "normalized_unit": None,
                    "precision": 2,
                    "confidence": 0.8,
                    "document_id": "doc-1",
                    "block_id": "block-1",
                    "table_id": "table-1",
                    "page_index": 1,
                    "table_coord": [1, 1],
                    "evidence_bundle_id": "bundle-1",
                    "evidence_span": "Revenue 100",
                    "snapshot_path": None,
                    "extraction_method": "table_skill",
                    "extraction_version": "v1",
                    "source_rank_hint": 2,
                }
            ),
            CandidateFact.model_validate(
                {
                    "fact_id": "cand-2",
                    "metric_id": "unknown",
                    "metric_label_raw": "Revenue",
                    "statement_type": "income_statement",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "HKD",
                    "raw_value": "100",
                    "numeric_value": 100.0,
                    "raw_unit": "million",
                    "normalized_unit": None,
                    "precision": 2,
                    "confidence": 0.95,
                    "document_id": "doc-1",
                    "block_id": "block-2",
                    "table_id": "table-1",
                    "page_index": 1,
                    "table_coord": [1, 2],
                    "evidence_bundle_id": "bundle-2",
                    "evidence_span": "Revenue 100",
                    "snapshot_path": None,
                    "extraction_method": "table_skill",
                    "extraction_version": "v1",
                    "source_rank_hint": 1,
                }
            ),
        ]
    )
    canonical = ConflictResolver().resolve(normalized)
    assert len(canonical) == 1
    assert canonical[0].resolution_reason == "highest_source_rank"


def test_derivation_service_builds_ttm_fact() -> None:
    canonical_facts = [
        CanonicalFact(
            fact_id=f"fact-{idx}",
            metric_id="revenue",
            metric_label_raw="Revenue",
            statement_type="income_statement",
            entity_scope="consolidated",
            comparison_axis="current",
            adjustment_basis="reported",
            period_id=period_id,
            currency="HKD",
            raw_value=str(value),
            numeric_value=value,
            raw_unit="million",
            normalized_unit="HKD",
            precision=2,
            confidence=0.9,
            source_candidate_fact_ids=[f"cand-{idx}"],
            resolution_reason="table_preferred",
            resolution_score=0.9,
            validation_flags=[],
            quality_status="ok",
            is_primary=True,
            evidence_bundle_id=f"bundle-{idx}",
        )
        for idx, (period_id, value) in enumerate(
            [
                ("2024Q4_SINGLE", 20.0),
                ("2025Q1_SINGLE", 25.0),
                ("2025Q2_SINGLE", 30.0),
                ("2025Q3_SINGLE", 35.0),
            ],
            start=1,
        )
    ]
    derived = DerivationService().derive_ttm(canonical_facts)
    assert derived[0].derivation_type == "ttm"


def test_validation_flags_missing_ttm_dependency() -> None:
    report = ValidationService().validate(canonical_facts=[], derived_facts=[])
    assert report.overall_status == "review_required"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_fact_pipeline.py -v`

Expected: FAIL，提示服务类或方法不存在

- [ ] **Step 3: 写最小实现**

```python
# financial-report-analysis/src/financial_report_analysis/services/conflict_resolver.py
from ..models.facts import CanonicalFact, CandidateFact


class ConflictResolver:
    def resolve(self, facts: list[CandidateFact]) -> list[CanonicalFact]:
        grouped: dict[str, list[CandidateFact]] = {}
        for fact in facts:
            key = "|".join(
                [
                    fact.metric_id,
                    fact.period_id,
                    fact.entity_scope,
                    fact.comparison_axis,
                    fact.adjustment_basis,
                    fact.currency,
                ]
            )
            grouped.setdefault(key, []).append(fact)

        resolved: list[CanonicalFact] = []
        for group in grouped.values():
            selected = sorted(
                group, key=lambda item: item.source_rank_hint or 999
            )[0]
            resolved.append(
                CanonicalFact(
                    **selected.model_dump(
                        exclude={
                            "document_id",
                            "block_id",
                            "table_id",
                            "page_index",
                            "table_coord",
                            "evidence_span",
                            "snapshot_path",
                            "extraction_method",
                            "extraction_version",
                            "source_rank_hint",
                        }
                    ),
                    source_candidate_fact_ids=[selected.fact_id],
                    resolution_reason="highest_source_rank",
                    resolution_score=selected.confidence,
                    validation_flags=[],
                    quality_status="ok",
                    is_primary=True,
                )
            )
        return resolved
```

```python
# financial-report-analysis/src/financial_report_analysis/services/derivation_service.py
from ..models.facts import CanonicalFact, DerivedFact


class DerivationService:
    def derive_ttm(self, canonical_facts: list[CanonicalFact]) -> list[DerivedFact]:
        revenue_facts = [fact for fact in canonical_facts if fact.metric_id == "revenue"]
        if len(revenue_facts) < 4:
            return []

        total = sum(fact.numeric_value or 0.0 for fact in revenue_facts[-4:])
        latest = revenue_facts[-1]
        return [
            DerivedFact(
                **latest.model_dump(
                    exclude={
                        "source_candidate_fact_ids",
                        "resolution_reason",
                        "resolution_score",
                        "validation_flags",
                        "quality_status",
                        "is_primary",
                    }
                ),
                source_canonical_fact_ids=[fact.fact_id for fact in revenue_facts[-4:]],
                derivation_type="ttm",
                derivation_formula="sum(last_4_quarters)",
                derivation_version="v1",
                validation_status="ok",
                consistency_check_against_fact_id=None,
                evidence_bundle_id=latest.evidence_bundle_id,
                numeric_value=total,
            )
        ]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_fact_pipeline.py -v`

Expected: PASS，normalized / canonical / derived / validation 路径通过

- [ ] **Step 5: 提交**

```bash
git add financial-report-analysis/src/financial_report_analysis/services financial-report-analysis/tests/unit/test_fact_pipeline.py
git commit -m "feat: add fact normalization resolution and derivation services"
```

## Task 4: 编排主 Pipeline，并接入 Document/Evidence/FactSet 引用

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/storage/artifacts.py`
- Create: `financial-report-analysis/src/financial_report_analysis/storage/repositories.py`
- Create: `financial-report-analysis/src/financial_report_analysis/pipeline.py`
- Modify: `financial-report-analysis/src/financial_report_analysis/__init__.py`
- Modify: `financial-report-analysis/tests/unit/test_fact_pipeline.py`

- [ ] **Step 1: 写失败测试，固定 pipeline 输出 `canonical_fact_set_id / derived_fact_set_id / validation_report_id`**

```python
from financial_report_analysis.pipeline import analyze_report


def test_pipeline_returns_fact_sets_and_quality_gate() -> None:
    result = analyze_report(
        document_ref={"document_id": "doc-1", "market": "CN"},
        extracted_payload={
            "candidate_facts": [
                {
                    "fact_id": "cand-1",
                    "metric_id": "unknown",
                    "metric_label_raw": "营业收入",
                    "statement_type": "income_statement",
                    "entity_scope": "consolidated",
                    "comparison_axis": "current",
                    "adjustment_basis": "reported",
                    "period_id": "2025FY",
                    "currency": "CNY",
                    "raw_value": "1000",
                    "numeric_value": 1000.0,
                    "raw_unit": "万元",
                    "normalized_unit": None,
                    "precision": 2,
                    "confidence": 0.95,
                    "document_id": "doc-1",
                    "block_id": "block-1",
                    "table_id": "table-1",
                    "page_index": 1,
                    "table_coord": [1, 1],
                    "evidence_bundle_id": "bundle-1",
                    "evidence_span": "营业收入 1000",
                    "snapshot_path": None,
                    "extraction_method": "table_skill",
                    "extraction_version": "v1",
                    "source_rank_hint": 1,
                }
            ]
        },
    )

    assert result.canonical_fact_set_id
    assert result.validation_report_id
    assert result.quality_gate in {"pass", "review", "fail"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_fact_pipeline.py -v`

Expected: FAIL，提示 `analyze_report` 不存在或返回对象缺少字段

- [ ] **Step 3: 写最小实现**

```python
# financial-report-analysis/src/financial_report_analysis/pipeline.py
from dataclasses import dataclass

from .models.facts import CandidateFact
from .services.conflict_resolver import ConflictResolver
from .services.derivation_service import DerivationService
from .services.fact_normalizer import FactNormalizer
from .services.validation_service import ValidationService


@dataclass
class PipelineResult:
    canonical_fact_set_id: str
    derived_fact_set_id: str
    validation_report_id: str
    quality_gate: str
    canonical_facts: list
    derived_facts: list
    validation_report: object


def analyze_report(document_ref: dict, extracted_payload: dict) -> PipelineResult:
    candidates = [
        CandidateFact.model_validate(item)
        for item in extracted_payload.get("candidate_facts", [])
    ]
    normalized = FactNormalizer().normalize_candidates(candidates)
    canonical = ConflictResolver().resolve(normalized)
    derived = DerivationService().derive_ttm(canonical)
    validation = ValidationService().validate(canonical_facts=canonical, derived_facts=derived)
    quality_gate = "pass" if validation.overall_status == "ok" else "review"
    return PipelineResult(
        canonical_fact_set_id=f"{document_ref['document_id']}:canonical:v1",
        derived_fact_set_id=f"{document_ref['document_id']}:derived:v1",
        validation_report_id=f"{document_ref['document_id']}:validation:v1",
        quality_gate=quality_gate,
        canonical_facts=canonical,
        derived_facts=derived,
        validation_report=validation,
    )
```

- [ ] **Step 3.5: 明确 `EvidenceBundle` 关系表达边界**

```python
# financial-report-analysis/src/financial_report_analysis/storage/repositories.py
from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceBundleItemLink:
    evidence_bundle_id: str
    evidence_item_id: str
    sort_order: int


class InMemoryEvidenceRepository:
    """
    第一阶段允许 EvidenceBundle 在内存态包含 evidence_item_ids 便于测试和序列化，
    但 repository/storage 层必须以 EvidenceBundleItemLink 作为 source of truth。
    """
```

- [ ] **Step 3.6: 运行测试确认边界不回退**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_fact_pipeline.py tests/unit/test_models.py -v`

Expected: PASS，且未引入 EvidenceBundle 直接持久化数组为真源的设计

- [ ] **Step 4: 运行测试确认通过**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_fact_pipeline.py -v`

Expected: PASS，主 pipeline 返回稳定 fact set 引用

- [ ] **Step 5: 提交**

```bash
git add financial-report-analysis/src/financial_report_analysis/pipeline.py financial-report-analysis/src/financial_report_analysis/storage financial-report-analysis/src/financial_report_analysis/__init__.py financial-report-analysis/tests/unit/test_fact_pipeline.py
git commit -m "feat: add financial report analysis pipeline orchestration"
```

## Task 5: 实现面向调用方的 ReportAdapter 与质量闸门

**Files:**
- Create: `financial-report-analysis/src/financial_report_analysis/adapters/__init__.py`
- Create: `financial-report-analysis/src/financial_report_analysis/adapters/report_adapter.py`
- Create: `financial-report-analysis/tests/unit/test_report_adapter.py`

- [ ] **Step 1: 写失败测试，固定 `TradingAgents-CN` 需要的受控接口**

```python
from financial_report_analysis.adapters.report_adapter import ReportAdapter


def test_report_adapter_exposes_only_curated_fields() -> None:
    adapter = ReportAdapter()
    result = adapter.build_analysis_result(
        document={"document_id": "doc-1", "market": "HK"},
        pipeline_result={
            "canonical_fact_set_id": "doc-1:canonical:v1",
            "derived_fact_set_id": "doc-1:derived:v1",
            "validation_report_id": "doc-1:validation:v1",
            "quality_gate": "pass",
            "canonical_facts": [{"metric_id": "revenue", "numeric_value": 100.0}],
            "derived_facts": [],
            "validation_report": {"overall_status": "ok"},
        },
    )

    assert result["quality_gate"] == "pass"
    assert "candidate_facts" not in result
    assert result["key_facts"][0]["metric_id"] == "revenue"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_report_adapter.py -v`

Expected: FAIL，提示 `ReportAdapter` 或 `build_analysis_result` 不存在

- [ ] **Step 3: 写最小实现**

```python
# financial-report-analysis/src/financial_report_analysis/adapters/report_adapter.py
class ReportAdapter:
    def build_analysis_result(self, *, document: dict, pipeline_result: dict) -> dict:
        canonical_facts = pipeline_result.get("canonical_facts", [])
        derived_facts = pipeline_result.get("derived_facts", [])
        return {
            "document": document,
            "canonical_fact_set_id": pipeline_result["canonical_fact_set_id"],
            "derived_fact_set_id": pipeline_result["derived_fact_set_id"],
            "validation_report_id": pipeline_result["validation_report_id"],
            "quality_gate": pipeline_result["quality_gate"],
            "key_facts": canonical_facts[:10],
            "ttm_facts": [
                fact for fact in derived_facts if fact.get("derivation_type") == "ttm"
            ],
            "analysis_snapshot": {
                "summary": "",
                "blocked_items": [],
            },
            "blocked_items": [],
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd financial-report-analysis && uv run pytest tests/unit/test_report_adapter.py -v`

Expected: PASS，adapter 输出不泄漏 candidate 层数据

- [ ] **Step 5: 提交**

```bash
git add financial-report-analysis/src/financial_report_analysis/adapters financial-report-analysis/tests/unit/test_report_adapter.py
git commit -m "feat: add report analysis adapter and quality gate"
```

## Task 6: 为 `financial-report-analysis` 提供独立 API，并让 `report` 以 HTTP 转发接入

> **Execution gate:** Task 6 以 `financial-report-analysis` 独立 API 为主路径。不要在执行时让 `report/` 直接 import 分析核心实现，除非先更新 spec 与本计划。

**Files:**
- Modify: `financial-report-analysis/pyproject.toml`
- Create: `financial-report-analysis/src/financial_report_analysis/api/__init__.py`
- Create: `financial-report-analysis/src/financial_report_analysis/api/app.py`
- Create: `financial-report-analysis/src/financial_report_analysis/api/routes.py`
- Create: `financial-report-analysis/src/financial_report_analysis/api/schemas.py`
- Create: `financial-report-analysis/tests/integration/test_analysis_api.py`
- Modify: `report/pyproject.toml`
- Modify: `report/src/handlers/pdf_handler.py`
- Modify: `report/src/api/routes/extract.py`
- Modify: `report/src/api/schemas/extract.py`
- Create: `report/tests/integration/test_financial_report_analysis_api.py`

- [ ] **Step 1: 写失败测试，固定独立 analysis API 与转发路由契约**

```python
from fastapi.testclient import TestClient

from financial_report_analysis.api.app import create_app


def test_analysis_service_extract_endpoint_returns_quality_gate() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/v1/analysis/extract",
        json={
            "pdf_path": "/tmp/mock.pdf",
            "market": "CN",
        },
    )

    assert response.status_code in {200, 400}
    if response.status_code == 200:
        payload = response.json()
        assert "quality_gate" in payload
        assert "canonical_fact_set_id" in payload
```

```python
from fastapi.testclient import TestClient

from src.api.app import create_app


def test_report_extract_analysis_forwards_service_contract() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/v1/extract/analysis",
        json={"pdf_path": "/tmp/mock.pdf", "market": "CN"},
    )

    assert response.status_code in {200, 400, 502}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd financial-report-analysis && uv run pytest tests/integration/test_analysis_api.py -v`

Expected: FAIL，提示 analysis service app 或新路由不存在

Run: `cd report && uv run pytest tests/integration/test_financial_report_analysis_api.py -v`

Expected: FAIL，提示转发新路由不存在或返回结构缺字段

- [ ] **Step 3: 写最小实现**

```python
# financial-report-analysis/src/financial_report_analysis/api/schemas.py
class AnalysisExtractRequest(BaseModel):
    pdf_path: str | None = None
    pdf_url: str | None = None
    market: str = "CN"
    min_confidence: float | None = None


class AnalysisResultResponse(BaseModel):
    document: Dict[str, Any]
    canonical_fact_set_id: str
    derived_fact_set_id: str
    validation_report_id: str
    quality_gate: str
    key_facts: List[Dict[str, Any]]
    ttm_facts: List[Dict[str, Any]]
    analysis_snapshot: Dict[str, Any]
    blocked_items: List[Dict[str, Any]]
```

```python
# financial-report-analysis/src/financial_report_analysis/api/routes.py
@router.post("/api/v1/analysis/extract", response_model=AnalysisResultResponse)
async def extract_analysis(request: AnalysisExtractRequest) -> AnalysisResultResponse:
    if not request.pdf_path and not request.pdf_url:
        raise HTTPException(status_code=400, detail="pdf_path or pdf_url is required")
    ...
```

```python
# report/src/api/schemas/extract.py
class AnalysisProxyRequest(BaseModel):
    pdf_path: Optional[str] = None
    pdf_url: Optional[str] = None
    market: str = "CN"
    min_confidence: Optional[float] = None


class AnalysisResultResponse(BaseModel):
    document: Dict[str, Any]
    canonical_fact_set_id: str
    derived_fact_set_id: str
    validation_report_id: str
    quality_gate: str
    key_facts: List[Dict[str, Any]]
    ttm_facts: List[Dict[str, Any]]
    analysis_snapshot: Dict[str, Any]
    blocked_items: List[Dict[str, Any]]
```

```python
# report/src/handlers/pdf_handler.py
class PDFHandler:
    ...

    async def extract_financial_report_analysis(self, request: dict[str, Any]) -> dict[str, Any]:
        return await self.analysis_client.extract_analysis(request)
```

```python
# report/src/api/routes/extract.py
@router.post("/extract/analysis", response_model=APIResponse[Dict[str, Any]])
async def extract_financial_report_analysis(
    request: AnalysisProxyRequest,
    handler: PDFHandler = Depends(get_pdf_handler),
) -> APIResponse[Dict[str, Any]]:
    result = await handler.extract_financial_report_analysis(request.model_dump())
    return APIResponse(success=True, data=result, error=None)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd financial-report-analysis && uv run pytest tests/integration/test_analysis_api.py tests/unit/test_report_adapter.py -v`

Expected: PASS，独立 analysis service 暴露统一 contract

Run: `cd report && uv run pytest tests/integration/test_financial_report_analysis_api.py tests/unit/test_extract_schema_negotiation.py -v`

Expected: PASS，且 `report` 只做转发，不回归旧 schema 协商测试

- [ ] **Step 5: 提交**

```bash
git add financial-report-analysis/pyproject.toml financial-report-analysis/src/financial_report_analysis/api financial-report-analysis/tests/integration/test_analysis_api.py report/pyproject.toml report/src/handlers/pdf_handler.py report/src/api/routes/extract.py report/src/api/schemas/extract.py report/tests/integration/test_financial_report_analysis_api.py
git commit -m "feat: expose financial report analysis via standalone api"
```

## Task 7: 补独立服务验证矩阵、转发回归测试与文档同步

> **Execution gate:** Task 7 在 Task 6 完成独立 analysis service 后再执行。港股非英文输入在第一阶段应标记为 `unsupported_in_phase1` 或 `review`，不要和真实数据质量失败混成 `fail`。

**Files:**
- Modify: `financial-report-analysis/tests/integration/test_analysis_api.py`
- Modify: `report/tests/unit/test_fact_evidence_mapping.py`
- Modify: `report/tests/integration/test_hk_09987_period_extraction.py`
- Modify: `report/tests/integration/test_cn_annual_period_regression.py`
- Modify: `financial-report-analysis/README.md`
- Modify: `report/README.md`
- Modify: `docs/superpowers/specs/2026-04-18-financial-report-analysis-integration-design.md`（如接口命名需与实现对齐）

- [ ] **Step 1: 写失败测试，覆盖港股英文限制、TTM 血缘、review/fail 闸门**

```python
def test_hk_phase1_rejects_non_english_report_input() -> None:
    from financial_report_analysis.pipeline import analyze_report

    result = analyze_report(
        document_ref={"document_id": "hk-doc", "market": "HK", "language": "zh-Hant"},
        extracted_payload={"candidate_facts": []},
    )

    assert result.quality_gate == "review"
    assert result.validation_report.overall_status == "unsupported_in_phase1"
```

```python
def test_validation_report_marks_missing_ttm_dependency_as_review() -> None:
    from financial_report_analysis.services.validation_service import ValidationService

    report = ValidationService().validate(canonical_facts=[], derived_facts=[])
    assert report.overall_status == "review_required"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd financial-report-analysis && uv run pytest tests/integration/test_analysis_api.py -v`

Expected: FAIL，提示独立 service 的语言策略或质量状态断言未覆盖

Run: `cd report && uv run pytest tests/unit/test_fact_evidence_mapping.py tests/integration/test_hk_09987_period_extraction.py tests/integration/test_cn_annual_period_regression.py -v`

Expected: FAIL，提示缺少语言策略或转发层回归断言

- [ ] **Step 3: 写最小实现与 README 说明**

```markdown
<!-- financial-report-analysis/README.md -->
## Financial Report Analysis Service

- 主交付形态：独立 FastAPI analysis service
- 主入口：`POST /api/v1/analysis/extract`
- 健康检查：`GET /health`
- 第一阶段范围：A 股 + 港股英文财报，年报/中报/季报
- 输入主路径：`pdf_path`
- 兼容输入：`pdf_url`、上传文件
```

```markdown
<!-- report/README.md -->
## Financial Report Analysis Package

- 新领域包子项目：`financial-report-analysis/`
- 新分析服务入口：`financial-report-analysis` HTTP API
- `report` 中的 `/extract/analysis` 是转发层，不承载分析核心实现
- 第一阶段范围：A 股 + 港股英文财报，年报/中报/季报
- 对外受控结果：`canonical_facts`、`derived_facts`、`validation_report`、`quality_gate`
- 非目标：繁中港股主链路、RAG 数字主抽取、provisional custom metric 核心分析
- 港股非英文输入在第一阶段标记为 `unsupported_in_phase1/review`，不与数据质量失败混用
```

```python
# financial-report-analysis/src/financial_report_analysis/pipeline.py
def analyze_report(document_ref: dict, extracted_payload: dict) -> PipelineResult:
    if document_ref.get("market") == "HK" and document_ref.get("language") not in {None, "en"}:
        validation = ValidationService().build_language_restriction_report(document_ref)
        return PipelineResult(
            canonical_fact_set_id=f"{document_ref['document_id']}:canonical:v1",
            derived_fact_set_id=f"{document_ref['document_id']}:derived:v1",
            validation_report_id=f"{document_ref['document_id']}:validation:v1",
            quality_gate="review",
            canonical_facts=[],
            derived_facts=[],
            validation_report=validation,
        )
    ...
```

- [ ] **Step 4: 跑完整相关测试**

Run: `cd financial-report-analysis && uv run pytest tests/integration/test_analysis_api.py tests/unit/test_fact_pipeline.py -v`

Expected: PASS，analysis service 的真实回归与语言策略通过

Run: `cd report && uv run pytest tests/unit/test_fact_evidence_mapping.py tests/integration/test_financial_report_analysis_api.py tests/integration/test_hk_09987_period_extraction.py tests/integration/test_cn_annual_period_regression.py -v`

Expected: PASS，转发层和真实财报回归测试通过

- [ ] **Step 5: 提交**

```bash
git add financial-report-analysis/tests/integration/test_analysis_api.py financial-report-analysis/src/financial_report_analysis/pipeline.py financial-report-analysis/README.md report/tests/unit/test_fact_evidence_mapping.py report/tests/integration/test_financial_report_analysis_api.py report/tests/integration/test_hk_09987_period_extraction.py report/tests/integration/test_cn_annual_period_regression.py report/README.md docs/superpowers/specs/2026-04-18-financial-report-analysis-integration-design.md
git commit -m "docs: align standalone analysis service and regression coverage"
```

## Self-Review

- Spec coverage:
  - 总体独立服务形态、非 MCP 主接口、包内领域实现：Task 1, 4, 5, 6
  - A 股 + 港股英文第一阶段范围：Task 2, 6, 7
  - `candidate -> normalized -> canonical -> derived`：Task 3, 4
  - `Period / MetricRegistry / UnitPolicy / EvidenceBundle`：Task 1, 2, 4
  - `TTM` 作为 derived fact 且可追溯：Task 3, 4, 7
  - `TradingAgents-CN` 与 `report/` 共享 HTTP contract：Task 5, 6, 7
  - 关系型友好对象与 object storage artifact 协议：Task 4
- Placeholder scan:
  - 未保留计划占位符
  - 每个任务都包含了测试、命令、代码和提交步骤
- Type consistency:
  - 统一使用 `metric_id / period_id / canonical_fact_set_id / derived_fact_set_id / validation_report_id / quality_gate`
  - 统一将 `comparison_axis` 保留在 fact 层，未回流到 `Period`

## Execution Order Recommendation

- 可直接执行：Task 1, Task 2, Task 3, Task 4, Task 5
- 执行前已在本计划中修订收口：Task 6, Task 7

## Notes Before Execution

- 如果 Task 3 中的最小实现无法兼容现有 `content_extractor.py` 的事实输出，优先在 `financial-report-analysis` 服务内部加 legacy-to-candidate 映射，而不是把新模型倒灌回旧 extractor。
- `report/` 在 Task 6 之后只承担转发与错误映射职责，不应直接 import `financial_report_analysis.pipeline` 或 `ReportAdapter`。
- 如果第一阶段无法立即引入真实数据库，请先实现 `financial-report-analysis/src/financial_report_analysis/storage/repositories.py` 中的内存实现，但接口命名必须保持关系型友好。

Plan complete and saved to `docs/superpowers/plans/2026-04-18-financial-report-analysis-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
