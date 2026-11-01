#!/usr/bin/env python3
"""PreToolUse hook (Bash): chặn lệnh phá dữ liệu gốc và lệnh gọi API LLM thương mại.

Exit 2 + stderr → lệnh bị chặn, Claude nhận lý do.
"""

from __future__ import annotations

import json
import re
import sys

RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(rm|mv|truncate|shred)\b[^|;&]*\bdata/"),
        "Không xoá/di chuyển dữ liệu gốc trong data/ (SPEC §2, dữ liệu là read-only).",
    ),
    (
        re.compile(r"\bsed\s+-i[^|;&]*\bdata/|>\s*data/|\btee\b[^|;&]*\bdata/"),
        "Không ghi đè file trong data/. Ghi kết quả vào runs/ hoặc .cache/.",
    ),
    (
        re.compile(r"\bgit\s+push\b[^|;&]*(--force|-f\b)"),
        "Không force-push. Hỏi người dùng trước.",
    ),
    (
        re.compile(
            r"(api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis\.com|api\.mistral\.ai|"
            r"api\.groq\.com|api\.together\.xyz|api\.deepseek\.com)"
        ),
        "Không gọi API LLM thương mại (R3). Nếu cần cho sinh dữ liệu huấn luyện, hỏi người dùng — câu hỏi mở với BTC (SPEC §9).",
    ),
    (
        re.compile(r"\b(git\s+add|cp|rsync)\b[^|;&]*\bdata/(public_test|private_test)/[^|;&]*\b(tests|training|artifacts)/"),
        "Không sao chép dữ liệu test vào tests/training/artifacts (R6).",
    ),
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    for pat, reason in RULES:
        if pat.search(cmd):
            print(f"Lệnh bị chặn bởi guard_bash: {reason}\nLệnh: {cmd}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
