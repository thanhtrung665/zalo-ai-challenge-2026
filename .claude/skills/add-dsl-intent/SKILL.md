---
name: add-dsl-intent
description: Thêm metric, entity, period kind hoặc trường mới vào DSL câu hỏi của DataMate, đồng bộ Pydantic schema, prompt, few-shot, executor và tài liệu. Dùng khi câu hỏi không biểu diễn được bằng DSL hiện tại (DSL ra `custom`) và nhóm câu đủ lớn.
argument-hint: "[tên metric/intent]"
---

# /add-dsl-intent

1. **Chứng minh nhu cầu:** đếm số câu train (và tỉ lệ ước tính) cần intent `$ARGUMENTS`; < 10 câu → để codegen xử lý, không thêm.
2. Thiết kế: tên enum, tham số, định nghĩa theo rulebook (mục nào), kiểu đáp án. Kiểm tra không trùng nghĩa với metric có sẵn.
3. Cập nhật đồng bộ, theo thứ tự:
   1. `docs/DSL.md` (bảng metric/period + ví dụ),
   2. `datamate/nlu/dsl.py` (Pydantic + JSON schema cho giải mã có ràng buộc),
   3. executor (dùng `/implement-rule` cho luật),
   4. `prompts/` (mô tả ngắn + 1 ví dụ trong đặc tả DSL),
   5. nhãn DSL: chạy lại `scripts/label_dsl.py` cho các câu liên quan.
4. Test: Pydantic round-trip; executor trên fixture; NLU trên 10 câu train mẫu (dùng backend thật nếu có GPU, mock nếu không).
5. `/evaluate dev` — intent mới phải không làm giảm PA tổng.
6. Ghi `docs/DECISIONS.md` (vì sao thêm, phạm vi).
