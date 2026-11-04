# MODELS — khai báo model dùng lúc inference

Bắt buộc theo luật thi (Rule 2): mọi model dùng lúc inference phải được khai báo trong README của giải pháp, tổng tham số ≤ 15B,
weights công khai trước 01/10/2026, giấy phép cho phép sử dụng. Bảng này được copy vào README của image ở T42.

Số tham số lấy từ `uv run python -m datamate.tools.count_params <thư mục weights>` (đọc header safetensors, tính mọi tensor kể cả vision encoder).

| Vai trò | Model | Link | Giấy phép | Ngày phát hành | Số tham số (count_params) | Lượng tử hoá | Fine-tune |
|---|---|---|---|---|---|---|---|
| LLM chính | _chưa chốt (T09)_ | | | | | | |
| Embedding (tuỳ chọn) | | | | | | | |
| **Tổng** | | | | | **≤ 15.000.000.000** | | |

Ứng viên (SPEC §7): Qwen3.5-9B (~10B, Apache-2.0), Qwen3-14B (~14,8B, Apache-2.0), Qwen2.5-Coder-14B-Instruct (~14,7B, Apache-2.0),
multilingual-e5-small (~118M, MIT).

> **Trạng thái 04/11/2026:** chưa chốt model, chưa đo số nào. Tên repo Hugging Face là dự kiến (`configs/models.yaml`). Giấy phép, ngày tạo và
> số tham số sẽ do `scripts/fetch_model.py` lấy từ HfApi và `count_params` (ghi vào `models/<tên>/MODEL_INFO.json`). Không điền vào bảng trên
> khi chưa có số đó.
