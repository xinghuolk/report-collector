from financial_report_analysis import models
from financial_report_analysis.ingestion import normalize_table_semantics
from financial_report_analysis.models import (
    NormalizedTableCellValue,
    NormalizedTableColumn,
    NormalizedTableRow,
    NormalizedTableSemantics,
)
from financial_report_analysis.models import table_semantics
from financial_report_analysis.registries import MetricMappingDefinition, load_metric_registry


def test_table_semantic_models_are_publicly_exported() -> None:
    assert models.NormalizedTableCellValue is NormalizedTableCellValue
    assert models.NormalizedTableColumn is NormalizedTableColumn
    assert models.NormalizedTableRow is NormalizedTableRow
    assert models.NormalizedTableSemantics is NormalizedTableSemantics
    assert table_semantics.NormalizedTableSemantics is NormalizedTableSemantics


def test_model_package_all_includes_semantic_exports() -> None:
    assert "NormalizedTableCellValue" in models.__all__
    assert "NormalizedTableColumn" in models.__all__
    assert "NormalizedTableRow" in models.__all__
    assert "NormalizedTableSemantics" in models.__all__


def test_ingestion_package_exports_semantic_normalizer() -> None:
    assert callable(normalize_table_semantics)


def test_registries_package_exports_metric_mapping_registry() -> None:
    registry = load_metric_registry()

    assert callable(load_metric_registry)
    assert isinstance(registry.definitions[0], MetricMappingDefinition)
