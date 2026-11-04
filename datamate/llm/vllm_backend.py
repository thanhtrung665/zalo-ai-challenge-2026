"""Backend vLLM offline: temperature 0, seed cố định, giải mã JSON có ràng buộc theo schema Pydantic.

vLLM chỉ import khi tạo backend (máy không GPU vẫn import được gói `datamate.llm`).
Tên tham số structured output đổi theo phiên bản vLLM (`structured_outputs` mới, `guided_decoding` cũ): dò lúc chạy.
Phiên bản chạy được trên từng phần cứng phải ghim ở Dockerfile và ghi docs/DECISIONS.md.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from datamate.llm.base import GenResult, LLMError, T, parse_result
from datamate.llm.config import SEED, LLMProfile

logger = logging.getLogger(__name__)


def _mean_logprob(out: Any) -> float | None:
    """Trung bình logprob mỗi token của lời giải; None nếu vLLM không trả."""
    cum = getattr(out, "cumulative_logprob", None)
    n = len(getattr(out, "token_ids", []) or [])
    if cum is not None and n:
        return float(cum) / n
    lps = getattr(out, "logprobs", None)
    if not lps:
        return None
    vals: list[float] = []
    for tok, d in zip(out.token_ids, lps, strict=False):
        lp = d.get(tok) if isinstance(d, dict) else None
        if lp is not None:
            vals.append(float(getattr(lp, "logprob", lp)))
    return sum(vals) / len(vals) if vals else None


class VLLMBackend:
    def __init__(self, model_path: str, profile: LLMProfile, *, enable_thinking: bool = False) -> None:
        try:
            import vllm
            from vllm import SamplingParams
        except ImportError as e:  # pragma: no cover - nhánh này chỉ xảy ra khi thiếu vLLM
            raise LLMError(f"chưa cài vLLM (uv sync --extra llm): {e}") from e

        self._SamplingParams = SamplingParams
        self._structured_cls, self._structured_kw = self._detect_structured_api()
        self._enable_thinking = enable_thinking
        kwargs: dict[str, Any] = {
            "model": model_path,
            "dtype": profile.dtype,
            "seed": SEED,
            "tensor_parallel_size": profile.tensor_parallel_size,
            "max_model_len": profile.max_model_len,
            "gpu_memory_utilization": profile.gpu_memory_utilization,
            "enable_prefix_caching": profile.enable_prefix_caching,
            "enforce_eager": profile.enforce_eager,
            "trust_remote_code": False,
        }
        if profile.quantization:
            kwargs["quantization"] = profile.quantization
        try:
            self._llm = vllm.LLM(**kwargs)
        except Exception as e:  # noqa: BLE001 - vLLM ném nhiều loại lỗi (CUDA, OOM, cấu hình); gói lại để tầng trên rơi về dự phòng
            raise LLMError(f"không khởi tạo được vLLM: {type(e).__name__}: {e}") from e

    @staticmethod
    def _detect_structured_api() -> tuple[Any, str]:
        try:
            from vllm.sampling_params import StructuredOutputsParams

            return StructuredOutputsParams, "structured_outputs"
        except ImportError:
            from vllm.sampling_params import GuidedDecodingParams

            return GuidedDecodingParams, "guided_decoding"

    def _params(self, max_tokens: int, schema: type[T] | None, stop: list[str] | None) -> Any:
        kw: dict[str, Any] = {
            "temperature": 0.0,
            "top_p": 1.0,
            "seed": SEED,
            "max_tokens": max_tokens,
            "logprobs": 1,
            "stop": stop,
        }
        if schema is not None:
            kw[self._structured_kw] = self._structured_cls(json=schema.model_json_schema())
        return self._SamplingParams(**kw)

    def _run(self, prompts: list[str], params: Any) -> list[tuple[str, float | None, float]]:
        messages = [[{"role": "user", "content": p}] for p in prompts]
        t0 = time.perf_counter()
        try:
            outs = self._llm.chat(
                messages,
                params,
                use_tqdm=False,
                chat_template_kwargs={"enable_thinking": self._enable_thinking},
            )
        except Exception as e:  # noqa: BLE001 - xem ghi chú ở __init__
            raise LLMError(f"vLLM lỗi khi sinh: {type(e).__name__}: {e}") from e
        per = (time.perf_counter() - t0) / max(1, len(prompts))
        return [(o.outputs[0].text, _mean_logprob(o.outputs[0]), per) for o in outs]

    def generate_json(self, prompts: list[str], schema: type[T], *, max_tokens: int = 4096) -> list[GenResult]:
        rows = self._run(prompts, self._params(max_tokens, schema, None))
        return [parse_result(text, schema, mean_logprob=lp, latency_s=lat) for text, lp, lat in rows]

    def generate_text(
        self, prompts: list[str], *, max_tokens: int = 1024, stop: list[str] | None = None
    ) -> list[GenResult]:
        rows = self._run(prompts, self._params(max_tokens, None, stop))
        return [GenResult(text=text, mean_logprob=lp, latency_s=lat) for text, lp, lat in rows]


def extract_json(text: str) -> str:
    """Lấy đoạn JSON object ngoài cùng (dùng cho backend không giải mã có ràng buộc)."""
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b <= a:
        return text
    candidate = text[a : b + 1]
    try:
        json.loads(candidate)
    except ValueError:
        return text
    return candidate
