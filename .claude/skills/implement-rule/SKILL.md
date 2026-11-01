---
name: implement-rule
description: Hiện thực một luật nghiệp vụ trong rulebook (doanh thu, thời gian, xếp hạng, công nợ, kho, giá vốn, luật ngành) vào executor DataMate theo quy trình test-trước và đối chiếu với câu hỏi train. Dùng khi thêm hoặc sửa một luật, hoặc khi error-analysis chỉ ra lỗi nhóm `rule`.
argument-hint: "[mục rulebook, vd. '§4 Tuổi nợ']"
---

# /implement-rule

Đối số: luật cần làm `$ARGUMENTS`.

1. **Đọc nguyên văn** luật trong `data/train/rulebook.md` và `data/public_test/rulebook.md`. Ghi lại khác biệt giữa hai bản (nếu có).
   Luật ngành thắng luật chung khi mâu thuẫn.
2. **Diễn giải** luật thành các điều kiện kiểm được (bảng: điều kiện → hệ quả). Liệt kê ca biên: đơn huỷ, đơn trả một phần, đơn đang giao,
   bản ghi sau as_of, khách lẻ, đơn vị lớn, bằng nhau khi xếp hạng, kỳ ngoài dữ liệu.
3. **Test trước** trong `tests/executor/test_<nhóm>.py`: fixture DataFrame nhỏ tự tạo (5–20 dòng) phủ các ca biên;
   đáp án tính tay **từng bước** trong comment.
4. **Cài đặt** trong `datamate/executor/rules/<nhóm>.py` (hoặc `industry_<ngành>.py`): một hàm thuần, docstring trích mục rulebook.
   Dùng `datamate/timeutil` cho mọi kỳ; tiền `int`; làm tròn bằng `decimal`.
5. **Đăng ký** luật vào bảng tra của executor và cập nhật hash trong `configs/implemented_rules.yaml`.
6. **Đối chiếu train**: lọc câu train có liên quan (từ khoá + nhãn DSL nếu có), chạy executor với DSL đúng, so gold.
   Tỉ lệ đúng < 95% → mở `/error-analysis` cho tập câu này, sửa, lặp lại.
7. Nhờ subagent `rules-auditor` rà lại hàm vừa viết so với nguyên văn rulebook (đưa đường dẫn file + mục rulebook).
8. `make test`, `make lint`, `make compliance` xanh; ghi PROGRESS.
