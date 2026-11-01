---
paths:
  - "datamate/**/*.py"
  - "scripts/**/*.py"
  - "tests/**/*.py"
---

# Quy ước Python

- Python ≥ 3.11, `from __future__ import annotations`, type hints cho mọi hàm public.
- Cấu trúc trao đổi giữa các tầng dùng Pydantic v2 (`model_config = ConfigDict(frozen=True)` khi có thể).
- Tiền VND là `int`. Làm tròn bằng `decimal.Decimal(...).quantize(..., rounding=ROUND_HALF_UP)`; không dùng `round()` float cho tiền.
- Không `print` trong thư viện — dùng `logging.getLogger(__name__)`. `print` chỉ ở CLI (`if __name__ == "__main__"`).
- Không `except Exception: pass`. Lỗi ở một câu hỏi → câu đó abstain + ghi lỗi vào log câu đó.
- Hàm thuần, không trạng thái toàn cục ẩn; cấu hình đọc từ `configs/*.yaml` qua `datamate/config.py`.
- Mỗi module mới có file test tương ứng trong `tests/`; fixture nhỏ tự tạo trong `tests/fixtures/`, **không** copy dữ liệu thi vào repo.
- Chạy `make lint` và `make test` trước khi báo xong.
