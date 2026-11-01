---
paths:
  - "datamate/eval/**"
  - "datamate/gate/**"
  - "splits/**"
  - "runs/**"
---

# Đánh giá và gate

Đặc tả: SPEC §3, §6.7, §8.

- Scorer phải đúng luật chấm chính thức; mọi thay đổi scorer cần test mới. Không "nới" scorer để điểm đẹp hơn.
- Holdout chia **theo shop**; không để cùng một shop nằm ở cả dữ liệu dùng để chỉnh (few-shot, nhãn DSL, gate) và fold đang chấm.
- Tập khoá chỉ chấm ở gate G1, G2. Ghi mỗi lần chấm vào `docs/PROGRESS.md`.
- Ngưỡng gate τ học trên **out-of-fold**; báo cáo cả kịch bản bỏ một ngành; chọn τ thận trọng khi hai kết quả lệch nhau.
- Mỗi lần chạy lưu `runs/<YYYYMMDD-HHMM>-<gitsha>/` (predictions, logs, report.md). Không ghi đè run cũ.
- So sánh chỉ hợp lệ khi cùng tập câu và cùng scorer. Báo cáo PA, coverage, precision theo intent và kiểu đáp án.
