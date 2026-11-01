---
name: error-analysis
description: Phân tích lỗi của một lần chạy đánh giá DataMate — gắn nhãn nguyên nhân cho câu sai, gom nhóm, ước lượng PA thu hồi được, đề xuất việc sửa theo thứ tự ưu tiên. Dùng sau /evaluate hoặc khi PA giảm.
argument-hint: "[runs/<run-dir>]"
context: fork
agent: error-analyst
---

# /error-analysis

Đầu vào: thư mục run `$ARGUMENTS` (mặc định: run mới nhất trong `runs/`).

1. Đọc `report.md`, `predictions.jsonl`, gold tương ứng, và `logs/<id>.json` của các câu sai.
2. Lấy tối đa 40 câu sai, ưu tiên câu có độ tin cậy gate cao nhất (sai mà tự tin), rồi câu thuộc intent nhiều lỗi nhất.
3. Với mỗi câu, xác định **một** nguyên nhân gốc:
   `ingest` (đọc/parse sai) · `mapping` (map cột sai/thiếu) · `entity` (link sai thực thể) · `nlu` (DSL sai metric/period/filter/rank) ·
   `time` (quy đổi kỳ sai) · `rule` (luật executor sai so với rulebook) · `format` (kiểu/làm tròn) · `gate` (nên abstain) ·
   `unanswerable` (nhầm có/không trả lời được) · `gold?` (nghi đáp án chuẩn khác cách hiểu — ghi lý do).
4. Tính lại tay **ít nhất 3 câu** để xác nhận nguyên nhân (truy vấn DuckDB/pandas trực tiếp trên CanonicalStore).
5. Gom nhóm: số câu, ΔPA ước tính nếu sửa (mỗi câu sai → đúng = +2/N; sai → abstain = +1/N).
6. Viết `<run>/error_analysis.md`: bảng nhóm lỗi xếp theo ΔPA, 2–3 ví dụ mỗi nhóm, đề xuất sửa cụ thể (file, hàm), rủi ro hồi quy.

Không sửa code trong skill này — chỉ phân tích và đề xuất.
