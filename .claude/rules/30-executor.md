---
paths:
  - "datamate/executor/**"
  - "datamate/timeutil/**"
  - "datamate/rulebook/**"
---

# Executor, thời gian, rulebook

Đặc tả: SPEC §6.5, §6.8, `docs/DSL.md`. Nguồn sự thật nghiệp vụ: `data/<split>/rulebook.md` của split đang chạy.

- Mỗi luật = một hàm, docstring ghi **mục rulebook** (vd. `rulebook §4 Nợ một đơn tại ngày X`) và tóm tắt luật bằng lời của mình.
- Viết test **trước**: fixture nhỏ tự tạo, đáp án tính tay ghi trong comment (từng bước), rồi mới cài đặt.
- Đơn hợp lệ cho doanh thu/SL/số đơn: không huỷ và không trả (trả một phần cũng loại cả đơn); đơn đang giao vẫn tính; kỳ theo ngày đặt.
- Bỏ bản ghi có ngày sau `as_of_date`, trừ trạng thái huỷ/trả ghi trên đơn.
- Bằng nhau khi xếp hạng → theo **mã tăng dần** (không có mã thì theo tên). Ít hơn k ứng viên → trả tất cả.
- Thời gian luôn qua `datamate/timeutil`; cấm tự tính tuần/tháng/Tết rải rác trong executor.
- Phần trăm thay đổi so với kỳ trước, giảm ra số âm; chênh lệch = kỳ hỏi − kỳ so; % và trung bình (không phải tiền) làm tròn 2 chữ số.
- Thiếu khái niệm trong Capabilities → trả `Unanswerable(reason=...)`, không trả 0.
- Luật ngành đặt trong `executor/rules/industry_<ngành>.py`; luật ngành thắng luật chung khi mâu thuẫn.
- Khi thêm/sửa một luật, cập nhật hash trong `configs/implemented_rules.yaml` để bộ diff rulebook biết luật đã được hiện thực.
- Nếu rulebook của split mới khác rulebook train ở một luật đã hiện thực: không sửa đè, thêm tham số/biến thể và chọn theo nội dung rulebook lúc chạy.
