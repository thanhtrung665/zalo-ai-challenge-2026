"""Dev: build CanonicalStore từ mapping viết tay (research/mappings/<biz>.json) rồi chạy validator.

Dùng để kiểm build/validate trên dữ liệu thật và làm đáp án chuẩn đo độ đúng của LLM mapping (T10).
Không thuộc runtime; được phép nhắc tên shop.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from datamate.ingest.loader import load_business
from datamate.schema.build import build_store
from datamate.schema.mapping import ShopMapping
from datamate.schema.validate import validate_store


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True)
    ap.add_argument("--mappings", default=str(Path(__file__).parent / "mappings"))
    ap.add_argument("biz", nargs="*", help="mặc định: mọi mapping có trong thư mục")
    args = ap.parse_args(argv)
    ids = args.biz or sorted(p.stem for p in Path(args.mappings).glob("*.json"))
    bad = 0
    for biz in ids:
        mapping = ShopMapping.model_validate_json((Path(args.mappings) / f"{biz}.json").read_text(encoding="utf-8"))
        store = build_store(load_business(Path(args.split) / "data" / biz), mapping)
        issues = validate_store(store)
        t = store.tables
        print(
            f"== {biz}: orders={len(t['orders'])} lines={len(t['order_lines'])} products={len(t['products'])} "
            f"conv={len(t['unit_conversions'])} pay={len(t['payments'])} purchases={len(t['purchases'])} "
            f"junk={store.dropped_junk_rows}"
        )
        print(f"   caps: { {k: v for k, v in store.capabilities.model_dump().items() if v is True} }")
        print(f"   ranges: {store.capabilities.date_ranges}")
        for i in issues:
            print(f"   [{i.severity}] {i.code} {i.table}: {i.message} ({i.count})")
        bad += sum(i.severity == "error" for i in issues)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
