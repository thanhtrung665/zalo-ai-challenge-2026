# DATA_FINDINGS — dữ liệu train thật (BTC phát hành)

Ngày phân tích: 31/10/2026. Nguồn: `train.zip` của BTC (186 MB giải nén). Báo cáo kiểm kê đầy đủ: `uv run python -m datamate.tools.inventory`.
Đây là bằng chứng cho các quyết định D-003…D-006 trong `docs/DECISIONS.md`.

## 1. Tóm tắt

- **Cách hiểu rulebook đã được xác nhận bằng số:** tự tính tay 111 câu ở 2 shop có định dạng rất khác nhau (biz_101 CSV phẳng; biz_102 Excel
  chia sheet theo tháng, ô số lượng lẫn chữ) → **111/111 khớp tuyệt đối** với đáp án chuẩn. Script: `research/reference_checks.py`.
- **Tên hàng có biến thể trong cùng shop** (vd. "Coca Cola 330ml" và "Coca  Cola 330ml" hai dấu cách): phải gộp trước khi tính,
  nếu không doanh thu mặt hàng sai (đã gặp: 428.000 thay vì 2.726.000).
- **Scorer đã khớp đáp án thật** (T02): gold tự chấm = 1,0; toàn abstain = 0; thay mọi tên bằng mã/alias và đảo hàng table = 1,0.
  Đã sửa một lỗi: alias của **table** là theo từng hàng (trước đó scorer bỏ qua).
- **Mọi file đọc được** bằng python-calamine / csv / sqlite3 (30 shop, 339 bảng/sheet, ~4 triệu dòng vật lý), không lỗi.

## 2. Cấu trúc split (đúng như SPEC §2.1)

```
train/  rulebook.md · calendar.csv (2024-01-01..2027-12-31, cột date, weekday, lunar_day, lunar_month, lunar_year, lunar_leap, holiday)
        questions.jsonl (3.000) · answers.jsonl (3.000, mọi dòng có id, type, answer, alias)
        data/biz_101 … biz_130/  (*.csv | *.xlsx | *.sqlite + README.md)
```

Rulebook train trùng nguyên văn bản đã phân tích trước đó. 21 file csv, 107 xlsx, 1 sqlite.

| Ngành (suy từ từ khoá, chỉ để chia fold) | Số shop |
|---|---|
| Tạp hoá | 6 |
| Cà phê | 5 |
| Vật liệu xây dựng | 6 |
| Nhà thuốc | 6 |
| Nhà hàng / quán nhậu | 6 |
| Không rõ (biz_110: chỉ có danh sách hoá đơn, không có dòng hàng) | 1 |

Shop có 40 câu (biz_101, 107, 110, 113, 114, 125, 126) là shop **một file phẳng**; shop có 118–119 câu là shop nhiều file/bảng.

## 3. Đáp án (answers.jsonl)

| Kiểu | Số câu | Đặc điểm đã đo |
|---|---|---|
| number | 1.884 | **100% là số nguyên** (kể cả trung bình mỗi đơn — đã làm tròn về đồng). 2 câu = 0, 2 câu âm (chênh lệch) |
| percent | 578 | float 2 chữ số; 136 câu âm; lớn nhất 391,3; 2 câu = 0 |
| list | 193 | 106 list tên (3, 5 hoặc 11 phần tử); 87 list số dài 2–3 (vd. tồn theo đơn vị lớn `[thùng, lẻ]`, nhiều số đo theo thứ tự câu hỏi) |
| date | 145 | 129 dạng `YYYY-MM-DD`, 16 dạng `YYYY-MM` |
| string | 88 | 42 có alias |
| unanswerable | 70 | `"answer": null` |
| boolean | 23 | 10 true / 13 false |
| table | 19 | đều dạng `{"columns": ["khach_hang", "so_tien_no"], ...}` (top khách nợ) |

**Hình dạng `alias` (xác nhận):**
- string: list phẳng — mã + mọi cách viết khác có trong dữ liệu, vd. `["SP0076", "Costar Omega 3 1000 mg lọ 100 viên"]`.
- list tên: list-các-list theo vị trí, vd. `[["SP0001"], ["SP0027", "Ong PVC Binh Minh D32 cay 4m"]]`.
- table: list-các-list **theo hàng**, áp cho ô tên, vd. `[["KH0124"], ["KH0056", "Luu Ha An"]]`.
- Các kiểu khác: `[]`.

Hệ quả: dữ liệu đôi khi có cả bản viết không dấu của tên hàng/khách; scorer nhận bản đó vì nó nằm trong alias. Hệ thống nên trả **tên chuẩn
(dạng có dấu, xuất hiện nhiều nhất) hoặc mã** — cả hai đều được chấm đúng.

## 4. Câu hỏi

- `as_of_date` từ 2025-01-15 đến 2026-09-20. **79% câu có as_of = mốc "Dữ liệu có đến hết" trong README**, 21% sớm hơn
  (thường là câu "hôm nay/hôm qua"); **không câu nào sau mốc**. Với as_of sớm hơn, phải bỏ bản ghi sau as_of (rulebook đầu văn bản).
- Biểu thức thời gian (đếm thô, một câu có thể nhiều): "tháng M/Y" 1.866 · có năm 420 · so sánh/tăng/giảm 231 · ngày cụ thể 216 ·
  hôm nay 189 · tháng này 152 · tuần trước 114 · hôm qua 91 · quý 81 · ca sáng/chiều 77 · tháng trước 65 · N ngày gần nhất 46 ·
  tuần này 19 · Tết 5 · tháng không ghi năm 4.
- Nhóm intent (gắn nhãn thô bằng từ khoá, có chồng lấn): doanh thu ~760 · số đơn/khác ~880 · xếp hạng ~280 · huỷ/trả ~240 · giá ~180 ·
  khách ~180 · tồn kho ~130 · công nợ ~115 · nhập hàng ~115 · số lượng ~55 · lãi/giá vốn ~25 · hạn dùng ~20 · nhân viên ~15.
  → **Doanh thu, số đơn, xếp hạng, tỉ lệ huỷ** là phần lớn điểm: làm chắc các nhóm này trước (T12).
- Văn phong: không dấu, viết tắt (dthu, bnhiu, hqua, sp, dc), gõ sai (`thangs`, `tawng/giamr`, `naof`, `vaayj`), xưng hô ("e", "ê", "check giùm").

**Câu unanswerable (70)** — mọi câu đều có as_of = mốc README. Hai dạng:
1. Kỳ hỏi nằm **trước khi shop có dữ liệu** (vd. "tháng 2/2025" ở shop bắt đầu muộn hơn) → cần biết **ngày bắt đầu** dữ liệu từ chính dữ liệu.
2. Shop **không ghi loại thông tin** đó: địa chỉ khách, đánh giá/khen nhân viên, "lành nghề", giá vốn, phiếu nhập, hạn dùng ở quán cà phê,
   tồn kho theo đơn vị lớn khi không có bảng quy đổi…

## 5. README

- Cả 30 README có `## File`, `## Quy ước` và câu **"Dữ liệu có đến hết dd/mm/yyyy"** → parse bằng regex, không cần LLM.
- 18 README ghi **bảng quy đổi đơn vị dạng văn bản** (`- Coca Cola 330ml: 1 thùng = 24 lon`) → parse bằng regex thành `unit_conversions`.
  Các shop khác có file quy đổi riêng (vd. `DanhSachQuyDoi.xlsx`) hoặc cột "Quy ra ĐV lẻ" trong file bán.
- Mục `## Cột trong <file>` mô tả nghĩa từng cột ở phần lớn shop: đầu vào chính cho schema mapping.
- README nói rõ quan hệ file ("nối với các danh sách sản phẩm qua tên sản phẩm", "thông tin đơn lặp lại ở mọi dòng của đơn",
  "danh sách dài tách thành nhiều file đuôi _1, _2 hoặc _2025, _2026", "mỗi tháng một sheet, tên sheet ghi tháng và năm").

## 6. Bẫy dữ liệu đã thấy tận mắt

| Bẫy | Ví dụ thật | Cách xử lý |
|---|---|---|
| Header không ở dòng 1 | biz_118: 3 dòng tiêu đề ("SỔ CHI TIẾT BÁN HÀNG", "Kỳ báo cáo: toàn bộ", dòng trống) trước header | Bộ dò header (T04) |
| Ô số lượng lẫn chữ | biz_102: `"1 chai"`, `"10 hộp"`, `"1 kg"` cạnh `"2.0"` | Lấy **số đầu tiên** |
| **Đơn vị chứa số** | biz_102: `"1 hộp 30"`, `"1 bao 25kg"` (đơn vị là "hộp 30", "bao 25kg") | Không ghép các chữ số; khớp đơn vị với bảng quy đổi |
| Tiền lẫn định dạng | `"38,000"` cạnh `"20000"`; biz_118 `"65,000.0000"` | Parser tiền tiếng Việt (T05) |
| Ngày tiếng Việt | biz_101: `"1 thg 6 2025"` | Parser ngày (T05) |
| Tên trạng thái khác nhau theo shop | biz_101: Xong / Đã hủy / **Đổi trả** / Đang giao · biz_102: Đã hoàn thành / Đã hủy / **Đã hoàn hàng** / Đang giao dịch | Map về 4 trạng thái chuẩn (T10) |
| Khách lẻ ghi nhiều kiểu | `"Khách lẻ"`, `"lẻ"` | Map về null (khách vãng lai) |
| **Biến thể tên cùng mặt hàng** | biz_101: `"Coca Cola 330ml"` (1.531 dòng) và `"Coca  Cola 330ml"` (144 dòng); alias đáp án có bản không dấu | Gộp theo khoá bỏ dấu + gộp khoảng trắng; hiển thị cách viết phổ biến nhất (T13) |
| Sổ chia sheet theo tháng | biz_102 `T01_2025`…`T06_2026`; biz_118 `T02-2025`… | Gộp sheet cùng cột (T04) |
| File tách theo phần | `_1`, `_2`, `_2026` | Gộp file cùng cột (T04) |
| Cột rác | biz_118: `Hình ảnh (url1,url2...)`, `Vị trí`, `Trọng lượng` | Mapping bỏ qua |

## 7. Kiểm chứng tính tay (research/reference_checks.py)

| Shop | Định dạng | Nhóm câu kiểm | Khớp |
|---|---|---|---|
| biz_101 | 1 CSV phẳng, ngày "thg", có cột "Quy ra ĐV lẻ" | 13 dạng câu | 111/111 (cả hai shop) |
| biz_102 | Excel 18 sheet theo tháng + file quy đổi, SL lẫn chữ | (như trên) | |

Dạng câu đã kiểm (số câu): doanh thu tháng (20) · trung bình mỗi đơn (13) · số đơn hôm qua (12) · số đơn bị huỷ trong tháng (12) ·
doanh thu hôm qua (10) · ngày doanh thu cao nhất (9) · doanh thu một mặt hàng (9) · số kg một mặt hàng (8) · doanh thu hôm nay (7) ·
bán chạy top-1/3/5 (6) · số đơn hôm nay (4) · số đơn quý (1).

Luật đã được số liệu xác nhận:
- bỏ **cả đơn** có dòng huỷ hoặc trả; giữ đơn đang giao; kỳ theo ngày đặt;
- doanh thu = Σ thành tiền dòng (sau giảm giá dòng);
- **số đơn huỷ** đếm đơn có trạng thái huỷ, **không** gồm đơn trả hàng;
- bán chạy theo SL quy về đơn vị cơ bản (hệ số từ file quy đổi hoặc cột quy đổi sẵn);
- trung bình mỗi đơn = doanh thu / số đơn hợp lệ, làm tròn về đồng (nửa đồng lên);
- "hôm qua" = as_of − 1 ngày; "hôm nay" = đúng ngày as_of;
- gộp biến thể tên hàng trước khi tính.

Chưa kiểm bằng số (việc của T12/T16): tie-break theo mã, công nợ, kho, giá vốn, luật ngành, so sánh kỳ, Tết.
