"""Lịch âm–dương từ `calendar.csv` (cột: date, weekday, lunar_day, lunar_month, lunar_year, lunar_leap, holiday).

Tết năm Y (theo dương lịch của mùng 1) = từ 23 tháng Chạp đến hết mùng 10 tháng Giêng. Không dựa vào
ngữ nghĩa cột `lunar_year`: bắt cặp "23/12 âm (không nhuận)" với "10/1 âm (không nhuận)" đầu tiên sau đó;
Y = năm dương của ngày mùng 10.
"""

from __future__ import annotations

import csv
import datetime as dt
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from datamate.timeutil.errors import TimeError


class CalendarError(TimeError):
    """Thiếu dữ liệu lịch cho kỳ được hỏi."""


def _truthy(v: Any) -> bool:
    return str(v).strip().lower() in ("1", "true", "t", "yes", "y")


class LunarCalendar:
    def __init__(self, tet_spans: Mapping[int, tuple[dt.date, dt.date]]) -> None:
        self._tet = dict(tet_spans)

    @classmethod
    def from_rows(cls, rows: Iterable[Mapping[str, Any]]) -> LunarCalendar:
        parsed = sorted(
            (
                dt.date.fromisoformat(str(r["date"]).strip()[:10]),
                int(r["lunar_month"]),
                int(r["lunar_day"]),
                _truthy(r.get("lunar_leap", 0)),
            )
            for r in rows
        )
        spans: dict[int, tuple[dt.date, dt.date]] = {}
        start: dt.date | None = None
        for day, month, lday, leap in parsed:
            if leap:
                continue
            if month == 12 and lday == 23:
                start = day
            elif month == 1 and lday == 10 and start is not None:
                if 0 < (day - start).days <= 60:
                    spans[day.year] = (start, day)
                start = None
        return cls(spans)

    @classmethod
    def from_csv(cls, path: str | Path) -> LunarCalendar:
        with open(path, encoding="utf-8", newline="") as f:
            return cls.from_rows(csv.DictReader(f))

    def tet_span(self, year: int) -> tuple[dt.date, dt.date]:
        """(23 tháng Chạp, mùng 10 tháng Giêng) của Tết năm `year`."""
        if year not in self._tet:
            raise CalendarError(f"calendar không có Tết năm {year}")
        return self._tet[year]

    def latest_tet_year(self, as_of: dt.date) -> int:
        """Tết gần nhất đã bắt đầu (23 Chạp ≤ as_of)."""
        years = [y for y, (s, _) in self._tet.items() if s <= as_of]
        if not years:
            raise CalendarError(f"calendar không có Tết nào bắt đầu trước {as_of}")
        return max(years)
