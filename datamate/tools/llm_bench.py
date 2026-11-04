"""Benchmark LLM trên bài map schema (T09): JSON hợp lệ, số lỗi validator, độ khớp mapping chuẩn, thời gian, VRAM.

    uv run python -m datamate.tools.llm_bench --model models/qwen --split .cache/split/train --profile rtx5090x2 \
        --out runs/llm_bench/qwen.json [--shops <shop_id> ...]

Không chọn shop theo tên trong code: mặc định lấy 5 shop cách đều trong danh sách đã sắp xếp.
Mapping chuẩn lấy từ `research/mappings` (bản nháp đã đọc lướt — xem D-008), nên độ khớp chỉ là tham khảo;
số lỗi validator mới là tín hiệu độc lập.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from datamate.ingest.loader import load_business
from datamate.llm.base import GenResult, LLMBackend, T
from datamate.llm.config import add_override_args, profile_from_args
from datamate.schema.agreement import agreement
from datamate.schema.mapper import map_shop
from datamate.schema.mapping import ShopMapping
from datamate.schema.propose import propose_mapping

DEFAULT_GOLD = Path(__file__).resolve().parents[2] / "research" / "mappings"


@dataclass
class CountingBackend:
    """Bọc backend để đếm số lời gọi và tỉ lệ JSON hợp lệ ngay lần đầu."""

    inner: LLMBackend
    calls: int = 0
    valid: int = 0
    latencies: list[float] = field(default_factory=list)

    def generate_json(self, prompts: list[str], schema: type[T], *, max_tokens: int = 4096) -> list[GenResult]:
        res = self.inner.generate_json(prompts, schema, max_tokens=max_tokens)
        self.calls += len(res)
        self.valid += sum(r.parsed is not None for r in res)
        self.latencies += [r.latency_s for r in res]
        return res

    def generate_text(
        self, prompts: list[str], *, max_tokens: int = 1024, stop: list[str] | None = None
    ) -> list[GenResult]:
        return self.inner.generate_text(prompts, max_tokens=max_tokens, stop=stop)


def pick_shops(split: Path, n: int) -> list[str]:
    ids = sorted(p.name for p in (split / "data").iterdir() if p.is_dir())
    if n >= len(ids):
        return ids
    step = len(ids) / n
    return [ids[int(i * step)] for i in range(n)]


def peak_vram_gb() -> float | None:
    try:
        import torch

        if torch.cuda.is_available():
            return round(max(torch.cuda.max_memory_allocated(i) for i in range(torch.cuda.device_count())) / 1e9, 2)
    except ImportError:
        pass
    return None


def run_bench(
    backend: LLMBackend,
    split: Path,
    shops: list[str],
    gold_dir: Path = DEFAULT_GOLD,
    max_rounds: int = 2,
) -> dict[str, Any]:
    counting = CountingBackend(backend)
    rows: list[dict[str, Any]] = []
    for biz in shops:
        biz_data = load_business(split / "data" / biz)
        t0 = time.perf_counter()
        res = map_shop(biz_data, counting, max_rounds=max_rounds)
        elapsed = time.perf_counter() - t0
        row: dict[str, Any] = {
            "shop": biz,
            "source": res.source,
            "rounds": res.rounds,
            "errors": res.n_errors,
            "warnings": sum(i.severity == "warn" for i in res.issues),
            "seconds": round(elapsed, 1),
            "log": res.log,
        }
        gold_path = gold_dir / f"{biz}.json"
        if gold_path.exists():
            gold = ShopMapping.model_validate_json(gold_path.read_text(encoding="utf-8"))
            a = agreement(res.mapping, gold)
            h = agreement(propose_mapping(biz_data)[0], gold)
            row |= {"f1": round(a.f1, 3), "status_acc": round(a.status_accuracy, 3), "heuristic_f1": round(h.f1, 3)}
            row["missing"], row["extra"] = [list(c) for c in a.missing[:8]], [list(c) for c in a.extra[:8]]
        rows.append(row)
    n = max(1, len(rows))
    return {
        "shops": rows,
        "json_valid_rate": round(counting.valid / counting.calls, 3) if counting.calls else None,
        "llm_calls": counting.calls,
        "mean_errors": round(sum(r["errors"] for r in rows) / n, 2),
        "mean_f1": round(sum(r.get("f1", 0) for r in rows) / n, 3),
        "used_llm_result": sum(r["source"] == "llm" for r in rows),
        "seconds_total": round(sum(r["seconds"] for r in rows), 1),
        "peak_vram_gb": peak_vram_gb(),
    }


def to_markdown(name: str, params: int | None, rep: dict[str, Any]) -> str:
    lines = [
        f"# Benchmark {name}",
        f"- tham số (count_params): {params:,}" if params else "- tham số: chưa đo",
        f"- JSON hợp lệ ngay lần đầu: {rep['json_valid_rate']} ({rep['llm_calls']} lời gọi)",
        f"- lỗi validator trung bình/shop: {rep['mean_errors']} · F1 mapping trung bình: {rep['mean_f1']}",
        f"- kết quả LLM được dùng: {rep['used_llm_result']}/{len(rep['shops'])} shop · "
        f"tổng {rep['seconds_total']} s · VRAM đỉnh: {rep['peak_vram_gb']} GB",
        "",
        "| shop | nguồn | vòng | lỗi | F1 | F1 nháp | trạng thái | giây |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rep["shops"]:
        lines.append(
            f"| {r['shop']} | {r['source']} | {r['rounds']} | {r['errors']} | {r.get('f1', '-')} | "
            f"{r.get('heuristic_f1', '-')} | {r.get('status_acc', '-')} | {r['seconds']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Benchmark LLM trên bài map schema")
    ap.add_argument("--model", required=True, help="thư mục weights")
    ap.add_argument("--split", required=True, help="thư mục split có data/<biz>")
    ap.add_argument("--profile", default=None, help="hồ sơ trong configs/llm.yaml")
    add_override_args(ap)
    ap.add_argument("--shops", nargs="*", default=[])
    ap.add_argument("--n-shops", type=int, default=5)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    from datamate.llm.factory import create_backend
    from datamate.tools.count_params import count_dir

    split = Path(args.split)
    shops = args.shops or pick_shops(split, args.n_shops)
    params, param_warnings = count_dir(Path(args.model))
    t0 = time.perf_counter()
    profile = profile_from_args(args)
    backend = create_backend(args.model, profile)
    load_s = round(time.perf_counter() - t0, 1)
    rep = run_bench(backend, split, shops)
    rep |= {
        "model": args.model,
        "profile": args.profile,
        "profile_effective": profile.model_dump(),
        "params": params,
        "param_warnings": param_warnings,
        "load_seconds": load_s,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    out.with_suffix(".md").write_text(to_markdown(Path(args.model).name, params, rep), encoding="utf-8")
    print(to_markdown(Path(args.model).name, params, rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
