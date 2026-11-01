---
name: build-ingest
description: Hướng dẫn chi tiết xây tầng nạp và làm sạch dữ liệu DataMate (CSV/XLSX/SQLite, dò header, preamble, gộp sheet, parse số/ngày tiếng Việt, fill-down, dedupe). Dùng cho task T04, T05 hoặc khi lỗi nhóm `ingest`.
---

# /build-ingest

Đặc tả: SPEC §6.1, `.claude/rules/20-ingest-schema.md`.

## Thiết kế module

```
datamate/ingest/
├── readers.py      # read_csv_raw, read_xlsx_raw (calamine), read_sqlite_raw → list[RawSheet] (ma trận chuỗi + metadata)
├── header.py       # detect_header(rows) -> HeaderGuess(row_index, score, preamble)
├── numbers.py      # parse_vn_number(s) -> int | float | None
├── dates.py        # parse_vn_date(s, *, sheet_year, number_format) -> date | datetime | None
├── grouping.py     # detect_order_level_columns, fill_down, dedupe_within_order
├── tables.py       # assemble(RawSheet...) -> RawTable (gộp sheet cùng cột, cột _src_*)
└── cache.py        # parquet cache theo sha256 file
```

## Từng bước

1. `readers.py`: đọc thành **ma trận chuỗi** (chưa có header). XLSX: calamine cho giá trị; openpyxl `read_only=True` để lấy `number_format`
   của ô trong các cột nghi là ngày (chỉ đọc ~50 dòng đầu mỗi cột). SQLite: `sqlite3.connect(f"file:{p}?mode=ro", uri=True)`.
2. `header.py`: với mỗi dòng trong 12 dòng đầu, điểm = 0,4·(tỉ lệ ô chữ không phải số) + 0,3·(tỉ lệ ô khác nhau) + 0,3·(tỉ lệ ô khớp
   từ vựng cột trong `configs/column_vocab.yaml`). Dòng điểm cao nhất là header; dòng trên là preamble. Header 2 tầng (ô gộp) → nối tên.
3. `numbers.py` — test tối thiểu: `"1.250.000"→1250000`, `"1,250,000"→1250000`, `"1.250.000đ"→1250000`, `"1.250.000 VND"`, `"(50.000)"→-50000`,
   `"-50.000"`, `"12,5"→12.5`, `"12.5"→12.5`, `"1.5"` (ngữ cảnh SL) → 1.5, `""→None`, `"abc"→None`, `"1tr2"` → None (không đoán).
4. `dates.py` — test: serial `45658`→2025-01-01, serial dạng chuỗi `"45658"`, `"01/02/2026"`→1/2 (ngày trước tháng), `"2026-02-01"`,
   `"1 thg 2, 2026"`, `"01/02"` + sheet_year, datetime có giờ, giá trị ngoài khoảng 2015–2030 → None + cảnh báo.
5. `grouping.py`: cột cấp đơn = cột mà ô trống xuất hiện **đúng** ở các dòng có mã đơn trống/lặp → fill-down trong nhóm;
   dedupe chỉ trong nhóm đơn; bảng không có cột mã đơn → không fill, không dedupe.
6. `tables.py`: gộp sheet có cùng tập cột (sau chuẩn hoá tên) — sheet theo tháng, file theo năm.
7. `datamate/tools/inventory.py` dùng các module trên để in báo cáo mỗi shop.

## Chấp nhận

Theo PLAN T04/T05: 100% file đọc được; ≥ 40 test parser; tỉ lệ không parse < 0,5% trên cột đã nhận diện; không null nào thành 0.
