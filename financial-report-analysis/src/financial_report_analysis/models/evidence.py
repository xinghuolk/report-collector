from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(kw_only=True)
class EvidenceItem:
    evidence_item_id: str


@dataclass(kw_only=True)
class EvidenceBundle:
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    _primary_evidence_item_id: str | None = None

    @property
    def primary_evidence_item_id(self) -> str | None:
        if self._primary_evidence_item_id is not None:
            return self._primary_evidence_item_id
        if not self.evidence_items:
            return None
        return self.evidence_items[0].evidence_item_id

