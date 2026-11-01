#!/usr/bin/env python3
"""PostToolUse hook (Edit|Write|MultiEdit): chặn vi phạm luật thi ngay khi Claude sửa file.

Exit 2 + stderr → Claude nhận phản hồi và phải sửa lại file.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path")
    if not file_path:
        return 0

    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".").resolve()
    sys.path.insert(0, str(root))
    try:
        from datamate.tools.compliance import scan_file
    except Exception:  # khung chưa đầy đủ thì bỏ qua, không chặn công việc
        return 0

    path = Path(file_path)
    if not path.is_absolute():
        path = root / path
    violations = scan_file(path, root)
    if not violations:
        return 0

    msg = ["Vi phạm luật thi DataMate (SPEC §4) trong file vừa sửa — hãy sửa ngay:"]
    msg += [f"  - {v.format()}" for v in violations]
    msg.append(
        "Không hard-code business_id/id câu hỏi; không dùng thư viện mạng/API trong code runtime; "
        "không đọc questions/answers của public/private test trong code huấn luyện."
    )
    print("\n".join(msg), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
