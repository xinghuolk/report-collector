from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(kw_only=True)
class EvidenceItem:
    evidence_item_id: str
    document_id: str
    source_type: str
    block_id: str | None = None
    table_id: str | None = None
    page_no: int | None = None
    text_excerpt: str | None = None
    table_coord: str | None = None
    object_uri: str | None = None
    content_hash: str | None = None
    confidence: float | None = None
    created_by: str | None = None
    schema_version: str | None = None


@dataclass(kw_only=True)
class EvidenceBundle:
    evidence_bundle_id: str
    document_id: str
    bundle_type: Literal[
        "fact_support",
        "derivation_support",
        "validation_support",
        "analysis_support",
    ]
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    primary_evidence_item_id: str | None = None
    summary: str | None = None
    bundle_confidence: float | None = None
    created_at: str | None = None
    schema_version: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_items and self.primary_evidence_item_id is not None:
            raise ValueError(
                "primary_evidence_item_id cannot be set when evidence_items are empty"
            )
        if not self.evidence_items:
            return
        if self.primary_evidence_item_id is None:
            raise ValueError(
                "primary_evidence_item_id must be set when evidence_items are present"
            )
        if self.primary_evidence_item_id not in {
            item.evidence_item_id for item in self.evidence_items
        }:
            raise ValueError(
                "primary_evidence_item_id must match one of evidence_items"
            )
