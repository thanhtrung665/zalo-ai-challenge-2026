"""Kiểm chứng các dạng tiền đặc biệt (k, tr, 9tr9) bằng cách đối chiếu chéo trong cùng dòng.

Với mỗi dòng có cột tiền dạng đặc biệt, so với (số lượng × đơn giá) hoặc cột thành tiền khác
để biết "9tr9" nghĩa là 9,9 triệu hay 9.900.000.
"""

from __future__ import annotations

import argparse
import collections
import re
from pathlib import Path

import pandas as pd

from datamate.ingest.header import _normalize_text
from datamate.ingest.loader import load_business

MONEY_HINT = ("thanh tien", "tong tien", "tien hang", "doanh thu", "amount", "total")
PRICE_HINT = ("don gia", "gia ban", "gia nhap", "price")
QTY_HINT = ("so luong", "sl", "qty", "quantity")

SPECIAL = re.compile(r"^\s*(-?\d+)\s*(k|tr)(\d*)\s*$", re.IGNORECASE)
SHORT_TR = re.compile(r"^\s*(-?\d+)\s*tr\s*(\d+)\s*$", re.IGNORECASE)


def pick_cols(t: pd.DataFrame) -> tuple[str | None, str | None, str | None]:
    amount = price = qty = None
    for c in t.columns:
        if c.startswith("_src_"):
            continue
        cn = _normalize_text(c)
        if amount is None and any(w in cn for w in MONEY_HINT):
            amount = c
        elif price is None and any(w in cn for w in PRICE_HINT):
            price = c
        elif qty is None and any(w in cn for w in QTY_HINT):
            qty = c
    return amount, price, qty


def plain_number(s: str) -> float | None:
    s = str(s).strip().replace("đ", "").replace(" ", "")
    if not s:
        return None
    try:
        if re.fullmatch(r"-?\d+", s):
            return float(s)
        if re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):  # 1.250.000
            return float(s.replace(".", ""))
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+", s):  # 1,250,000
            return float(s.replace(",", ""))
        if re.fullmatch(r"-?\d+[.,]\d+", s):  # 12,5 / 12.5
            return float(re.sub(r",", ".", s))
    except ValueError:
        return None
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="data/train/train")
    ap.add_argument("--limit", type=int, default=8)
    args = ap.parse_args(argv)

    hits = collections.Counter()
    shown: dict[str, list[tuple[str, str, str, str]]] = collections.defaultdict(list)

    for biz_dir in sorted((Path(args.split) / "data").iterdir()):
        if not biz_dir.is_dir():
            continue
        try:
            data = load_business(biz_dir)
        except Exception:  # noqa: BLE001,S110
            continue
        for t in data.tables:
            amount, price, qty = pick_cols(t.df)
            for col in t.df.columns:
                if col.startswith("_src_"):
                    continue
                cn = _normalize_text(col)
                if not any(w in cn for w in MONEY_HINT + PRICE_HINT):
                    continue
                for _, row in t.df[[c for c in (col, amount, price, qty) if c]].head(4000).iterrows():
                    s = str(row[col]).strip()
                    m = SPECIAL.match(s)
                    if not m:
                        continue
                    kind = m.group(2).lower() + ("_tail" if m.group(3) else "")
                    hits[kind] += 1
                    if len(shown[kind]) < args.limit:
                        ctx = {k: str(row[k]) for k in (amount, price, qty) if k and k != col}
                        other = plain_number(str(row[amount])) if amount and amount != col else None
                        est = None
                        if price and qty and amount and amount != col:
                            pv, qv = plain_number(str(row[price])), plain_number(str(row[qty]))
                            if pv is not None and qv is not None:
                                est = pv * qv
                        shown[kind].append((str(biz_dir.name), col, s, f"ctx={ctx} amount={other} price*qty={est}"))

    for kind, cnt in hits.most_common():
        print(f"\n=== {kind}: {cnt} ô ===")
        for biz, col, s, ctx in shown[kind]:
            print(f"  {biz} | {col} = {s!r} | {ctx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
