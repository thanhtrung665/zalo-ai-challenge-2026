---
name: status
description: Tóm tắt tình trạng dự án DataMate — task đã xong/còn lại, PA mới nhất, mốc gần nhất, rủi ro. Dùng khi người dùng hỏi tiến độ, "đang tới đâu", trước mỗi gate.
---

# /status

1. Đọc `PLAN.md`: đếm task `[x]`/`[ ]` theo giai đoạn; liệt kê task dở và task kế tiếp đủ điều kiện.
2. Đọc `docs/PROGRESS.md`: Baseline, 5 dòng nhật ký gần nhất, lần nộp public gần nhất.
3. Tính số ngày đến mốc gần nhất: G1 07/11, G2 13/11, nộp image 16/11 (form chỉ mở trong ngày), private 20–23/11.
4. Nếu đang ở một Gate: so tiêu chí gate với số liệu thực tế, kết luận **đạt / chưa đạt** kèm con số.
5. Rủi ro: task trễ so với ngày trong PLAN, PA giảm, chưa chạy thử Docker trên 5090, `MODELS.md` chưa chốt.

Trình bày ≤ 15 dòng: bảng tiến độ theo giai đoạn, PA, mốc, 1–3 rủi ro, đề xuất việc kế tiếp.
