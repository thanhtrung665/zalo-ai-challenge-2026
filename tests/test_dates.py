"""Test parser ngày tiếng Việt / Excel serial — ca lấy từ dạng thật trong dữ liệu BTC.

Dạng đã đo (khảo sát T05, train):
- `01/01/2025` (89.831 ô), `2025-02-01 06:03:42`, `2024-10-29`, `10 thg 6 2025`, serial `45689`, `10/1` (thiếu năm).
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from datamate.ingest.dates import infer_sheet_year, parse_date_column, parse_vn_date


class TestIsoAndSlash:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2024-10-29", date(2024, 10, 29)),
            ("2025-02-01 06:03:42", date(2025, 2, 1)),
            ("2025-02-01T06:03:42", date(2025, 2, 1)),
            ("01/01/2025", date(2025, 1, 1)),
            ("31/12/2025", date(2025, 12, 31)),
            ("1/2/2026", date(2026, 2, 1)),
            ("2025/02/01", date(2025, 2, 1)),
        ],
    )
    def test_full_dates(self, raw: str, expected: date) -> None:
        got = parse_vn_date(raw)
        assert got == expected
        assert type(got) is date

    def test_datetime_input_returns_date(self) -> None:
        got = parse_vn_date(datetime(2025, 3, 4, 15, 30))
        assert got == date(2025, 3, 4)
        assert type(got) is date


class TestVietnameseMonthWords:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1 thg 6 2025", date(2025, 6, 1)),
            ("10 thg 6 2025", date(2025, 6, 10)),
            ("1 thg 10 2025", date(2025, 10, 1)),
            ("31 thg 12 2025", date(2025, 12, 31)),
            ("1 tháng 6 năm 2025", date(2025, 6, 1)),
            ("01/02/2026 08:30", date(2026, 2, 1)),
        ],
    )
    def test_vn_month(self, raw: str, expected: date) -> None:
        assert parse_vn_date(raw) == expected


class TestDayMonthBeforeMonth:
    """Dữ liệu BTC dùng ngày trước tháng. 02/01 = 2 tháng 1, KHÔNG phải 1 tháng 2."""

    def test_day_first(self) -> None:
        assert parse_vn_date("02/01/2026") == date(2026, 1, 2)
        assert parse_vn_date("02/01/2026") != date(2026, 2, 1)

    def test_ambiguous_us_style_not_used(self) -> None:
        # 25/12/2025 không thể là tháng 25 -> chắc chắn ngày trước tháng
        assert parse_vn_date("25/12/2025") == date(2025, 12, 25)


class TestExcelSerial:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (45658, date(2025, 1, 1)),
            ("45658", date(2025, 1, 1)),
            ("45689.0", date(2025, 2, 1)),
            (45689.0, date(2025, 2, 1)),
            (1.0, None),  # ngoài khoảng tin cậy -> không đoán
            ("30000", None),  # serial hợp lệ nhưng năm 1982 ngoài khoảng 2015–2030
            (60000, None),  # năm 2064 ngoài khoảng
            (42005, date(2015, 1, 1)),  # biên dưới khoảng năm
            (47848, date(2030, 12, 31)),  # biên trên khoảng năm
        ],
    )
    def test_serial(self, raw, expected: date | None) -> None:
        assert parse_vn_date(raw) == expected


class TestMissingYear:
    def test_day_slash_month_with_sheet_year(self) -> None:
        assert parse_vn_date("10/1", sheet_year=2025) == date(2025, 1, 10)
        assert parse_vn_date("1/1", sheet_year=2026) == date(2026, 1, 1)

    def test_day_slash_month_without_year_is_none(self) -> None:
        assert parse_vn_date("10/1") is None


class TestOutOfRangeAndJunk:
    @pytest.mark.parametrize("raw", ["", "  ", "abc", "-", "không có", "chưa giao"])
    def test_junk_is_none(self, raw: str) -> None:
        assert parse_vn_date(raw) is None

    def test_none_input(self) -> None:
        assert parse_vn_date(None) is None

    @pytest.mark.parametrize("raw", ["01/01/1900", "01/01/2085", date(1999, 12, 31)])
    def test_outside_valid_range(self, raw) -> None:
        assert parse_vn_date(raw) is None

    def test_invalid_calendar_date_is_none(self) -> None:
        assert parse_vn_date("31/02/2025") is None

    def test_year_month_only_is_not_a_date(self) -> None:
        # "2025-09" là format đáp án, không phải ô ngày trong file
        assert parse_vn_date("2025-09") is None


class TestValidRangeBoundaries:
    def test_lower_bound(self) -> None:
        assert parse_vn_date("01/01/2015") == date(2015, 1, 1)

    def test_upper_bound(self) -> None:
        assert parse_vn_date("31/12/2030") == date(2030, 12, 31)


class TestColumnYearInference:
    """Rulebook §8: 'Ngày không ghi năm | năm của sheet chứa dòng đó'."""

    def test_infer_sheet_year_majority(self) -> None:
        assert infer_sheet_year(["01/01/2025", "1/1", "1 thg 1 2025", "2025-03-04"]) == 2025

    def test_infer_sheet_year_none(self) -> None:
        assert infer_sheet_year(["1/1", "2/1"]) is None
        assert infer_sheet_year([]) is None

    def test_column_parses_missing_year_dates(self) -> None:
        vals = ["1/1", "01/01/2025", "1 thg 1 2025", "15/1"]
        got = parse_date_column(vals)
        assert got == [date(2025, 1, 1), date(2025, 1, 1), date(2025, 1, 1), date(2025, 1, 15)]

    def test_column_junk_stays_none(self) -> None:
        got = parse_date_column(["01/01/2025", "không có", ""])
        assert got == [date(2025, 1, 1), None, None]

    def test_column_year_follows_previous_row(self) -> None:
        # Sổ ghi theo thời gian: ô thiếu năm lấy năm của dòng có năm gần nhất phía trước
        vals = ["20/12/2025", "3/1", "20/01/2026", "5/2"]
        got = parse_date_column(vals)
        assert got == [date(2025, 12, 20), date(2026, 1, 3), date(2026, 1, 20), date(2026, 2, 5)]

    def test_column_year_before_first_year_uses_first_year(self) -> None:
        vals = ["1/1", "15/3/2025"]
        got = parse_date_column(vals)
        assert got == [date(2025, 1, 1), date(2025, 3, 15)]


def test_duration_columns_with_day_unit_are_not_dates():
    from datamate.tools.parse_report import classify_column

    assert classify_column("Hạn nợ (ngày)", ["30", "60"]) is None
    assert classify_column("Hạn góp (ngày)", ["3", "12"]) is None
    assert classify_column("Ngày bán", ["02/01/2026"]) == "date"
