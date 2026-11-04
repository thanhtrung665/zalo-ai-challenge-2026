"""Chọn hồ sơ LLM (configs/llm.yaml) theo phần cứng thật. Hàm thuần, không import torch."""

from __future__ import annotations

from dataclasses import dataclass

BF16_MIN_CC = (8, 0)
HEADROOM = 1.35  # trọng số bf16 phải chiếm tối đa ~74% VRAM để còn chỗ cho KV cache và kích hoạt


@dataclass(frozen=True)
class GpuInfo:
    name: str
    mem_gb: float
    cc: tuple[int, int]


def weights_gb(params_b: float, bytes_per_param: float = 2.0) -> float:
    return params_b * bytes_per_param


def recommend_profile(gpus: list[GpuInfo], params_b: float = 10.0) -> tuple[str | None, list[str]]:
    """Trả (tên hồ sơ hoặc None, ghi chú). `params_b`: số tham số model dự định chạy (tỉ), tính trọng số bf16/fp16."""
    notes: list[str] = []
    if not gpus:
        return None, ["không thấy GPU"]
    n = len(gpus)
    per_card = min(g.mem_gb for g in gpus)
    bf16 = all(g.cc >= BF16_MIN_CC for g in gpus)
    need = weights_gb(params_b) * HEADROOM
    if any(g.cc[0] >= 12 for g in gpus):
        notes.append("Blackwell (sm_120): cần torch + vLLM build với CUDA >= 12.8")
    if not bf16:
        notes.append("GPU không có bf16 -> dùng float16; số học khác máy chấm, chỉ để gỡ lỗi/so sánh tương đối")
        if per_card < need and n > 1 and per_card * n >= need:
            notes.append(f"model cần tensor-parallel {n}: thêm --tp {n}")
        return "gpu_fp16", notes
    if per_card >= need:
        is_5090 = all("5090" in g.name for g in gpus) and n >= 2
        return ("rtx5090x2" if is_5090 else "gpu_bf16"), notes
    if n >= 2 and per_card * n >= need:
        notes.append(f"model ~{params_b:g}B bf16 cần ~{weights_gb(params_b):.0f} GB: chia {n} card (tensor-parallel)")
        return "rtx5090x2_tp2", notes
    notes.append(
        f"VRAM không đủ cho ~{params_b:g}B bf16 (cần ~{need:.0f} GB, có {per_card * n:.0f} GB): "
        "dùng model nhỏ hơn hoặc lượng tử"
    )
    return None, notes
