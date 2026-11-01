"""Kiểm tra file submission.jsonl trước khi nộp (format theo rulebook §9 và SPEC §3).

Lỗi (exit 1): JSON hỏng, thiếu id, trùng id, id lạ, type không hợp lệ, answer sai format của type.
Cảnh báo: thiếu câu (sẽ tính abstain), list rỗng.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from datamate.eval.scorer import ALL_TYPES, is_number

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH = re.compile(r"^\d{4}-\d{2}$")


def _valid_date(s: str) -> bool:
    try:
        if _DATE.match(s):
            date.fromisoformat(s)
            return True
        if _MONTH.match(s):
            y, m = s.split("-")
            return 1 <= int(m) <= 12 and int(y) > 0
    except ValueError:
        return False
    return False


def _scalar_ok(x: Any) -> bool:
    return (isinstance(x, str) and x.strip() != "") or is_number(x)


def check_record(r: Any) -> list[str]:
    """Trả về danh sách lỗi format của một bản ghi."""
    if not isinstance(r, dict):
        return ["bản ghi không phải object JSON"]
    errs: list[str] = []
    if not isinstance(r.get("id"), str) or not r["id"]:
        errs.append("thiếu id dạng chuỗi")
    t = r.get("type")
    if t not in ALL_TYPES:
        return [*errs, f"type không hợp lệ: {t!r}"]
    if "reason" in r and not isinstance(r["reason"], str):
        errs.append("reason phải là chuỗi (nếu không, BTC coi dòng này là bỏ trống)")
    if t in ("abstain", "unanswerable"):
        return errs
    if "answer" not in r:
        return [*errs, "thiếu answer"]
    a = r["answer"]
    if t in ("number", "percent") and not is_number(a):
        errs.append(f"{t} phải là JSON number (không phải chuỗi/bool): {a!r}")
    elif t == "string" and not (isinstance(a, str) and a.strip()):
        errs.append(f"string phải là chuỗi không rỗng: {a!r}")
    elif t == "date" and not (isinstance(a, str) and _valid_date(a)):
        errs.append(f"date phải là 'YYYY-MM-DD' hoặc 'YYYY-MM': {a!r}")
    elif t == "boolean" and not isinstance(a, bool):
        errs.append(f"boolean phải là true/false: {a!r}")
    elif t == "list":
        if not isinstance(a, list):
            errs.append("list phải là mảng JSON (kể cả một phần tử)")
        elif not all(_scalar_ok(x) for x in a):
            errs.append("phần tử list phải là chuỗi không rỗng hoặc số")
    elif t == "table":
        if not isinstance(a, dict) or not isinstance(a.get("columns"), list) or not isinstance(a.get("rows"), list):
            errs.append('table phải là {"columns": [...], "rows": [[...], ...]}')
        else:
            cols = a["columns"]
            if not cols or not all(isinstance(c, str) and c for c in cols):
                errs.append("columns phải là danh sách chuỗi không rỗng")
            for i, row in enumerate(a["rows"]):
                if not isinstance(row, list) or len(row) != len(cols):
                    errs.append(f"rows[{i}] phải là mảng dài {len(cols)}")
                elif not all(_scalar_ok(x) for x in row):
                    errs.append(f"rows[{i}] có ô không phải chuỗi/số")
    return errs


def validate(pred_path: str | Path, questions_path: str | Path | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    q_ids: set[str] | None = None
    if questions_path:
        q_ids = set()
        with open(questions_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    q_ids.add(json.loads(line)["id"])

    with open(pred_path, encoding="utf-8") as f:
        for n, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"dòng {n}: JSON hỏng ({e.msg})")
                continue
            for e in check_record(r):
                errors.append(f"dòng {n}: {e}")
            qid = r.get("id") if isinstance(r, dict) else None
            if isinstance(qid, str):
                if qid in seen:
                    errors.append(f"dòng {n}: trùng id {qid}")
                seen.add(qid)
                if q_ids is not None and qid not in q_ids:
                    errors.append(f"dòng {n}: id {qid} không có trong questions")
            if isinstance(r, dict) and r.get("type") == "list" and r.get("answer") == []:
                warnings.append(f"dòng {n}: list rỗng")

    if q_ids is not None:
        missing = q_ids - seen
        if missing:
            warnings.append(f"thiếu {len(missing)}/{len(q_ids)} câu (sẽ tính abstain)")
    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kiểm tra submission.jsonl DataMate")
    ap.add_argument("pred")
    ap.add_argument("--questions", help="questions.jsonl để kiểm id")
    args = ap.parse_args(argv)
    errors, warnings = validate(args.pred, args.questions)
    for w in warnings:
        print(f"CẢNH BÁO: {w}")
    for e in errors[:200]:
        print(f"LỖI: {e}")
    if errors:
        print(f"→ KHÔNG HỢP LỆ: {len(errors)} lỗi")
        return 1
    print("→ HỢP LỆ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
