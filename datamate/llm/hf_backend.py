"""Backend Transformers (dự phòng khi vLLM không chạy được, vd. GPU cũ hoặc bản vLLM không hỗ trợ phần cứng).

KHÔNG giải mã có ràng buộc: JSON sinh tự do rồi parse; lỗi quay về vòng sửa của tầng gọi. Chậm hơn vLLM rất nhiều.
Chỉ dùng để phát triển/benchmark; bản nộp dùng VLLMBackend (rule 40-llm: đầu ra có cấu trúc dùng giải mã ràng buộc).
"""

from __future__ import annotations

import time
from typing import Any

from datamate.llm.base import GenResult, LLMError, T, parse_result
from datamate.llm.config import SEED, LLMProfile
from datamate.llm.vllm_backend import extract_json


class HFBackend:
    def __init__(self, model_path: str, profile: LLMProfile, *, enable_thinking: bool = False) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as e:  # pragma: no cover
            raise LLMError(f"chưa cài transformers/torch: {e}") from e
        torch.manual_seed(SEED)
        self._torch = torch
        self._enable_thinking = enable_thinking
        dtype = {"bfloat16": torch.bfloat16, "float16": torch.float16, "auto": "auto"}[profile.dtype]
        self._tok = AutoTokenizer.from_pretrained(model_path, padding_side="left")
        if self._tok.pad_token is None:
            self._tok.pad_token = self._tok.eos_token
        kw: dict[str, Any] = {"torch_dtype": dtype, "device_map": "auto"}
        if profile.quantization == "bitsandbytes":
            from transformers import BitsAndBytesConfig

            kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
        try:
            self._model = AutoModelForCausalLM.from_pretrained(model_path, **kw)
        except Exception as e:  # noqa: BLE001 - OOM/CUDA/cấu hình; gói lại để tầng trên rơi về dự phòng
            raise LLMError(f"không nạp được model HF: {type(e).__name__}: {e}") from e
        self._model.eval()

    def _chat_text(self, prompt: str) -> str:
        msgs = [{"role": "user", "content": prompt}]
        try:
            return self._tok.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=True, enable_thinking=self._enable_thinking
            )
        except TypeError:
            return self._tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)

    def _gen(self, prompts: list[str], max_tokens: int, batch_size: int = 4) -> list[tuple[str, float | None, float]]:
        torch = self._torch
        rows: list[tuple[str, float | None, float]] = []
        for i in range(0, len(prompts), batch_size):
            chunk = [self._chat_text(p) for p in prompts[i : i + batch_size]]
            enc = self._tok(chunk, return_tensors="pt", padding=True).to(self._model.device)
            t0 = time.perf_counter()
            try:
                with torch.no_grad():
                    out = self._model.generate(
                        **enc,
                        max_new_tokens=max_tokens,
                        do_sample=False,
                        return_dict_in_generate=True,
                        output_scores=True,
                    )
            except Exception as e:  # noqa: BLE001
                raise LLMError(f"HF lỗi khi sinh: {type(e).__name__}: {e}") from e
            per = (time.perf_counter() - t0) / len(chunk)
            new = out.sequences[:, enc["input_ids"].shape[1] :]
            lps = self._model.compute_transition_scores(out.sequences, out.scores, normalize_logits=True)
            for j in range(new.shape[0]):
                mask = new[j] != self._tok.pad_token_id
                text = self._tok.decode(new[j][mask], skip_special_tokens=True)
                n = int(mask.sum())
                mean_lp = float(lps[j][mask].sum() / n) if n else None
                rows.append((text, mean_lp, per))
        return rows

    def generate_json(self, prompts: list[str], schema: type[T], *, max_tokens: int = 4096) -> list[GenResult]:
        return [
            parse_result(extract_json(text), schema, mean_logprob=lp, latency_s=lat)
            for text, lp, lat in self._gen(prompts, max_tokens)
        ]

    def generate_text(
        self, prompts: list[str], *, max_tokens: int = 1024, stop: list[str] | None = None
    ) -> list[GenResult]:
        out = []
        for text, lp, lat in self._gen(prompts, max_tokens):
            if stop:
                for s in stop:
                    text = text.split(s)[0]
            out.append(GenResult(text=text, mean_logprob=lp, latency_s=lat))
        return out
