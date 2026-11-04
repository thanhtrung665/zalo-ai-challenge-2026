"""Đề xuất ShopMapping bằng từ vựng chung + mô tả README (không LLM).

Dùng làm (1) bản nháp đưa vào prompt cho LLM, (2) phương án dự phòng khi LLM hỏng, (3) mốc đo cho mapping LLM.
Từ vựng là tên cột phổ biến trong dữ liệu phát hành, KHÔNG có nhánh theo tên shop. ~30% tên cột của shop mới
không có trong từ vựng (đo trên public_test) nên đây chỉ là prior; LLM mới là bộ phận chính.
"""

from __future__ import annotations

import re
from collections import Counter

from datamate.ingest.header import _normalize_text
from datamate.ingest.loader import BusinessData
from datamate.ingest.tables import RawTable
from datamate.schema.mapping import ShopMapping, TableMapping
from datamate.schema.profile import table_key


def compact(s: str) -> str:
    """Tên cột chuẩn hoá bỏ dấu và bỏ khoảng trắng: 'Mã hóa đơn' / 'MaHoaDon' → 'mahoadon'."""
    return _normalize_text(s).replace(" ", "")


# khái niệm -> [(regex trên tên compact, trọng số)]
NAME_RULES: dict[str, list[tuple[str, int]]] = {
    "order_id": [
        (
            r"^(madonhang|mahoadon|madon|mabill|mahd|sohd|sohoadon|machungtu|sochungtu|soct|magd|magiaodich|madh|orderid|sodon|donso|bill|hd)$",
            5,
        ),
        (r"^(maphieu|sophieu|id)$", 2),
    ],
    "date": [
        (
            r"^(ngay|ngayban|ngaydathang|ngaylap|ngaymua|ngaythang|ngaygiaodich|ngayhd|date|ngaydat|ngayxuat|ngaybanhang)$",
            5,
        ),
        (r"^(thoigian|thoidiem|thoigianlap|ngaygiolap)$", 3),
    ],
    "time": [(r"^(gio|giotaodon|giotao|giodat|gioban|thoigiantao)$", 4)],
    "status": [
        (r"^(trangthai|trangthaidonhang|trangthaidon|tinhtrang|tinhtrangdon|ketqua|status|xuly|trangthaixuly)$", 5),
    ],
    "customer_name": [
        (
            r"^(tenkhachhang|khachhang|tenkh|khachhangten|tenkhach|khach|kh|doitac|benmua|khachhangmua|khachhangtenkhach)$",
            4,
        ),
    ],
    "customer_code": [(r"^(makh|makhachhang|makhmua|makhachmua|customerid|makhachle|makhachlesi|makhachmuas?)$", 5)],
    "payment_method": [
        (r"^(phuongthucthanhtoan|phuongthuctt|pttt|httt|hinhthucthanhtoan|phuongthuc|trabang|loaitt)$", 5),
    ],
    "channel": [(r"^(kenhban|kenhbanhang|nguondon|banqua|loaiban|nguon|kenh)$", 5)],
    "staff": [(r"^(nguoiban|manvban|manhanvien|nhanvienban|manv)$", 5)],
    "order_discount": [(r"^(giamgia|chietkhau|ck|giamgiahd)$", 2)],
    "order_total": [
        (r"^(tongsaugiamgia|tongdon|tongbill|phaithu|tongthanhtoan|phaithuthucte)$", 5),
        (r"^(tongtien|tong|tongcong)$", 3),
    ],
    "shipping_fee": [(r"^(phivanchuyen|phiship|phigiaohang|phigiao)$", 5)],
    "vat": [(r"^(thuegtgt|vat|thue)$", 5)],
    "product_name": [
        (
            r"^(tenhang|tenhanghoa|tensanpham|sanpham|hanghoa|hang|mathang|tenmathang|tenmon|mon|noidung|product|tensp|hangban|tenhang)$",
            5,
        ),
    ],
    "product_code": [
        (
            r"^(mahang|mahanghoa|masp|masanpham|masku|mahh|mamathang|mamon|idsp|mahangban|masanphamban|sku|mamatHang)$",
            5,
        ),
    ],
    "quantity": [
        (r"^(soluong|sl|sluong|slg|soluongsanpham|soluongban|slban|soluonghang|soluonggiao|slthucgiao|sl)$", 5),
    ],
    "quantity_base": [
        (r"^(soluongquydoi|soluongle|quyradvle|slquydoi|slle|slquyrale|slcoban|soluongdvtcoban|soluongquyrale)$", 5),
    ],
    "unit": [(r"^(donvitinh|dvt|donvi|dvtinh|unit|dv|dvi|donvitinh)$", 5)],
    "unit_price": [(r"^(dongia|giasanpham|giaban|gia|giale|gia1dv|giadonvi|price|giabanle|dongiaban|dongiad)$", 5)],
    "line_amount": [(r"^(thanhtien|thanhtiend|tien|tienban|ttien|trigia|amount|ttien)$", 5), (r"^(tong)$", 1)],
    "line_discount": [(r"^(giamgia|ck|khuyenmai|chietkhau)$", 3)],
    "line_cost": [(r"^(giavon|giavonlucban)$", 5)],
    "product_group": [(r"^(nhomhang|nhomhanghoa|nhomhang3cap|danhmuc|phanloai|nhom|loaisanpham|loaihang)$", 5)],
    "base_unit": [(r"^(donvicoban|donvicoso|donvigoc|dvgoc|donvi|dvt|donvitinh|dvnho)$", 4)],
    "catalog_cost": [(r"^(giavon|giavonhienhai|giavonhien|giavonhang|giavonhientai)$", 5)],
    "factor": [(r"^(tiledoi|tilequydoi|hesoqd|heso|hesoquydoi|quydoi|bang)$", 5)],
    "large_unit": [(r"^(donviquydoi|dvlon|donvilon|donvinhap|dvtnhap|dvnhap)$", 5)],
    "pay_date": [(r"^(thoigianthu|ngaythu|ngaygiothu|thoidiem|thoigian|ngaytt|ngayttoan)$", 4)],
    "pay_amount": [(r"^(sotienthu|giatri|tien|sotien|sotienthu|dathu|dathu)$", 4)],
    "receipt_id": [(r"^(manhaphang|maphieunhap|madonnhap|sophieu|maphieu)$", 5)],
    "receipt_date": [(r"^(ngaynhap|ngaynhapkho|thoigian)$", 5)],
    "supplier": [(r"^(manhacungcap|mancc|nhacungcap|ncc)$", 5)],
    "purchase_qty": [(r"^(slnhap|soluongnhap|soluong)$", 5)],
    "purchase_cost": [(r"^(gianhap|dongianhap|dongia)$", 5)],
    "batch": [(r"^(lo|malo|solo)$", 5)],
    "expiry": [(r"^(hansudung|hsd|hansudung)$", 5)],
    "receipt_total": [(r"^(cantrancc|tonggiatrinhap|tongtienphieu|tongphieu)$", 5)],
    "stock": [(r"^(toncuoiky|toncuoi|tonkho|tonthuc|tonkhohientai)$", 5)],
    "expense_cat": [(r"^(muc|loaichi|hangmuc|danhmuc)$", 5)],
    "expense_date": [(r"^(ngaychi)$", 5)],
}

NAME_RULES.update(
    {
        "paid": [(r"^(khachdatra|khachtra|dathu|dathanhtoan|datra|thanhtoan|dathutoi)$", 5)],
        "debt": [(r"^(conno|chuatra|duno|conlai|conphaithu|no)$", 5)],
        "returned_qty": [(r"^(soluongtra|sltra|soluongtradvtcoban|sltradvtcoban|sltraquydoi|soluongtraquydoi)$", 5)],
        "lot_qty": [(r"^(soluongdvtcoban|slquyrale|slquydoi|soluongquydoi|slcoban|soluong)$", 3)],
        "line_no": [(r"^(stt|sothutu|thutu|no|dong|sodong)$", 4)],
        "return_date": [(r"^(ngaygiotra|ngaytra|thoigiantra)$", 5)],
        "refund": [(r"^(tienhoantra|sotienhoan|hoantien)$", 5)],
        "delivery_date": [(r"^(ngaygiaohang|ngaygiao|ngaycho|ngayxuat)$", 5)],
        "delivery_batch": [(r"^(langiao|luotgiao|dotgiao)$", 5)],
        "plate": [(r"^(biensoxe|bienso)$", 5)],
        "driver": [(r"^(nguoigiaohang|nguoicho|laixe|taixe)$", 5)],
        "due_days": [(r"^(songayduocno|hannongay|hanno|songayno)$", 5)],
        "due_date": [(r"^(hanthanhtoan|hantra|hanphaitra)$", 5)],
        "effective_date": [(r"^(ngayapdung|ngayhieuluc)$", 5)],
        "new_price": [(r"^(giamoi|giaapdung|giabanle|gia)$", 4)],
        "old_price": [(r"^(giacu|giatruoc)$", 5)],
        "expense_amount": [(r"^(sotien|sotienchi|tien)$", 4)],
    }
)
NAME_RULES.update(
    {
        "active_ingredient": [(r"^(hoatchat|thanhphanchinh)$", 5)],
        "prescription": [(r"^(thuockedon|kedon|bantheodon)$", 5)],
    }
)
NAME_RULES["product_name"].append((r"^(tengoi)$", 3))

# mô tả README (đã chuẩn hoá) -> khái niệm; trọng số 6 (README là bằng chứng mạnh nhất)
DESC_RULES: dict[str, str] = {
    "ma don": "order_id",
    "tên hàng": "product_name",
    "ten hang": "product_name",
    "ma hang": "product_code",
    "so luong": "quantity",
    "don vi co ban": "base_unit",
    "ngay ban": "date",
    "don gia": "unit_price",
    "trang thai don": "status",
    "don vi tinh": "unit",
    "thanh tien sau giam": "line_amount",
    "so luong da doi ra don vi co ban": "quantity_base",
    "ten khach khach le neu khong luu": "customer_name",
    "ten khach khach khong luu khach le": "customer_name",
    "nhom hang": "product_group",
    "ma phieu nhap": "receipt_id",
    "ngay nhap": "receipt_date",
    "ma khach trong neu khach le": "customer_code",
    "kenh ban": "channel",
    "gio dat don": "time",
    "thoi diem dat don ngay gio": "date",
    "tong tien don": "order_total",
    "so khach phai tra cho ca don da tinh giam gia cua don va phi giao": "order_total",
    "gia nhap mot don vi theo don vi nhap cua dong": "purchase_cost",
    "so luong nhap": "purchase_qty",
    "don vi nhap": "large_unit",
    "phi giao hang cua ca don lap lai o moi dong cua don": "shipping_fee",
    "phi giao hang": "shipping_fee",
    "ngay giao": "delivery_date",
    "gia von": "catalog_cost",
    "hinh thuc thanh toan": "payment_method",
}

_STATUS_RULES: list[tuple[str, str]] = [
    (r"\bhuy\b|cancel|void|khong giao duoc|giao that bai", "cancelled"),
    (r"tra hang|tra lai|tra ve|doi tra|hoan hang|hoan tra|return|refund|hoan lai", "returned"),
    (
        r"dang giao|giao dich|xu ly|\bcho\b|pending|shipping|deliver|van chuyen|dang chuan bi|dang gui|\bgui\b",
        "delivering",
    ),
    (r"xong|hoan thanh|da lay|da giao|complete|done|thanh cong|da ban|da thanh toan|paid|^ok$", "completed"),
]


def classify_status_value(value: str) -> str | None:
    """Từ khoá → một trong bốn trạng thái; không nhận ra → None (để LLM/validator xử lý)."""
    v = _normalize_text(value)
    for pat, status in _STATUS_RULES:
        if re.search(pat, v):
            return status
    return None


def _desc_map(biz: BusinessData, table: RawTable) -> dict[str, str]:
    """README: cột (đã chuẩn hoá) -> mô tả (đã chuẩn hoá) cho file nguồn của bảng."""
    out: dict[str, str] = {}
    for fname, cols in biz.readme.column_descriptions.items():
        if any(fname == f or fname.rsplit(".", 1)[0] == f.rsplit(".", 1)[0] for f in table.source_files):
            for col, desc in cols.items():
                out[compact(col.strip("*"))] = _normalize_text(desc)
    return out


def score_columns(biz: BusinessData, table: RawTable) -> dict[str, dict[str, int]]:
    """khái niệm -> {cột nguồn: điểm}."""
    descs = _desc_map(biz, table)
    scores: dict[str, dict[str, int]] = {}
    for col in table.df.columns:
        if col.startswith("_src_"):
            continue
        c = compact(col)
        d = descs.get(c, "")
        for concept, rules in NAME_RULES.items():
            for pat, w in rules:
                if re.match(pat, c):
                    scores.setdefault(concept, {})[col] = max(scores.get(concept, {}).get(col, 0), w)
        if d:
            hits = [k for k in DESC_RULES if d == k or d.startswith(k + " ")]
            if hits:  # khoá dài nhất thắng: "số lượng đã đổi ra đơn vị cơ bản" ≠ "số lượng"
                concept = DESC_RULES[max(hits, key=len)]
                scores.setdefault(concept, {})[col] = max(scores.get(concept, {}).get(col, 0), 6)
    return scores


def _best(scores: dict[str, dict[str, int]], concept: str, taken: set[str], min_score: int = 2) -> str | None:
    cands = {c: s for c, s in scores.get(concept, {}).items() if c not in taken and s >= min_score}
    if not cands:
        return None
    col = max(cands, key=lambda c: (cands[c], -list(scores[concept]).index(c)))
    taken.add(col)
    return col


def detect_role(table: RawTable, scores: dict[str, dict[str, int]]) -> str:
    """Vai trò bảng: sales_flat|sales_lines|orders|products|conversions|payments|purchase_*|sale_lots|...|ignore."""
    has = {k for k, v in scores.items() if any(s >= 3 for s in v.values())}
    names = " ".join(compact(c) for c in table.df.columns)
    nhap = "nhap" in names or "ncc" in names or "nhacungcap" in names
    prod = "product_name" in has or "product_code" in has
    oid = "order_id" in has
    if "stock" in has and not oid and "product_group" not in has:
        return "stock_report"
    if "factor" in has and ("large_unit" in has or "unit" in has) and not oid:
        return "conversions"
    if "effective_date" in has and prod and not oid:
        return "price_history"
    if oid and "return_date" in has and not prod:
        return "returns"
    if oid and ("due_days" in has or "due_date" in has) and not prod and "date" not in has:
        return "debt_terms"
    if oid and "delivery_date" in has and prod:
        return "deliveries"
    if oid and "batch" in has and "returned_qty" in has and not prod:
        return "sale_lots"
    if ("active_ingredient" in has or "prescription" in has) and prod and not oid:
        return "drug_info"
    if "expense_date" in has and "expense_amount" in has:
        return "expenses"
    if nhap and prod and ("purchase_qty" in has or "quantity" in has) and "receipt_id" in has and "status" not in has:
        return "purchase_lines"
    if nhap and not prod and ("supplier" in has or "receipt_date" in has) and "receipt_id" in has:
        return "purchase_header"
    if oid and prod and "quantity" in has and ("line_amount" in has or "unit_price" in has):
        return "sales_flat" if ("date" in has and ("status" in has or "customer_name" in has)) else "sales_lines"
    if oid and "date" in has and ("order_total" in has or "status" in has) and not prod:
        return "orders"
    if oid and "pay_amount" in has and ("payment_method" in has or "pay_date" in has) and not prod:
        return "payments"
    if (
        prod
        and not oid
        and "quantity" not in has
        and ("product_group" in has or "base_unit" in has or "catalog_cost" in has)
    ):
        return "products"
    if prod and "date" in has and "quantity" in has and ("line_amount" in has or "unit_price" in has):
        return "sales_flat"  # sổ bán không có cột mã đơn riêng: mỗi dòng một lần bán
    return "ignore"


def _tm(src: str, **targets: dict[str, str | None]) -> TableMapping:
    return TableMapping(
        source=src,
        targets={t: {k: v for k, v in cols.items() if v} for t, cols in targets.items() if any(cols.values())},
    )


def propose_for_table(biz: BusinessData, table: RawTable, key: str) -> tuple[str, TableMapping | None]:
    s = score_columns(biz, table)
    role = detect_role(table, s)
    taken: set[str] = set()
    b = lambda c, **kw: _best(s, c, taken, **kw)  # noqa: E731
    if role in ("sales_flat", "sales_lines"):
        oid = b("order_id")
        lines = {
            "order_id": oid,
            "product_code": b("product_code"),
            "product_name": b("product_name"),
            "quantity": b("quantity"),
            "quantity_base": b("quantity_base"),
            "unit": b("unit"),
            "unit_price": b("unit_price"),
            "line_discount": b("line_discount") if role == "sales_lines" else None,
            "line_amount": b("line_amount"),
            "line_cost_per_unit": b("line_cost"),
        }
        if role == "sales_lines":
            return role, _tm(key, order_lines=lines)
        orders = {
            "order_id": oid,
            "order_datetime": b("date"),
            "order_time": b("time"),
            "status": b("status"),
            "customer_name": b("customer_name"),
            "customer_code": b("customer_code"),
            "payment_method": b("payment_method"),
            "channel": b("channel"),
            "order_total": b("order_total"),
            "paid_amount": b("paid"),
            "debt_amount": b("debt"),
        }
        return role, _tm(key, orders=orders, order_lines=lines)
    if role == "orders":
        orders = {
            "order_id": b("order_id"),
            "order_datetime": b("date"),
            "order_time": b("time"),
            "status": b("status"),
            "customer_code": b("customer_code"),
            "customer_name": b("customer_name"),
            "payment_method": b("payment_method"),
            "channel": b("channel"),
            "order_discount": b("order_discount"),
            "shipping_fee": b("shipping_fee"),
            "vat": b("vat"),
            "order_total": b("order_total"),
            "staff": b("staff"),
            "paid_amount": b("paid"),
            "debt_amount": b("debt"),
        }
        return role, _tm(key, orders=orders)
    if role == "products":
        prods = {
            "product_code": b("product_code"),
            "product_name": b("product_name"),
            "product_group": b("product_group"),
            "base_unit": b("base_unit"),
            "catalog_cost": b("catalog_cost"),
        }
        return role, _tm(key, products=prods)
    if role == "drug_info":
        drug = {
            "product_code": b("product_code"),
            "product_name": b("product_name"),
            "active_ingredient": b("active_ingredient"),
            "is_prescription": b("prescription"),
        }
        return role, _tm(key, products=drug)
    if role == "conversions":
        conv = {
            "product_code": b("product_code"),
            "product_name": b("product_name"),
            "unit": b("large_unit") or b("unit"),
            "factor_to_base": b("factor"),
        }
        prods = {"product_name": conv["product_name"], "base_unit": b("base_unit")} if conv["product_name"] else {}
        return role, _tm(key, unit_conversions=conv, products=prods)
    if role == "payments":
        pay = {
            "order_id": b("order_id"),
            "pay_date": b("pay_date"),
            "amount": b("pay_amount"),
            "method": b("payment_method"),
        }
        return role, _tm(key, payments=pay)
    if role == "purchase_header":
        hdr = {
            "receipt_id": b("receipt_id"),
            "receipt_date": b("receipt_date"),
            "supplier": b("supplier"),
            "status": b("status"),
            "amount": b("receipt_total"),
        }
        return role, _tm(key, purchase_headers=hdr)
    if role == "purchase_lines":
        pl = {
            "receipt_id": b("receipt_id"),
            "product_code": b("product_code"),
            "product_name": b("product_name"),
            "quantity": b("purchase_qty") or b("quantity"),
            "unit": b("unit") or b("large_unit"),
            "unit_cost": b("purchase_cost"),
            "batch_no": b("batch"),
            "expiry_date": b("expiry"),
            "receipt_date": b("receipt_date"),
            "supplier": b("supplier"),
        }
        return role, _tm(key, purchases=pl)
    if role == "sale_lots":
        lots = {
            "order_id": b("order_id"),
            "line_no": b("line_no"),
            "batch_no": b("batch"),
            "quantity_base": b("lot_qty"),
            "returned_base": b("returned_qty"),
        }
        return role, _tm(key, sale_lots=lots)
    if role == "returns":
        ret = {"order_id": b("order_id"), "return_date": b("return_date"), "refund_amount": b("refund")}
        return role, _tm(key, returns=ret)
    if role == "deliveries":
        dl = {
            "order_id": b("order_id"),
            "delivery_date": b("delivery_date"),
            "batch_no": b("delivery_batch"),
            "product_name": b("product_name"),
            "quantity": b("quantity"),
            "unit": b("unit"),
            "vehicle_plate": b("plate"),
            "driver": b("driver"),
        }
        return role, _tm(key, deliveries=dl)
    if role == "debt_terms":
        dt_ = {"order_id": b("order_id"), "due_days": b("due_days"), "due_date": b("due_date")}
        return role, _tm(key, debt_terms=dt_)
    if role == "price_history":
        ph = {
            "product_code": b("product_code"),
            "product_name": b("product_name"),
            "effective_date": b("effective_date"),
            "price": b("new_price"),
            "old_price": b("old_price"),
        }
        return role, _tm(key, price_history=ph)
    if role == "expenses":
        ex = {"date": b("expense_date"), "category": b("expense_cat"), "amount": b("expense_amount")}
        return role, _tm(key, expenses=ex)
    return role, None


def propose_mapping(biz: BusinessData) -> tuple[ShopMapping, dict[str, str]]:
    """Trả (mapping đề xuất, vai trò từng bảng nguồn). Trạng thái lấy từ các giá trị thực của cột trạng thái đã chọn."""
    tms: list[TableMapping] = []
    roles: dict[str, str] = {}
    status_values: Counter[str] = Counter()
    purchase_sizes: set[int] = set()
    for t in biz.tables:
        key = table_key(t, biz.tables)
        role, tm = propose_for_table(biz, t, key)
        if role == "purchase_lines":
            if len(t.df) in purchase_sizes:  # sổ lô cùng số dòng với bảng dòng nhập: cùng dữ liệu, không nạp hai lần
                role, tm = "duplicate_purchase_lines", None
            purchase_sizes.add(len(t.df))
        roles[key] = role
        if tm is None:
            continue
        tms.append(tm)
        st = tm.targets.get("orders", {}).get("status")
        if st:
            status_values.update(t.df[st].astype(str).str.strip().tolist())
    smap = {v: s for v in status_values if v and (s := classify_status_value(v))}
    return ShopMapping(tables=tms, status_map=smap), roles
