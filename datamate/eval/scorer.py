"""Scorer theo luật chấm chính thức của DataMate (SPEC §3).

- Mỗi câu: đúng +1, abstain/thiếu 0, sai -1. PA = tổng / N (N = số câu trong gold sau khi lọc ids).
- Đúng chỉ khi type trùng type tham chiếu và giá trị khớp theo luật của type.
- Trả lời bất kỳ cho câu unanswerable là sai; trả unanswerable đúng khi và chỉ khi tham chiếu là unanswerable.

Hình dạng `alias` đã xác nhận trên answers.jsonl train (T02, docs/DECISIONS.md D-003):
- string: list phẳng các cách viết khác + mã, vd. ["SP0076", "Costar Omega 3 1000 mg lọ 100 viên"].
- list tên: list-các-list theo từng vị trí, vd. [["SP0001"], ["SP0027", "Ong PVC Binh Minh D32 cay 4m"]]; list số: [].
- table: list-các-list theo từng hàng, áp cho ô tên của hàng đó, vd. [["KH0124"], ["KH0056", "Luu Ha An"]].
- number/percent/date/boolean/unanswerable: []. Unanswerable có "answer": null.

Các điểm BTC chưa nói rõ:
- Dòng nộp trùng id: lấy dòng đầu tiên (validator coi trùng id là lỗi).
- Dòng hỏng JSON, hoặc có `reason` không phải chuỗi: coi như không có dòng (abstain), theo rulebook §7.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

VALUE_TYPES = ("number", "percent", "string", "date", "boolean", "list", "table")
ALL_TYPES = (*VALUE_TYPES, "unanswerable", "abstain")
NUM_TOL = 1e-6

_NON_WORD = re.compile(r"[^\w\s]|_", flags=re.UNICODE)
_WS = re.compile(r"\s+", flags=re.UNICODE)


# ---------------------------------------------------------------- chuẩn hoá và so khớp từng kiểu


def normalize_str(s: str) -> str:
    """NFC → chữ thường → ký tự không phải chữ/số/khoảng trắng thành khoảng trắng → gộp khoảng trắng.

    Giữ dấu tiếng Việt.
    """
    s = unicodedata.normalize("NFC", s).lower()
    s = _NON_WORD.sub(" ", s)
    return _WS.sub(" ", s).strip()


def is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _round2(x: float | int) -> Decimal:
    try:
        return Decimal(repr(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:  # pragma: no cover - chỉ khi x không hữu hạn, đã chặn bởi is_number
        return Decimal("NaN")


def match_number(ans: Any, ref: Any) -> bool:
    return is_number(ans) and is_number(ref) and abs(float(ans) - float(ref)) <= NUM_TOL


def match_percent(ans: Any, ref: Any) -> bool:
    return is_number(ans) and is_number(ref) and _round2(ans) == _round2(ref)


def match_string(ans: Any, ref: Any, aliases: list[Any] | None = None) -> bool:
    if not isinstance(ans, str) or not isinstance(ref, str):
        return False
    accepted = {normalize_str(ref)}
    for a in aliases or []:
        if isinstance(a, str):
            accepted.add(normalize_str(a))
    return normalize_str(ans) in accepted


def match_date(ans: Any, ref: Any) -> bool:
    return isinstance(ans, str) and isinstance(ref, str) and ans.strip() == ref.strip()


def match_boolean(ans: Any, ref: Any) -> bool:
    return isinstance(ans, bool) and isinstance(ref, bool) and ans is ref


def match_scalar(ans: Any, ref: Any, aliases: list[Any] | None = None) -> bool:
    """Phần tử của list/ô của table: số theo luật number, chuỗi theo luật string."""
    if is_number(ref):
        return match_number(ans, ref)
    if isinstance(ref, str):
        return match_string(ans, ref, aliases)
    if isinstance(ref, bool):
        return match_boolean(ans, ref)
    return ans == ref


def _position_aliases(ref: list[Any], aliases: Any) -> list[list[Any]]:
    n = len(ref)
    if isinstance(aliases, list) and len(aliases) == n and all(isinstance(a, list) for a in aliases):
        return [list(a) for a in aliases]
    if n == 1 and isinstance(aliases, list) and all(isinstance(a, str) for a in aliases):
        return [list(aliases)]
    return [[] for _ in range(n)]


def match_list(ans: Any, ref: Any, aliases: Any = None) -> bool:
    if not isinstance(ans, list) or not isinstance(ref, list) or len(ans) != len(ref):
        return False
    per_pos = _position_aliases(ref, aliases)
    return all(match_scalar(a, r, al) for a, r, al in zip(ans, ref, per_pos, strict=True))


def _table_parts(t: Any) -> tuple[list[str], list[list[Any]]] | None:
    if not isinstance(t, dict):
        return None
    cols, rows = t.get("columns"), t.get("rows")
    if not isinstance(cols, list) or not isinstance(rows, list):
        return None
    if not all(isinstance(c, str) for c in cols) or not all(isinstance(r, list) and len(r) == len(cols) for r in rows):
        return None
    return cols, rows


def _bipartite_match(n: int, ok: list[list[bool]]) -> bool:
    """Ghép hoàn hảo n hàng tham chiếu với n hàng trả lời (Kuhn)."""
    match_of_ans = [-1] * n

    def try_assign(i: int, seen: list[bool]) -> bool:
        for j in range(n):
            if ok[i][j] and not seen[j]:
                seen[j] = True
                if match_of_ans[j] == -1 or try_assign(match_of_ans[j], seen):
                    match_of_ans[j] = i
                    return True
        return False

    return all(try_assign(i, [False] * n) for i in range(n))


def match_table(ans: Any, ref: Any, aliases: Any = None) -> bool:
    """Cột theo tên (không khớp thì theo vị trí); hàng so như tập hợp.

    `aliases` (đã xác nhận trên answers.jsonl train): list cùng độ dài với `rows`, mỗi phần tử là danh sách
    cách viết khác/mã của **ô tên** trong hàng đó → áp cho mọi ô chuỗi của hàng tham chiếu tương ứng.
    """
    pa, pr = _table_parts(ans), _table_parts(ref)
    if pa is None or pr is None:
        return False
    a_cols, a_rows = pa
    r_cols, r_rows = pr
    if len(a_cols) != len(r_cols) or len(a_rows) != len(r_rows):
        return False
    na, nr = [normalize_str(c) for c in a_cols], [normalize_str(c) for c in r_cols]
    if sorted(na) == sorted(nr) and len(set(nr)) == len(nr):
        order = [na.index(c) for c in nr]  # cột theo tên
    else:
        order = list(range(len(r_cols)))  # tên không khớp → theo vị trí
    a_rows = [[row[k] for k in order] for row in a_rows]
    n = len(r_rows)
    row_aliases = _position_aliases(r_rows, aliases)
    ok = [
        [all(match_scalar(a, r, row_aliases[i]) for a, r in zip(a_rows[j], r_rows[i], strict=True)) for j in range(n)]
        for i in range(n)
    ]
    return _bipartite_match(n, ok)


# ---------------------------------------------------------------- chấm từng câu


@dataclass(frozen=True)
class Gold:
    id: str
    type: str
    answer: Any
    alias: Any = None

    @property
    def is_unanswerable(self) -> bool:
        return self.type == "unanswerable"


def score_one(pred: dict[str, Any] | None, gold: Gold) -> int:
    """+1 đúng, 0 abstain, -1 sai."""
    if pred is None:
        return 0
    ptype = pred.get("type")
    if ptype == "abstain":
        return 0
    if gold.is_unanswerable:
        return 1 if ptype == "unanswerable" else -1
    if ptype != gold.type:
        return -1
    ans, ref, al = pred.get("answer"), gold.answer, gold.alias
    ok = {
        "number": lambda: match_number(ans, ref),
        "percent": lambda: match_percent(ans, ref),
        "string": lambda: match_string(ans, ref, al if isinstance(al, list) else None),
        "date": lambda: match_date(ans, ref),
        "boolean": lambda: match_boolean(ans, ref),
        "list": lambda: match_list(ans, ref, al),
        "table": lambda: match_table(ans, ref, al),
    }.get(ptype, lambda: False)()
    return 1 if ok else -1


# ---------------------------------------------------------------- đọc file


def load_gold(path: str | Path) -> dict[str, Gold]:
    out: dict[str, Gold] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            gtype = r.get("type") or ("unanswerable" if r.get("answer") is None else None)
            if r.get("answer") is None and gtype != "unanswerable":
                gtype = "unanswerable"
            out[r["id"]] = Gold(id=r["id"], type=gtype, answer=r.get("answer"), alias=r.get("alias"))
    return out


def load_predictions(path: str | Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Trả về (pred theo id, danh sách cảnh báo). Dòng hỏng → bỏ qua (abstain)."""
    preds: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                warnings.append(f"dòng {n}: JSON hỏng → abstain")
                continue
            if not isinstance(r, dict) or not isinstance(r.get("id"), str):
                warnings.append(f"dòng {n}: thiếu id → bỏ qua")
                continue
            if "reason" in r and not isinstance(r["reason"], str):
                warnings.append(f"dòng {n}: reason không phải chuỗi → abstain")
                continue
            if r["id"] in preds:
                warnings.append(f"dòng {n}: trùng id {r['id']} → giữ dòng đầu")
                continue
            preds[r["id"]] = r
    return preds, warnings


def load_ids(path: str | Path | None) -> set[str] | None:
    if path is None:
        return None
    text = Path(path).read_text(encoding="utf-8").strip()
    if text.startswith("["):
        return set(json.loads(text))
    return {ln.strip() for ln in text.splitlines() if ln.strip()}


# ---------------------------------------------------------------- tổng hợp


@dataclass
class Report:
    n: int = 0
    correct: int = 0
    wrong: int = 0
    abstain: int = 0
    by_type: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    wrong_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def pa(self) -> float:
        return (self.correct - self.wrong) / self.n if self.n else 0.0

    @property
    def coverage(self) -> float:
        return (self.correct + self.wrong) / self.n if self.n else 0.0

    @property
    def precision(self) -> float:
        answered = self.correct + self.wrong
        return self.correct / answered if answered else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "correct": self.correct,
            "wrong": self.wrong,
            "abstain": self.abstain,
            "pa": round(self.pa, 6),
            "coverage": round(self.coverage, 6),
            "precision": round(self.precision, 6),
            "by_type": {t: dict(c) for t, c in sorted(self.by_type.items())},
        }

    def to_markdown(self) -> str:
        lines = [
            "# Kết quả chấm",
            "",
            f"N = {self.n} · **PA = {self.pa:.4f}** · "
            f"coverage = {self.coverage:.4f} · precision = {self.precision:.4f}",
            f"đúng {self.correct} · sai {self.wrong} · abstain {self.abstain}",
            "",
            "| Kiểu (tham chiếu) | N | Đúng | Sai | Abstain | PA |",
            "|---|---|---|---|---|---|",
        ]
        for t, c in sorted(self.by_type.items()):
            n = c["correct"] + c["wrong"] + c["abstain"]
            pa = (c["correct"] - c["wrong"]) / n if n else 0.0
            lines.append(f"| {t} | {n} | {c['correct']} | {c['wrong']} | {c['abstain']} | {pa:.4f} |")
        if self.wrong_ids:
            lines += ["", f"Câu sai (tối đa 50/{len(self.wrong_ids)}): " + ", ".join(self.wrong_ids[:50])]
        if self.warnings:
            lines += ["", "Cảnh báo:", *[f"- {w}" for w in self.warnings[:50]]]
        return "\n".join(lines) + "\n"


def score(preds: dict[str, dict[str, Any]], gold: dict[str, Gold], ids: set[str] | None = None) -> Report:
    rep = Report()
    for qid in sorted(gold):
        if ids is not None and qid not in ids:
            continue
        g = gold[qid]
        s = score_one(preds.get(qid), g)
        rep.n += 1
        key = {1: "correct", 0: "abstain", -1: "wrong"}[s]
        setattr(rep, key, getattr(rep, key) + 1)
        rep.by_type[g.type][key] += 1
        if s == -1:
            rep.wrong_ids.append(qid)
    extra = set(preds) - set(gold)
    if extra:
        rep.warnings.append(f"{len(extra)} id trong file nộp không có trong gold (bỏ qua)")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Chấm submission theo luật DataMate")
    ap.add_argument("--pred", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--ids", help="file id (mỗi dòng một id, hoặc JSON list) để lọc tập chấm")
    ap.add_argument("--report", help="ghi báo cáo markdown")
    ap.add_argument("--json", action="store_true", help="in kết quả dạng JSON")
    args = ap.parse_args(argv)

    preds, warnings = load_predictions(args.pred)
    rep = score(preds, load_gold(args.gold), load_ids(args.ids))
    rep.warnings = warnings + rep.warnings
    if args.report:
        Path(args.report).write_text(rep.to_markdown(), encoding="utf-8")
    if args.json:
        print(json.dumps(rep.to_dict(), ensure_ascii=False))
    else:
        print(rep.to_markdown())
    return 0


if __name__ == "__main__":
    sys.exit(main())
