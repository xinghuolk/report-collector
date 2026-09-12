from __future__ import annotations

from dataclasses import dataclass, field

from financial_report_analysis.models.common import Extensions


@dataclass(kw_only=True)
class DocumentBlock:
    block_id: str
    document_id: str
    page_no: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    block_type: str | None = None
    text: str = ""
    structured_repr: dict[str, object] = field(default_factory=dict)
    table_cells: list[list[object]] = field(default_factory=list)
    reading_order: int | None = None
    extensions: Extensions = field(default_factory=dict)
