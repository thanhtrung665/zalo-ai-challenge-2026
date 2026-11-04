# PROGRESS — nhật ký tiến độ

Mỗi task xong hoặc mỗi lần đo PA thêm một dòng **ở đầu bảng** (mới nhất trên cùng).

## Baseline hiện tại

| Chỉ số | Giá trị | Run | Ngày |
|---|---|---|---|
| PA trung bình 5 fold | — | — | — |
| Coverage / precision | — / — | — | — |
| PA tập khoá (chỉ ở G1, G2) | — | — | — |
| PA public leaderboard | — | — | — |
| Thời gian / câu | — | — | — |

## Nhật ký

| Ngày | Task | Thay đổi | PA 5 fold | Ghi chú |
|---|---|---|---|---|
| 2026-11-04 | T09 (chuẩn bị) | `datamate/llm` (giao diện batch, VLLM/HF/mock, hồ sơ phần cứng + ghi đè CLI), `tools/{llm_bench,hardware,model_check}`, `scripts/{fetch_model,llm_smoke,env_report}.py`, `remote/` (setup, dữ liệu, tải model, smoke, bench; chạy qua SSH/tmux); 332 test | — | T09 chưa tick: code GPU mới được test bằng vllm giả; cần chạy trên máy thuê. Bỏ gói Kaggle (D-009) |
| 2026-11-04 | T10 (phần lớn) | `propose/prompt/mapper/mapping_report`, backend LLM giả + giao diện; schema +6 bảng (D-008); sửa `detect_order_id_column` (T05) và dòng tổng ngày; 30 shop train build không lỗi nặng; ~330 test | — | T10 chưa tick: cần LLM thật (T09), review của người dùng, đo độ đúng ở T12 |
| 2026-11-04 | T10 (một phần) | `datamate/schema/{canonical,mapping,profile,build,validate}.py` + `research/mappings/` (3 shop) + `research/build_check.py`; 21 test | — | Build khớp số dòng gốc trên biz_101/102/109; validator bắt được lỗi bản thân (NA→"na", đơn vị trong ô SL). Còn LLM prompt/retry |
| 2026-11-04 | T05 | Sửa lỗi cache ghi đè bảng cùng tên (T04); đo lại parse trên dữ liệu đúng: train 0/10,54M, public 37/4,23M | — | Số liệu parse đo trước đó bị loại bỏ (đo trên cache hỏng). Việc dở: lọc dòng ghi chú cuối bảng + header lặp ở T10 |
| 2026-11-04 | T05/T06 | Đo parse trên train + public_test thật; sửa `parse_report` (đếm lỗi bị cắt ở 200, tổng ô cộng dồn, cột `(ngày)` là số ngày); predict trên public_test hợp lệ 1000/1000 | — | Hoàn thành T05, T06 (chờ nộp thử leaderboard). Dữ liệu giải nén ở /tmp vì `data/` bị chặn ghi |
| 2026-11-04 | T11 | `datamate/timeutil/` (periods, calendar/Tết, ca, kỳ so sánh), 93 test tính tay | — | Hoàn thành T11 |
| 2026-11-04 | T06 | `datamate/predict.py` + `datamate/io/`: abstain toàn bộ, ghi/flush từng dòng, log từng câu, watchdog 5h30; 4 test | — | Chưa tick: cần chạy trên public_test thật + nộp thử |
| 2026-11-01 | T04 | `datamate/ingest/` (readers, header, tables, cache, loader) + `datamate/schema/readme.py` (D-006) | — | Hoàn thành T04, 46 tests pass |
| 2026-11-01 | T00 | Khởi tạo môi trường: `uv sync`, `make test`, `make lint`, `make compliance` exit 0, git init | — | Hoàn thành T00 |
| 2026-10-31 | — | Bộ kiểm tham chiếu `research/reference_checks.py`: 111/111 câu (biz_101, biz_102) khớp tuyệt đối | — | Xác nhận cách hiểu rulebook; thành test hồi quy |
| 2026-10-31 | T03 | `splits/folds.json`: khoá biz_108/115/123 (355 câu), 5 fold 512–552 câu | — | D-004 |
| 2026-10-31 | T02 | Scorer áp alias theo hàng cho table; kiểm trên answers.jsonl thật | — | D-003 |
| 2026-10-31 | T01 | `datamate/tools/inventory.py`; 30 shop, 339 bảng, 0 lỗi đọc; `docs/DATA_FINDINGS.md` | — | Dữ liệu train BTC |
| 2026-10-27 | — | Khởi tạo bộ khung dự án | — | — |

## Nộp leaderboard public

| Ngày giờ | Commit | PA public | PA 5 fold cùng commit | Ghi chú |
|---|---|---|---|---|

## Nộp image

| Lần | Ngày giờ | Link Drive | SHA-256 | Commit |
|---|---|---|---|---|
