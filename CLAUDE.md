# CLAUDE.md — DataMate Agent

Dự án: agent trả lời câu hỏi tiếng Việt trên dữ liệu bảng của cửa hàng nhỏ, cho bảng **DataMate — Zalo AI Challenge 2026**.
Mục tiêu: Top 10 bảng chung cuộc (BTC chạy lại Docker trên private test), nhắm top 2.

## Đọc trước khi làm bất cứ việc gì

1. `SPEC.md` — đặc tả chuẩn (bài toán, luật chấm, ràng buộc, kiến trúc, từng tầng).
2. `PLAN.md` — danh sách task theo thứ tự, mỗi task có tiêu chí chấp nhận. **Luôn làm theo PLAN.md.**
3. `docs/PROGRESS.md` — nhật ký: đã làm gì, PA mới nhất, việc dở dang.
4. `docs/DATA_FINDINGS.md` — sự thật đã đo trên dữ liệu train của BTC (bẫy dữ liệu, hình dạng alias, luật đã kiểm bằng số).
5. Khi làm tầng nào, đọc thêm tài liệu của tầng đó: `docs/DSL.md`, `docs/CANONICAL_SCHEMA.md`.

Cách làm việc chuẩn: gõ `/next-step` để lấy task kế tiếp và thực hiện theo quy trình chuẩn.

## Luật cứng của cuộc thi (vi phạm = bị loại)

- **≤ 15B tham số** cho tổng mọi model dùng lúc inference. Kiểm bằng `uv run python -m datamate.tools.count_params <dirs...>`.
- **Offline hoàn toàn** lúc inference: không gọi API, không tải gì, không import `requests`/`httpx`/`openai`/`anthropic` trong `datamate/`.
- **Cấm** hard-code đáp án và **cấm** logic rẽ nhánh theo `business_id` (vd. `biz_118`) hay id câu hỏi (vd. `q_06de...`).
- **Cấm** dùng `public_test`/`private_test` để huấn luyện, gán nhãn, viết few-shot hay tinh chỉnh luật theo từng câu.
- `/data` là **read-only**; mọi file tạm ghi vào `/tmp` (hoặc `runs/`, `.cache/` khi dev).
- Mọi con số trong đáp án phải do **code** tính (executor/codegen), không để LLM tự nhẩm.
- Output phải **tất định**: temperature 0, seed cố định, thứ tự xử lý cố định.

## Lệnh

```bash
uv sync --extra dev --extra data     # môi trường dev + xử lý dữ liệu (thêm --extra llm trên máy GPU)
uv run python -m datamate.tools.inventory --split data/train --out runs/inventory/train.md
uv run python -m datamate.eval.folds --split data/train --out splits/folds.json   # đã chạy, đừng đổi seed
uv run python research/reference_checks.py --split data/train                    # phải in "Khớp 111/111"
make test                            # pytest toàn bộ
make lint                            # ruff check + ruff format --check
make compliance                      # quét vi phạm luật thi trong code runtime
uv run python -m datamate.eval.validate <submission.jsonl> --questions <questions.jsonl>
uv run python -m datamate.eval.scorer --pred <pred.jsonl> --gold data/train/answers.jsonl [--ids splits/fold_k.txt]
uv run python -m datamate.tools.count_params /models/main [/models/embed]
```

Dữ liệu đặt tại `data/train/`, `data/public_test/` (và `data/private_test/` sau 20/11). **Không sửa, không commit** dữ liệu gốc.

`research/` chứa code nghiên cứu (vd. `reference_checks.py`: 111 câu train tính tay khớp chuẩn). Không thuộc runtime, không vào image,
được phép nhắc tên shop cụ thể. **Không** import `research/` từ `datamate/`.

## Quy ước code

- Python 3.12, type hints đầy đủ, Pydantic v2 cho mọi cấu trúc trao đổi giữa các tầng, `ruff` format.
- Mỗi luật rulebook = một hàm có docstring trích mục rulebook (vd. `# rulebook §1 Doanh thu một đơn`) + ít nhất một test tính tay.
- Tiền là `int` (VND). Làm tròn bằng `decimal`, không dùng `round()` của float cho tiền.
- Không `print` trong thư viện; dùng `logging`. Log từng câu ở predict ghi JSON vào `logs/<id>.json`.
- Không bắt `Exception` rồi nuốt lỗi: lỗi ở một câu → câu đó abstain + log lỗi, không làm hỏng cả lần chạy.
- Test đặt trong `tests/`, đặt tên `test_<module>.py`; fixture dữ liệu nhỏ tự tạo trong `tests/fixtures/` (không copy dữ liệu thi).

## Quy trình mỗi thay đổi

1. Đọc task trong `PLAN.md` và tiêu chí chấp nhận.
2. Viết test trước (fixture tính tay) → cài đặt → `make test`.
3. Nếu thay đổi ảnh hưởng đáp án: chạy `/evaluate` trên các fold, so với baseline trong `docs/PROGRESS.md`. PA giảm → không merge.
4. Cập nhật checkbox trong `PLAN.md`, ghi một dòng vào `docs/PROGRESS.md`, quyết định thiết kế quan trọng ghi `docs/DECISIONS.md`.
5. Commit nhỏ, message dạng `T12: revenue + period compare (+0.04 PA)`.

## Khi không chắc

- Luật nghiệp vụ không rõ → đọc `data/<split>/rulebook.md` và README của shop; vẫn không rõ → hỏi người dùng, không đoán.
- Câu trả lời của hệ thống không chắc → **abstain** (0 điểm) tốt hơn đoán (−1 điểm).
- Không tự ý đổi model, kiến trúc, ngưỡng gate hay format output mà không ghi vào `docs/DECISIONS.md`.
