"""Kiểm kê một split DataMate (PLAN T01): shop, file, sheet/bảng, số dòng, vài dòng đầu, mốc dữ liệu trong README,
phân bố kiểu đáp án và hình dạng `alias` (nếu có answers.jsonl).

Cần extra `data` (python-calamine). Dùng:
    uv run python -m datamate.tools.inventory --split data/train --out runs/inventory/train.md
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_CUTOFF = re.compile(r"Dữ liệu có đến hết (\d{1,2}/\d{1,2}/\d{4})")
_CONV = re.compile(r"1 [^=\n]+ = \d+")


def _read_csv_rows(path: Path, limit: int | None = None) -> tuple[list[list[str]], str]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1258"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover
        enc, text = "latin-1", raw.decode("latin-1")
    rows = list(csv.reader(io.StringIO(text)))
    return (rows[:limit] if limit else rows), enc


def table_summaries(path: Path, head: int = 5) -> list[dict[str, Any]]:
    """Mỗi phần tử: tên sheet/bảng, số dòng vật lý, số cột, `head` dòng đầu (chuỗi đã cắt)."""
    cut = lambda r: [str(c)[:30] for c in r[:14]]  # noqa: E731
    out: list[dict[str, Any]] = []
    if path.suffix.lower() == ".csv":
        rows, enc = _read_csv_rows(path)
        out.append(
            {
                "table": "-",
                "rows": len(rows),
                "cols": max((len(r) for r in rows), default=0),
                "encoding": enc,
                "head": [cut(r) for r in rows[:head]],
            }
        )
    elif path.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        from python_calamine import CalamineWorkbook

        wb = CalamineWorkbook.from_path(str(path))
        for name in wb.sheet_names:
            rows = wb.get_sheet_by_name(name).to_python(skip_empty_area=False)
            out.append(
                {
                    "table": name,
                    "rows": len(rows),
                    "cols": max((len(r) for r in rows), default=0),
                    "head": [cut(r) for r in rows[:head]],
                }
            )
    elif path.suffix.lower() in (".sqlite", ".db", ".sqlite3"):
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            for (t,) in con.execute("select name from sqlite_master where type='table' order by name"):
                n = con.execute(f'select count(*) from "{t}"').fetchone()[0]
                cols = [r[1] for r in con.execute(f'pragma table_info("{t}")')]
                rows = [list(r) for r in con.execute(f'select * from "{t}" limit {head - 1}')]
                out.append({"table": t, "rows": n, "cols": len(cols), "head": [cut(cols)] + [cut(r) for r in rows]})
        finally:
            con.close()
    return out


def readme_facts(text: str) -> dict[str, Any]:
    m = _CUTOFF.search(text)
    return {
        "chars": len(text),
        "cutoff": m.group(1) if m else None,
        "unit_conversions_in_text": len(_CONV.findall(text)),
        "column_sections": len(re.findall(r"^## Cột trong", text, flags=re.M)),
    }


def answer_stats(path: Path) -> dict[str, Any]:
    types: Counter = Counter()
    alias_shapes: Counter = Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        a = json.loads(line)
        types[a["type"]] += 1
        al = a.get("alias") or []
        shape = (
            "empty"
            if not al
            else "flat"
            if all(isinstance(x, str) for x in al)
            else "per_position"
            if all(isinstance(x, list) for x in al)
            else "mixed"
        )
        alias_shapes[f"{a['type']}:{shape}"] += 1
    return {"types": dict(types.most_common()), "alias_shapes": dict(sorted(alias_shapes.items()))}


def inventory(split: Path) -> dict[str, Any]:
    shops: dict[str, Any] = {}
    for biz in sorted((split / "data").iterdir()):
        if not biz.is_dir():
            continue
        readme = biz / "README.md"
        entry: dict[str, Any] = {
            "readme": readme_facts(readme.read_text(encoding="utf-8")) if readme.exists() else {},
            "files": [],
        }
        for f in sorted(biz.iterdir()):
            if f.name == "README.md":
                continue
            fe: dict[str, Any] = {"name": f.name, "bytes": f.stat().st_size}
            try:
                fe["tables"] = table_summaries(f)
            except Exception as e:  # kiểm kê không được dừng vì một file lỗi
                fe["error"] = repr(e)
            entry["files"].append(fe)
        shops[biz.name] = entry
    res: dict[str, Any] = {"split": str(split), "shops": shops}
    qp = split / "questions.jsonl"
    if qp.exists():
        res["questions_per_shop"] = dict(
            sorted(
                Counter(
                    json.loads(ln)["business_id"] for ln in qp.read_text(encoding="utf-8").splitlines() if ln.strip()
                ).items()
            )
        )
    ap = split / "answers.jsonl"
    if ap.exists():
        res["answers"] = answer_stats(ap)
    return res


def to_markdown(inv: dict[str, Any]) -> str:
    L = [f"# Kiểm kê `{inv['split']}`", ""]
    L += [
        "| Shop | Câu hỏi | File | Bảng/sheet | Dòng vật lý | Đuôi | Mốc README | Quy đổi trong README | Lỗi |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    qps = inv.get("questions_per_shop", {})
    for b, e in inv["shops"].items():
        tabs = [t for f in e["files"] for t in f.get("tables", [])]
        exts = sorted({Path(f["name"]).suffix for f in e["files"]})
        errs = [f["name"] for f in e["files"] if "error" in f]
        rd = e["readme"]
        L.append(
            f"| {b} | {qps.get(b, '')} | {len(e['files'])} | {len(tabs)} | {sum(t['rows'] for t in tabs):,} | "
            f"{' '.join(exts)} | {rd.get('cutoff')} | {rd.get('unit_conversions_in_text')} | {', '.join(errs)} |"
        )
    if "answers" in inv:
        L += [
            "",
            "## Đáp án",
            "",
            f"Kiểu: {inv['answers']['types']}",
            "",
            f"Hình dạng alias: {inv['answers']['alias_shapes']}",
        ]
    L += ["", "## Dòng đầu từng bảng", ""]
    for b, e in inv["shops"].items():
        L.append(f"### {b}")
        for f in e["files"]:
            for t in f.get("tables", []):
                L.append(f"- `{f['name']}` :: `{t['table']}` — {t['rows']:,} dòng × {t['cols']} cột")
                for r in t["head"][:4]:
                    L.append("    - " + " · ".join(r))
        L.append("")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kiểm kê split DataMate")
    ap.add_argument("--split", default="data/train")
    ap.add_argument("--out", default="runs/inventory/train.md")
    args = ap.parse_args(argv)
    inv = inventory(Path(args.split))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_markdown(inv), encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")
    n_err = sum("error" in f for e in inv["shops"].values() for f in e["files"])
    print(f"{len(inv['shops'])} shop, lỗi đọc: {n_err} → {out}")
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
