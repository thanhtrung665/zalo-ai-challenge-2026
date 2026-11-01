from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from datamate.tools.compliance import scan_file, scan_tree

ROOT = Path(__file__).resolve().parents[1]


def _mk(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_detects_hardcoded_ids_and_network(tmp_path) -> None:
    p = _mk(
        tmp_path, "datamate/executor/x.py", 'import requests\nif bid == "biz_118":\n    pass\nq = "q_06de33fa21cc"\n'
    )
    rules = {v.rule.split()[0] for v in scan_file(p, tmp_path)}
    assert rules == {"R3", "R4"}
    assert len(scan_file(p, tmp_path)) == 3


def test_allow_comment_and_exempt_dirs(tmp_path) -> None:
    p = _mk(tmp_path, "datamate/x.py", 'x = "biz_118"  # compliance: allow (ví dụ trong docstring)\n')
    assert scan_file(p, tmp_path) == []
    t = _mk(tmp_path, "tests/test_x.py", 'x = "biz_118"\n')
    assert scan_file(t, tmp_path) == []
    e = _mk(tmp_path, "datamate/eval/x.py", "import requests\n")  # eval không chạy lúc inference
    assert scan_file(e, tmp_path) == []


def test_training_cannot_read_test_answers(tmp_path) -> None:
    p = _mk(tmp_path, "scripts/train.py", 'open("data/public_test/questions.jsonl")\n')
    assert any(v.rule.startswith("R6") for v in scan_file(p, tmp_path))


def test_repo_itself_is_clean() -> None:
    assert scan_tree(ROOT) == []


def _run_hook(name: str, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / ".claude" / "hooks" / name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(ROOT), "PATH": ""},
    )


def test_guard_bash_hook() -> None:
    assert _run_hook("guard_bash.py", {"tool_input": {"command": "rm -rf data/train"}}).returncode == 2
    assert _run_hook("guard_bash.py", {"tool_input": {"command": "sed -i s/a/b/ data/train/x.csv"}}).returncode == 2
    assert _run_hook("guard_bash.py", {"tool_input": {"command": "curl https://api.openai.com/v1/x"}}).returncode == 2
    assert _run_hook("guard_bash.py", {"tool_input": {"command": "uv run pytest -q"}}).returncode == 0
    assert _run_hook("guard_bash.py", {"tool_input": {"command": "ls data/train"}}).returncode == 0


def test_check_forbidden_hook(tmp_path) -> None:
    bad = ROOT / "datamate" / "_tmp_hook_probe.py"
    try:
        bad.write_text('X = "biz_101"\n', encoding="utf-8")
        r = _run_hook("check_forbidden.py", {"tool_input": {"file_path": str(bad)}})
        assert r.returncode == 2
        assert "R4" in r.stderr
        bad.write_text("X = 1\n", encoding="utf-8")
        assert _run_hook("check_forbidden.py", {"tool_input": {"file_path": str(bad)}}).returncode == 0
    finally:
        bad.unlink(missing_ok=True)
