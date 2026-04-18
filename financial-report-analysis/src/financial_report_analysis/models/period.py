from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

PeriodType = Literal["POINT", "DURATION"]
ReportingScope = Literal["Q1", "Q2", "H1", "Q3", "Q3_YTD", "FY", "CUSTOM"]
AdjustedStatus = Literal["ORIGINAL", "RESTATED"]


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
    adjusted_status: AdjustedStatus | None = None
    disclosure_label_raw: str | None = None
    is_stub_period: bool = False
    period_metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.period_type not in {self.POINT, self.DURATION}:
            raise ValueError("period_type must be POINT or DURATION")
