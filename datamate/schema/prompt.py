"""Dựng prompt cho LLM map dữ liệu thô của một shop về schema chuẩn (skill build-schema-mapping, bước 2)."""

from __future__ import annotations

import json
import re

from datamate.ingest.loader import BusinessData
from datamate.schema.canonical import CANONICAL, INTERMEDIATE, ORDER_STATUSES, VIRTUAL
from datamate.schema.mapping import ShopMapping
from datamate.schema.profile import TableProfile, table_key
from datamate.schema.validate import Issue

README_MAX_CHARS = 6000
_CONVERSION_LINE = re.compile(r"^\s*-\s+.+:\s*1\s+.+=\s*[\d.,]+\s+.+$")
STATUS_MAX_VALUES = 15

INSTRUCTIONS = f"""Bạn map dữ liệu thô của MỘT cửa hàng về schema chuẩn. Chỉ trả về JSON đúng schema `ShopMapping`.

Quy tắc:
1. `tables[].source` là khoá bảng nguồn đúng như liệt kê dưới đây.
   `targets` = {{bảng chuẩn: {{cột chuẩn: TÊN CỘT NGUỒN NGUYÊN VĂN}}}}.
2. Chỉ dùng cột nguồn có thật. Không bịa cột. Cột không có trong dữ liệu thì bỏ qua, đừng đoán.
3. Một bảng nguồn có thể cấp cho nhiều bảng chuẩn (bảng phẳng: vừa `orders` vừa `order_lines`).
   Bảng không ghi mã đơn thì không map `order_id`.
4. Dùng mô tả cột trong README làm bằng chứng chính; tên cột có thể bị đổi tên/viết tắt.
5. `status_map`: giá trị trạng thái gốc → một trong {list(ORDER_STATUSES)}.
   Đơn trả hàng (kể cả trả một phần) = returned. Đơn huỷ ≠ trả hàng.
   Không map giá trị lạ vào đại một trạng thái: bỏ trống để báo lỗi.
6. `order_total` là số khách phải trả cả đơn sau giảm giá cấp đơn, gồm phí giao.
   `line_amount` là thành tiền dòng sau giảm giá dòng.
7. `quantity` là số lượng theo đơn vị của dòng; `quantity_base` là số lượng đã đổi ra đơn vị cơ bản (nếu file có).
8. Bảng thông tin khách hàng, nhân viên, tồn kho cuối kỳ, phòng/bàn: bỏ qua (không có bảng chuẩn tương ứng).
9. Không tính toán số liệu, không sửa dữ liệu. Chỉ chọn cột."""

_COL_HELP = {
    "orders": "một dòng mỗi đơn; order_total=tổng khách phải trả; paid_amount/debt_amount=đã trả/còn nợ ghi trên đơn; "
    "order_time=cột giờ riêng (nếu có)",
    "order_lines": "một dòng mỗi dòng hàng của đơn; line_amount=thành tiền dòng sau giảm giá dòng; "
    "line_cost_per_unit=giá vốn ghi trên dòng bán",
    "products": "danh mục hàng; catalog_cost=giá vốn danh mục; base_unit=đơn vị cơ bản; "
    "is_prescription/active_ingredient: thuốc",
    "unit_conversions": "hệ số: 1 `unit` lớn = factor_to_base đơn vị cơ bản",
    "payments": "mỗi khoản thu theo đơn (kể cả trả nợ sau)",
    "purchases": "dòng nhập hàng; gồm receipt_date/supplier nếu dòng nhập đã chứa chúng",
    "purchase_headers": "đầu phiếu nhập (ngày, nhà cung cấp, tổng tiền phiếu)",
    "sale_lots": "bán theo lô; returned_base>0 nghĩa là đơn có trả hàng",
    "returns": "phiếu trả hàng",
    "deliveries": "bảng kê giao hàng (đợt giao, xe, tài xế)",
    "debt_terms": "hạn thanh toán / số ngày được nợ theo đơn",
    "price_history": "lịch sử giá bán (ngày áp dụng, giá mới, giá cũ)",
    "expenses": "sổ chi phí",
    "stock_movements": "sổ kho",
}


def canonical_spec() -> str:
    lines = ["Bảng chuẩn và cột (kiểu):"]
    for table, cols in {**CANONICAL, **INTERMEDIATE}.items():
        all_cols = {**cols, **VIRTUAL.get(table, {})}
        lines.append(f"- {table}: " + ", ".join(f"{c}:{k}" for c, k in all_cols.items()))
        if table in _COL_HELP:
            lines.append(f"    ({_COL_HELP[table]})")
    return "\n".join(lines)


def trim_readme(text: str) -> str:
    """Bỏ danh sách quy đổi đơn vị (code tự đọc bằng regex) rồi cắt độ dài."""
    kept = [ln for ln in text.splitlines() if not _CONVERSION_LINE.match(ln)]
    out = "\n".join(kept)
    return out if len(out) <= README_MAX_CHARS else out[:README_MAX_CHARS] + "\n...[cắt]"


def render_profiles(profiles: list[TableProfile], biz: BusinessData) -> str:
    raw_by_key = {table_key(t, biz.tables): t for t in biz.tables}
    lines: list[str] = []
    for p in profiles:
        key = p.key
        lines.append(f"### bảng `{key}` — {p.n_rows} dòng — file: {', '.join(p.source_files[:2])}")
        for c in p.columns:
            if c.inferred_type == "empty":
                lines.append(f"  - `{c.name}`: (cột trống)")
                continue
            sample = " | ".join(s[:40] for s in c.samples[:4])
            extra = f", khoảng {c.min:g}..{c.max:g}" if c.min is not None and c.max is not None else ""
            lines.append(
                f"  - `{c.name}`: {c.inferred_type}, trống {c.null_rate:.0%}, "
                f"{c.n_unique} giá trị khác nhau{extra}; vd: {sample}"
            )
        # liệt kê đủ giá trị của cột ít giá trị khác nhau (ứng viên trạng thái / hình thức thanh toán)
        for c in p.columns:
            if c.inferred_type == "text" and 2 <= c.n_unique <= STATUS_MAX_VALUES:
                vals = raw_by_key[key].df[c.name].astype(str).str.strip().value_counts()
                lines.append(f"    giá trị của `{c.name}`: " + "; ".join(f"{v} ({n})" for v, n in vals.items()))
    return "\n".join(lines)


def build_mapping_prompt(
    biz: BusinessData,
    profiles: list[TableProfile],
    draft: ShopMapping | None = None,
    issues: list[Issue] | None = None,
    previous_response: str | None = None,
    error: str | None = None,
) -> str:
    parts = [
        INSTRUCTIONS,
        canonical_spec(),
        "## README của cửa hàng\n" + trim_readme(biz.readme.raw_text),
        "## Dữ liệu thô\n" + render_profiles(profiles, biz),
    ]
    if draft is not None:
        parts.append(
            "## Bản nháp tự động từ quy tắc (có thể sai; sửa nếu README/dữ liệu cho thấy khác)\n"
            + json.dumps(draft.model_dump(mode="json"), ensure_ascii=False)
        )
    if previous_response is not None:
        parts.append("## Phản hồi lần trước của bạn\n" + previous_response)
    if error:
        parts.append("## Lỗi cấu trúc cần sửa\n" + error)
    if issues:
        parts.append(
            "## Lỗi phát hiện khi áp mapping lên dữ liệu thật — hãy sửa mapping\n"
            + "\n".join(f"- [{i.severity}] {i.code} ({i.table}): {i.message} (số lượng: {i.count})" for i in issues)
        )
    parts.append("Trả về DUY NHẤT một JSON `ShopMapping`.")
    return "\n\n".join(parts)
