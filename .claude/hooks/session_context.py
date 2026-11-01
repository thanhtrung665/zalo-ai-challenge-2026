#!/usr/bin/env python3
"""SessionStart hook: in ra ngữ cảnh ngắn (task kế tiếp, số ngày đến hạn nộp) để Claude bắt đầu đúng chỗ."""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

DEADLINES = [
    (date(2026, 11, 7), "Gate G1: PA 5 fold >= 0,50"),
    (date(2026, 11, 13), "Gate G2: khoá code, PA 5 fold >= 0,70"),
    (date(2026, 11, 16), "Nộp image Docker (form chỉ mở trong ngày 16/11)"),
    (date(2026, 11, 20), "BTC phát hành private test 09:00"),
    (date(2026, 11, 23), "Hạn upload submission private 23:59"),
]


def main() -> None:
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    plan = root / "PLAN.md"
    lines = ["[DataMate] Ngữ cảnh phiên:"]
    if plan.exists():
        text = plan.read_text(encoding="utf-8")
        done = len(re.findall(r"^- \[x\] \*\*T\d+", text, flags=re.M))
        todo = re.findall(r"^- \[ \] \*\*(T\d+ — [^*]+)\*\*", text, flags=re.M)
        lines.append(f"- PLAN.md: {done} task đã xong, {len(todo)} còn lại.")
        if todo:
            lines.append(f"- Task chưa xong đầu tiên: {todo[0].strip()} (kiểm tra phụ thuộc trước khi làm).")
    today = date.today()
    upcoming = [(d, s) for d, s in DEADLINES if d >= today]
    if upcoming:
        d, s = upcoming[0]
        lines.append(f"- Mốc gần nhất: {s} — còn {(d - today).days} ngày ({d.isoformat()}).")
    lines.append("- Luật cứng: <=15B tham số, offline, không hard-code id, không dùng dữ liệu test để huấn luyện. Xem CLAUDE.md.")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
