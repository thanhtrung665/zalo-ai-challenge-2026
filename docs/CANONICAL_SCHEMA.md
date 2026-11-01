# Schema chuẩn (CanonicalStore)

Mọi shop được map về các bảng dưới đây (`datamate/schema/canonical.py`, Pydantic + DataFrame). Cột không có trong dữ liệu shop thì **vắng mặt**
(không điền giá trị giả) và được ghi `False` trong `Capabilities`. Kiểu: `str`, `int` (tiền VND, số đếm), `float` (SL lẻ), `date`, `datetime`, `bool`.

## Bảng

### products
| Cột | Kiểu | Ghi chú |
|---|---|---|
| product_code | str | Khoá; không có mã thì sinh mã ổn định từ tên chuẩn hoá (ghi `code_synthetic=True`) |
| product_name | str | Tên nguyên văn (giữ mọi biến thể tên trong `product_aliases`) |
| product_group | str | Nhóm hàng đúng như file |
| base_unit | str | Đơn vị cơ bản |
| catalog_cost | int | Giá vốn 1 đơn vị cơ bản trong danh mục (dùng cho giá trị tồn kho) |
| is_for_resale | bool | Hàng mua về để bán (khác món pha chế/chế biến) |
| is_prescription | bool | Nhà thuốc: thuốc kê đơn |
| active_ingredient | str | Nhà thuốc: hoạt chất, giữ nguyên chuỗi |
| extra | dict | Thuộc tính ngành: size, số sữa, hãng, dòng máy… |

### product_aliases
`product_code, alias` — mọi cách viết tên xuất hiện trong dữ liệu (để nhận diện và để đáp án khớp alias).

### unit_conversions
`product_code, unit, factor_to_base` — đơn vị không có dòng quy đổi là đơn vị cơ bản, hệ số 1.

### orders
| Cột | Kiểu | Ghi chú |
|---|---|---|
| order_id | str | Khoá |
| order_datetime | datetime | Ngày (giờ nếu có) đặt — quyết định kỳ |
| status | enum | `completed, cancelled, returned, delivering` (đơn có trả một phần → `returned`) |
| customer_code | str? | Null = khách lẻ / vãng lai |
| customer_name | str? | Tên ghi trên đơn |
| customer_group | str? | Nhóm khách |
| payment_method | str? | Theo hình thức ghi trên đơn (tiền mặt, chuyển khoản, ghi nợ, COD…) |
| channel | str? | Tại quầy, sàn TMĐT, … |
| order_discount | int | Giảm giá cấp đơn / voucher (không trừ vào doanh thu) |
| shipping_fee | int | Phí giao |
| vat | int | |
| order_total | int? | Số khách phải trả cả đơn, nếu file có |
| staff | str? | Nhân viên bán / thợ |
| branch | str? | |
| note | str? | Ghi chú gốc |
| return_date | date? | Nếu có phiếu trả |

### order_lines
`order_id, line_no, product_code, quantity, unit, quantity_base, unit_price, line_discount, line_amount, line_cost_per_unit, is_service_fee`
— `line_amount` = thành tiền đã trừ giảm giá dòng; `line_cost_per_unit` = giá vốn ghi trên dòng (cho **một đơn vị bán**); `is_service_fee` = dòng "Phí phục vụ".

### payments
`order_id, pay_date, amount, method` — mọi khoản trả, kể cả trả ngay lúc mua và trả nợ sau.

### purchases
`receipt_id, receipt_date, supplier, product_code, quantity, unit, unit_cost, amount, status, batch_no, expiry_date, is_opening_stock`.

### stock_movements (nếu shop có sổ kho riêng)
`date, product_code, qty_in_base, qty_out_base, reason, batch_no`.

### expenses
`date, category, amount`.

### domain_events
Bảng mở cho ngành đặc thù, mỗi loại một `event_type`: `repair_ticket` (biển số, dòng xe, việc làm, thợ, bảo hành), `warranty`,
`installment` (kỳ góp, hạn, đã góp), `membership` (ngày đăng ký), `delivery_batch` (đợt giao), `cash_shift_report`…

## Capabilities

```python
class Capabilities(BaseModel):
    has_customer_code: bool
    has_customer_name: bool
    has_line_cost: bool          # giá vốn trên dòng bán → lãi gộp
    has_catalog_cost: bool       # giá vốn danh mục → giá trị tồn kho
    has_purchases: bool
    has_batches_expiry: bool
    has_payments: bool           # → công nợ
    has_expenses: bool           # → lãi ròng
    has_staff: bool
    has_order_time: bool         # → ca, giờ cao điểm
    has_channel: bool
    has_unit_conversions: bool
    date_ranges: dict[str, tuple[date, date]]   # theo loại sự kiện: orders, purchases, payments, expenses…
    notes: list[str]             # điều README nói rõ là KHÔNG có
```

Executor kiểm Capabilities trước khi tính. Thiếu khái niệm câu hỏi cần → đề xuất `unanswerable` (gate quyết định cuối).
