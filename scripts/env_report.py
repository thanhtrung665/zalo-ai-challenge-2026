"""Dev: báo cáo môi trường GPU/phiên bản và đề xuất hồ sơ LLM; ghi JSON để ghim phiên bản vào Dockerfile (T40).

uv run python scripts/env_report.py [--params-b 10] [--out runs/env_report.json]
"""

from __future__ import annotations

import argparse
import importlib
import json
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datamate.tools.hardware import GpuInfo, recommend_profile  # noqa: E402


def version(mod: str) -> str | None:
    try:
        return str(importlib.import_module(mod).__version__)
    except Exception:  # noqa: BLE001 - chỉ để chẩn đoán: thiếu hoặc hỏng đều ghi None
        return None


def ram_gb() -> float | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal"):
                return round(int(line.split()[1]) / 1e6, 1)
    except OSError:
        pass
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params-b", type=float, default=10.0, help="số tham số model dự định chạy (tỉ)")
    ap.add_argument("--out", default=str(ROOT / "runs" / "env_report.json"))
    args = ap.parse_args(argv)

    rep: dict = {
        "python": platform.python_version(),
        "os": platform.platform(),
        "ram_gb": ram_gb(),
        "disk_free_gb": round(shutil.disk_usage(ROOT).free / 1e9, 1),
        "packages": {m: version(m) for m in ("torch", "vllm", "transformers", "pydantic", "pandas")},
    }
    gpus: list[GpuInfo] = []
    try:
        import torch

        rep["cuda_runtime"] = torch.version.cuda
        for i in range(torch.cuda.device_count()):
            p = torch.cuda.get_device_properties(i)
            gpus.append(GpuInfo(p.name, round(p.total_memory / 1e9, 1), (p.major, p.minor)))
        rep["bf16_supported"] = bool(gpus) and torch.cuda.is_bf16_supported()
    except ImportError:
        rep["cuda_runtime"] = None
    rep["gpus"] = [{"name": g.name, "mem_gb": g.mem_gb, "compute_capability": f"{g.cc[0]}.{g.cc[1]}"} for g in gpus]
    profile, notes = recommend_profile(gpus, args.params_b)
    rep["recommended_profile"], rep["notes"] = profile, notes
    if rep["packages"]["vllm"] is None:
        rep["notes"].append("chưa import được vLLM: uv sync --extra llm (cần CUDA/torch khớp phiên bản)")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
