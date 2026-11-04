"""Dev: xác minh thẻ model theo luật thi rồi tải weights về `models/<tên>` (chạy trên máy phát triển có Internet).

    uv run python scripts/fetch_model.py qwen3.5-9b [qwen3-14b ...]   # tên trong configs/models.yaml
    uv run python scripts/fetch_model.py --hf-id Org/Repo --name my-model
    uv run python scripts/fetch_model.py qwen3.5-9b --verify-only     # chỉ kiểm thẻ, không tải

Tải model chỉ được phép lúc PHÁT TRIỂN. Code runtime (`datamate/`) không import huggingface_hub và không gọi mạng.
Chỉ ghi vào MODELS.md những gì script này in ra; ghi thêm `models/<tên>/MODEL_INFO.json` làm bằng chứng.
Token (nếu model gated): đặt biến môi trường HF_TOKEN, không ghi vào file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datamate.tools.count_params import count_dir  # noqa: E402
from datamate.tools.model_check import check_model_info, passes  # noqa: E402

WEIGHT_PATTERNS = ["*.json", "*.safetensors", "*.txt", "tokenizer*", "*.model", "*.jinja"]


def load_candidates() -> dict[str, dict]:
    cfg = yaml.safe_load((ROOT / "configs" / "models.yaml").read_text(encoding="utf-8"))
    return {c["name"]: c for c in cfg["candidates"]}


def verify(hf_id: str) -> tuple[dict, list]:
    from huggingface_hub import HfApi

    info = HfApi().model_info(hf_id)
    lic = getattr(info.card_data, "license", None) if info.card_data else None
    total = getattr(info.safetensors, "total", None) if info.safetensors else None
    created = info.created_at.date() if info.created_at else None
    record = {
        "hf_id": hf_id,
        "license": lic,
        "created": created.isoformat() if created else None,
        "params_metadata": total,
        "gated": bool(info.gated),
        "sha": info.sha,
        "last_modified": info.last_modified.isoformat() if info.last_modified else None,
    }
    return record, check_model_info(lic, created, total, quantized="awq" in hf_id.lower() or "gptq" in hf_id.lower())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Xác minh thẻ và tải model")
    ap.add_argument("names", nargs="*", help="tên trong configs/models.yaml")
    ap.add_argument("--hf-id")
    ap.add_argument("--name")
    ap.add_argument("--dest", default=str(ROOT / "models"))
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args(argv)

    jobs: list[tuple[str, str]] = []
    cands = load_candidates()
    for n in args.names:
        if n not in cands:
            print(f"không có {n!r} trong configs/models.yaml (có: {sorted(cands)})")
            return 2
        jobs.append((n, cands[n]["hf_id"]))
    if args.hf_id:
        jobs.append((args.name or args.hf_id.split("/")[-1].lower(), args.hf_id))
    if not jobs:
        ap.error("cần tên model hoặc --hf-id")

    rc = 0
    for name, hf_id in jobs:
        print("=" * 72, f"\n{name} <- {hf_id}")
        try:
            record, findings = verify(hf_id)
        except ImportError as e:
            print(f"  thiếu thư viện ({e}): chạy `uv sync --extra llm`")
            return 2
        except Exception as e:  # noqa: BLE001 - lỗi mạng/quyền/tên sai: báo rõ cho người chạy, không dừng cả lô
            print(f"  KHÔNG đọc được thẻ model: {type(e).__name__}: {e}")
            rc = 1
            continue
        for f in findings:
            print(f"  [{f.level}] {f.message}")
        if not passes(findings):
            print("  => LOẠI theo luật thi, không tải.")
            rc = 1
            continue
        if args.verify_only:
            continue
        from huggingface_hub import snapshot_download

        dest = Path(args.dest) / name
        snapshot_download(hf_id, local_dir=dest, allow_patterns=WEIGHT_PATTERNS)
        params, warns = count_dir(dest)
        record |= {"params_counted": params, "count_warnings": warns}
        (dest / "MODEL_INFO.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  đã tải về {dest}; count_params = {params:,} ({params / 1e9:.3f}B)")
        for w in warns:
            print(f"  CẢNH BÁO: {w}")
        if params > 15_000_000_000:
            print("  => VƯỢT 15B theo count_params")
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
