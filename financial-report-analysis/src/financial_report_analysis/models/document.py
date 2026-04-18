from __future__ import annotations

from dataclasses import dataclass, field

from financial_report_analysis.models.common import Extensions


@dataclass(kw_only=True)
class DocumentBlock:
    block_id: str
    document_id: str
    text: str = ""
    extensions: Extensions = field(default_factory=dict)
