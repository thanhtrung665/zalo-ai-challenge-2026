"""Khảo sát dạng giá trị thật theo nhóm cột (tiền / số lượng / ngày) để thiết kế parser T05.

Chỉ đọc, không sửa dữ liệu. Chạy:
    PYTHONIOENCODING=utf-8 uv run python -m datamate.tools.survey_values --split data/train/train
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

from datamate.ingest.header import _normalize_text
from datamate.ingest.loader import load_business

MONEY_WORDS = (
    "thanh tien",
    "tong tien",
    "tien hang",
    "don gia",
    "gia ban",
    "gia nhap",
    "doanh thu",
    "amount",
    "total",
    "price",
)
QTY_WORDS = ("so luong", "sl", "qty", "quantity")
DATE_WORDS = ("ngay", "date", "thoi gian", "created", "han dung", "hsd")


def classify(col_norm: str) -> str | None:
    for w in MONEY_WORDS:
        if w in col_norm:
            return "money"
    for w in QTY_WORDS:
        if w in col_norm:
            return "qty"
    for w in DATE_WORDS:
        if w in col_norm:
            return "date"
    return None


def shape(s: str) -> str:
    """Trừu tượng hoá một giá trị thành 'hình dạng' để đếm biến thể."""
    s = s.strip()
    if not s:
        return "<empty>"
    s = re.sub(r"[0-9]", "9", s)
    s = re.sub(r"9+", "9", s)
    return s[:40]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="data/train/train")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args(argv)

    split = Path(args.split)
    shapes: dict[str, collections.Counter[str]] = {
        "money": collections.Counter(),
        "qty": collections.Counter(),
        "date": collections.Counter(),
    }
    samples: dict[str, list[str]] = {"money": [], "qty": [], "date": []}
    col_names: dict[str, collections.Counter[str]] = {
        "money": collections.Counter(),
        "qty": collections.Counter(),
        "date": collections.Counter(),
    }

    for biz_dir in sorted((split / "data").iterdir()):
        if not biz_dir.is_dir():
            continue
        try:
            data = load_business(biz_dir)
        except Exception as e:  # noqa: BLE001 - báo cáo, không làm hỏng lượt khảo sát
            print(f"{biz_dir.name}: LỖI {type(e).__name__}: {e}", file=sys.stderr)
            continue
        for t in data.tables:
            for col in t.df.columns:
                if col.startswith("_src_"):
                    continue
                kind = classify(_normalize_text(col))
                if kind is None:
                    continue
                col_names[kind][col] += 1
                values = [v for v in t.df[col].tolist() if v and str(v).strip()]
                for v in values[:4000]:
                    shapes[kind][shape(str(v))] += 1
                    if len(samples[kind]) < 60 and len(samples[kind]) < shapes[kind].total() // 50 + 1:
                        samples[kind].append(str(v))

    for kind in ("money", "qty", "date"):
        print(f"\n=== {kind.upper()} ===")
        print("Tên cột gặp nhiều nhất:", ", ".join(f"{n}({c})" for n, c in col_names[kind].most_common(10)))
        print(f"{'hình dạng':<34} {'số ô':>8}")
        for sh, cnt in shapes[kind].most_common(args.top):
            print(f"{sh:<34} {cnt:>8}")
        print("ví dụ thật:", samples[kind][:14])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
