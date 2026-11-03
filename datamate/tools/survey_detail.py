"""Khảo sát chi tiết: phân loại chuỗi tiền/ngày theo (tiền tố, hậu tố, số chữ số mỗi nhóm) và in ví dụ thật.

Chỉ đọc. Chạy:
    PYTHONIOENCODING=utf-8 uv run python -m datamate.tools.survey_values --detail --split data/train/train
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

from datamate.ingest.header import _normalize_text
from datamate.ingest.loader import load_business
from datamate.tools.survey_values import classify


def detail_shape(s: str) -> str:
    """Giữ số chữ số của từng nhóm số + phần chữ trước/sau, để phân biệt 1.250.000 vs 12,5."""
    s = s.strip()
    if not s:
        return "<empty>"
    out = []
    for m in re.finditer(r"\d+|[^\d]+", s):
        tok = m.group(0)
        if tok.isdigit():
            out.append(f"#{len(tok)}")
        else:
            out.append(tok)
    return "".join(out)[:44]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="data/train/train")
    ap.add_argument("--top", type=int, default=22)
    args = ap.parse_args(argv)

    split = Path(args.split)
    buckets: dict[str, collections.Counter[str]] = {
        "money": collections.Counter(),
        "qty": collections.Counter(),
        "date": collections.Counter(),
    }
    examples: dict[str, dict[str, list[str]]] = {"money": {}, "qty": {}, "date": {}}

    for biz_dir in sorted((split / "data").iterdir()):
        if not biz_dir.is_dir():
            continue
        try:
            data = load_business(biz_dir)
        except Exception as e:  # noqa: BLE001
            print(f"{biz_dir.name}: LỖI {type(e).__name__}: {e}", file=sys.stderr)
            continue
        for t in data.tables:
            for col in t.df.columns:
                if col.startswith("_src_"):
                    continue
                kind = classify(_normalize_text(col))
                if kind is None:
                    continue
                for v in t.df[col].tolist()[:3000]:
                    if not v or not str(v).strip():
                        continue
                    v = str(v)
                    sh = detail_shape(v)
                    buckets[kind][sh] += 1
                    ex = examples[kind].setdefault(sh, [])
                    if v not in ex and len(ex) < 3:
                        ex.append(v)

    for kind in ("money", "qty", "date"):
        print(f"\n=== {kind.upper()} ===")
        for sh, cnt in buckets[kind].most_common(args.top):
            print(f"{sh:<30} {cnt:>8}  vd={examples[kind][sh]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
