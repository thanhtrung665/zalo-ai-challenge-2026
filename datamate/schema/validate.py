"""Validator cho CanonicalStore: kiểm bằng code, không tin LLM (skill build-schema-mapping, bước 3)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict

from datamate.schema.canonical import CanonicalStore

Severity = Literal["error", "warn"]

MIN_DATE = dt.date(2015, 1, 1)
MAX_DATE = dt.date(2030, 12, 31)
POSITIVE_QTY_RATIO = 0.99
TOTAL_MATCH_RATIO = 0.95
DANGLING_RATIO = 0.01


class Issue(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    severity: Severity
    table: str
    message: str
    count: int = 0


def _ratio(n: int, d: int) -> float:
    return n / d if d else 0.0


def validate_store(store: CanonicalStore) -> list[Issue]:
    t = store.tables
    issues: list[Issue] = []
    orders, lines = t["orders"], t["order_lines"]

    # 1. khoá duy nhất
    if not orders.empty:
        dup = int(orders["order_id"].duplicated().sum())
        if dup:
            issues.append(
                Issue(code="dup_order_id", severity="error", table="orders", message="order_id trùng", count=dup)
            )
    elif not lines.empty:
        issues.append(
            Issue(code="no_orders", severity="error", table="orders", message="có dòng bán nhưng không có đơn")
        )
    pr = t["products"]
    if pr["product_code"].duplicated().any():
        issues.append(
            Issue(
                code="dup_product_code",
                severity="error",
                table="products",
                message="product_code trùng",
                count=int(pr["product_code"].duplicated().sum()),
            )
        )

    # 2. trạng thái đều đã map
    if "status_raw" in orders:
        bad = orders[orders["status_raw"].notna() & orders["status"].isna()]
        if len(bad):
            vals = sorted(bad["status_raw"].astype(str).unique())[:8]
            issues.append(
                Issue(
                    code="unmapped_status",
                    severity="error",
                    table="orders",
                    message=f"trạng thái chưa map: {vals}",
                    count=len(bad),
                )
            )

    # 3. khoá ngoại order_lines → orders
    if not orders.empty and not lines.empty:
        dangling = int((~lines["order_id"].isin(orders["order_id"])).sum())
        if _ratio(dangling, len(lines)) > DANGLING_RATIO:
            issues.append(
                Issue(
                    code="lines_without_order",
                    severity="error",
                    table="order_lines",
                    message="dòng bán không có đơn tương ứng",
                    count=dangling,
                )
            )

    # 4. số lượng dương
    if not lines.empty:
        q = lines["quantity"].dropna()
        pos = int((q > 0).sum())
        if q.empty:
            issues.append(
                Issue(
                    code="no_quantity",
                    severity="error",
                    table="order_lines",
                    message="không có số lượng nào parse được",
                )
            )
        elif _ratio(pos, len(q)) < POSITIVE_QTY_RATIO:
            issues.append(
                Issue(
                    code="nonpositive_qty",
                    severity="error",
                    table="order_lines",
                    message="quá 1% số lượng không dương",
                    count=len(q) - pos,
                )
            )

    # 5. ngày trong khoảng hợp lý
    for table, col in (
        ("orders", "order_datetime"),
        ("purchases", "receipt_date"),
        ("payments", "pay_date"),
        ("expenses", "date"),
    ):
        s = t[table][col].dropna() if col in t[table] else pd.Series(dtype="datetime64[ns]")
        if s.empty:
            continue
        out = int(((s.dt.date < MIN_DATE) | (s.dt.date > MAX_DATE)).sum())
        if out:
            issues.append(
                Issue(
                    code="date_out_of_range",
                    severity="error",
                    table=table,
                    message=f"{col} ngoài {MIN_DATE}..{MAX_DATE}",
                    count=out,
                )
            )
    if not orders.empty and orders["order_datetime"].isna().mean() > 0.01:
        issues.append(
            Issue(
                code="missing_order_date",
                severity="error",
                table="orders",
                message="quá 1% đơn không có ngày",
                count=int(orders["order_datetime"].isna().sum()),
            )
        )

    # 6. tổng đơn ≈ Σ thành tiền dòng (± ship/giảm giá/VAT)
    if (
        not orders.empty
        and not lines.empty
        and orders["order_total"].notna().any()
        and lines["line_amount"].notna().any()
    ):
        sums = lines.groupby("order_id")["line_amount"].sum(min_count=1)
        o = orders.set_index("order_id")
        both = o.join(sums.rename("_sum"), how="inner").dropna(subset=["order_total", "_sum"])
        if len(both):

            def classify(r: pd.Series) -> str:
                """ok | surcharge (tổng > Σ dòng: phí giao/VAT chưa có cột riêng) | discount (tổng hơi nhỏ hơn: voucher
                cấp đơn không có cột riêng) | deficit (tổng nhỏ hơn hẳn Σ dòng: sai cột)."""
                tot, s = int(r["order_total"]), int(r["_sum"])
                ship = int(r["shipping_fee"]) if pd.notna(r["shipping_fee"]) else 0
                vat = int(r["vat"]) if pd.notna(r["vat"]) else 0
                disc = int(r["order_discount"]) if pd.notna(r["order_discount"]) else 0
                cands = {s, s + ship, s - disc, s + ship - disc, s + ship + vat - disc, s + vat - disc, s + vat}
                if any(abs(tot - c) <= 1 for c in cands):
                    return "ok"
                if tot > s - disc:
                    return "surcharge"
                return "deficit" if s > 0 and tot < 0.5 * s else "discount"

            kinds = both.apply(classify, axis=1)
            n = len(both)
            deficit, surcharge, discount = (int((kinds == k).sum()) for k in ("deficit", "surcharge", "discount"))
            if _ratio(deficit, n) > 1 - TOTAL_MATCH_RATIO:
                issues.append(
                    Issue(
                        code="total_mismatch",
                        severity="error",
                        table="orders",
                        message=f"{deficit}/{n} đơn có tổng nhỏ hơn một nửa Σ thành tiền dòng (sai cột tổng?)",
                        count=deficit,
                    )
                )
            if surcharge:
                issues.append(
                    Issue(
                        code="unexplained_surcharge",
                        severity="warn",
                        table="orders",
                        message=f"{surcharge}/{n} đơn có tổng lớn hơn Σ dòng (phí giao/VAT chưa có cột riêng?)",
                        count=surcharge,
                    )
                )
            if discount:
                issues.append(
                    Issue(
                        code="implicit_order_discount",
                        severity="warn",
                        table="orders",
                        message=f"{discount}/{n} đơn có tổng nhỏ hơn Σ dòng (voucher cấp đơn chưa có cột riêng?)",
                        count=discount,
                    )
                )

    # 7. đơn vị lớn phải có hệ số (cảnh báo từ build)
    for w in store.warnings:
        issues.append(Issue(code="missing_unit_factor", severity="warn", table="order_lines", message=w))
    return issues
