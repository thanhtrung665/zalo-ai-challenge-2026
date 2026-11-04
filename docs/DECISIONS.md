# DECISIONS — nhật ký quyết định kiến trúc

Mỗi quyết định: ngày, bối cảnh, lựa chọn, lý do, hệ quả. Mới nhất ở trên.

## D-008 · 2026-11-04 · Mở rộng schema chuẩn và bộ đề xuất mapping heuristic

- Bối cảnh: map 30 shop train lộ ra dữ liệu mà schema ban đầu không có chỗ chứa: giao nhiều đợt, hạn công nợ, lịch sử giá, bán theo lô kèm
  số lượng trả lại, phiếu trả hàng, số đã trả/còn nợ ghi trên đơn. Rulebook train có luật cho cả những thứ này.
- Lựa chọn: thêm `sale_lots, returns, deliveries, debt_terms, price_history` và `orders.paid_amount/debt_amount` (xem CANONICAL_SCHEMA.md).
  Thêm `schema/propose.py` (từ vựng tên cột + mô tả README, không LLM) làm bản nháp cho prompt, phương án dự phòng và mốc đo.
- Số đo: 104/356 (29%) tên cột của public_test không có trong train → từ vựng cố định chỉ là prior yếu; LLM là bộ phận chính.
- Bẫy dữ liệu đã bắt được nhờ validator: cột mã đơn "Mã đơn hàng" bị loại nhầm vì chứa "hàng" (T05, lỗi ở `grouping.py`);
  dòng "Tổng ngày dd/mm" xen trong sổ tự ghi (không có trong README); cache ghi đè bảng cùng tên.
- **Chưa được kiểm độc lập:** `research/mappings/*.json` là bản nháp heuristic được tôi đọc lướt, không phải đáp án chuẩn đã duyệt. Độ đúng thật
  chỉ đo được ở T12 (doanh thu/số lượng khớp `answers.jsonl`). Trạng thái "Không giao được" tạm map `cancelled`, "hàng trả về" ⇒ `returned`,
  "ok" ⇒ `completed`; cần kiểm bằng câu train ở T12.
- Không hand-label shop của public_test (ranh giới luật thi); mapping chuẩn chỉ cho shop train.

## D-007 · 2026-11-04 · Quy ước timeutil cho kỳ so sánh và Tết

- Bối cảnh: DSL §3 định nghĩa `previous_period` = kỳ liền trước cùng độ dài (riêng `this_month`: cùng số ngày của tháng trước).
- Lựa chọn: làm đúng chữ DSL. Hệ quả: `last_month`/`month` so sánh với 28–31 ngày liền trước, **không** phải tháng dương lịch liền trước.
  `this_month` cắt ở cuối tháng trước nếu hôm nay là ngày 29–31. Tết không dựa cột `lunar_year`: bắt cặp 23/12 với 10/1 (không nhuận) kế tiếp;
  `tet` không ghi năm = Tết gần nhất đã bắt đầu. `all`/`as_of_end_of_day` cần `data_start` do caller truyền.
- Rủi ro cần kiểm khi có `rulebook.md`/câu train so sánh kỳ (T12): nếu rulebook nói "tháng trước" là tháng dương lịch thì sửa riêng cho `last_month`/`month`.

## D-006 · 2026-10-31 · Parse README bằng regex trước khi gọi LLM

- Bối cảnh: cả 30 README có `## File`, `## Quy ước`, "Dữ liệu có đến hết dd/mm/yyyy"; 18 README ghi quy đổi dạng "1 thùng = 24 lon".
- Lựa chọn: `schema/readme.py` trích bằng regex: mốc dữ liệu, bảng quy đổi văn bản, danh sách file, mô tả từng cột. Kết quả đưa vào prompt
  mapping và Capabilities. LLM chỉ dùng cho phần mô tả tự do.
- Hệ quả: mốc dữ liệu và quy đổi đơn vị tất định, không phụ thuộc LLM. Nếu README split mới khác mẫu → rơi về LLM, không lỗi.

## D-005 · 2026-10-31 · Gộp biến thể tên và lấy số lượng là số đầu tiên

- Bằng chứng: biz_101 có "Coca Cola 330ml" và "Coca  Cola 330ml" (hai dấu cách) — không gộp thì doanh thu mặt hàng sai (428.000 thay vì
  2.726.000). biz_102 có ô số lượng "1 hộp 30", "1 bao 25kg" (đơn vị chứa số).
- Lựa chọn: khoá thực thể = bỏ dấu + chữ thường + gộp khoảng trắng; tên hiển thị = cách viết phổ biến nhất (hoặc mã nếu có).
  Số lượng = số **đầu tiên** trong ô; phần còn lại là tên đơn vị, khớp với bảng quy đổi.
- Rủi ro: hai mặt hàng khác nhau chỉ khác dấu sẽ bị gộp nhầm — kiểm bằng cảnh báo khi một khoá gom > 1 mã hàng khác nhau.

## D-004 · 2026-10-31 · Fold theo shop, ngành suy từ từ khoá

- `datamate/eval/folds.py` → `splits/folds.json`: tập khoá biz_108, biz_115, biz_123 (355 câu); 5 fold 512–552 câu, mỗi fold đủ 5–6 ngành.
- Ngành suy từ README + câu hỏi train (6 tạp hoá, 5 cà phê, 6 VLXD, 6 nhà thuốc, 6 nhà hàng, 1 không rõ). Nhãn chỉ dùng cho fold/
  kịch bản bỏ ngành, **không** dùng lúc inference.

## D-003 · 2026-10-31 · Hình dạng alias và scorer

- Xác nhận trên answers.jsonl: string → list phẳng; list tên → list-các-list theo vị trí; table → list-các-list **theo hàng** (áp cho ô tên);
  kiểu khác → []. Unanswerable có `"answer": null`.
- Sửa scorer: áp alias theo hàng cho table (trước đó bỏ qua → chấm sai khi trả mã khách trong bảng). Thêm test với dữ liệu dạng thật.
- Kiểm chứng: gold tự chấm 1,0; toàn abstain 0; tên→mã + đảo hàng 1,0; lỗi định dạng điển hình đều bị chấm sai.

## D-001 · 2026-10-27 · Kiến trúc lai: DSL + executor + codegen + gate

- Bối cảnh: ~82% đáp án là số khớp tuyệt đối; PA phạt −1 khi sai; private có ngành và luật mới; giới hạn ≤ 15B, offline.
- Lựa chọn: LLM chỉ hiểu câu hỏi/dữ liệu (DSL, mapping, codegen); mọi con số do code tính; cổng abstain hiệu chỉnh trên holdout chia theo shop.
- Lý do: text-to-SQL tự do bằng model ≤ 15B trên dữ liệu bẩn khó khớp tuyệt đối; executor có test tính tay cho độ chính xác cao và tất định.
- Hệ quả: phải đầu tư mạnh vào schema mapping và thư viện luật; câu ngoài DSL đi codegen hoặc abstain.

## D-002 · 2026-10-27 · Thước đo chính là PA holdout chia theo shop

- Leaderboard public không kiểm cách tạo file → không phản ánh hệ thống offline ≤ 15B. Chỉ dùng để đo lệch phân phối.

## Mẫu

```
## D-XXX · YYYY-MM-DD · <tiêu đề>
- Bối cảnh:
- Lựa chọn:
- Lý do (số liệu, run):
- Hệ quả:
```
