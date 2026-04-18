from __future__ import annotations

from dataclasses import dataclass, field

from financial_report_analysis.models.common import Extensions


@dataclass(kw_only=True)
class Document:
    document_id: str
    extensions: Extensions = field(default_factory=dict)

