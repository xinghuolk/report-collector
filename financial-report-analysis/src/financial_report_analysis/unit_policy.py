from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NormalizedReportValue:
    normalized_value: float | int | None
    normalized_unit: str | None
    normalized_currency: str | None


@dataclass(frozen=True, slots=True)
class PresentationReportValue:
    presentation_value: float | int | None
    presentation_unit: str
    presentation_policy_name: str


class UnitPolicy:
    _THOUSAND_UNIT_SUFFIX = "'000"
    _UNIT_MULTIPLIERS = {
        "thousand": 1_000.0,
        "thousands": 1_000.0,
        "million": 1_000_000.0,
        "millions": 1_000_000.0,
        "billion": 1_000_000_000.0,
        "billions": 1_000_000_000.0,
        "千元": 1_000.0,
        "万元": 10_000.0,
        "万": 10_000.0,
        "百万元": 1_000_000.0,
        "百万": 1_000_000.0,
        "亿元": 100_000_000.0,
        "亿": 100_000_000.0,
    }

    def normalize_report_value(
        self,
        numeric_value: float | int | None,
        raw_unit: str | None,
        raw_currency: str | None,
    ) -> NormalizedReportValue:
        multiplier = self._unit_multiplier(raw_unit)
        normalized_value = (
            numeric_value * multiplier if numeric_value is not None else None
        )
        normalized_unit = raw_currency or raw_unit
        return NormalizedReportValue(
            normalized_value=normalized_value,
            normalized_unit=normalized_unit,
            normalized_currency=raw_currency,
        )

    def to_presentation(
        self,
        numeric_value: float | int | None,
        normalized_currency: str | None,
    ) -> PresentationReportValue:
        presentation_unit = normalized_currency or "unitless"
        return PresentationReportValue(
            presentation_value=numeric_value,
            presentation_unit=presentation_unit,
            presentation_policy_name="default_phase1",
        )

    def _unit_multiplier(self, raw_unit: str | None) -> float:
        if raw_unit is None:
            return 1.0

        normalized_unit = raw_unit.strip().replace("人民币", "")
        normalized_unit = normalized_unit.replace(" ", "")
        normalized_unit = normalized_unit.casefold()
        if normalized_unit.upper().endswith(self._THOUSAND_UNIT_SUFFIX):
            return 1000.0
        if normalized_unit in self._UNIT_MULTIPLIERS:
            return self._UNIT_MULTIPLIERS[normalized_unit]
        return 1.0
