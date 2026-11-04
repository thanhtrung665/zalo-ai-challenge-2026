"""Bảng chuẩn (docs/CANONICAL_SCHEMA.md): tên cột + kiểu, Capabilities, CanonicalStore."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

Kind = Literal["str", "money", "float", "int", "date", "datetime", "bool"]

ORDER_STATUSES = ("completed", "cancelled", "returned", "delivering")

# bảng chuẩn -> {cột: kiểu}
CANONICAL: dict[str, dict[str, Kind]] = {
    "orders": {
        "order_id": "str",
        "order_datetime": "datetime",
        "status": "str",
        "customer_code": "str",
        "customer_name": "str",
        "customer_group": "str",
        "payment_method": "str",
        "channel": "str",
        "order_discount": "money",
        "shipping_fee": "money",
        "vat": "money",
        "order_total": "money",
        "staff": "str",
        "branch": "str",
        "note": "str",
        "return_date": "date",
        "paid_amount": "money",  # khách đã trả ghi ngay trên đơn (file không có sổ thu riêng)
        "debt_amount": "money",  # còn nợ ghi trên đơn
    },
    "order_lines": {
        "order_id": "str",
        "line_no": "int",
        "product_code": "str",
        "product_name": "str",  # tên ghi trên dòng; dùng để nối/sinh mã hàng
        "quantity": "float",
        "unit": "str",
        "quantity_base": "float",
        "unit_price": "money",
        "line_discount": "money",
        "line_amount": "money",
        "line_cost_per_unit": "money",
        "is_service_fee": "bool",
    },
    "products": {
        "product_code": "str",
        "product_name": "str",
        "product_group": "str",
        "base_unit": "str",
        "catalog_cost": "money",
        "is_for_resale": "bool",
        "is_prescription": "bool",
        "active_ingredient": "str",
        "code_synthetic": "bool",
    },
    "unit_conversions": {"product_code": "str", "product_name": "str", "unit": "str", "factor_to_base": "float"},
    "payments": {"order_id": "str", "pay_date": "date", "amount": "money", "method": "str"},
    "purchases": {
        "receipt_id": "str",
        "receipt_date": "date",
        "supplier": "str",
        "product_code": "str",
        "product_name": "str",
        "quantity": "float",
        "unit": "str",
        "unit_cost": "money",
        "amount": "money",
        "status": "str",
        "batch_no": "str",
        "expiry_date": "date",
        "is_opening_stock": "bool",
    },
    "stock_movements": {
        "date": "date",
        "product_code": "str",
        "qty_in_base": "float",
        "qty_out_base": "float",
        "reason": "str",
        "batch_no": "str",
    },
    "expenses": {"date": "date", "category": "str", "amount": "money"},
    # D-008: bảng nghiệp vụ có trong dữ liệu train mà rulebook có luật tương ứng
    "sale_lots": {
        "order_id": "str",
        "line_no": "int",
        "batch_no": "str",
        "quantity_base": "float",
        "returned_base": "float",
    },
    "returns": {"order_id": "str", "return_date": "date", "refund_amount": "money", "reason": "str"},
    "deliveries": {
        "order_id": "str",
        "delivery_date": "date",
        "batch_no": "str",  # đợt giao (1, 2, 3)
        "product_name": "str",
        "quantity": "float",
        "unit": "str",
        "vehicle_plate": "str",
        "driver": "str",
    },
    "debt_terms": {"order_id": "str", "due_days": "int", "due_date": "date"},
    "price_history": {
        "product_code": "str",
        "product_name": "str",
        "effective_date": "date",
        "price": "money",
        "old_price": "money",
    },
}

# Cột ảo: chỉ có ở mapping, build gộp vào cột thật (giờ đặt đơn tách riêng cột ngày).
VIRTUAL: dict[str, dict[str, Kind]] = {
    "orders": {"order_time": "str"},
    "purchase_headers": {},
}

# Bảng trung gian: build nối vào bảng chuẩn (phiếu nhập tách đầu phiếu / dòng).
INTERMEDIATE = {
    "purchase_headers": {
        "receipt_id": "str",
        "receipt_date": "date",
        "supplier": "str",
        "status": "str",
        "amount": "money",
    }
}


def target_columns(table: str) -> dict[str, Kind]:
    """Mọi cột hợp lệ của một đích mapping (kể cả cột ảo và bảng trung gian)."""
    if table in INTERMEDIATE:
        return dict(INTERMEDIATE[table])
    if table not in CANONICAL:
        raise KeyError(table)
    return {**CANONICAL[table], **VIRTUAL.get(table, {})}


class Capabilities(BaseModel):
    model_config = ConfigDict(frozen=True)

    has_customer_code: bool = False
    has_customer_name: bool = False
    has_line_cost: bool = False
    has_catalog_cost: bool = False
    has_purchases: bool = False
    has_batches_expiry: bool = False
    has_payments: bool = False
    has_expenses: bool = False
    has_staff: bool = False
    has_order_time: bool = False
    has_channel: bool = False
    has_unit_conversions: bool = False
    date_ranges: dict[str, tuple[dt.date, dt.date]] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


@dataclass
class CanonicalStore:
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    capabilities: Capabilities = field(default_factory=Capabilities)
    # số dòng rác đã bỏ khi build, theo bảng nguồn (dòng ghi chú cuối bảng, header lặp lẫn trong dữ liệu)
    dropped_junk_rows: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)  # validator hiển thị
    info: list[str] = field(default_factory=list)  # ghi chú build (vd. số đơn đổi sang returned)

    def __getitem__(self, name: str) -> pd.DataFrame:
        return self.tables[name]
