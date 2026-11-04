"""Hồ sơ chạy LLM (configs/llm.yaml)."""

from __future__ import annotations

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
