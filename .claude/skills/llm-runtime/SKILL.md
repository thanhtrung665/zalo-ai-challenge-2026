---
name: llm-runtime
description: Hướng dẫn xây lớp LLM của DataMate (vLLM offline, giải mã JSON có ràng buộc, tất định, backend mock) và benchmark chọn model trong giới hạn 15B tham số. Dùng cho task T09, khi đổi model, hoặc khi gặp lỗi vLLM/CUDA.
---

# /llm-runtime

Đặc tả: SPEC §7, `.claude/rules/40-llm.md`, `MODELS.md`.

## Giao diện

```python
class LLMBackend(Protocol):
    def generate_json(self, prompts: list[str], schema: type[BaseModel], *, max_tokens: int) -> list[GenResult]: ...
    def generate_text(self, prompts: list[str], *, max_tokens: int, stop: list[str] | None = None) -> list[GenResult]: ...

@dataclass
class GenResult:
    text: str
    parsed: BaseModel | None
    mean_logprob: float | None   # feature cho gate
    latency_s: float
```

- `VLLMBackend`: `vllm.LLM(model=..., dtype="bfloat16", seed=0, tensor_parallel_size=..., max_model_len=16384,
  gpu_memory_utilization=0.85, enable_prefix_caching=True)`; `SamplingParams(temperature=0, top_p=1, logprobs=1, ...)` với structured output
  JSON theo schema (tên tham số theo đúng phiên bản vLLM đã ghim). Qwen3.5: tắt thinking qua chat template (`enable_thinking=False`);
  chạy chỉ phần ngôn ngữ nếu bản vLLM hỗ trợ (`--language-model-only`).
- `MockBackend`: trả kết quả từ dict cố định → dùng trong test, không cần GPU.
- Gọi theo **batch** (mọi câu của một shop một lượt) và theo thứ tự cố định.

## Benchmark chọn model (T09)

1. Tải weights trên máy dev (được phép tải lúc phát triển), lưu `models/<tên>/`. Ghi link model card, giấy phép, ngày phát hành.
2. `uv run python -m datamate.tools.count_params models/<tên>` — ghi số vào `MODELS.md`. Tổ hợp vượt 15B → loại.
3. Đo trên schema mapping 5 shop: tỉ lệ JSON hợp lệ, độ đúng mapping (so review tay), thời gian, VRAM đỉnh.
4. Ở T14 đo thêm trên NLU 200 câu dev: tỉ lệ DSL đúng (so nhãn thực thi), PA end-to-end.
5. Chọn model, ghi `docs/DECISIONS.md` kèm bảng số liệu.

## Sự cố RTX 5090 / Blackwell thường gặp

- Cần CUDA ≥ 12.8 và bản PyTorch/vLLM có kernel sm_120. Lỗi "no kernel image" → sai bản build.
- Lỗi attention backend → thử backend FlashInfer hoặc FlashAttention 2 (FA3 không hỗ trợ Blackwell tiêu dùng).
- Ghi lại tổ hợp phiên bản chạy được vào `docs/DECISIONS.md` và ghim trong Dockerfile.
