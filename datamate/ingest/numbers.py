"""Parse số, số lượng, phần trăm kiểu Việt Nam từ ô dữ liệu thô (SPEC §6.1, rulebook §8).

Nguyên tắc:
- Không bao giờ đổi "không parse được" thành 0 — trả `None`.
- Tiền trả `int` VND; chỉ dùng `Decimal`, không qua float.
- Số lượng = **số đầu tiên** trong ô; phần chữ còn lại là đơn vị (có thể chứa số: "1 hộp 30").

Dấu phân cách (đã kiểm bằng số trên dữ liệu BTC, xem `tests/test_numbers.py`):
- Có hậu tố `k`/`tr`/`triệu`/`nghìn` → dấu `,`/`.` là **thập phân**: `1,6256tr` = 1.625.600.
- Dấu phân cách nhóm đều đúng 3 chữ số và không có hậu tố → phân cách nghìn: `1.250.000`, `1,250,000`.
- Chỉ một dấu, phần sau có 1–2 chữ số → thập phân: `12,5`.
- `1tr090` → 1.090.000 (hậu tố `tr` rồi đúng 3 chữ số là phần nghìn viết tắt). Đuôi ngắn hơn → `None`.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_THOUSANDS_DOT = re.compile(r"^-?\d{1,3}(\.\d{3})+$")
_THOUSANDS_COMMA = re.compile(r"^-?\d{1,3}(,\d{3})+$")
_DECIMAL_MIXED = re.compile(r"^-?\d{1,3}(,\d{3})*\.\d+$")  # 65,000.0000 / 1,550,000.0000
_PLAIN_INT = re.compile(r"^-?\d+$")
_SHORTHAND = re.compile(r"^(-?\d+(?:[.,]\d+)?)\s*(k|ng|nghìn|nghin|tr|triệu|trieu)\s*(\d{1,3})?$", re.IGNORECASE)
_FIRST_NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?")

_SHORTHAND_MULTIPLIER = {
    "k": 1_000,
    "ng": 1_000,
    "nghìn": 1_000,
    "nghin": 1_000,
    "tr": 1_000_000,
    "triệu": 1_000_000,
    "trieu": 1_000_000,
}


def _strip_currency_and_space(s: str) -> str:
    s = s.replace(" ", " ").replace("₫", "đ")
    s = re.sub(r"(?i)\b(vnd|vnđ|usd)\b", "", s)
    s = s.replace("đ", "").replace("Đ", "")
    s = re.sub(r"\s+", "", s)
    return s.strip()


def _decimal_to_number(dec: Decimal) -> int | float:
    """Trả int nếu là số nguyên chính xác, ngược lại float."""
    if dec == dec.to_integral_value():
        return int(dec)
    return float(dec)


def _parse_shorthand(s: str) -> int | float | None:
    m = _SHORTHAND.match(s)
    if not m:
        return None
    core, suffix, tail = m.group(1), m.group(2).lower(), m.group(3)
    try:
        base = Decimal(core.replace(",", "."))
    except InvalidOperation:
        return None
    value = base * _SHORTHAND_MULTIPLIER[suffix]
    if tail:
        # Chỉ dạng đuôi 3 chữ số đã kiểm bằng số: "1tr090" = 1.090.000 (bằng 10 × 109.000đ
        # trong bảng chi tiết bán của một shop VLXD). Đuôi ngắn hơn không có bằng chứng → không đoán.
        if len(tail) != 3:
            return None
        value += Decimal(int(tail)) * _SHORTHAND_MULTIPLIER[suffix] / Decimal(1000)
    return _decimal_to_number(value)


def parse_vn_number(raw: str | int | float | None) -> int | float | None:
    """Parse một ô thành số (tiền/thập phân). Không parse được → `None`, không bao giờ 0."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw) if raw.is_integer() else raw

    s = str(raw).strip()
    if not s:
        return None

    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    s = _strip_currency_and_space(s)
    if s.startswith("+") or s.startswith("-"):
        if s[0] == "-":
            negative = not negative
        s = s[1:]

    percent = False
    if s.endswith("%"):
        percent = True
        s = s[:-1]

    if not s or not any(ch.isdigit() for ch in s):
        return None

    shorthand = _parse_shorthand(s)
    if shorthand is not None:
        value = -shorthand if negative else shorthand
        return value

    value: Decimal | None = None
    try:
        if _PLAIN_INT.match(s):
            value = Decimal(s)
        elif _THOUSANDS_DOT.match(s):
            value = Decimal(s.replace(".", ""))
        elif _THOUSANDS_COMMA.match(s) or _DECIMAL_MIXED.match(s):
            value = Decimal(s.replace(",", ""))
        elif re.match(r"^-?\d+\.\d+$", s):
            value = Decimal(s)
        elif re.match(r"^-?\d+,\d+$", s):
            value = Decimal(s.replace(",", "."))
        elif re.match(r"^-?\d{1,3}(\.\d{3})+,\d+$", s):
            value = Decimal(s.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None

    if value is None:
        return None
    if percent:
        value = value  # 12,4% -> 12.4 (số phần trăm, không chia 100)
    if negative:
        value = -value
    return _decimal_to_number(value)


def parse_quantity(raw: str | int | float | None) -> tuple[int | float | None, str | None]:
    """Parse ô số lượng: trả `(số, đơn vị)`.

    Số = **số đầu tiên** trong ô ("1 hộp 30" → 1, đơn vị "hộp 30"). Không nối chữ số.
    Không parse được → `(None, None)`.
    """
    if raw is None:
        return None, None
    if isinstance(raw, bool):
        return None, None
    if isinstance(raw, int):
        return raw, None
    if isinstance(raw, float):
        return (int(raw) if raw.is_integer() else raw), None

    s = str(raw).strip()
    if not s:
        return None, None

    m = _FIRST_NUMBER.search(s)
    if not m:
        return None, None

    qty = parse_vn_number(m.group(0))
    if qty is None:
        return None, None

    unit = (s[: m.start()] + s[m.end() :]).strip()
    unit = re.sub(r"\s+", " ", unit).strip(" .-")
    return qty, (unit or None)


def parse_percent(raw: str | int | float | None) -> float | None:
    """Parse ô phần trăm: "12,4%" → 12.4 (giá trị phần trăm, không chia 100)."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    s = str(raw).strip()
    if not s:
        return None
    v = parse_vn_number(s)
    if v is None:
        return None
    return float(v)
