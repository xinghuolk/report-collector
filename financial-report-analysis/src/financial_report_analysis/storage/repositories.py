from __future__ import annotations

from dataclasses import dataclass, field

from financial_report_analysis.models.evidence import EvidenceBundle, EvidenceItem

from .artifacts import EvidenceBundleRecord


@dataclass(frozen=True, slots=True)
class EvidenceBundleItemLink:
    evidence_bundle_id: str
    evidence_item_id: str
    sort_order: int


@dataclass(slots=True)
class InMemoryEvidenceRepository:
    _bundle_records: dict[str, EvidenceBundleRecord] = field(default_factory=dict)
    _evidence_items: dict[str, EvidenceItem] = field(default_factory=dict)
    _bundle_item_links: dict[str, list[EvidenceBundleItemLink]] = field(
        default_factory=dict
    )

    def save_evidence_bundle(self, bundle: EvidenceBundle) -> None:
        self._bundle_records[bundle.evidence_bundle_id] = EvidenceBundleRecord(
            evidence_bundle_id=bundle.evidence_bundle_id,
            document_id=bundle.document_id,
            bundle_type=bundle.bundle_type,
            primary_evidence_item_id=bundle.primary_evidence_item_id,
            summary=bundle.summary,
            bundle_confidence=bundle.bundle_confidence,
            created_at=bundle.created_at,
            schema_version=bundle.schema_version,
        )
        self._bundle_item_links[bundle.evidence_bundle_id] = [
            EvidenceBundleItemLink(
                evidence_bundle_id=bundle.evidence_bundle_id,
                evidence_item_id=item.evidence_item_id,
                sort_order=index,
            )
            for index, item in enumerate(bundle.evidence_items)
        ]
        for item in bundle.evidence_items:
            self._evidence_items[item.evidence_item_id] = item

    def save_evidence_item(self, item: EvidenceItem) -> None:
        self._evidence_items[item.evidence_item_id] = item

    def link_evidence_bundle_item(
        self,
        *,
        evidence_bundle_id: str,
        evidence_item_id: str,
        sort_order: int,
    ) -> None:
        if evidence_item_id not in self._evidence_items:
            raise ValueError(
                f"cannot link missing evidence item: {evidence_item_id}"
            )
        self._bundle_item_links.setdefault(evidence_bundle_id, []).append(
            EvidenceBundleItemLink(
                evidence_bundle_id=evidence_bundle_id,
                evidence_item_id=evidence_item_id,
                sort_order=sort_order,
            )
        )

    def get_evidence_bundle(self, evidence_bundle_id: str) -> EvidenceBundle | None:
        record = self._bundle_records.get(evidence_bundle_id)
        if record is None:
            return None

        links = sorted(
            self._bundle_item_links.get(evidence_bundle_id, []),
            key=lambda link: (link.sort_order, link.evidence_item_id),
        )
        missing_item_ids = [
            link.evidence_item_id
            for link in links
            if link.evidence_item_id not in self._evidence_items
        ]
        if missing_item_ids:
            raise ValueError(
                "missing linked evidence item(s): " + ", ".join(sorted(missing_item_ids))
            )
        evidence_items = [
            self._evidence_items[link.evidence_item_id]
            for link in links
        ]
        return EvidenceBundle(
            evidence_bundle_id=record.evidence_bundle_id,
            document_id=record.document_id,
            bundle_type=record.bundle_type,
            evidence_items=evidence_items,
            primary_evidence_item_id=record.primary_evidence_item_id,
            summary=record.summary,
            bundle_confidence=record.bundle_confidence,
            created_at=record.created_at,
            schema_version=record.schema_version,
        )

    def list_evidence_bundle_item_links(
        self,
        evidence_bundle_id: str,
    ) -> tuple[EvidenceBundleItemLink, ...]:
        return tuple(
            sorted(
                self._bundle_item_links.get(evidence_bundle_id, []),
                key=lambda link: (link.sort_order, link.evidence_item_id),
            )
        )
