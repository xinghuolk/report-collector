from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(kw_only=True)
class EvidenceItem:
    evidence_item_id: str


@dataclass(kw_only=True)
class EvidenceBundle:
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    primary_evidence_item_id: str | None = None
