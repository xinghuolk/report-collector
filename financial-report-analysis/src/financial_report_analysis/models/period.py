from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

PeriodType = Literal["POINT", "DURATION"]


@dataclass(kw_only=True)
class Period:
    POINT = "POINT"
    DURATION = "DURATION"

    period_type: PeriodType
    as_of_date: date | None = None
