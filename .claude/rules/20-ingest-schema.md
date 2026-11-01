---
paths:
  - "datamate/ingest/**"
  - "datamate/schema/**"
  - "datamate/entities/**"
---

# Nạp dữ liệu, schema chuẩn, thực thể

Đặc tả: SPEC §6.1–6.3, `docs/CANONICAL_SCHEMA.md`.

- Đọc CSV `dtype=str`; không để pandas tự suy kiểu rồi mất số 0 đầu mã hay biến ngày thành số.
- Header có thể ở dòng 2–4: luôn chạy bộ dò header; giữ preamble làm metadata (năm của sheet).
- Không bao giờ đổi null/không parse được thành 0. "Không có dữ liệu" khác "bằng 0" (rulebook §7).
- Fill-down chỉ cho cột cấp đơn ở các dòng tiếp nối của **cùng đơn** (rulebook §8). Dòng trùng hoàn toàn trong cùng đơn tính một lần;
  hai dòng giống nhau của hai đơn khác nhau tính cả hai; bảng không ghi theo đơn giữ mọi dòng.
- Không join thẳng `order_lines` với `payments` (cả hai nhiều dòng/đơn) — gộp theo `order_id` trước.
- Giữ cột truy vết `_src_file`, `_src_sheet`, `_src_row` cho mọi bảng.
- Mapping do LLM đề xuất phải qua validator bằng code; không tin mapping chưa kiểm.
- **Không** có mapping, ngoại lệ hay từ điển viết tay theo `business_id`. Quy tắc phải chạy được cho shop/ngành chưa từng thấy.
- Bản tên bỏ dấu chỉ dùng để tìm kiếm; đáp án luôn là tên nguyên văn trong dữ liệu (hoặc mã).
- **Gộp biến thể tên** cùng mặt hàng/khách trước mọi phép tính (khoảng trắng kép, bản không dấu — D-005). Ví dụ thật: "Coca Cola 330ml"
  và "Coca  Cola 330ml"; không gộp thì doanh thu mặt hàng sai.
- Số lượng = **số đầu tiên** trong ô; đơn vị có thể chứa số ("1 hộp 30", "1 bao 25kg"). Không nối các chữ số thành một số.
- README luôn có mốc "Dữ liệu có đến hết dd/mm/yyyy" và thường có bảng quy đổi "1 thùng = 24 lon": parse bằng regex (D-006) trước khi gọi LLM.
- Tên trạng thái khác nhau giữa các shop ("Xong", "Đổi trả", "Đã hoàn hàng", "Đang giao dịch"…): luôn map qua mapping, không so chuỗi cứng.
- Bằng chứng và ví dụ đầy đủ: `docs/DATA_FINDINGS.md`. Bộ hồi quy: `research/reference_checks.py` (111/111 câu khớp chuẩn).
- Trạng thái đơn chỉ có 4 loại: hoàn thành, huỷ, trả hàng, đang giao. Sổ không có cột trạng thái → đọc Ghi chú (rulebook public).
