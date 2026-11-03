"""Khảo sát riêng các ô số lượng/số có dấu phân cách để chốt quy tắc parse (T05)."""

from __future__ import annotations

import argparse
import collections
import re
from pathlib import Path

from datamate.ingest.header import _normalize_text
from datamate.ingest.loader import load_business
from datamate.tools.survey_values import classify

SEP = re.compile(r"[.,]")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="data/train/train")
    args = ap.parse_args(argv)

    qty_sep = collections.Counter()
    qty_examples: dict[str, list[str]] = {}
    date_odd = collections.Counter()
    date_examples: dict[str, list[str]] = {}

    for biz_dir in sorted((Path(args.split) / "data").iterdir()):
        if not biz_dir.is_dir():
            continue
        try:
            data = load_business(biz_dir)
        except Exception:  # noqa: BLE001,S110
            continue
        for t in data.tables:
            for col in t.df.columns:
                if col.startswith("_src_"):
                    continue
                cn = _normalize_text(col)
                kind = classify(cn)
                if kind == "qty":
                    for v in t.df[col].tolist()[:3000]:
                        s = str(v).strip() if v else ""
                        if s and SEP.search(s):
                            qty_sep[s] += 1
                            qty_examples.setdefault(s, [])
                elif kind == "date":
                    for v in t.df[col].tolist()[:2000]:
                        s = str(v).strip() if v else ""
                        if not s:
                            continue
                        # bỏ qua cột đếm ngày (số ngày được nợ...)
                        if "ngay duoc no" in cn or "so ngay" in cn:
                            continue
                        if re.fullmatch(r"\d{1,4}", s):
                            date_odd[s] += 1
                            date_examples.setdefault(s, [])

    print("=== QTY có dấu phân cách (top 40 giá trị thật) ===")
    for s, c in qty_sep.most_common(40):
        print(f"  {s!r:<24} {c}")
    print("\n=== DATE là số thuần 1-4 chữ số (nghi cột đếm, không phải ngày) ===")
    for s, c in date_odd.most_common(15):
        print(f"  {s!r:<10} {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
