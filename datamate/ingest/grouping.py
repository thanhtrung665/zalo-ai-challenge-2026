"""Làm sạch bảng ghi theo đơn: fill-down cột cấp đơn và dedupe dòng trùng trong cùng đơn.

Rulebook §8:
- "Ô để trống ở các dòng sau của cùng một nhóm dòng = giống ô đó ở dòng đầu nhóm".
- "Hai dòng của **cùng một đơn** giống nhau ở mọi ô = lỗi xuất file, tính một lần.
  Hai dòng giống nhau của hai đơn khác nhau là hai lần bán, tính cả hai."
- "Bảng không ghi theo đơn: mỗi dòng là một lần ghi; hai dòng giống nhau trong cùng file vẫn tính cả hai."

Thứ tự: dedupe trên ô **gốc** trước, rồi mới fill-down (fill trước sẽ biến các dòng vốn
khác nhau ở ô trống thành giống nhau và xoá nhầm).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from datamate.ingest.header import _normalize_text

_ORDER_ID_HINTS = (
    "ma don",
    "ma hd",
    "ma hoa don",
    "so hd",
    "so hoa don",
    "ma chung tu",
    "so chung tu",
    "so phieu",
    "ma phieu",
    "order id",
    "order",
    "ma ct",
    "invoice",
    "receipt",
    "so ct",
)

_NOT_ORDER_ID = ("ngay", "date", "ten", "khach", "hang", "san pham", "sp", "thoi gian", "trang thai")


@dataclass
class CleanResult:
    """Kết quả làm sạch một bảng ghi theo đơn."""

    df: pd.DataFrame
    order_col: str | None
    filled_cells: int
    dropped_duplicates: int

    @property
    def num_rows(self) -> int:
        return len(self.df)


def _data_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if not c.startswith("_src_")]


def detect_order_id_column(df: pd.DataFrame, *, min_repeat_ratio: float = 0.05) -> str | None:
    """Nhận diện cột mã đơn: tên khớp từ vựng **và** giá trị lặp lại đủ nhiều.

    Không có mã đơn (sổ thu chi, nhật ký) → `None` để bảng được giữ nguyên.
    """
    best: str | None = None
    best_score = 0.0
    n = len(df)
    if n == 0:
        return None

    for col in _data_columns(df):
        cn = _normalize_text(col)
        name_match = any(h in cn for h in _ORDER_ID_HINTS)
        # Loại cột tên/ngày/khách... theo TỪ nguyên vẹn, không theo chuỗi con ("ma don hang" chứa "hang")
        if not name_match and any(f" {bad} " in f" {cn} " for bad in _NOT_ORDER_ID):
            continue
        values = df[col].astype(str).str.strip()
        non_blank = values[values != ""]
        if non_blank.empty:
            continue
        repeat_ratio = 1.0 - (non_blank.nunique() / len(non_blank))
        blank_ratio = 1.0 - (len(non_blank) / n)

        # Mã đơn thật: tên khớp, có lặp lại (nhiều dòng/đơn) hoặc có ô trống nối tiếp
        if name_match and (repeat_ratio >= min_repeat_ratio or blank_ratio > 0):
            score = 2.0 + repeat_ratio + blank_ratio
            if score > best_score:
                best_score = score
                best = col
        # Tên không khớp nhưng lặp mạnh và giá trị ngắn, ít khoảng trắng: nghi mã đơn
        elif not name_match and repeat_ratio >= 0.5 and non_blank.str.len().max() <= 30:
            score = repeat_ratio
            if score > best_score:
                best_score = score
                best = col

    return best


def clean_order_table(df: pd.DataFrame) -> CleanResult:
    """Dedupe dòng trùng trong cùng đơn rồi fill-down các cột cấp đơn. Không sửa `df` gốc."""
    out = df.copy(deep=True)
    order_col = detect_order_id_column(out)
    if order_col is None:
        return CleanResult(df=out, order_col=None, filled_cells=0, dropped_duplicates=0)

    data_cols = _data_columns(out)

    # 1. Dedupe: hai dòng giống hệt mọi ô dữ liệu trong CÙNG một đơn
    before = len(out)
    out["__group_id"] = out[order_col].astype(str).str.strip().replace("", pd.NA).ffill().fillna("__no_order__")
    out = out.drop_duplicates(subset=["__group_id", *data_cols], keep="first")
    dropped = before - len(out)

    # 2. Fill-down cột cấp đơn: cột mà trong một đơn có ĐÚNG MỘT giá trị khác rỗng
    filled = 0
    order_series = out["__group_id"]
    for col in data_cols:
        vals = out[col].astype(str).str.strip()
        non_blank = vals != ""
        if not non_blank.any():
            continue
        n_distinct_per_order = vals[non_blank].groupby(order_series[non_blank]).nunique()
        if n_distinct_per_order.empty or (n_distinct_per_order > 1).any():
            # Cột có nhiều giá trị khác nhau trong một đơn → cột cấp dòng, không fill
            continue
        first_val = vals[non_blank].groupby(order_series[non_blank]).first()
        missing = ~non_blank
        if missing.any():
            to_fill = order_series[missing].map(first_val)
            mask = to_fill.notna()
            if mask.any():
                out.loc[mask[mask].index, col] = to_fill[mask]
                filled += int(mask.sum())

    out = out.drop(columns="__group_id")
    return CleanResult(df=out, order_col=order_col, filled_cells=filled, dropped_duplicates=dropped)
