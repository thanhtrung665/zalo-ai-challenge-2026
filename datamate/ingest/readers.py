"""Đọc dữ liệu thô từ CSV, XLSX, SQLite thành ma trận chuỗi (RawSheet) chưa có header."""

from __future__ import annotations

import csv
import io
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RawSheet:
    """Biểu diễn một sheet hoặc bảng thô dưới dạng ma trận chuỗi."""

    name: str  # Tên sheet/bảng (với CSV là "-")
    rows: list[list[str]]  # Mọi ô là chuỗi
    src_file: str  # Tên hoặc đường dẫn tương đối của file nguồn
    source_type: str  # "csv", "xlsx", "sqlite"
    extra: dict[str, Any] = field(default_factory=dict)  # Metadata thêm (encoding, number_formats...)

    @property
    def num_rows(self) -> int:
        return len(self.rows)

    @property
    def num_cols(self) -> int:
        return max((len(r) for r in self.rows), default=0)


def _decode_csv_bytes(raw: bytes) -> tuple[str, str]:
    """Dò encoding theo thứ tự ưu tiên: utf-8-sig -> utf-8 -> cp1258 -> fallback latin-1."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"

    # Thử charset-normalizer nếu có
    try:
        import charset_normalizer

        match = charset_normalizer.from_bytes(raw).best()
        if match is not None and match.encoding in ("utf_8", "utf_8_sig", "cp1258"):
            try:
                dec_enc = "utf-8-sig" if match.encoding in ("utf_8", "utf_8_sig") else match.encoding
                return raw.decode(dec_enc), dec_enc
            except UnicodeDecodeError:
                pass
    except Exception:
        pass

    for enc in ("utf-8-sig", "utf-8", "cp1258"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace"), "latin-1"


def read_csv_raw(path: Path) -> list[RawSheet]:
    """Đọc file CSV thành RawSheet với toàn bộ ô dạng chuỗi."""
    raw = path.read_bytes()
    text, enc = _decode_csv_bytes(raw)
    reader = csv.reader(io.StringIO(text))
    rows: list[list[str]] = []
    for row in reader:
        # Giữ nguyên giá trị dưới dạng chuỗi, strip whitespace thừa ở 2 đầu và BOM
        rows.append([c.strip().lstrip("\ufeff") if c is not None else "" for c in row])
    return [
        RawSheet(
            name="-",
            rows=rows,
            src_file=path.name,
            source_type="csv",
            extra={"encoding": enc},
        )
    ]


def _inspect_xlsx_number_formats(path: Path, max_rows: int = 50) -> dict[str, dict[int, str]]:
    """Dùng openpyxl read_only đọc lướt các dòng đầu để lấy number_format của từng cột theo sheet."""
    formats_by_sheet: dict[str, dict[int, str]] = {}
    try:
        from openpyxl import load_workbook

        wb = load_workbook(str(path), read_only=True, data_only=False)
        for sheetname in wb.sheetnames:
            ws = wb[sheetname]
            col_formats: dict[int, str] = {}
            for r_idx, row in enumerate(ws.iter_rows(values_only=False)):
                if r_idx >= max_rows:
                    break
                for c_idx, cell in enumerate(row):
                    if cell is not None and getattr(cell, "number_format", None):
                        fmt = str(cell.number_format)
                        if fmt not in ("General", "@", ""):
                            col_formats.setdefault(c_idx, fmt)
            formats_by_sheet[sheetname] = col_formats
        wb.close()
    except Exception:
        # Nếu openpyxl lỗi hoặc không đọc được, không ảnh hưởng đến luồng chính
        pass
    return formats_by_sheet


def read_xlsx_raw(path: Path) -> list[RawSheet]:
    """Đọc mọi sheet trong file Excel bằng python-calamine cực nhanh, kết hợp openpyxl để lấy number_format."""
    from python_calamine import CalamineWorkbook

    wb = CalamineWorkbook.from_path(str(path))
    formats_by_sheet = _inspect_xlsx_number_formats(path)
    sheets: list[RawSheet] = []

    for name in wb.sheet_names:
        sheet_data = wb.get_sheet_by_name(name).to_python(skip_empty_area=False)
        rows: list[list[str]] = []
        for r in sheet_data:
            row_strs: list[str] = []
            for cell in r:
                if cell is None:
                    row_strs.append("")
                elif isinstance(cell, bool):
                    row_strs.append(str(cell))
                elif isinstance(cell, float):
                    # Nếu là float tròn số nguyên (ví dụ 1000.0) nhưng có thể là mã hoặc số lượng
                    if cell.is_integer():
                        row_strs.append(str(int(cell)))
                    else:
                        row_strs.append(str(cell))
                else:
                    row_strs.append(str(cell).strip())
            rows.append(row_strs)

        sheets.append(
            RawSheet(
                name=name,
                rows=rows,
                src_file=path.name,
                source_type="xlsx",
                extra={"number_formats": formats_by_sheet.get(name, {})},
            )
        )
    return sheets


def read_sqlite_raw(path: Path) -> list[RawSheet]:
    """Đọc mọi bảng trong SQLite qua URI read-only, chuyển tất cả ô thành chuỗi."""
    sheets: list[RawSheet] = []
    con = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        cursor = con.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cursor.fetchall()]

        for table in tables:
            cursor.execute(f'PRAGMA table_info("{table}")')
            col_names = [r[1] for r in cursor.fetchall()]

            cursor.execute(f'SELECT * FROM "{table}"')
            rows: list[list[str]] = [col_names]  # Dòng 0 là tên cột
            for row in cursor.fetchall():
                rows.append([str(c).strip() if c is not None else "" for c in row])

            sheets.append(
                RawSheet(
                    name=table,
                    rows=rows,
                    src_file=path.name,
                    source_type="sqlite",
                    extra={"is_sqlite_table": True},
                )
            )
    finally:
        con.close()
    return sheets


def read_raw_file(path: Path) -> list[RawSheet]:
    """Dispatch hàm đọc theo định dạng file."""
    suf = path.suffix.lower()
    if suf == ".csv":
        return read_csv_raw(path)
    if suf in (".xlsx", ".xlsm", ".xls"):
        return read_xlsx_raw(path)
    if suf in (".sqlite", ".db", ".sqlite3"):
        return read_sqlite_raw(path)
    raise ValueError(f"Định dạng file không được hỗ trợ: {path}")
