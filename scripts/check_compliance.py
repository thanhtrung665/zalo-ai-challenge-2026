"""Quét toàn repo tìm vi phạm luật thi (SPEC §4). Exit 1 nếu có vi phạm.

Dùng: uv run python scripts/check_compliance.py
Thoát hiểm có chủ đích: thêm comment `compliance: allow` trên đúng dòng đó và giải thích trong docs/DECISIONS.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datamate.tools.compliance import scan_tree  # noqa: E402


def main() -> int:
    violations = scan_tree(ROOT)
    if not violations:
        print("compliance: sạch — không phát hiện vi phạm.")
        return 0
    print(f"compliance: {len(violations)} vi phạm")
    for v in violations:
        print("  " + v.format())
    return 1


if __name__ == "__main__":
    sys.exit(main())
