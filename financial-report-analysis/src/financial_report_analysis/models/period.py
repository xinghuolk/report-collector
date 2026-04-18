from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

PeriodType = Literal["POINT", "DURATION"]
ReportingScope = Literal["Q1", "Q2", "H1", "Q3", "Q3_YTD", "FY", "CUSTOM"]
AdjustedStatus = Literal["ORIGINAL", "RESTATED"]
AccountingStandard = Literal["CAS", "IFRS", "HKFRS", "OTHER"]

_REPORTING_SCOPES = {"Q1", "Q2", "H1", "Q3", "Q3_YTD", "FY", "CUSTOM"}
_ADJUSTED_STATUSES = {"ORIGINAL", "RESTATED"}
_ACCOUNTING_STANDARDS = {"CAS", "IFRS", "HKFRS", "OTHER"}


@dataclass(kw_only=True)
class Period:
    POINT = "POINT"
    DURATION = "DURATION"

    period_id: str
    period_type: PeriodType
    reporting_scope: ReportingScope | None = None
    fiscal_year: int | None = None
    fiscal_period_index: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    as_of_date: date | None = None
    calendar_year: int | None = None
    adjusted_status: AdjustedStatus | None = None
    disclosure_label_raw: str | None = None
    fiscal_label: str | None = None
    accounting_standard: AccountingStandard | None = None
    is_stub_period: bool = False
    period_metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.period_type not in {self.POINT, self.DURATION}:
            raise ValueError("period_type must be POINT or DURATION")
        if self.reporting_scope is not None and self.reporting_scope not in _REPORTING_SCOPES:
            raise ValueError("reporting_scope is not a supported period enum value")
        if self.adjusted_status is not None and self.adjusted_status not in _ADJUSTED_STATUSES:
            raise ValueError("adjusted_status is not a supported period enum value")
        if (
            self.accounting_standard is not None
            and self.accounting_standard not in _ACCOUNTING_STANDARDS
        ):
            raise ValueError("accounting_standard is not a supported period enum value")
        if self.period_type == self.POINT and self.as_of_date is None:
            raise ValueError("as_of_date is required for POINT periods")
