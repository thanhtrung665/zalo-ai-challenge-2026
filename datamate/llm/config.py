"""Hồ sơ chạy LLM (configs/llm.yaml)."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "configs" / "llm.yaml"
SEED = 0


class LLMProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    backend: Literal["vllm", "hf"] = "vllm"
    dtype: Literal["bfloat16", "float16", "auto"] = "bfloat16"
    tensor_parallel_size: int = 1
    max_model_len: int = 16384
    gpu_memory_utilization: float = 0.85
    enable_prefix_caching: bool = True
    enforce_eager: bool = False
    quantization: str | None = None


def load_profile(name: str | None = None, path: Path | None = None) -> LLMProfile:
    """Đọc hồ sơ theo `name` → biến `DATAMATE_LLM_PROFILE` → `default_profile`."""
    cfg = yaml.safe_load((path or DEFAULT_CONFIG).read_text(encoding="utf-8"))
    chosen = name or os.environ.get("DATAMATE_LLM_PROFILE") or cfg["default_profile"]
    if chosen not in cfg["profiles"]:
        raise KeyError(f"không có hồ sơ LLM {chosen!r}; có: {sorted(cfg['profiles'])}")
    return LLMProfile.model_validate(cfg["profiles"][chosen])


def apply_overrides(
    profile: LLMProfile,
    *,
    tensor_parallel_size: int | None = None,
    dtype: str | None = None,
    max_model_len: int | None = None,
    gpu_memory_utilization: float | None = None,
    quantization: str | None = None,
) -> LLMProfile:
    """Ghi đè một vài tham số của hồ sơ (CLI của công cụ benchmark/smoke); giá trị None = giữ nguyên."""
    changes = {
        k: v
        for k, v in {
            "tensor_parallel_size": tensor_parallel_size,
            "dtype": dtype,
            "max_model_len": max_model_len,
            "gpu_memory_utilization": gpu_memory_utilization,
            "quantization": quantization,
        }.items()
        if v is not None
    }
    return LLMProfile.model_validate({**profile.model_dump(), **changes})


def add_override_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--tp", type=int, default=None, help="ghi đè tensor_parallel_size")
    ap.add_argument("--dtype", choices=["bfloat16", "float16", "auto"], default=None)
    ap.add_argument("--max-model-len", type=int, default=None)
    ap.add_argument("--gpu-util", type=float, default=None, help="gpu_memory_utilization")
    ap.add_argument("--quantization", default=None)


def profile_from_args(args: argparse.Namespace) -> LLMProfile:
    return apply_overrides(
        load_profile(args.profile),
        tensor_parallel_size=args.tp,
        dtype=args.dtype,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_util,
        quantization=args.quantization,
    )
