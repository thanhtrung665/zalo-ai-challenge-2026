# DSL — biểu diễn câu hỏi

LLM chuyển câu hỏi thành một đối tượng `Query` (Pydantic v2, `datamate/nlu/dsl.py`). Executor nhận `Query` + `as_of_date` + CanonicalStore
và trả về đáp án có kiểu. **LLM không bao giờ tính số, không quy đổi ngày.**

Đây là đặc tả khởi điểm (v1). Thêm intent/metric mới bằng skill `/add-dsl-intent` và ghi lý do vào `docs/DECISIONS.md`.

## 1. Cấu trúc

```json
{
  "metric": "revenue",
  "entity": "shop",
  "filters": [{"field": "product_group", "op": "eq", "value": "Trà sữa"}],
  "period": {"kind": "last_week"},
  "compare": null,
  "group_by": null,
  "rank": null,
  "unit": null,
  "answer_type": "number",
  "notes": "doanh thu tuần trước của nhóm trà sữa"
}
```

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `metric` | enum `Metric` | Số đo cần tính (§2) |
| `entity` | enum `Entity` | Đối tượng được đo / xếp hạng: `shop, product, product_group, customer, customer_group, staff, supplier, branch, payment_method, channel, weekday, hour, day, month, batch, active_ingredient, vehicle, brand, model_line, size` |
| `filters` | list `Filter` | `field` + `op` (`eq, ne, in, gt, gte, lt, lte, contains`) + `value`. Giá trị tên được entity linker chuẩn hoá về mã |
| `period` | `Period` | Kỳ chính (§3) |
| `compare` | `Compare` \| null | `{ "period": Period, "output": "diff" \| "pct_change" \| "ratio" \| "both" }` |
| `group_by` | `Entity` \| null | Trả về bảng/list theo nhóm |
| `rank` | `Rank` \| null | `{ "order": "desc" \| "asc", "k": int \| null, "by": Metric \| null }` — `k=null` với câu "... nhất" nghĩa là k=1 |
| `unit` | str \| null | Đơn vị câu hỏi nêu ("ly", "bao", "thùng") — để lọc theo đơn vị cơ bản hoặc quy đổi |
| `answer_type` | enum | `number, percent, string, date, boolean, list, table` |
| `notes` | str | Diễn giải ngắn của LLM — chỉ để log, executor không đọc |

## 2. Metric (v1)

| Nhóm | Metric | Định nghĩa (theo rulebook train — rulebook của split đè lên) |
|---|---|---|
| Bán hàng | `revenue` | Σ thành tiền dòng của đơn hợp lệ (§1) |
| | `quantity_base` | Σ SL quy về đơn vị cơ bản, đơn hợp lệ |
| | `order_count` | Số đơn hợp lệ |
| | `customer_count` | Số khách có ≥ 1 đơn hợp lệ |
| | `avg_order_value` | revenue / order_count, làm tròn đồng (nửa đồng lên) |
| | `order_presence_count` | Số đơn hợp lệ có mặt hàng (mặt hàng ưa chuộng) |
| | `cancel_rate` | % đơn huỷ trên mọi đơn đặt trong kỳ (mọi trạng thái) |
| | `cancel_count` | Số đơn huỷ |
| | `share_of_revenue` | % doanh thu nhóm / doanh thu cả shop cùng kỳ (gồm vãng lai) |
| | `distinct_days_purchased` | Số ngày có mua (khách trung thành) |
| | `working_days` | Số ngày có ≥ 1 đơn/phiếu do người đó làm |
| | `unit_price_on_day` | Đơn giá / 1 đơn vị cơ bản trước chiết khấu dòng, đơn đặt ngày D (tính cả đơn huỷ/trả) |
| | `price_increase_effect` | So SL N ngày kể từ lần tăng giá với N ngày trước đó |
| Lãi, vốn | `gross_profit` | revenue − Σ (SL × giá vốn ghi trên dòng bán) |
| | `net_profit_month` | gross_profit tháng − mọi chi phí trong sổ chi phí tháng đó |
| | `cogs` | Σ giá vốn dòng bán |
| Nhập, kho | `purchase_amount` | Σ tiền phiếu nhập không huỷ, theo ngày phiếu |
| | `purchase_count` | Số phiếu nhập không huỷ (NCC chính) |
| | `avg_purchase_price` | Bình quân theo SL nhập, theo đơn vị nhập |
| | `stock_on_hand` | Tồn lúc hết ngày (từ đầu dữ liệu đến hết ngày) |
| | `stock_big_unit` | list `[số đơn vị lớn nguyên, số đơn vị cơ bản lẻ]` |
| | `stock_value` | Σ tồn × giá vốn danh mục, chỉ hàng còn tồn |
| | `out_of_stock_items` | Hàng mua về để bán có tồn = 0 lúc hết ngày |
| | `unsold_items` | Hàng từng bán trước kỳ nhưng không có đơn hợp lệ trong kỳ |
| | `purchase_minus_sales` | SL nhập − SL bán (đơn hợp lệ), cùng đơn vị |
| | `expiring_batches` | Lô còn tồn có hạn trong [D, D+N]; tiền vốn theo giá nhập của lô |
| Công nợ | `debt_outstanding` | Σ phần chưa trả của tổng đơn (gồm ship, trừ giảm giá đơn) với nợ > 0, hết ngày X |
| | `debt_by_customer` | Bảng nợ theo khách (khách lẻ không có dòng) |
| | `debt_age_days` | Số ngày từ ngày đặt |
| | `debt_added` | Phần chưa trả ngay trong ngày mua, đơn ghi nợ đặt trong kỳ |
| | `debt_collected` | Khoản trả sau ngày mua, ngày trả trong kỳ |
| | `overdue_installments` | Kỳ góp có hạn trước hôm nay chưa góp đủ |
| Khác | `count_distinct` | Đếm đối tượng khác nhau theo `entity` (vd. số biển số xe) |
| | `exists` | boolean: có/không |
| | `first_date` / `last_date` | Ngày đầu/cuối thoả điều kiện |
| | `peak_hour` | Giờ bắt đầu khung 1 giờ có nhiều đơn nhất (number) |
| | `warranty_rate` | Tỉ lệ bảo hành theo luật ngành |
| | `custom` | Không biểu diễn được → chuyển codegen |

## 3. Period

`{"kind": ..., ...tham số}` — code trong `datamate/timeutil` quy ra `[start, end]` (gồm hai đầu) theo `as_of_date`.

| kind | Tham số | Quy đổi |
|---|---|---|
| `today`, `yesterday` | — | một ngày |
| `day` | `date` | một ngày |
| `as_of_end_of_day` | `date` \| null | trạng thái lúc hết ngày (tính từ đầu dữ liệu) — dùng cho tồn, nợ |
| `this_week` | — | thứ Hai tuần này → hôm nay |
| `last_week` | — | cả tuần trước (T2–CN) |
| `this_month` | — | ngày 1 → hôm nay |
| `last_month` | — | cả tháng trước |
| `month` | `month`, `year` \| null | cả tháng; thiếu năm → năm nay nếu không sau hôm nay, ngược lại năm trước |
| `quarter` | `quarter`, `year` \| null | như trên |
| `year_to_date` | — | 01/01 → hôm nay |
| `year` | `year` | cả năm |
| `last_n_days` | `n` | n ngày liền, ngày cuối là hôm nay |
| `range` | `start`, `end` | gồm hai đầu |
| `tet` | `year` \| null | 23 tháng Chạp (năm âm Y−1) → hết mùng 10 Giêng (năm âm Y), tra `calendar.csv` |
| `before_tet` | `year` \| null | cùng số ngày ngay trước 23 tháng Chạp |
| `all` | — | toàn bộ dữ liệu đến hết hôm nay |

Kỳ so sánh trong `compare.period` thêm các kind: `previous_period` (kỳ liền trước cùng độ dài — riêng `this_month` lấy **cùng số ngày** của tháng trước),
`same_period_last_year`.

Bộ lọc giờ: filter `field="shift"` với `value` ∈ `morning` (06:00–13:59), `afternoon` (14:00–21:59); `field="weekday"` 0–6 (0 = thứ Hai).

## 4. Ví dụ

| Câu hỏi | Query (rút gọn) |
|---|---|
| sp bán dc nhiều nhất tuần rồi là gì | `metric=quantity_base, entity=product, period=last_week, rank={desc,k=null}, answer_type=string` |
| tháng này doanh thu tăng hay giảm bao nhiêu % so với tháng trước | `metric=revenue, period=this_month, compare={previous_period, pct_change}, answer_type=percent` |
| còn ai nợ tiền chưa trả | `metric=debt_by_customer, entity=customer, period=as_of_end_of_day, answer_type=table` (hoặc list tuỳ câu) |
| thuốc nào sắp hết hạn trong 30 ngày tới | `metric=expiring_batches, entity=product, filters=[{field:days_ahead, value:30}], answer_type=list` |
| top 3 khách mua nhiều tiền nhất quý 2 | `metric=revenue, entity=customer, period={quarter,2}, rank={desc,k=3}, answer_type=list` |

## 5. Quy tắc cho LLM (đưa vào prompt)

1. Chỉ dùng giá trị enum có trong schema; không chắc metric → `custom`.
2. Không tự quy đổi ngày; không tự tính số; không đoán tên — giữ nguyên cụm từ người dùng viết trong `value`.
3. "nhất" không kèm số → `rank.k = null`. "top N" → `k = N`.
4. Câu hỏi "bao nhiêu %" → `percent`; "bao nhiêu tiền/ly/đơn" → `number`; "ngày nào/tháng nào" → `date`; "có ... không" → `boolean`;
   nhiều đối tượng → `list`; nhiều đối tượng × nhiều số đo → `table`.
