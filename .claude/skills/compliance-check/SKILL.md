---
name: compliance-check
description: Rà soát toàn diện việc tuân thủ luật thi DataMate trước khi nộp (tham số, giấy phép, offline, hard-code, dữ liệu test, Docker, log, tái lập, thời gian). Dùng cho task T42, trước mỗi lần build image nộp, hoặc khi người dùng hỏi "có vi phạm gì không".
---

# /compliance-check

Chạy lần lượt, ghi kết quả từng mục (ĐẠT / CHƯA ĐẠT + bằng chứng) vào `runs/compliance-<ngày>.md`.

## Tự động

1. `make compliance` — không được có vi phạm.
2. `uv run python -m datamate.tools.count_params <mọi thư mục model trong image>` — tổng ≤ 15.000.000.000.
3. `grep -rn "temperature" datamate/ prompts/ configs/` — mọi giá trị dùng lúc inference = 0.
4. `docker run --rm --gpus all --network none -v <public_test>:/data:ro -v ./result:/result <image>` — chạy hết, exit 0.
5. `uv run python -m datamate.eval.validate result/submission.jsonl --questions <public_test>/questions.jsonl` — hợp lệ, đủ id, không trùng.
6. Có `result/logs/` với một file cho mỗi id, chứa id, đáp án, thời gian.
7. Chạy lần 2 cùng image → so hai `submission.jsonl`: số câu khác nhau < 1%.

## Thủ công (kiểm bằng đọc)

8. `MODELS.md` đủ cột; link model card mở được; ngày phát hành < 01/10/2026; giấy phép cho phép dùng.
9. README trong image: mô tả giải pháp, bảng model, lệnh chạy, cách huấn luyện lại.
10. Image chứa mã huấn luyện (`training/`, `scripts/label_dsl.py`) + inference + weights + `predict.sh`.
11. Không có file dữ liệu public/private test trong image hay repo (`git ls-files | grep -E "public_test|private_test"` rỗng).
12. Không có few-shot/nhãn sinh từ câu test (`artifacts/` chỉ chứa id train).
13. Thời gian toàn bộ public test và ước tính cho private ≤ 3 giờ; watchdog đã test.

Nhờ subagent `compliance-reviewer` đọc lại diff từ lần nộp trước và đối chiếu SPEC §4. Mục nào CHƯA ĐẠT → không build bản nộp.
