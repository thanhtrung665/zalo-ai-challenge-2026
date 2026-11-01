"""Bộ hồi quy tham chiếu: 111 câu train tính tay theo rulebook phải khớp đáp án chuẩn.

Xem docs/DATA_FINDINGS.md §7.

Tự bỏ qua khi máy chưa có data/train hoặc chưa cài extra `data`.
Khi executor (T12) xong, thêm test so executor với cùng tập câu.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPLIT = ROOT / "data" / "train"

pytestmark = pytest.mark.skipif(
    not (SPLIT / "answers.jsonl").exists()
    or importlib.util.find_spec("pandas") is None
    or importlib.util.find_spec("python_calamine") is None,
    reason="cần data/train và extra `data` (uv sync --extra data)",
)


def test_reference_checks_match_gold(capsys: pytest.CaptureFixture[str]) -> None:
    sys.path.insert(0, str(ROOT / "research"))
    import reference_checks

    rc = reference_checks.main(["--split", str(SPLIT)])
    out = capsys.readouterr().out
    assert rc == 0, out[-3000:]
    assert "Khớp 111/111" in out
