# Luật thi — luôn áp dụng

Nguồn: SPEC.md §3–§4 (tóm tắt luật chính thức của BTC). Vi phạm bất kỳ mục nào có thể bị loại.

1. **Tham số:** tổng mọi model dùng lúc inference ≤ 15B (LLM + embedding + reranker + classifier; MoE tính đủ; vision encoder có trong
   weights cũng tính). Trước khi thêm bất kỳ model nào, chạy `count_params` và cập nhật `MODELS.md`.
2. **Ngày phát hành và giấy phép:** weights công khai trước 01/10/2026, giấy phép cho phép dùng. Ghi link model card vào `MODELS.md`.
3. **Offline:** code trong `datamate/`, `prompts/`, `configs/`, `docker/`, `predict.sh` không được gọi mạng, không tải model/dữ liệu,
   không import thư viện HTTP hay SDK LLM thương mại. Weights nằm sẵn trong image.
4. **Không hard-code:** không có literal `business_id` (vd. `biz_118`) hay id câu hỏi trong code runtime; không rẽ nhánh theo tên shop.
   Luật phải tổng quát, suy ra từ dữ liệu + README + rulebook lúc chạy.
5. **Dữ liệu test:** không dùng `public_test`/`private_test` để huấn luyện, viết few-shot, chỉnh prompt theo từng câu, hay gán nhãn tay.
   Được phép: đọc **rulebook** và **cấu trúc file** của public_test để làm loader/luật tổng quát; chạy pipeline để nộp leaderboard.
6. **Read-only:** `/data` (và `data/` khi dev) chỉ đọc. File tạm ghi vào `/tmp`, `runs/`, `.cache/`.
7. **Tất định:** temperature 0, seed cố định, thứ tự xử lý cố định; mọi nguồn ngẫu nhiên phải có seed.
8. **Đầu ra:** `submission.jsonl` ghi và flush **từng dòng**; log từng câu (id, đáp án, thời gian, DSL, code, output) vào `logs/`.
9. **Thời gian:** private ~500 câu ≤ 6 giờ gồm load model; mục tiêu ≤ 2 giờ; watchdog 5h30 → abstain phần còn lại.
10. **Abstain khi không chắc:** sai = −1, abstain = 0. `unanswerable` chỉ khi có bằng chứng cứng (thiếu khái niệm trong dữ liệu
    hoặc kỳ nằm hoàn toàn ngoài khoảng dữ liệu).

Nếu một yêu cầu của người dùng hoặc của task có vẻ vi phạm các mục trên: dừng lại, nói rõ mục bị vi phạm, đề xuất cách tuân thủ.
