# DataMate Agent — Zalo AI Challenge 2026

Bộ khung dự án để lập trình cùng Claude (Claude Code) trong Antigravity cho bảng **DataMate**.
Kế hoạch gốc: tài liệu "DataMate — Chiến lược Top 10 & vào chung kết".

## Bắt đầu

1. Mở thư mục này trong Antigravity; cài extension **Claude Code** (hoặc chạy `claude` trong terminal tích hợp) và đăng nhập.
2. Cài [uv](https://docs.astral.sh/uv/) rồi: `uv sync --extra dev --extra data`.
3. `git init && git add . && git commit -m "init: DataMate kit"`.
4. Giải nén dữ liệu: `data/train/`, `data/public_test/` (giữ nguyên cấu trúc của BTC; thư mục `data/` đã bị git ignore).
5. Trong Claude Code, gõ **`/next-step`**. Claude đọc `PLAN.md`, chọn task kế tiếp, làm theo quy trình, rồi báo kết quả.
   Lặp lại `/next-step` cho đến hết. Ở mỗi gate (G0, G1, G2) Claude sẽ dừng để bạn duyệt.

## Bộ khung gồm gì

| Đường dẫn | Vai trò |
|---|---|
| `CLAUDE.md` | Bộ nhớ dự án Claude đọc mỗi phiên: luật cứng, lệnh, quy ước, quy trình |
| `SPEC.md` | Đặc tả kỹ thuật chuẩn |
| `PLAN.md` | Task theo thứ tự, tiêu chí chấp nhận, gate |
| `MODELS.md` | Khai báo model (bắt buộc khi nộp) |
| `docs/DSL.md`, `docs/CANONICAL_SCHEMA.md` | Đặc tả DSL câu hỏi và schema chuẩn |
| `docs/PROGRESS.md`, `docs/DECISIONS.md` | Nhật ký tiến độ và quyết định |
| `.claude/settings.json` | Quyền công cụ + hooks |
| `.claude/rules/` | Luật theo vùng code (tự nạp khi Claude chạm file khớp `paths`) |
| `.claude/skills/` | Quy trình từng loại việc: `/next-step`, `/evaluate`, `/implement-rule`, `/error-analysis`, … |
| `.claude/agents/` | Subagent kiểm tra độc lập: `rules-auditor`, `compliance-reviewer`, `error-analyst` |
| `.claude/hooks/` | Hook chặn vi phạm luật thi (hard-code id, gọi mạng) và thao tác phá dữ liệu |
| `datamate/eval/` | Scorer theo luật chấm chính thức + validator file nộp (đã có, có test) |
| `datamate/tools/count_params.py` | Đếm tham số từ safetensors |
| `scripts/check_compliance.py` | Quét vi phạm luật thi trong code runtime |

## Skills có sẵn

| Lệnh | Khi dùng |
|---|---|
| `/next-step` | Làm task kế tiếp trong PLAN.md (dùng hằng ngày) |
| `/status` | Tóm tắt tiến độ, PA, task dở, rủi ro |
| `/evaluate` | Chạy đánh giá trên fold, so baseline, ghi báo cáo |
| `/error-analysis` | Phân loại lỗi của một lần chạy, đề xuất việc sửa |
| `/implement-rule` | Hiện thực một luật rulebook vào executor (test trước) |
| `/add-dsl-intent` | Thêm metric/intent mới vào DSL |
| `/build-ingest`, `/build-schema-mapping`, `/build-codegen`, `/llm-runtime` | Hướng dẫn chi tiết cho từng tầng |
| `/calibrate-gate` | Hiệu chỉnh ngưỡng abstain |
| `/finetune-lora` | Gán nhãn DSL bằng thực thi + LoRA |
| `/compliance-check` | Rà soát tuân thủ trước khi nộp |
| `/docker-release` | Build, kiểm tra, đóng gói image |
| `/public-submit` | Chuẩn bị và kiểm file nộp leaderboard |

## Lưu ý

- Hook chỉ chạy khi có `python3` trong PATH. Trên Windows, sửa lệnh trong `.claude/settings.json` thành `python`.
- Đây là khung + quy trình; phần lớn mã nguồn sẽ được Claude viết dần theo `PLAN.md`.
- Khi thông tin chính thức của BTC thay đổi (hướng dẫn Docker, giải đáp), cập nhật `SPEC.md` và ghi `docs/DECISIONS.md`.
