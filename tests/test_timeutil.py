"""Kiểm thử timeutil bằng tính tay.

as_of chính: 2025-03-12, thứ Tư (1/1/2025 là thứ Tư; cách 70 ngày = 10 tuần nên cùng thứ).
"""

import datetime as dt
from pathlib import Path

import pytest

from datamate.timeutil import (
    CalendarError,
    LunarCalendar,
    Period,
    TimeError,
    resolve_compare,
    resolve_period,
    shift_of_hour,
    weekday_of,
)

D = dt.date
AS_OF = D(2025, 3, 12)


def P(kind: str, **kw) -> Period:
    return Period(kind=kind, **kw)


def rng(p: Period, as_of: dt.date = AS_OF, **kw) -> tuple[dt.date, dt.date]:
    r = resolve_period(p, as_of, **kw)
    return r.start, r.end


# ---------- kỳ cơ bản ----------
@pytest.mark.parametrize(
    ("period", "as_of", "expected"),
    [
        (P("today"), AS_OF, (D(2025, 3, 12), D(2025, 3, 12))),
        (P("yesterday"), AS_OF, (D(2025, 3, 11), D(2025, 3, 11))),
        (P("yesterday"), D(2025, 1, 1), (D(2024, 12, 31), D(2024, 12, 31))),  # qua năm
        (P("yesterday"), D(2025, 3, 1), (D(2025, 2, 28), D(2025, 2, 28))),  # qua tháng, không nhuận
        (P("yesterday"), D(2024, 3, 1), (D(2024, 2, 29), D(2024, 2, 29))),  # qua tháng, nhuận
        (P("day", date=D(2025, 2, 3)), AS_OF, (D(2025, 2, 3), D(2025, 2, 3))),
        (P("this_week"), AS_OF, (D(2025, 3, 10), D(2025, 3, 12))),  # T2 → hôm nay
        (P("this_week"), D(2025, 3, 10), (D(2025, 3, 10), D(2025, 3, 10))),  # đúng thứ Hai
        (P("this_week"), D(2025, 3, 16), (D(2025, 3, 10), D(2025, 3, 16))),  # Chủ nhật
        (P("this_week"), D(2025, 1, 1), (D(2024, 12, 30), D(2025, 1, 1))),  # tuần qua năm
        (P("last_week"), AS_OF, (D(2025, 3, 3), D(2025, 3, 9))),
        (P("last_week"), D(2025, 3, 10), (D(2025, 3, 3), D(2025, 3, 9))),  # thứ Hai: tuần trước vừa kết thúc
        (P("last_week"), D(2025, 3, 16), (D(2025, 3, 3), D(2025, 3, 9))),  # Chủ nhật vẫn thuộc tuần này
        (P("last_week"), D(2025, 1, 1), (D(2024, 12, 23), D(2024, 12, 29))),
        (P("last_week"), D(2025, 1, 5), (D(2024, 12, 23), D(2024, 12, 29))),
        (P("this_month"), AS_OF, (D(2025, 3, 1), D(2025, 3, 12))),
        (P("this_month"), D(2025, 3, 1), (D(2025, 3, 1), D(2025, 3, 1))),
        (P("last_month"), AS_OF, (D(2025, 2, 1), D(2025, 2, 28))),
        (P("last_month"), D(2024, 3, 31), (D(2024, 2, 1), D(2024, 2, 29))),  # năm nhuận
        (P("last_month"), D(2025, 5, 31), (D(2025, 4, 1), D(2025, 4, 30))),  # 31 → tháng 30 ngày
        (P("last_month"), D(2025, 1, 15), (D(2024, 12, 1), D(2024, 12, 31))),  # đầu năm
        (P("last_month"), D(2025, 3, 1), (D(2025, 2, 1), D(2025, 2, 28))),
        (P("year_to_date"), AS_OF, (D(2025, 1, 1), D(2025, 3, 12))),
        (P("year_to_date"), D(2025, 1, 1), (D(2025, 1, 1), D(2025, 1, 1))),
        (P("year", year=2024), AS_OF, (D(2024, 1, 1), D(2024, 12, 31))),
        (P("last_n_days", n=7), AS_OF, (D(2025, 3, 6), D(2025, 3, 12))),
        (P("last_n_days", n=1), AS_OF, (D(2025, 3, 12), D(2025, 3, 12))),
        (P("last_n_days", n=30), AS_OF, (D(2025, 2, 11), D(2025, 3, 12))),  # 30 ngày: 11/2..12/3 (18+12)
        (P("last_n_days", n=7), D(2025, 1, 3), (D(2024, 12, 28), D(2025, 1, 3))),
        (P("range", start=D(2025, 1, 5), end=D(2025, 1, 5)), AS_OF, (D(2025, 1, 5), D(2025, 1, 5))),
        (P("range", start=D(2025, 1, 5), end=D(2025, 2, 6)), AS_OF, (D(2025, 1, 5), D(2025, 2, 6))),
    ],
)
def test_basic_periods(period, as_of, expected):
    assert rng(period, as_of) == expected


# ---------- tháng / quý thiếu năm ----------
@pytest.mark.parametrize(
    ("period", "expected"),
    [
        (P("month", month=3), (D(2025, 3, 1), D(2025, 3, 31))),  # tháng hiện tại → cả tháng, năm nay
        (P("month", month=2), (D(2025, 2, 1), D(2025, 2, 28))),
        (P("month", month=12), (D(2024, 12, 1), D(2024, 12, 31))),  # sau hôm nay → năm trước
        (P("month", month=4), (D(2024, 4, 1), D(2024, 4, 30))),
        (P("month", month=2, year=2024), (D(2024, 2, 1), D(2024, 2, 29))),
        (P("month", month=12, year=2025), (D(2025, 12, 1), D(2025, 12, 31))),  # có năm → giữ nguyên dù ở tương lai
        (P("quarter", quarter=1), (D(2025, 1, 1), D(2025, 3, 31))),
        (P("quarter", quarter=2), (D(2024, 4, 1), D(2024, 6, 30))),  # quý 2 chưa bắt đầu → năm trước
        (P("quarter", quarter=4), (D(2024, 10, 1), D(2024, 12, 31))),
        (P("quarter", quarter=3, year=2023), (D(2023, 7, 1), D(2023, 9, 30))),
        (P("quarter", quarter=4, year=2023), (D(2023, 10, 1), D(2023, 12, 31))),
    ],
)
def test_month_quarter_missing_year(period, expected):
    assert rng(period) == expected


def test_month_boundary_on_first_day():
    # as_of = đúng ngày 1 của tháng hỏi → không sau hôm nay → năm nay
    assert rng(P("month", month=4), D(2025, 4, 1)) == (D(2025, 4, 1), D(2025, 4, 30))
    assert rng(P("quarter", quarter=2), D(2025, 4, 1)) == (D(2025, 4, 1), D(2025, 6, 30))
    # một ngày trước đó → năm trước
    assert rng(P("month", month=4), D(2025, 3, 31)) == (D(2024, 4, 1), D(2024, 4, 30))


# ---------- all / as_of_end_of_day ----------
def test_all_and_end_of_day():
    ds = D(2024, 6, 1)
    assert rng(P("all"), data_start=ds) == (ds, AS_OF)
    assert rng(P("as_of_end_of_day"), data_start=ds) == (ds, AS_OF)
    assert rng(P("as_of_end_of_day", date=D(2025, 1, 31)), data_start=ds) == (ds, D(2025, 1, 31))


# ---------- tham số sai ----------
@pytest.mark.parametrize(
    "period",
    [
        P("day"),
        P("month"),
        P("month", month=13),
        P("month", month=0),
        P("quarter"),
        P("quarter", quarter=5),
        P("quarter", quarter=0),
        P("year"),
        P("last_n_days"),
        P("last_n_days", n=0),
        P("range", start=D(2025, 1, 1)),
        P("range", start=D(2025, 2, 1), end=D(2025, 1, 1)),
        P("tet"),  # thiếu calendar
    ],
)
def test_invalid_params(period):
    with pytest.raises(TimeError):
        resolve_period(period, AS_OF)


def test_period_from_dict_and_extra_forbidden():
    assert Period.model_validate({"kind": "last_n_days", "n": 3}).n == 3
    with pytest.raises(ValueError):
        Period.model_validate({"kind": "today", "foo": 1})


# ---------- ca, thứ ----------
@pytest.mark.parametrize(
    ("hour", "shift"),
    [(5, None), (6, "morning"), (13, "morning"), (14, "afternoon"), (21, "afternoon"), (22, None), (0, None)],
)
def test_shift(hour, shift):
    assert shift_of_hour(hour) == shift


def test_weekday():
    assert weekday_of(D(2025, 3, 10)) == 0  # thứ Hai
    assert weekday_of(D(2025, 3, 16)) == 6  # Chủ nhật


# ---------- kỳ so sánh ----------
def cmp(kind, base, as_of=AS_OF, **kw):
    r = resolve_compare(kind, base, as_of, **kw)
    return r.start, r.end


@pytest.mark.parametrize(
    ("base", "as_of", "expected"),
    [
        (P("today"), AS_OF, (D(2025, 3, 11), D(2025, 3, 11))),
        (P("last_week"), AS_OF, (D(2025, 2, 24), D(2025, 3, 2))),  # 7 ngày liền trước 3/3
        (P("this_week"), AS_OF, (D(2025, 3, 7), D(2025, 3, 9))),  # 3 ngày (10..12/3) → 7..9/3
        (P("last_month"), AS_OF, (D(2025, 1, 4), D(2025, 1, 31))),  # 28 ngày liền trước 1/2
        (P("quarter", quarter=1), AS_OF, (D(2024, 10, 3), D(2024, 12, 31))),  # 90 ngày; 10/3..31/12
        (P("year_to_date"), AS_OF, (D(2024, 10, 22), D(2024, 12, 31))),  # 71 ngày
        (P("last_n_days", n=7), AS_OF, (D(2025, 2, 27), D(2025, 3, 5))),
        # this_month: cùng số ngày của tháng trước
        (P("this_month"), AS_OF, (D(2025, 2, 1), D(2025, 2, 12))),
        (P("this_month"), D(2025, 3, 31), (D(2025, 2, 1), D(2025, 2, 28))),  # 31 ngày > tháng 2 → cắt cuối tháng
        (P("this_month"), D(2025, 5, 31), (D(2025, 4, 1), D(2025, 4, 30))),
        (P("this_month"), D(2025, 1, 15), (D(2024, 12, 1), D(2024, 12, 15))),  # đầu năm
        (P("this_month"), D(2025, 3, 1), (D(2025, 2, 1), D(2025, 2, 1))),
        (P("this_month"), D(2024, 3, 29), (D(2024, 2, 1), D(2024, 2, 29))),  # năm nhuận: đủ 29 ngày
    ],
)
def test_previous_period(base, as_of, expected):
    assert cmp("previous_period", base, as_of) == expected


@pytest.mark.parametrize(
    ("base", "as_of", "expected"),
    [
        (P("this_month"), AS_OF, (D(2024, 3, 1), D(2024, 3, 12))),
        (P("year", year=2024), AS_OF, (D(2023, 1, 1), D(2023, 12, 31))),
        (P("today"), D(2024, 2, 29), (D(2023, 2, 28), D(2023, 2, 28))),  # 29/2 → 28/2
        (P("range", start=D(2024, 2, 29), end=D(2024, 3, 1)), AS_OF, (D(2023, 2, 28), D(2023, 3, 1))),
        # lùi cả hai đầu một năm: 1/2..28/2/2025 → 1/2..28/2/2024 (không kéo dài tới 29/2)
        (P("last_month"), AS_OF, (D(2024, 2, 1), D(2024, 2, 28))),
    ],
)
def test_same_period_last_year(base, as_of, expected):
    assert cmp("same_period_last_year", base, as_of) == expected


def test_compare_undefined_for_all():
    with pytest.raises(TimeError):
        resolve_compare("previous_period", P("all"), AS_OF)
    with pytest.raises(TimeError):
        resolve_compare("same_period_last_year", P("as_of_end_of_day"), AS_OF)


# ---------- Tết ----------
def _rows(start: dt.date, spec: list[tuple[int, int, int, int]]):
    """spec: (lunar_month, ngày_đầu, ngày_cuối, leap) → các dòng liên tiếp từ start."""
    out, d = [], start
    for month, a, b, leap in spec:
        for ld in range(a, b + 1):
            out.append({"date": d.isoformat(), "lunar_month": month, "lunar_day": ld, "lunar_leap": leap})
            d += dt.timedelta(days=1)
    return out


@pytest.fixture
def cal() -> LunarCalendar:
    rows = []
    # Tết 2025 giả lập: 23/12 = 22/1/2025 … 29/12 = 28/1, 1/1 = 29/1 … 10/1 = 7/2 (17 ngày)
    rows += _rows(D(2025, 1, 22), [(12, 23, 29, 0), (1, 1, 10, 0)])
    # nhiễu: tháng 12 nhuận có ngày 23 giữa năm — không được nhận làm Tết
    rows += _rows(D(2025, 7, 1), [(12, 23, 25, 1)])
    # Tết 2026 giả lập: 23/12 = 10/2/2026, tháng Chạp đủ 30 ngày, 1/1 = 18/2, 10/1 = 27/2 (18 ngày)
    rows += _rows(D(2026, 2, 10), [(12, 23, 30, 0), (1, 1, 10, 0)])
    return LunarCalendar.from_rows(rows)


def test_tet_span(cal):
    assert cal.tet_span(2025) == (D(2025, 1, 22), D(2025, 2, 7))
    assert cal.tet_span(2026) == (D(2026, 2, 10), D(2026, 2, 27))


def test_tet_period_explicit_year(cal):
    assert rng(P("tet", year=2025), calendar=cal) == (D(2025, 1, 22), D(2025, 2, 7))
    assert rng(P("tet", year=2026), calendar=cal) == (D(2026, 2, 10), D(2026, 2, 27))


def test_tet_period_inferred_year(cal):
    assert rng(P("tet"), D(2025, 3, 12), calendar=cal) == (D(2025, 1, 22), D(2025, 2, 7))
    assert rng(P("tet"), D(2025, 1, 25), calendar=cal) == (D(2025, 1, 22), D(2025, 2, 7))  # đang trong Tết
    assert rng(P("tet"), D(2026, 3, 1), calendar=cal) == (D(2026, 2, 10), D(2026, 2, 27))


def test_tet_missing_year_raises(cal):
    with pytest.raises(CalendarError):
        resolve_period(P("tet", year=2030), AS_OF, calendar=cal)
    with pytest.raises(CalendarError):
        resolve_period(P("tet"), D(2025, 1, 10), calendar=cal)  # chưa có Tết nào bắt đầu


def test_before_tet(cal):
    # Tết 2025 dài 17 ngày → 17 ngày liền trước 22/1: 5/1..21/1
    assert rng(P("before_tet", year=2025), calendar=cal) == (D(2025, 1, 5), D(2025, 1, 21))
    # Tết 2026 dài 18 ngày → 23/1..9/2
    assert rng(P("before_tet", year=2026), calendar=cal) == (D(2026, 1, 23), D(2026, 2, 9))


def test_before_tet_has_same_length_as_tet(cal):
    for y in (2025, 2026):
        a = resolve_period(P("tet", year=y), AS_OF, calendar=cal)
        b = resolve_period(P("before_tet", year=y), AS_OF, calendar=cal)
        assert a.days == b.days
        assert (a.start - b.end).days == 1


def test_calendar_from_csv(tmp_path: Path):
    p = tmp_path / "calendar.csv"
    lines = ["date,weekday,lunar_day,lunar_month,lunar_year,lunar_leap,holiday"]
    for r in _rows(D(2025, 1, 22), [(12, 23, 29, 0), (1, 1, 10, 0)]):
        lines.append(f"{r['date']},0,{r['lunar_day']},{r['lunar_month']},2025,{r['lunar_leap']},")
    p.write_text("\n".join(lines), encoding="utf-8")
    c = LunarCalendar.from_csv(p)
    assert c.tet_span(2025) == (D(2025, 1, 22), D(2025, 2, 7))


def test_calendar_ignores_unpaired_start():
    # 23/12 mà không có 10/1 trong vòng 60 ngày → không tạo Tết
    c = LunarCalendar.from_rows(_rows(D(2025, 1, 22), [(12, 23, 29, 0)]))
    with pytest.raises(CalendarError):
        c.tet_span(2025)
