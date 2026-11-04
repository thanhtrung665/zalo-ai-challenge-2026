"""ColumnProfile: thống kê ngắn từng cột của bảng thô, đưa vào prompt mapping."""

from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel, ConfigDict

from datamate.ingest.dates import parse_vn_date
from datamate.ingest.numbers import parse_vn_number
from datamate.ingest.tables import RawTable

_TIME = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")
_SAMPLE_ROWS = 2000


class ColumnProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    inferred_type: str  # empty | date | time | number | text
    null_rate: float
    n_unique: int
    samples: list[str]
    min: float | None = None
    max: float | None = None


class TableProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    n_rows: int
    source_files: list[str]
    columns: list[ColumnProfile]


def table_key(table: RawTable, all_tables: list[RawTable]) -> str:
    """Khoá bảng ổn định: tên bảng; nếu trùng tên với bảng khác thì thêm `@<file nguồn đầu>`."""
    same = [t for t in all_tables if t.name == table.name]
    if len(same) <= 1:
        return table.name
    first = table.source_files[0] if table.source_files else str(all_tables.index(table))
    return f"{table.name}@{first}"


def _infer(values: list[str]) -> str:
    if not values:
        return "empty"
    n = len(values)
    nums = sum(parse_vn_number(v) is not None for v in values)
    times = sum(bool(_TIME.match(v)) for v in values)
    # ô có dấu / hoặc - kiểu ngày mới xét là ngày; số thuần 5 chữ số (serial) không tính để tránh nhầm với mã
    dates = sum(("/" in v or "-" in v or "thg" in v.lower()) and parse_vn_date(v) is not None for v in values)
    if times / n >= 0.8:
        return "time"
    if dates / n >= 0.8:
        return "date"
    if nums / n >= 0.8:
        return "number"
    return "text"


def profile_table(table: RawTable, key: str, max_samples: int = 5) -> TableProfile:
    cols: list[ColumnProfile] = []
    df = table.df
    head = df.iloc[:: max(1, len(df) // _SAMPLE_ROWS)] if len(df) > _SAMPLE_ROWS else df
    for col in df.columns:
        if col.startswith("_src_"):
            continue
        full = df[col].astype(str).str.strip()
        non_blank = full[full != ""]
        sample_vals = [v for v in head[col].astype(str).str.strip().tolist() if v]
        kind = _infer(sample_vals)
        nums = [parse_vn_number(v) for v in sample_vals] if kind == "number" else []
        nums = [x for x in nums if x is not None]
        top = [v for v, _ in Counter(sample_vals).most_common(max_samples)]
        cols.append(
            ColumnProfile(
                name=col,
                inferred_type=kind,
                null_rate=round(1 - len(non_blank) / len(full), 4) if len(full) else 1.0,
                n_unique=int(non_blank.nunique()),
                samples=top,
                min=float(min(nums)) if nums else None,
                max=float(max(nums)) if nums else None,
            )
        )
    return TableProfile(key=key, n_rows=len(df), source_files=table.source_files, columns=cols)


def profile_tables(tables: list[RawTable]) -> list[TableProfile]:
    return [profile_table(t, table_key(t, tables)) for t in tables]
