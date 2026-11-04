"""Dev: smoke test backend LLM trên GPU thật — chạy TRƯỚC khi benchmark để bắt lỗi môi trường sớm.

    uv run python scripts/llm_smoke.py --model models/qwen3.5-9b --profile rtx5090x2 [--tp 2]

Kiểm: (1) nạp được model; (2) JSON hợp lệ theo schema; (3) tất định: chạy lại cho cùng văn bản;
(4) độc lập batch: cùng một prompt chạy một mình và nằm trong batch có kết quả giống nhau
(ảnh hưởng T31, BTC chạy lại phải khớp);
(5) thời gian và VRAM. Kết quả (4) không đạt không phải lỗi chặn nhưng phải ghi lại: phải cố định cách xếp batch.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datamate.llm.config import add_override_args, profile_from_args  # noqa: E402
from datamate.llm.factory import create_backend  # noqa: E402


class Answer(BaseModel):
    category: str
    reason: str


PROMPTS = [
    f"Phân loại mặt hàng '{item}' vào một nhóm (đồ uống, thực phẩm hoặc gia dụng) và giải thích ngắn gọn."
    for item in ("Coca Cola 330ml", "Mì Hảo Hảo tôm chua cay", "Nước rửa chén Sunlight", "Bia Tiger 330ml")
]


def peak_vram_gb() -> float | None:
    try:
        import torch

        if torch.cuda.is_available():
            return round(max(torch.cuda.max_memory_allocated(i) for i in range(torch.cuda.device_count())) / 1e9, 2)
    except ImportError:
        pass
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--profile", default=None)
    add_override_args(ap)
    ap.add_argument("--out", default=str(ROOT / "runs" / "llm_smoke.json"))
    args = ap.parse_args(argv)

    profile = profile_from_args(args)
    t0 = time.perf_counter()
    backend = create_backend(args.model, profile)
    load_s = round(time.perf_counter() - t0, 1)

    t1 = time.perf_counter()
    first = backend.generate_json(PROMPTS, Answer, max_tokens=256)
    batch_s = round(time.perf_counter() - t1, 2)
    second = backend.generate_json(PROMPTS, Answer, max_tokens=256)
    alone = backend.generate_json(PROMPTS[1:2], Answer, max_tokens=256)

    rep = {
        "profile": profile.model_dump(),
        "load_seconds": load_s,
        "batch_seconds": batch_s,
        "json_valid": f"{sum(r.parsed is not None for r in first)}/{len(first)}",
        "deterministic_repeat": [a.text for a in first] == [b.text for b in second],
        "batch_invariant": alone[0].text == first[1].text,
        "mean_logprob": [None if r.mean_logprob is None else round(r.mean_logprob, 3) for r in first],
        "peak_vram_gb": peak_vram_gb(),
        "sample": first[0].text[:300],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    ok = rep["json_valid"] == f"{len(PROMPTS)}/{len(PROMPTS)}" and rep["deterministic_repeat"]
    if not rep["batch_invariant"]:
        print("CẢNH BÁO: kết quả phụ thuộc thành phần batch — cố định cách xếp batch ở predict (T31).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
