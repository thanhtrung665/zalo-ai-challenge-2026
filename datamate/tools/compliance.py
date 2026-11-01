"""Quét vi phạm luật thi trong mã nguồn (chỉ dùng thư viện chuẩn).

Dùng chung cho hook `.claude/hooks/check_forbidden.py` và `scripts/check_compliance.py`.

Luật được kiểm (SPEC §4):
- R3: không gọi dịch vụ ngoài trong code runtime (import thư viện HTTP/LLM API).
- R4: không hard-code theo business_id / id câu hỏi.
- R6: code runtime và huấn luyện không đọc questions/answers của public/private test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Thư mục chứa code chạy lúc inference (bị kiểm chặt nhất).
RUNTIME_DIRS = ("datamate", "prompts", "configs", "docker")
# Các phần trong datamate không chạy lúc inference: được phép đọc answers.jsonl của train.
RUNTIME_EXEMPT = ("datamate/eval/", "datamate/tools/compliance.py")
# Code huấn luyện / script: chỉ kiểm luật dữ liệu test và id cứng.
TRAINING_DIRS = ("scripts", "training")

SUFFIXES = {".py", ".sh", ".yaml", ".yml", ".json", ".md", ".txt", ".j2", ".jinja", ".toml", "Dockerfile"}


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str
    text: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.text.strip()[:160]}"


_ID_PATTERNS = [
    (re.compile(r"\bbiz_\d{2,}\b"), "R4 hard-code business_id"),
    (re.compile(r"\bq_[0-9a-f]{6,}\b"), "R4 hard-code question id"),
]
_NETWORK_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(requests|httpx|aiohttp|urllib3|urllib\.request|openai|anthropic|google\.generativeai|"
    r"google\.genai|cohere|mistralai|groq|together|litellm|huggingface_hub)\b"
)
_NETWORK_CALL = re.compile(r"(hf_hub_download|snapshot_download|from_pretrained\([^)]*https?://)")
_TEST_DATA = re.compile(r"(public_test|private_test)[^\n]*(answers|questions)\.jsonl")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def classify(rel: str) -> str | None:
    """Trả về 'runtime', 'training' hoặc None (không kiểm)."""
    if rel.startswith("tests/") or rel.startswith(".claude/") or rel.startswith("docs/"):
        return None
    if any(rel.startswith(p) for p in RUNTIME_EXEMPT):
        return "training"
    if rel.split("/")[0] in RUNTIME_DIRS or rel == "predict.sh" or rel == "Dockerfile":
        return "runtime"
    if rel.split("/")[0] in TRAINING_DIRS:
        return "training"
    return None


def scan_file(path: Path, root: Path) -> list[Violation]:
    rel = _rel(path, root)
    kind = classify(rel)
    if kind is None or not path.is_file():
        return []
    if path.suffix not in SUFFIXES and path.name not in SUFFIXES:
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    out: list[Violation] = []
    for i, line in enumerate(lines, start=1):
        if "compliance: allow" in line:  # thoát hiểm có chủ đích, phải giải thích trong PR
            continue
        for pat, rule in _ID_PATTERNS:
            if pat.search(line):
                out.append(Violation(rel, i, rule, line))
        if _TEST_DATA.search(line) and kind == "training":
            out.append(Violation(rel, i, "R6 dùng questions/answers của test trong code huấn luyện", line))
        if kind == "runtime":
            if path.suffix == ".py" and _NETWORK_IMPORT.search(line):
                out.append(Violation(rel, i, "R3 import thư viện mạng/API trong code runtime", line))
            if path.suffix == ".py" and _NETWORK_CALL.search(line):
                out.append(Violation(rel, i, "R3 tải model/dữ liệu qua mạng lúc runtime", line))
    return out


def scan_tree(root: Path) -> list[Violation]:
    out: list[Violation] = []
    for top in (*RUNTIME_DIRS, *TRAINING_DIRS):
        base = root / top
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                if "__pycache__" in p.parts:
                    continue
                out.extend(scan_file(p, root))
    for name in ("predict.sh", "Dockerfile"):
        p = root / name
        if p.exists():
            out.extend(scan_file(p, root))
    return out
