from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(kw_only=True)
class Period:
    POINT = "POINT"
    DURATION = "DURATION"

    period_type: str
    as_of_date: date | None = None

