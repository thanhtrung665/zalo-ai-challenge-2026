# prompts/

Template prompt có phiên bản, dùng bởi `datamate/llm`, `datamate/schema`, `datamate/nlu`, `datamate/codegen`.

Quy ước:
- Mỗi file một prompt: `schema_mapping.v1.md`, `nlu_dsl.v1.md`, `codegen.v1.md`. Đổi nội dung đáng kể → tăng phiên bản, giữ bản cũ đến khi so sánh xong.
- Phần cố định (vai trò, đặc tả, schema) đặt **đầu**; phần thay đổi theo câu hỏi đặt **cuối** (tận dụng prefix cache của vLLM).
- Ví dụ few-shot chỉ lấy từ train (`artifacts/dsl_labels.jsonl`), không viết tay từ câu hỏi public/private.
- Không chứa `business_id`, tên shop cụ thể hay đáp án cụ thể (hook kiểm tra tự động).
