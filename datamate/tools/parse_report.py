"""Đo tỉ lệ parse được trên các cột đã nhận diện là ngày / số tiền / số lượng (tiêu chí chấp nhận T05).

Chỉ đọc dữ liệu. Chạy:
    PYTHONIOENCODING=utf-8 uv run python -m datamate.tools.parse_report --split data/train/train
    PYTHONIOENCODING=utf-8 uv run python -m datamate.tools.parse_report --split data/public_test/public_test

Ngưỡng chấp nhận (PLAN T05): tỉ lệ ô không parse được < 0,5% trên cột đã nhận diện;
không có giá trị null nào bị đổi thành 0.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from datamate.ingest.dates import parse_date_column
from datamate.ingest.header import _normalize_text
from datamate.ingest.loader import load_business
from datamate.ingest.numbers import parse_quantity, parse_vn_number

# Cột "ngày" nhưng thực chất là số ngày / hạn mức / ngày sinh cá nhân, không phải mốc nghiệp vụ
_NOT_REALLY_DATE = (
    "so ngay",
    "ngay duoc no",
    "ngay thanh toan",
    "ky han",
    "so thang",
    "han muc",
    "tuoi",
    "ngay sinh",
    "sinh nhat",
)

MONEY_HINTS = (
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
QTY_HINTS = ("so luong", "sl", "qty", "quantity")
DATE_HINTS = ("ngay", "date", "thoi gian", "created", "han dung", "hsd", "ngay sinh", "sinh nhat")


def classify_column(col: str, sample: list[str]) -> str | None:
    cn = _normalize_text(col)
    if any(w in cn for w in _NOT_REALLY_DATE):
        return None
    if any(w in cn for w in MONEY_HINTS):
        return "money"
    if any(w in cn for w in QTY_HINTS):
        return "qty"
    if any(w in cn for w in DATE_HINTS):
        # Cột tên chứa "ngay"/"date" nhưng toàn ô chữ dài (ghi chú) thì bỏ
        if sample:
            numeric_like = sum(1 for s in sample if any(ch.isdigit() for ch in s))
            if numeric_like == 0:
                return None
        return "date"
    return None


@dataclass
class ColStats:
    total: int = 0
    blank: int = 0
    ok: int = 0
    failed: list[str] = field(default_factory=list)

    @property
    def non_blank(self) -> int:
        return self.total - self.blank

    @property
    def fail_rate(self) -> float:
        return len(self.failed) / self.non_blank if self.non_blank else 0.0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="data/train/train")
    ap.add_argument("--out", default="runs/parse_report.json")
    ap.add_argument("--max-fail-examples", type=int, default=6)
    args = ap.parse_args(argv)

    split = Path(args.split)
    per_col: dict[str, ColStats] = {}
    totals: Counter[str] = Counter()
    shop_errors: list[str] = []
    zero_from_null = 0

    for biz_dir in sorted((split / "data").iterdir()):
        if not biz_dir.is_dir():
            continue
        try:
            data = load_business(biz_dir)
        except Exception as e:  # noqa: BLE001 - báo cáo, không làm hỏng lượt đo
            shop_errors.append(f"{biz_dir.name}: {type(e).__name__}: {e}")
            continue
        for t in data.tables:
            for col in t.df.columns:
                if col.startswith("_src_"):
                    continue
                values = [str(v).strip() for v in t.df[col].tolist()]
                sample = [v for v in values if v][:50]
                kind = classify_column(col, sample)
                if kind is None:
                    continue
                stats = per_col.setdefault(f"{kind}:{col}", ColStats())
                parsed_col: list[object] = (
                    parse_date_column(values, sheet_years=t.sheet_years()) if kind == "date" else [None] * len(values)
                )
                for i, v in enumerate(values):
                    stats.total += 1
                    if not v:
                        stats.blank += 1
                        continue
                    if kind == "money":
                        parsed = parse_vn_number(v)
                    elif kind == "qty":
                        parsed, _ = parse_quantity(v)
                    else:
                        parsed = parsed_col[i]
                    if parsed is None:
                        if len(stats.failed) < 200:
                            stats.failed.append(v)
                    else:
                        stats.ok += 1
                        if parsed == 0 and v not in ("0", "0.0", "0,0", "0đ"):
                            zero_from_null += 1
                totals[kind] += stats.non_blank

    report = {
        "split": str(split),
        "shop_errors": shop_errors,
        "zero_created_from_nonzero_text": zero_from_null,
        "columns": {},
    }
    bad_cols: list[tuple[str, float, int]] = []
    for key, st in sorted(per_col.items()):
        report["columns"][key] = {
            "total": st.total,
            "blank": st.blank,
            "ok": st.ok,
            "fail": len(st.failed),
            "fail_rate": round(st.fail_rate, 6),
            "examples": st.failed[: args.max_fail_examples],
        }
        if st.fail_rate > 0.005 and len(st.failed) >= 5:
            bad_cols.append((key, st.fail_rate, len(st.failed)))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"Split: {split}  |  lỗi đọc shop: {len(shop_errors)}")
    for e in shop_errors:
        print(f"  LỖI {e}")
    print(f"Ô đã parse: {dict(totals)}")
    print(f"Null bị đổi thành 0: {zero_from_null}")
    print(f"Cột vượt ngưỡng 0,5% không parse được: {len(bad_cols)}")
    for key, rate, n in sorted(bad_cols, key=lambda x: -x[1])[:20]:
        ex = report["columns"][key]["examples"]
        print(f"  {key}: {rate:.2%} ({n} ô) vd={ex[:4]}")
    print(f"→ {out}")
    return 1 if (bad_cols or shop_errors or zero_from_null) else 0


if __name__ == "__main__":
    raise SystemExit(main())
