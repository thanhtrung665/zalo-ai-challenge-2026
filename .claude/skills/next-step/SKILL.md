---
name: next-step
description: Lấy task kế tiếp trong PLAN.md và thực hiện trọn vẹn theo quy trình chuẩn của dự án DataMate (đọc spec, test trước, cài đặt, đánh giá, cập nhật tiến độ). Dùng khi người dùng gõ /next-step, "làm tiếp", "task tiếp theo".
argument-hint: "[Txx — tuỳ chọn, chỉ định task]"
disable-model-invocation: true
---

# /next-step — làm task kế tiếp

Đối số: `$ARGUMENTS` (nếu có, là mã task như `T12`; nếu trống, tự chọn).

## Bước 1 — Định vị

1. Đọc `PLAN.md`, `docs/PROGRESS.md` (phần Baseline + 5 dòng nhật ký mới nhất).
2. Chọn task:
   - Có `$ARGUMENTS` → task đó (kiểm tra phụ thuộc đã `[x]`; chưa → báo và dừng).
   - Không có → task `[ ]` **đầu tiên** mà mọi phụ thuộc đã `[x]`.
   - Nếu task kế tiếp nằm sau một **Gate** chưa được người dùng xác nhận → chạy `/status`, trình bày kết quả gate và **dừng** chờ duyệt.
3. Nhắc lại cho người dùng (≤ 6 dòng): mã task, mục tiêu, tiêu chí chấp nhận, skill chuyên biệt liên quan (nếu PLAN ghi).

## Bước 2 — Chuẩn bị

1. Đọc mục SPEC tương ứng và tài liệu liên quan (`docs/DSL.md`, `docs/CANONICAL_SCHEMA.md`, rulebook của split).
2. Nếu PLAN ghi skill chuyên biệt (vd. `/implement-rule`) → đọc `.claude/skills/<tên>/SKILL.md` và theo quy trình đó.
3. Lập kế hoạch ngắn: file sẽ tạo/sửa, test sẽ viết, cách đo chấp nhận. Task lớn (> ~300 dòng code) → chia bước con, làm từng bước.
4. Có điểm mơ hồ ảnh hưởng thiết kế (luật nghiệp vụ, format, model) → hỏi người dùng **một lần, gộp câu hỏi**, rồi làm.

## Bước 3 — Thực hiện

1. Viết test trước (fixture nhỏ tự tạo, đáp án tính tay có giải thích).
2. Cài đặt tối thiểu cho test pass; tuân thủ `.claude/rules/*`.
3. `make test` và `make lint` phải xanh. `make compliance` phải sạch.
4. Nếu thay đổi ảnh hưởng đáp án của pipeline → chạy `/evaluate` (fold dev) và so với baseline.
   PA giảm > 0,005 mà không có lý do chấp nhận được → không coi là xong; phân tích bằng `/error-analysis`.

## Bước 4 — Kiểm chấp nhận

Đi qua **từng** tiêu chí Chấp nhận của task, ghi bằng chứng (lệnh đã chạy, con số). Thiếu bất kỳ tiêu chí nào → task chưa xong,
ghi rõ phần còn thiếu vào PROGRESS và báo người dùng.

## Bước 5 — Ghi nhận

1. Tick `[x]` task trong `PLAN.md` (chỉ khi đạt đủ).
2. Thêm một dòng ở đầu bảng nhật ký `docs/PROGRESS.md`: ngày, task, thay đổi, PA 5 fold (nếu đo), ghi chú. Cập nhật Baseline nếu PA tốt hơn.
3. Quyết định thiết kế mới → thêm mục `docs/DECISIONS.md`.
4. `git add` các file liên quan và commit: `Txx: <tóm tắt> (<thay đổi PA nếu có>)`.

## Bước 6 — Báo cáo

Trả lời người dùng ngắn gọn: task đã xong (hoặc phần còn thiếu), bằng chứng chấp nhận, PA mới (nếu có), task kế tiếp dự kiến.
Không tự động làm task tiếp theo — chờ người dùng gõ `/next-step` lần nữa.
