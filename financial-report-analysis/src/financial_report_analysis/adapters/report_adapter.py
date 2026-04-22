from __future__ import annotations

from dataclasses import asdict, is_dataclass
from collections.abc import Sequence
from typing import Any, Mapping

_API_VISIBLE_METRICS = {"n_income_attr_p", "basic_eps"}

_KEY_FACT_FIELDS = {
    "fact_id",
    "metric_id",
    "metric_label_raw",
    "statement_type",
    "entity_scope",
    "comparison_axis",
    "adjustment_basis",
    "period_id",
    "currency",
    "raw_value",
    "numeric_value",
    "raw_unit",
    "normalized_unit",
    "precision",
    "confidence",
    "validation_flags",
    "quality_status",
    "is_primary",
}

_TTM_FACT_FIELDS = _KEY_FACT_FIELDS | {
    "derivation_type",
    "derivation_formula",
    "derivation_version",
    "validation_status",
    "consistency_check_against_fact_id",
}


class ReportAdapter:
    def build_analysis_result(
        self,
        *,
        document: dict[str, Any],
        pipeline_result: Mapping[str, Any] | Any,
    ) -> dict[str, Any]:
        pipeline_data = self._to_mapping(pipeline_result)
        canonical_fact_items = [
            self._coerce_fact(fact)
            for fact in pipeline_data.get("canonical_facts", [])
        ]
        canonical_facts = [
            self._sanitize_fact(fact, allowed_fields=_KEY_FACT_FIELDS)
            for fact in canonical_fact_items
        ]
        derived_facts = [
            self._sanitize_fact(self._coerce_fact(fact), allowed_fields=_TTM_FACT_FIELDS)
            for fact in pipeline_data.get("derived_facts", [])
        ]
        review_packets = [
            self._coerce_review_packet(packet)
            for packet in pipeline_data.get("review_packets", [])
        ]
        blocked_items = self._build_blocked_items(pipeline_data.get("validation_report"))

        quality_gate = self._resolve_quality_gate(
            pipeline_quality_gate=pipeline_data.get("quality_gate"),
            validation_report=pipeline_data.get("validation_report"),
        )

        return {
            "document": dict(document),
            "canonical_fact_set_id": pipeline_data["canonical_fact_set_id"],
            "derived_fact_set_id": pipeline_data["derived_fact_set_id"],
            "validation_report_id": pipeline_data["validation_report_id"],
            "quality_gate": quality_gate,
            "key_facts": self._select_key_facts(canonical_facts),
            "ttm_facts": [
                fact for fact in derived_facts if fact.get("derivation_type") == "ttm"
            ],
            "analysis_snapshot": {
                "summary": "",
                "blocked_items": blocked_items,
                "review_packets": review_packets,
            },
            "blocked_items": blocked_items,
        }

    @staticmethod
    def _to_mapping(value: Mapping[str, Any] | Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
        raise TypeError("pipeline_result must be a mapping or dataclass-like object")

    @staticmethod
    def _coerce_fact(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        if is_dataclass(value):
            return asdict(value)
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
        raise TypeError("fact values must be mappings or dataclass-like objects")

    @staticmethod
    def _coerce_review_packet(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        if is_dataclass(value):
            data = asdict(value)
            if isinstance(data.get("competing_candidate_values"), tuple):
                data["competing_candidate_values"] = list(
                    data["competing_candidate_values"]
                )
            return data
        if hasattr(value, "to_dict"):
            return dict(value.to_dict())
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
        raise TypeError("review packet values must be mappings or dataclass-like objects")

    @staticmethod
    def _build_blocked_items(validation_report: Any) -> list[dict[str, Any]]:
        if validation_report is None:
            return []
        report = ReportAdapter._to_mapping(validation_report)
        overall_status = str(report.get("overall_status", ""))
        issues = report.get("issues", ())
        if isinstance(issues, str):
            issue_codes = [issues]
        elif isinstance(issues, Sequence):
            issue_codes = [str(issue) for issue in issues]
        else:
            issue_codes = [str(issues)]
        return [
            {
                "code": issue,
                "status": overall_status,
            }
            for issue in issue_codes
        ]

    @staticmethod
    def _sanitize_fact(
        fact: Mapping[str, Any],
        *,
        allowed_fields: set[str],
    ) -> dict[str, Any]:
        return {
            key: value
            for key, value in fact.items()
            if key in allowed_fields
        }

    @staticmethod
    def _select_key_facts(canonical_facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        consumable = [
            fact
            for fact in canonical_facts
            if fact.get("quality_status") in {None, "ok"}
            and not fact.get("validation_flags")
            and fact.get("entity_scope") not in {"unknown", "review_required"}
        ]
        prioritized = [
            fact for fact in consumable if fact.get("metric_id") in _API_VISIBLE_METRICS
        ]
        remainder = [
            fact for fact in consumable if fact.get("metric_id") not in _API_VISIBLE_METRICS
        ]
        return [*prioritized, *remainder][:10]

    @staticmethod
    def _quality_gate_from_validation_report(validation_report: Any) -> str:
        if validation_report is None:
            return "review"
        report = ReportAdapter._to_mapping(validation_report)
        overall_status = report.get("overall_status")
        if overall_status == "ok":
            return "pass"
        if overall_status == "review_required":
            return "review"
        return "fail"

    @staticmethod
    def _resolve_quality_gate(
        *,
        pipeline_quality_gate: Any,
        validation_report: Any,
    ) -> str:
        if pipeline_quality_gate is None:
            return ReportAdapter._quality_gate_from_validation_report(
                validation_report,
            )
        return str(pipeline_quality_gate)
