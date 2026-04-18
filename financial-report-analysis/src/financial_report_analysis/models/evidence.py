from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(kw_only=True)
class EvidenceItem:
    evidence_item_id: str


@dataclass(kw_only=True)
class EvidenceBundle:
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    primary_evidence_item_id: str | None = None

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
