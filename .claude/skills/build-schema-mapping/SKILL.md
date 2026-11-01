---
name: build-schema-mapping
description: Hướng dẫn chi tiết xây tầng map dữ liệu thô của mỗi shop về schema chuẩn DataMate bằng LLM + validator, sinh CanonicalStore và Capabilities. Dùng cho task T10 hoặc khi lỗi nhóm `mapping`.
---

# /build-schema-mapping

Đặc tả: SPEC §6.2, `docs/CANONICAL_SCHEMA.md`.

## Module

```
datamate/schema/
├── profile.py      # ColumnProfile: name, inferred_type, null_rate, n_unique, samples[5], min, max
├── mapping.py      # ShopMapping (Pydantic): table_roles, column_map, status_map, unit_map, notes
├── prompt.py       # dựng prompt từ README + profiles + đặc tả schema chuẩn
├── validate.py     # validators trả list[Issue]
├── build.py        # áp mapping → CanonicalStore (DataFrames chuẩn) + Capabilities
└── canonical.py    # định nghĩa bảng chuẩn, Capabilities
```

## Quy trình mỗi shop (chạy một lần lúc khởi động)

1. Profile mọi RawTable.
2. Prompt LLM (thinking tắt, JSON có ràng buộc theo `ShopMapping`): vai trò mỗi bảng (orders, order_lines, products, purchases…),
   cột nguồn cho mỗi cột chuẩn, bảng map giá trị trạng thái → 4 loại, đơn vị, ghi chú từ README (vd. "không có giá vốn").
3. Validate bằng code:
   - khoá duy nhất (`order_id` ở orders, `product_code` ở products);
   - Σ `line_amount` theo đơn ≈ tổng tiền hàng của đơn khi file có cột tổng (sai lệch ≤ 1 đồng hoặc bằng phí ship/giảm giá đơn);
   - SL > 0 trên ≥ 99% dòng bán; ngày nằm trong khoảng hợp lý;
   - mọi giá trị trạng thái đã được map; đơn vị lớn có hệ số.
4. Có issue → gửi lại LLM kèm danh sách issue (tối đa 2 vòng). Còn issue → bỏ khái niệm đó khỏi Capabilities, ghi log.
5. Build CanonicalStore + Capabilities; lưu `/tmp/datamate_cache/<shop-hash>/mapping.json` để tái dùng trong lần chạy.

## Kiểm tra

- Test validator trên fixture tự tạo (đúng và cố ý sai).
- Chạy 30 shop train; xuất `runs/mapping/<shop>.md` (mapping + issue) để người dùng review ≥ 10 shop.
- Không có bất kỳ ngoại lệ theo tên shop. Lỗi lặp lại ở nhiều shop → sửa prompt/validator tổng quát.
