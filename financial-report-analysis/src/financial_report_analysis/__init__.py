"""Financial report analysis domain package."""

from importlib import import_module

from financial_report_analysis.ingestion import PdfTableStructureAdapter
from financial_report_analysis.models.facts import CandidateFact, CanonicalFact
from financial_report_analysis.pipeline import PipelineResult, analyze_report

__all__ = [
    "CandidateFact",
    "CanonicalFact",
    "PdfTableStructureAdapter",
    "PipelineResult",
    "analyze_report",
]


def __getattr__(name: str) -> object:
    if name in {"p5", "semantic_fallback"}:
        module = import_module(f"financial_report_analysis.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
