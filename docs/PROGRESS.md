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
