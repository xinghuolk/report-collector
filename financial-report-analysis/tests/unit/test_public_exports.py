from financial_report_analysis import models
from financial_report_analysis.models import (
    NormalizedTableCellValue,
    NormalizedTableColumn,
    NormalizedTableRow,
    NormalizedTableSemantics,
)
from financial_report_analysis.models import table_semantics


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
