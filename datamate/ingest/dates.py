"""Parse ngày kiểu Việt Nam và Excel serial từ ô dữ liệu thô (SPEC §6.1).

Quy tắc đã kiểm bằng số trên dữ liệu BTC:
- **Ngày trước tháng** cho dạng `dd/mm/yyyy` (`02/01/2026` = 2 tháng 1).
- Excel serial: 1 = 1899-12-30, chỉ nhận 30000–60000 (1982-…-2064); ngoài khoảng → `None`.
- Ngày thiếu năm (`10/1`) cần `sheet_year`; thiếu → `None`, không đoán.
- Ngoài khoảng 2015–2030 → `None` (cảnh báo qua logger).
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

MIN_YEAR = 2015
MAX_YEAR = 2030
SERIAL_MIN = 30000
SERIAL_MAX = 60000
_EXCEL_EPOCH = date(1899, 12, 30)

_DMY = re.compile(r"^(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4})$")
_YMD = re.compile(r"^(\d{4})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})$")
_VN_THG = re.compile(
    r"^(\d{1,2})\s*(?:thg|tháng|thang)\s*(\d{1,2})\s*(?:năm|nam)?\s*,?\s*(\d{4})$",
    re.IGNORECASE,
)
_DM_NO_YEAR = re.compile(r"^(\d{1,2})\s*[/\-.]\s*(\d{1,2})$")
_DATETIME_PREFIX = re.compile(r"^(\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4})[ T]\d{1,2}:\d{2}(?::\d{2})?")


def _in_range(d: date) -> bool:
    return MIN_YEAR <= d.year <= MAX_YEAR


def _build(y: int, m: int, d: int, *, raw: object) -> date | None:
    try:
        out = date(y, m, d)
    except ValueError:
        logger.debug("Ngày không hợp lệ: %r", raw)
        return None
    if not _in_range(out):
        logger.debug("Ngày ngoài khoảng %d–%d: %r", MIN_YEAR, MAX_YEAR, raw)
        return None
    return out


def _from_serial(value: float, *, raw: object) -> date | None:
    if not (SERIAL_MIN <= value <= SERIAL_MAX):
        return None
    out = _EXCEL_EPOCH + timedelta(days=int(value))
    return out if _in_range(out) else None


def parse_vn_date(
    raw: str | int | float | date | datetime | None,
    *,
    sheet_year: int | None = None,
) -> date | None:
    """Parse một ô ngày. Không parse được → `None` (không bao giờ đoán bừa)."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        d = raw.date()
        return d if _in_range(d) else None
    if isinstance(raw, date):
        return raw if _in_range(raw) else None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return _from_serial(float(raw), raw=raw)

    s = str(raw).strip()
    if not s:
        return None
    s = re.sub(r"\s+", " ", s)

    m = _DATETIME_PREFIX.match(s)
    if m:
        s = m.group(1)

    if m := _YMD.match(s):
        return _build(int(m.group(1)), int(m.group(2)), int(m.group(3)), raw=raw)
    if m := _DMY.match(s):
        return _build(int(m.group(3)), int(m.group(2)), int(m.group(1)), raw=raw)
    if m := _VN_THG.match(s):
        return _build(int(m.group(3)), int(m.group(2)), int(m.group(1)), raw=raw)

    # Số thuần (serial dạng chuỗi)
    if re.fullmatch(r"\d{5}(?:\.0+)?", s):
        return _from_serial(float(s), raw=raw)

    if m := _DM_NO_YEAR.match(s):
        if sheet_year is None:
            return None
        return _build(int(sheet_year), int(m.group(2)), int(m.group(1)), raw=raw)

    return None


def infer_sheet_year(raws: list[str | None]) -> int | None:
    """Suy năm của sheet từ các ô có năm trong cùng cột (rulebook §8: ngày thiếu năm lấy năm của sheet).

    Lấy năm xuất hiện nhiều nhất trong các ô parse được; không có ô nào có năm → `None`.
    """
    years: dict[int, int] = {}
    for raw in raws:
        if raw is None:
            continue
        s = str(raw).strip()
        if not s:
            continue
        m = re.search(r"(?<!\d)(20[1-4]\d)(?!\d)", s)
        if not m:
            continue
        year = int(m.group(1))
        if MIN_YEAR <= year <= MAX_YEAR:
            years[year] = years.get(year, 0) + 1
    if not years:
        return None
    return max(years.items(), key=lambda kv: (kv[1], kv[0]))[0]


def year_from_sheet_name(name: str | None) -> int | None:
    """Lấy năm từ tên sheet ("Tháng 01-2025", "T02_2026") — nguồn đúng nhất cho rulebook §8."""
    if not name:
        return None
    for m in re.finditer(r"(?<!\d)(20[1-4]\d)(?!\d)", str(name)):
        year = int(m.group(1))
        if MIN_YEAR <= year <= MAX_YEAR:
            return year
    return None


def _raw_has_no_year(raw: object) -> bool:
    """Ô ngày có ghi năm hay không (dùng để biết ô có phải mốc chắc chắn)."""
    if raw is None or isinstance(raw, (int, float, date, datetime)):
        return False
    s = str(raw).strip()
    if not s:
        return False
    return not re.search(r"(?<!\d)(19|20)\d{2}(?!\d)", s)


def _seed_year(values: list[str | None], sheet_years: list[int | None] | None) -> int | None:
    """Năm khởi đầu cho các ô thiếu năm nằm trước ô có năm đầu tiên của cột."""
    if sheet_years:
        for y in sheet_years:
            if y is not None:
                return y
    for raw in values:
        if raw is None:
            continue
        m = re.search(r"(?<!\d)(20[1-4]\d)(?!\d)", str(raw))
        if m:
            return int(m.group(1))
    return None


def parse_date_column(
    values: list[str | None],
    sheet_years: list[int | None] | None = None,
) -> list[date | None]:
    """Parse cả cột ngày, tự suy năm cho ô thiếu năm (rulebook §8 "ngày không ghi năm").

    Luật suy năm (đo trên 1,46 triệu ô ngày của train, bóc năm 1/3 số ô làm hold-out):
    - Ô có năm của sheet → dùng năm của sheet.
    - Ô thiếu năm → năm của mốc gần nhất phía trước; **tháng nhỏ hơn tháng mốc** nghĩa là sổ
      đã sang năm mới → năm mốc + 1 ("cuộn năm", đúng 98,5% số ô).
    - Ô thiếu năm nằm trước ô có năm đầu tiên → dùng năm của ô có năm đầu tiên đó.
    - Không suy được → `None`, không đoán.

    "Năm đa số cả cột" chỉ đúng 61,2% nên không dùng.
    """
    out: list[date | None] = []
    running_year = _seed_year(values, sheet_years)
    running_month: int | None = None
    for i, raw in enumerate(values):
        explicit = sheet_years[i] if sheet_years is not None and i < len(sheet_years) else None

        d = parse_vn_date(raw, sheet_year=explicit if explicit is not None else running_year)
        if (
            d is not None
            and explicit is None
            and _raw_has_no_year(raw)
            and running_month is not None
            and running_year is not None
            and d.month < running_month
        ):
            try:
                d = date(running_year + 1, d.month, d.day)
            except ValueError:
                d = None
        if d is None:
            out.append(None)
            continue

        out.append(d)
        running_year, running_month = d.year, d.month
    return out
