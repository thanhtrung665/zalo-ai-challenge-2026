"""Period → [start, end] (gồm hai đầu) theo as_of_date. Tuần bắt đầu thứ Hai (SPEC §6.5)."""

from __future__ import annotations

import calendar as _cal
import datetime as dt
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from datamate.timeutil.calendar import LunarCalendar
from datamate.timeutil.errors import TimeError

__all__ = ["DateRange", "Period", "TimeError", "resolve_compare", "resolve_period", "shift_of_hour", "weekday_of"]

PeriodKind = Literal[
    "today",
    "yesterday",
    "day",
    "as_of_end_of_day",
    "this_week",
    "last_week",
    "this_month",
    "last_month",
    "month",
    "quarter",
    "year_to_date",
    "year",
    "last_n_days",
    "range",
    "tet",
    "before_tet",
    "all",
]
CompareKind = Literal["previous_period", "same_period_last_year"]

_DATA_START_DEFAULT = dt.date(1900, 1, 1)


class DateRange(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: dt.date
    end: dt.date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


class Period(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: PeriodKind
    date: dt.date | None = None
    month: int | None = None
    quarter: int | None = None
    year: int | None = None
    n: int | None = None
    start: dt.date | None = None
    end: dt.date | None = None


def _need(value: object, name: str, kind: str) -> None:
    if value is None:
        raise TimeError(f"period {kind!r} thiếu tham số {name!r}")


def month_range(year: int, month: int) -> DateRange:
    if not 1 <= month <= 12:
        raise TimeError(f"tháng không hợp lệ: {month}")
    return DateRange(start=dt.date(year, month, 1), end=dt.date(year, month, _cal.monthrange(year, month)[1]))


def _implied_year(first_day_of: Callable[[int], dt.date], as_of: dt.date, year: int | None) -> int:
    """Thiếu năm: năm nay nếu kỳ không bắt đầu sau hôm nay, ngược lại năm trước (SPEC §6.5)."""
    if year is not None:
        return year
    return as_of.year if first_day_of(as_of.year) <= as_of else as_of.year - 1


def _monday(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def weekday_of(d: dt.date) -> int:
    """0 = thứ Hai … 6 = Chủ nhật."""
    return d.weekday()


def shift_of_hour(hour: int) -> Literal["morning", "afternoon"] | None:
    """Ca sáng 06:00–13:59, ca chiều 14:00–21:59; ngoài hai ca → None."""
    if 6 <= hour <= 13:
        return "morning"
    if 14 <= hour <= 21:
        return "afternoon"
    return None


def resolve_period(
    period: Period,
    as_of: dt.date,
    calendar: LunarCalendar | None = None,
    data_start: dt.date | None = None,
) -> DateRange:
    """Quy `period` ra khoảng ngày theo `as_of`.

    `calendar` cần cho tet/before_tet; `data_start` cho all/as_of_end_of_day.
    """
    k = period.kind
    if k == "today":
        return DateRange(start=as_of, end=as_of)
    if k == "yesterday":
        d = as_of - dt.timedelta(days=1)
        return DateRange(start=d, end=d)
    if k == "day":
        _need(period.date, "date", k)
        return DateRange(start=period.date, end=period.date)  # type: ignore[arg-type]
    if k == "as_of_end_of_day":
        end = period.date or as_of
        return DateRange(start=data_start or _DATA_START_DEFAULT, end=end)
    if k == "this_week":
        return DateRange(start=_monday(as_of), end=as_of)
    if k == "last_week":
        mon = _monday(as_of) - dt.timedelta(days=7)
        return DateRange(start=mon, end=mon + dt.timedelta(days=6))
    if k == "this_month":
        return DateRange(start=as_of.replace(day=1), end=as_of)
    if k == "last_month":
        prev_end = as_of.replace(day=1) - dt.timedelta(days=1)
        return month_range(prev_end.year, prev_end.month)
    if k == "month":
        _need(period.month, "month", k)
        m: int = period.month  # type: ignore[assignment]
        if not 1 <= m <= 12:
            raise TimeError(f"tháng không hợp lệ: {m}")
        y = _implied_year(lambda yy: dt.date(yy, m, 1), as_of, period.year)
        return month_range(y, m)
    if k == "quarter":
        _need(period.quarter, "quarter", k)
        q: int = period.quarter  # type: ignore[assignment]
        if not 1 <= q <= 4:
            raise TimeError(f"quý không hợp lệ: {q}")
        y = _implied_year(lambda yy: dt.date(yy, 3 * q - 2, 1), as_of, period.year)
        return DateRange(start=dt.date(y, 3 * q - 2, 1), end=month_range(y, 3 * q).end)
    if k == "year_to_date":
        return DateRange(start=dt.date(as_of.year, 1, 1), end=as_of)
    if k == "year":
        _need(period.year, "year", k)
        return DateRange(start=dt.date(period.year, 1, 1), end=dt.date(period.year, 12, 31))  # type: ignore[arg-type]
    if k == "last_n_days":
        _need(period.n, "n", k)
        if period.n < 1:  # type: ignore[operator]
            raise TimeError(f"n phải ≥ 1: {period.n}")
        return DateRange(start=as_of - dt.timedelta(days=period.n - 1), end=as_of)  # type: ignore[operator]
    if k == "range":
        _need(period.start, "start", k)
        _need(period.end, "end", k)
        if period.start > period.end:  # type: ignore[operator]
            raise TimeError(f"range đảo ngược: {period.start} > {period.end}")
        return DateRange(start=period.start, end=period.end)  # type: ignore[arg-type]
    if k in ("tet", "before_tet"):
        if calendar is None:
            raise TimeError(f"period {k!r} cần calendar.csv")
        y = period.year if period.year is not None else calendar.latest_tet_year(as_of)
        s, e = calendar.tet_span(y)
        if k == "tet":
            return DateRange(start=s, end=e)
        n = (e - s).days + 1
        return DateRange(start=s - dt.timedelta(days=n), end=s - dt.timedelta(days=1))
    if k == "all":
        return DateRange(start=data_start or _DATA_START_DEFAULT, end=as_of)
    raise TimeError(f"period kind chưa hỗ trợ: {k!r}")  # pragma: no cover


def _shift_year(d: dt.date, delta: int) -> dt.date:
    y = d.year + delta
    if d.month == 2 and d.day == 29 and not _cal.isleap(y):
        return dt.date(y, 2, 28)
    return d.replace(year=y)


def resolve_compare(
    kind: CompareKind,
    base: Period,
    as_of: dt.date,
    calendar: LunarCalendar | None = None,
    data_start: dt.date | None = None,
) -> DateRange:
    """Kỳ so sánh của `base`.

    - `previous_period`: kỳ liền trước, cùng độ dài. Riêng `this_month`: **cùng số ngày** đầu của tháng trước
      (cắt ở cuối tháng).
    - `same_period_last_year`: dịch cả hai đầu lùi 1 năm (29/2 → 28/2 nếu năm kia không nhuận).
    """
    r = resolve_period(base, as_of, calendar, data_start)
    if base.kind in ("all", "as_of_end_of_day"):
        raise TimeError(f"không có kỳ so sánh cho {base.kind!r}")
    if kind == "same_period_last_year":
        return DateRange(start=_shift_year(r.start, -1), end=_shift_year(r.end, -1))
    if kind == "previous_period":
        if base.kind == "this_month":
            prev = month_range(*_prev_month(r.start))
            end = min(prev.end, prev.start + dt.timedelta(days=r.days - 1))
            return DateRange(start=prev.start, end=end)
        n = r.days
        return DateRange(start=r.start - dt.timedelta(days=n), end=r.start - dt.timedelta(days=1))
    raise TimeError(f"compare kind không hợp lệ: {kind!r}")


def _prev_month(first: dt.date) -> tuple[int, int]:
    d = first - dt.timedelta(days=1)
    return d.year, d.month
