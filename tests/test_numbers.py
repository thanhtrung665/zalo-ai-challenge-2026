"""Test parser số tiếng Việt — mọi ca lấy từ dạng thật đo được trong dữ liệu BTC.

Bằng chứng số cho các ca đặc biệt (xem `docs/DATA_FINDINGS.md` §6 và khảo sát T05):
- `1,6256tr` (biz_124) đối chiếu 254 × 6.400đ = 1.625.600 → dấu phẩy là thập phân khi có hậu tố `tr`.
- `1tr090` (biz_127) đối chiếu 10 × 109.000đ = 1.090.000 → phần sau `tr` là phần nghìn bị bỏ số 0.
- `41k` (biz_105) = 41.000.
"""

from __future__ import annotations

import pytest

from datamate.ingest.numbers import parse_percent, parse_quantity, parse_vn_number


class TestParseMoney:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1.250.000", 1_250_000),
            ("1,250,000", 1_250_000),
            ("1.250.000đ", 1_250_000),
            ("1.250.000 VND", 1_250_000),
            ("20000", 20_000),
            ("115000", 115_000),
            ("38,000", 38_000),
            ("560,000", 560_000),
            ("65,000.0000", 65_000),
            ("210,000.0000", 210_000),
            ("1,550,000.0000", 1_550_000),
            ("194.600đ", 194_600),
            ("2.758.000đ", 2_758_000),
            ("(50.000)", -50_000),
            ("-50.000", -50_000),
            ("- 50.000", -50_000),
            ("0", 0),
            ("  12,000  ", 12_000),
        ],
    )
    def test_money(self, raw: str, expected: int) -> None:
        assert parse_vn_number(raw) == expected

    @pytest.mark.parametrize(("raw", "expected"), [("12,5", 12.5), ("12.5", 12.5), ("1.5", 1.5)])
    def test_decimal(self, raw: str, expected: float) -> None:
        assert parse_vn_number(raw) == pytest.approx(expected)

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("41k", 41_000),
            ("232k", 232_000),
            ("1044k", 1_044_000),
            ("2640k", 2_640_000),
            ("41K", 41_000),
            ("1,6256tr", 1_625_600),
            ("2,197tr", 2_197_000),
            ("1,035tr", 1_035_000),
            ("2,197tr", 2_197_000),
            ("1,41tr", 1_410_000),
            ("1tr090", 1_090_000),
            ("1tr156", 1_156_000),
            ("1tr", 1_000_000),
            ("9tr", 9_000_000),
        ],
    )
    def test_shorthand(self, raw: str, expected: int) -> None:
        assert parse_vn_number(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", "abc", "N/A", "-", "1tr2abc", "chưa có", "9tr9"])
    def test_unparseable_is_none_never_zero(self, raw: str) -> None:
        assert parse_vn_number(raw) is None

    def test_none_input(self) -> None:
        assert parse_vn_number(None) is None

    def test_no_float_roundoff_for_money(self) -> None:
        # Tiền phải là int chính xác, không qua float
        v = parse_vn_number("1.999.999.999")
        assert v == 1_999_999_999
        assert isinstance(v, int)


class TestParseQuantity:
    @pytest.mark.parametrize(
        ("raw", "qty", "unit"),
        [
            ("1", 1, None),
            ("10", 10, None),
            ("2.0", 2, None),
            ("-9", -9, None),
            ("1 chai", 1, "chai"),
            ("1 hộp 30", 1, "hộp 30"),
            ("1 bao 25kg", 1, "bao 25kg"),
            ("2 m3", 2, "m3"),
            ("1 ly", 1, "ly"),
            ("10 hộp", 10, "hộp"),
            ("1 kg", 1, "kg"),
            ("144", 144, None),
            ("1 thùng", 1, "thùng"),
        ],
    )
    def test_quantity(self, raw: str, qty: float, unit: str | None) -> None:
        got_qty, got_unit = parse_quantity(raw)
        assert got_qty == pytest.approx(qty)
        assert got_unit == unit

    def test_quantity_integer_returns_int(self) -> None:
        qty, _ = parse_quantity("10")
        assert isinstance(qty, int)

    @pytest.mark.parametrize("raw", ["", "  ", "abc", "-", "chai"])
    def test_quantity_unparseable(self, raw: str) -> None:
        assert parse_quantity(raw) == (None, None)

    def test_quantity_none(self) -> None:
        assert parse_quantity(None) == (None, None)


class TestParsePercent:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("12.4", 12.4),
            ("12,4", 12.4),
            ("12,4%", 12.4),
            ("12%", 12.0),
            ("-3,5", -3.5),
            ("100", 100.0),
            ("0", 0.0),
        ],
    )
    def test_percent(self, raw: str, expected: float) -> None:
        assert parse_percent(raw) == pytest.approx(expected)

    @pytest.mark.parametrize("raw", ["", "abc", "%"])
    def test_percent_unparseable(self, raw: str) -> None:
        assert parse_percent(raw) is None
