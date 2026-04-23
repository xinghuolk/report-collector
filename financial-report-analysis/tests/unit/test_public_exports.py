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
from financial_report_analysis.semantic_fallback import (
    CurrencyFallbackRequest,
    OllamaSemanticFallbackClient,
    SemanticFallbackSettings,
    SemanticFallbackResult,
    SemanticFallbackService,
    UnitFallbackRequest,
    build_semantic_fallback_service,
    load_semantic_fallback_settings,
    supported_currency_outputs,
    supported_unit_outputs,
)


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


def test_semantic_fallback_package_exports_public_entry_points() -> None:
    assert OllamaSemanticFallbackClient.__name__ == "OllamaSemanticFallbackClient"
    assert SemanticFallbackSettings.__name__ == "SemanticFallbackSettings"
    assert SemanticFallbackService.__name__ == "SemanticFallbackService"
    assert SemanticFallbackResult.__name__ == "SemanticFallbackResult"
    assert CurrencyFallbackRequest.__name__ == "CurrencyFallbackRequest"
    assert UnitFallbackRequest.__name__ == "UnitFallbackRequest"
    assert callable(build_semantic_fallback_service)
    assert callable(load_semantic_fallback_settings)
    assert supported_currency_outputs() == ("CNY", "HKD", "USD", "unknown")
    assert supported_unit_outputs() == (
        "yuan",
        "thousand",
        "million",
        "billion",
        "percent",
        "unknown",
    )


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
