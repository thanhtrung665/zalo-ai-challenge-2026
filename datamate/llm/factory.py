"""Tạo backend từ hồ sơ phần cứng."""

from __future__ import annotations

from datamate.llm.base import LLMBackend
from datamate.llm.config import LLMProfile, load_profile


def create_backend(model_path: str, profile: LLMProfile | str | None = None) -> LLMBackend:
    prof = profile if isinstance(profile, LLMProfile) else load_profile(profile)
    if prof.backend == "vllm":
        from datamate.llm.vllm_backend import VLLMBackend

        return VLLMBackend(model_path, prof)
    from datamate.llm.hf_backend import HFBackend

    return HFBackend(model_path, prof)
