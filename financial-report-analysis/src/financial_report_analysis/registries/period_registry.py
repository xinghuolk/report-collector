from __future__ import annotations

from datetime import date

from financial_report_analysis.models.period import Period


class PeriodRegistry:
    def __init__(self) -> None:
        self._duration_periods: dict[tuple[object, ...], Period] = {}

    def get_or_create_duration(
        self,
        fiscal_year: int,
        reporting_scope: str,
        start_date: date,
        end_date: date,
        accounting_standard: str,
        disclosure_label_raw: str,
    ) -> Period:
        normalized_reporting_scope = self._normalize_reporting_scope(reporting_scope)
        normalized_accounting_standard = accounting_standard.casefold()
        key = (
            fiscal_year,
            normalized_reporting_scope.casefold(),
            start_date,
            end_date,
            normalized_accounting_standard,
        )
        if key not in self._duration_periods:
            self._duration_periods[key] = Period(
                period_id=self._build_period_id(
                    fiscal_year=fiscal_year,
                    reporting_scope=normalized_reporting_scope,
                    start_date=start_date,
                    end_date=end_date,
                    accounting_standard=normalized_accounting_standard,
                ),
                period_type=Period.DURATION,
                reporting_scope=normalized_reporting_scope,
                fiscal_year=fiscal_year,
                fiscal_period_index=self._fiscal_period_index(
                    normalized_reporting_scope
                ),
                start_date=start_date,
                end_date=end_date,
                calendar_year=end_date.year,
                adjusted_status="ORIGINAL",
                disclosure_label_raw=disclosure_label_raw,
                fiscal_label=disclosure_label_raw,
                accounting_standard=normalized_accounting_standard,
                is_stub_period=False,
                period_metadata={},
            )
        return self._duration_periods[key]

    @staticmethod
    def _build_period_id(
        *,
        fiscal_year: int,
        reporting_scope: str,
        start_date: date,
        end_date: date,
        accounting_standard: str,
    ) -> str:
        return (
            "duration::"
            f"{accounting_standard.lower()}::"
            f"{fiscal_year}::"
            f"{reporting_scope.lower()}::"
            f"{start_date.isoformat()}::"
            f"{end_date.isoformat()}"
        )

    @staticmethod
    def _fiscal_period_index(reporting_scope: str) -> int | None:
        scope_to_index = {
            "Q1": 1,
            "Q2": 2,
            "H1": 2,
            "Q3": 3,
            "Q3_YTD": 3,
            "FY": 4,
        }
        return scope_to_index.get(reporting_scope)

    @staticmethod
    def _normalize_reporting_scope(reporting_scope: str) -> str:
        return reporting_scope.upper()
