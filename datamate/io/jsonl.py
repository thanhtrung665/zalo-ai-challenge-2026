"""JSONL: đọc theo thứ tự file, ghi và flush từng dòng (luật thi: bị cắt giữa chừng vẫn chấm phần đã ghi)."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from types import TracebackType
from typing import Any


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Đọc mọi dòng không rỗng, giữ nguyên thứ tự file."""
    out: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def iter_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


class JsonlWriter:
    """Ghi mỗi bản ghi một dòng rồi flush + fsync ngay."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self.path, "w", encoding="utf-8")  # noqa: SIM115

    def write(self, record: dict[str, Any]) -> None:
        self._f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._f.flush()
        os.fsync(self._f.fileno())

    def close(self) -> None:
        if not self._f.closed:
            self._f.close()

    def __enter__(self) -> JsonlWriter:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()
