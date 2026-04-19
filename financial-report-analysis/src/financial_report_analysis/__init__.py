"""Financial report analysis domain package."""

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
