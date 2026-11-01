---
name: public-submit
description: Chuẩn bị file submission.jsonl cho leaderboard public của DataMate từ đúng pipeline offline, kiểm tra hợp lệ và ghi nhật ký. Dùng khi người dùng muốn nộp leaderboard public.
disable-model-invocation: true
---

# /public-submit

Mục đích: đo độ lệch giữa holdout và public — **không** để tối ưu điểm public.

1. Xác nhận commit hiện tại đã có kết quả `/evaluate dev` (để so sánh). Chưa có → chạy trước.
2. `/evaluate public` → `runs/<run>/submission.jsonl` (pipeline offline, model ≤ 15B, đúng cấu hình sẽ đóng gói).
3. `uv run python -m datamate.eval.validate runs/<run>/submission.jsonl --questions data/public_test/questions.jsonl` — phải hợp lệ, đủ id.
4. Thống kê: số câu trả lời / unanswerable / abstain theo kiểu đáp án.
5. Đưa đường dẫn file cho người dùng tự upload trên portal (giới hạn 5 lần/ngày; dùng 1–2 lần).
6. Sau khi người dùng báo điểm: ghi vào bảng "Nộp leaderboard public" trong `docs/PROGRESS.md` (ngày giờ, commit, PA public, PA 5 fold).
   PA public thấp hơn PA 5 fold > 0,10 → chạy `/error-analysis` tập trung vào ngành/luật mới của public (đọc rulebook public, không đọc câu hỏi để chỉnh từng câu).

Tuyệt đối không dùng output của mô hình/API ngoài, không sửa tay bất kỳ dòng nào trong file nộp.
