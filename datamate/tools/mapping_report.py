"""Xuất báo cáo review mapping từng shop: `runs/mapping/<shop>.md`.

Gồm vai trò bảng, cột đã map kèm ví dụ, bảng trạng thái, kết quả build và lỗi.

uv run python -m datamate.tools.mapping_report --split data/train --mappings research/mappings --out runs/mapping
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from datamate.ingest.loader import load_business
from datamate.schema.build import build_store
from datamate.schema.mapping import ShopMapping
from datamate.schema.profile import table_key
from datamate.schema.validate import validate_store


def render(biz_dir: Path, mapping: ShopMapping) -> str:
    biz = load_business(biz_dir)
    store = build_store(biz, mapping)
    issues = validate_store(store)
    raw = {table_key(t, biz.tables): t for t in biz.tables}
    mapped = {tm.source for tm in mapping.tables}
    out = [f"# Mapping {biz.biz_id}", ""]
    out.append("## Bảng nguồn")
    for key, t in raw.items():
        out.append(f"- `{key}` ({len(t.df)} dòng): " + ("**đã map**" if key in mapped else "bỏ qua"))
    out += ["", "## Cột đã map"]
    for tm in mapping.tables:
        df = raw[tm.source].df
        out.append(f"### `{tm.source}`")
        for target, cols in tm.targets.items():
            for canon, src in cols.items():
                ex = " | ".join(df[src].astype(str).str.strip().replace("", "∅").head(3).tolist())
                out.append(f"- `{target}.{canon}` ← `{src}`   (vd: {ex})")
    out += ["", "## Trạng thái (giá trị gốc → chuẩn, số đơn)"]
    o = store["orders"]
    if "status_raw" in o:
        for (raw_v, st), n in o.groupby(["status_raw", "status"], dropna=False).size().items():
            out.append(f"- `{raw_v}` → **{st}** ({n})")
    out += ["", "## Kết quả build"]
    t = store.tables
    out.append(" · ".join(f"{k}={len(v)}" for k, v in t.items() if len(v)))
    out.append(f"- dòng rác đã bỏ: {store.dropped_junk_rows}")
    out += [f"- {m}" for m in store.info]
    out.append(f"- khả năng: {[k for k, v in store.capabilities.model_dump().items() if v is True]}")
    out.append(f"- khoảng ngày: {store.capabilities.date_ranges}")
    out += ["", "## Lỗi / cảnh báo"]
    out += [f"- [{i.severity}] `{i.code}` {i.table}: {i.message} ({i.count})" for i in issues] or ["- không có"]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True)
    ap.add_argument("--mappings", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("biz", nargs="*")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ids = args.biz or sorted(p.stem for p in Path(args.mappings).glob("*.json"))
    for biz in ids:
        m = ShopMapping.model_validate_json((Path(args.mappings) / f"{biz}.json").read_text(encoding="utf-8"))
        (out / f"{biz}.md").write_text(render(Path(args.split) / "data" / biz, m), encoding="utf-8")
        print(f"→ {out / f'{biz}.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
