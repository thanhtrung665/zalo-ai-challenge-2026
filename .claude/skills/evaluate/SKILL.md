---
name: evaluate
description: Chạy pipeline DataMate trên các fold holdout chia theo shop, chấm bằng scorer chính thức, so với baseline và ghi báo cáo. Dùng sau mọi thay đổi ảnh hưởng đáp án, khi người dùng hỏi "PA bao nhiêu", hoặc ở gate.
argument-hint: "[dev|locked|fold:<k>|public]"
---

# /evaluate

Đối số `$ARGUMENTS`: `dev` (mặc định — 5 fold), `fold:<k>`, `locked` (tập khoá — **chỉ ở gate G1/G2**), `public` (tạo file nộp, không chấm).

## Quy trình

1. Kiểm tra cây làm việc sạch hoặc ghi `git diff --stat` vào báo cáo; lấy `gitsha` ngắn.
2. Tạo thư mục `runs/<YYYYMMDD-HHMM>-<gitsha>-<mode>/`.
3. Chạy pipeline trên câu hỏi của tập chọn (train questions lọc theo `splits/folds.json`):
   - Khi chạy fold k: few-shot, nhãn DSL, gate **không** được dùng dữ liệu của shop trong fold k.
   - Ghi `predictions.jsonl` + `logs/`.
4. Validate: `uv run python -m datamate.eval.validate <run>/predictions.jsonl --questions <questions đã lọc>`.
5. Chấm: `uv run python -m datamate.eval.scorer --pred <run>/predictions.jsonl --gold data/train/answers.jsonl --ids <ids> --report <run>/report.md`.
6. So với Baseline trong `docs/PROGRESS.md`: ΔPA, Δcoverage, Δprecision; theo kiểu đáp án và theo intent (từ log DSL).
7. Liệt kê 10 câu **sai có độ tin cậy cao nhất** (nguy hiểm nhất) trong báo cáo.
8. Ghi một dòng vào `docs/PROGRESS.md`. Chỉ cập nhật Baseline khi PA 5 fold tăng và người dùng/task chấp nhận thay đổi.

## Chế độ `public`

Chạy pipeline trên `data/public_test`, validate, lưu `runs/.../submission.jsonl`. Không chấm (không có đáp án). Dùng `/public-submit` để nộp.

## Lưu ý

- Không bao giờ dùng kết quả `locked` để chỉnh luật/prompt — chỉ để xác nhận gate.
- Báo PA với 3 chữ số thập phân; luôn kèm số câu N.
