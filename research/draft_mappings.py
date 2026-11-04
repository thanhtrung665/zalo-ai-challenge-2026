"""Dev: sinh bản nháp mapping bằng bộ đề xuất heuristic cho mọi shop trong một split, ghi vào research/mappings/.

Chỉ dùng với split train (có đáp án để đối chiếu). Bản nháp phải được người xem lại và sửa tay
trước khi coi là mapping chuẩn.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from datamate.ingest.loader import load_business
from datamate.schema.propose import propose_mapping


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True)
    ap.add_argument("--out", default=str(Path(__file__).parent / "mappings"))
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("biz", nargs="*")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ids = args.biz or sorted(p.name for p in (Path(args.split) / "data").iterdir() if p.is_dir())
    for biz in ids:
        dest = out / f"{biz}.json"
        if dest.exists() and not args.overwrite:
            print(f"bỏ qua {biz} (đã có)")
            continue
        mapping, _ = propose_mapping(load_business(Path(args.split) / "data" / biz))
        dest.write_text(mapping.model_dump_json(indent=1), encoding="utf-8")
        print(f"ghi {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
