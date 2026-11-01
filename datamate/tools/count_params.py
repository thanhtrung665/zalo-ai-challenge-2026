"""Đếm tham số của model từ header safetensors (không cần tải weights, không cần torch).

Luật thi (Rule 2): tổng tham số mọi model dùng lúc inference ≤ 15B, tính cả MoE và mọi phần có trong weights
(ví dụ vision encoder của model đa phương thức, dù không dùng).

Dùng:  python -m datamate.tools.count_params models/main [models/embed ...]
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

LIMIT = 15_000_000_000
_OTHER_WEIGHT_SUFFIXES = {".bin", ".pt", ".pth", ".gguf", ".ckpt", ".onnx"}


def safetensors_params(path: Path) -> int:
    with open(path, "rb") as f:
        (header_len,) = struct.unpack("<Q", f.read(8))
        header = json.loads(f.read(header_len))
    total = 0
    for name, info in header.items():
        if name == "__metadata__":
            continue
        total += math.prod(info["shape"]) if info["shape"] else 1
    return total


def count_dir(root: Path) -> tuple[int, list[str]]:
    files = sorted(root.rglob("*.safetensors")) if root.is_dir() else [root]
    warnings = [
        f"{p} không phải safetensors — KHÔNG được đếm, cần kiểm tay"
        for p in (root.rglob("*") if root.is_dir() else [])
        if p.suffix in _OTHER_WEIGHT_SUFFIXES
    ]
    if not files:
        warnings.append(f"{root}: không tìm thấy file .safetensors")
    return sum(safetensors_params(p) for p in files), warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Đếm tham số model (safetensors) và kiểm giới hạn 15B")
    ap.add_argument("paths", nargs="+", help="thư mục model hoặc file .safetensors")
    ap.add_argument("--limit", type=int, default=LIMIT)
    args = ap.parse_args(argv)

    grand = 0
    for p in map(Path, args.paths):
        n, warns = count_dir(p)
        grand += n
        print(f"{p}: {n:,} tham số ({n / 1e9:.3f}B)")
        for w in warns:
            print(f"  CẢNH BÁO: {w}")
    status = "ĐẠT" if grand <= args.limit else "VƯỢT GIỚI HẠN"
    print(f"TỔNG: {grand:,} ({grand / 1e9:.3f}B) / giới hạn {args.limit / 1e9:.0f}B → {status}")
    return 0 if grand <= args.limit else 1


if __name__ == "__main__":
    sys.exit(main())
