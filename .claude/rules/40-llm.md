---
paths:
  - "datamate/llm/**"
  - "datamate/nlu/**"
  - "datamate/codegen/**"
  - "prompts/**"
---

# LLM, NLU, codegen

Đặc tả: SPEC §6.4, §6.6, §7.

- Mọi lời gọi LLM đi qua `datamate/llm` (một backend vLLM offline + một backend mock cho test). Không gọi vLLM trực tiếp ở nơi khác.
- Sampling mặc định: `temperature=0`, `top_p=1`, `seed=0`. Chế độ thinking **tắt** cho mapping và DSL.
- Đầu ra có cấu trúc luôn dùng giải mã có ràng buộc theo JSON schema sinh từ Pydantic; parse lại bằng Pydantic, lỗi → retry tối đa 1 lần rồi abstain.
- Prompt đặt trong `prompts/*.md` (template), có phiên bản; phần chung (đặc tả, schema shop) đặt **đầu** prompt để tận dụng prefix cache.
- Few-shot chỉ lấy từ **train** (`artifacts/dsl_labels.jsonl`); khi đánh giá theo fold, few-shot không được lấy từ shop trong fold đang chấm.
- LLM không tính số và không quy đổi ngày: chỉ điền DSL hoặc viết code gọi thư viện luật.
- Codegen chạy trong sandbox (tiến trình con, timeout 20 s, giới hạn bộ nhớ, AST guard). Không `exec` code LLM trong tiến trình chính.
- Log đầy đủ prompt id, phiên bản prompt, output thô, thời gian cho từng lời gọi.
- Đổi model hoặc thêm model: chạy `count_params`, cập nhật `MODELS.md`, ghi `docs/DECISIONS.md`.
