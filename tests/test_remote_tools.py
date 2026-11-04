from __future__ import annotations

import datetime as dt

import pytest

from datamate.llm.config import apply_overrides, load_profile
from datamate.tools.hardware import GpuInfo, recommend_profile
from datamate.tools.model_check import check_model_info, passes


def g(name: str, gb: float, cc: tuple[int, int]) -> GpuInfo:
    return GpuInfo(name, gb, cc)


def test_recommend_two_5090_small_and_large_model():
    two = [g("NVIDIA GeForce RTX 5090", 32, (12, 0))] * 2
    # 10B bf16 = 20 GB × 1,35 = 27 GB <= 32 -> một card
    assert recommend_profile(two, 10)[0] == "rtx5090x2"
    # 14,8B bf16 = 29,6 GB × 1,35 = 40 GB > 32 -> chia hai card
    prof, notes = recommend_profile(two, 14.8)
    assert prof == "rtx5090x2_tp2" and any("tensor-parallel" in n for n in notes)
    assert any("Blackwell" in n for n in recommend_profile(two, 10)[1])


def test_recommend_big_single_gpu_and_old_gpu_and_too_small():
    assert recommend_profile([g("NVIDIA A100 80GB", 80, (8, 0))], 14.8)[0] == "gpu_bf16"
    prof, notes = recommend_profile([g("Tesla T4", 15, (7, 5))] * 2, 10)
    assert prof == "gpu_fp16" and any("bf16" in n for n in notes) and any("--tp 2" in n for n in notes)
    prof, notes = recommend_profile([g("RTX 4090", 24, (8, 9))], 14.8)
    assert prof is None and any("VRAM không đủ" in n for n in notes)
    assert recommend_profile([], 10) == (None, ["không thấy GPU"])


def test_model_check_rules():
    ok = check_model_info("apache-2.0", dt.date(2025, 4, 29), 14_800_000_000)
    assert passes(ok) and all(f.level == "ok" for f in ok)
    assert not passes(check_model_info("apache-2.0", dt.date(2025, 1, 1), 15_000_000_001))  # vượt 15B
    assert not passes(check_model_info("apache-2.0", dt.date(2026, 10, 1), 9_000_000_000))  # không trước 01/10/2026
    unknown = check_model_info(None, None, None, quantized=True)
    assert passes(unknown) and sum(f.level == "warn" for f in unknown) == 4
    assert any("không thuộc nhóm" in f.message for f in check_model_info("custom-license", dt.date(2025, 1, 1), 1))


def test_apply_overrides_keeps_unset_and_validates():
    base = load_profile("rtx5090x2")
    p = apply_overrides(base, tensor_parallel_size=2, max_model_len=4096)
    assert p.tensor_parallel_size == 2 and p.max_model_len == 4096 and p.dtype == "bfloat16"
    assert apply_overrides(base) == base
    with pytest.raises(ValueError):
        apply_overrides(base, dtype="int8")
