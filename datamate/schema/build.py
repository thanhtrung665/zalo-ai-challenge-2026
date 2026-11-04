"""Áp ShopMapping lên dữ liệu thô → CanonicalStore + Capabilities (docs/CANONICAL_SCHEMA.md).

Mọi con số do code parse; LLM chỉ chọn cột nguồn. Không có nhánh theo tên shop.
"""

from __future__ import annotations

import logging
import re
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from datamate.ingest.dates import parse_date_column
from datamate.ingest.header import _normalize_text
from datamate.ingest.loader import BusinessData
from datamate.ingest.numbers import parse_quantity, parse_vn_number
from datamate.ingest.tables import RawTable
from datamate.schema.canonical import CANONICAL, CanonicalStore, Capabilities, Kind, target_columns
from datamate.schema.mapping import ShopMapping
from datamate.schema.profile import table_key

logger = logging.getLogger(__name__)

_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")
_TRUE = {"1", "true", "yes", "y", "x", "co", "có", "đúng", "dung", "t"}
_FALSE = {"0", "false", "no", "n", "khong", "không", "sai", "f"}


class MappingError(ValueError):
    """Mapping tham chiếu bảng/cột nguồn không tồn tại."""


def norm_name(s: object) -> str:
    """Khoá so khớp tên: bỏ dấu, chữ thường, gộp khoảng trắng (D-005: 'Coca  Cola' = 'Coca Cola')."""
    if s is None or (not isinstance(s, str) and pd.isna(s)):
        return ""
    return _normalize_text(str(s))


# ---------------------------------------------------------------- parse từng kiểu cột
def _money(v: str) -> int | None:
    n = parse_vn_number(v)
    if n is None:
        return None
    return int(Decimal(str(n)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _bool(v: str) -> bool | None:
    s = v.strip().lower()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    return None


def _str_series(values: list[str]) -> pd.Series:
    return pd.Series([v.strip() or None for v in values], dtype="object")


def _parse_column(values: list[str], kind: Kind, raw: RawTable) -> pd.Series:
    if kind == "str":
        return _str_series(values)
    if kind == "money":
        return pd.Series([_money(v) for v in values], dtype="Int64")
    if kind == "int":
        return pd.Series([_money(v) for v in values], dtype="Int64")
    if kind == "float":
        return pd.Series([parse_vn_number(v) for v in values], dtype="Float64")
    if kind == "bool":
        return pd.Series([_bool(v) for v in values], dtype="boolean")
    if kind in ("date", "datetime"):
        dates = parse_date_column(list(values), sheet_years=raw.sheet_years())
        return pd.Series(pd.to_datetime(pd.Series(dates, dtype="object")), dtype="datetime64[ns]")
    raise ValueError(kind)  # pragma: no cover


def _time_delta(values: list[str]) -> pd.Series:
    out: list[pd.Timedelta | None] = []
    for v in values:
        m = _TIME.search(v)
        if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
            out.append(pd.Timedelta(hours=int(m.group(1)), minutes=int(m.group(2)), seconds=int(m.group(3) or 0)))
        else:
            out.append(None)
    return pd.Series(out, dtype="timedelta64[ns]")


# ---------------------------------------------------------------- trích một bảng nguồn
def _junk_mask(raw: RawTable, source_cols: list[str]) -> pd.Series:
    """Dòng rác: ghi chú cuối bảng ("Ghi chú: ...") hoặc header lặp lẫn trong dữ liệu (ô bằng đúng tên cột)."""
    df = raw.df
    mask = pd.Series(False, index=df.index)
    for c in source_cols:
        col = df[c].astype(str).str.strip()
        header = norm_name(c)
        norm = col.map(norm_name)
        mask |= (norm == header) & (header != "")
        mask |= col.str.lower().str.startswith("ghi chú:") | col.str.lower().str.startswith("ghi chu:")
    return mask


def _extract(
    raw: RawTable, table: str, colmap: dict[str, str], consts: dict[str, str], keep: pd.Series
) -> pd.DataFrame:
    kinds = target_columns(table)
    df = raw.df
    for src in colmap.values():
        if src not in df.columns:
            raise MappingError(f"bảng {raw.name!r} không có cột {src!r}")
    out: dict[str, pd.Series] = {}
    units_from_qty: pd.Series | None = None
    for canon, src in colmap.items():
        values = df[src].astype(str).tolist()
        kind = kinds[canon]
        if canon == "quantity":
            parsed = [parse_quantity(v) for v in values]
            out[canon] = pd.Series([p[0] for p in parsed], dtype="Float64")
            units_from_qty = pd.Series([p[1] for p in parsed], dtype="object")
        elif canon == "order_time":
            out[canon] = _time_delta(values)
        else:
            out[canon] = _parse_column(values, kind, raw)
    if "order_datetime" in out:
        src = colmap["order_datetime"]
        own_time = _time_delta(df[src].astype(str).tolist())
        extra = out.pop("order_time", None)
        out["order_datetime"] = out["order_datetime"] + (extra if extra is not None else own_time).fillna(
            pd.Timedelta(0)
        )
    out.pop("order_time", None)
    if units_from_qty is not None and "unit" in kinds:
        # đơn vị ghi trong ô số lượng ("1 hộp 30") là dự phòng khi không có cột đơn vị hoặc ô đơn vị trống
        out["unit"] = out["unit"].where(out["unit"].notna(), units_from_qty) if "unit" in out else units_from_qty
    for canon, value in consts.items():
        out[canon] = pd.Series([value] * len(df), dtype="object")
    res = pd.DataFrame(out)
    res.index = df.index
    return res.loc[keep].reset_index(drop=True)


# ---------------------------------------------------------------- lắp ráp
def _concat(parts: list[pd.DataFrame], table: str) -> pd.DataFrame:
    cols = list(target_columns(table))
    if not parts:
        return pd.DataFrame(columns=cols)
    df = pd.concat(parts, ignore_index=True)
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df


def _synthetic_code(name: object) -> str | None:
    key = norm_name(name)
    return f"syn_{key.replace(' ', '_')}" if key else None


def _fill_codes(df: pd.DataFrame, name_to_code: dict[str, str]) -> pd.DataFrame:
    """Dòng thiếu mã hàng: nối theo tên chuẩn hoá tới danh mục, không có thì sinh mã ổn định từ tên."""
    if "product_name" not in df.columns:
        return df
    missing = df["product_code"].isna()
    if missing.any():
        keys = df.loc[missing, "product_name"].map(norm_name)
        df.loc[missing, "product_code"] = [name_to_code.get(k) or _synthetic_code(k) for k in keys]
    return df


def build_store(biz: BusinessData, mapping: ShopMapping) -> CanonicalStore:
    by_key = {table_key(t, biz.tables): t for t in biz.tables}
    parts: dict[str, list[pd.DataFrame]] = {}
    store = CanonicalStore()

    for tm in mapping.tables:
        if tm.source not in by_key:
            raise MappingError(f"bảng nguồn {tm.source!r} không tồn tại (có: {sorted(by_key)})")
        raw = by_key[tm.source]
        used = sorted({s for cm in tm.targets.values() for s in cm.values()})
        missing = [s for s in used if s not in raw.df.columns]
        if missing:
            raise MappingError(f"bảng {tm.source!r} không có cột {missing}")
        junk = _junk_mask(raw, used) if used else pd.Series(False, index=raw.df.index)
        store.dropped_junk_rows[tm.source] = int(junk.sum())
        keep = ~junk
        for target, colmap in tm.targets.items():
            parts.setdefault(target, []).append(_extract(raw, target, colmap, tm.constants.get(target, {}), keep))
        for target in tm.constants:
            if target not in tm.targets:
                raise MappingError(f"constants cho {target!r} nhưng bảng nguồn không có targets cho nó")

    # --- products + tên → mã
    products = _concat(parts.get("products", []), "products")
    products["code_synthetic"] = products["code_synthetic"].astype("boolean")
    no_code = products["product_code"].isna()
    if no_code.any():
        products.loc[no_code, "product_code"] = products.loc[no_code, "product_name"].map(_synthetic_code)
        products.loc[no_code, "code_synthetic"] = True
    products = products.dropna(subset=["product_code"]).drop_duplicates("product_code", keep="first")
    name_to_code = {
        norm_name(n): c for c, n in zip(products["product_code"], products["product_name"], strict=True) if n
    }

    # --- order_lines
    lines = _concat(parts.get("order_lines", []), "order_lines")
    lines = _fill_codes(lines, name_to_code)

    # --- purchases (nối đầu phiếu)
    purchases = _concat(parts.get("purchases", []), "purchases")
    purchases = _fill_codes(purchases, name_to_code)
    headers = _concat(parts.get("purchase_headers", []), "purchases") if "purchase_headers" in parts else None
    if headers is not None and not headers.empty:
        hdr = pd.concat(parts["purchase_headers"], ignore_index=True).drop_duplicates("receipt_id", keep="first")
        hdr = hdr.set_index("receipt_id")
        for col in ("receipt_date", "supplier", "status"):
            if col in hdr.columns:
                filled = purchases["receipt_id"].map(hdr[col])
                purchases[col] = purchases[col].where(purchases[col].notna(), filled) if col in purchases else filled

    # --- sản phẩm xuất hiện ở dòng bán/nhập nhưng thiếu trong danh mục → thêm dòng (mã tổng hợp nếu mã sinh từ tên)
    seen = pd.concat(
        [
            lines[["product_code", "product_name"]],
            purchases[["product_code", "product_name"]],
        ],
        ignore_index=True,
    ).dropna(subset=["product_code"])
    extra = seen[~seen["product_code"].isin(products["product_code"])]
    if not extra.empty:
        most_common = extra.groupby("product_code")["product_name"].agg(
            lambda s: s.dropna().mode().iloc[0] if s.notna().any() else None
        )
        add = pd.DataFrame(
            {
                "product_code": most_common.index,
                "product_name": most_common.values,
                "code_synthetic": [str(c).startswith("syn_") for c in most_common.index],
            }
        )
        products = pd.concat([products, add], ignore_index=True)
    for c in CANONICAL["products"]:
        if c not in products.columns:
            products[c] = pd.NA
    products = products[list(CANONICAL["products"])].reset_index(drop=True)

    # --- đơn vị quy đổi
    conv = _concat(parts.get("unit_conversions", []), "unit_conversions")
    if conv["product_code"].isna().any() and "product_name" in conv:
        miss = conv["product_code"].isna()
        conv.loc[miss, "product_code"] = conv.loc[miss, "product_name"].map(lambda n: name_to_code.get(norm_name(n)))
    readme_rows = []
    for u in biz.readme.unit_conversions:
        code = name_to_code.get(norm_name(u.product)) or _synthetic_code(u.product)
        readme_rows.append(
            {"product_code": code, "product_name": u.product, "unit": u.large_unit, "factor_to_base": float(u.ratio)}
        )
    if readme_rows:
        conv = pd.concat([conv, pd.DataFrame(readme_rows)], ignore_index=True)
    conv = conv.dropna(subset=["product_code", "unit", "factor_to_base"]).drop_duplicates(["product_code", "unit"])
    conv["unit_key"] = conv["unit"].map(norm_name)

    # --- đơn vị cơ bản còn thiếu: hàng không có dòng quy đổi, chỉ bán bằng một đơn vị → đó là đơn vị cơ bản
    need = products["base_unit"].isna()
    if need.any():
        conv_codes = set(conv["product_code"])
        units = lines.dropna(subset=["unit"]).groupby("product_code")["unit"].agg(lambda s: s.map(norm_name).nunique())
        first_unit = lines.dropna(subset=["unit"]).groupby("product_code")["unit"].first()
        for i in products.index[need]:
            code = products.at[i, "product_code"]
            if code not in conv_codes and units.get(code) == 1:
                products.at[i, "base_unit"] = first_unit[code]

    # --- quantity_base
    lines["line_no"] = lines["line_no"].astype("Int64")
    if lines["line_no"].isna().all():
        lines["line_no"] = lines.groupby("order_id").cumcount().add(1).astype("Int64")
    if lines["quantity_base"].isna().any():
        factor = {
            (c, u): f for c, u, f in zip(conv["product_code"], conv["unit_key"], conv["factor_to_base"], strict=True)
        }
        base_unit = dict(zip(products["product_code"], products["base_unit"].map(norm_name), strict=True))
        unit_key = lines["unit"].map(norm_name)
        fac = [factor.get((c, u)) for c, u in zip(lines["product_code"], unit_key, strict=True)]
        unknown = 0
        for i, f in enumerate(fac):
            if f is None:
                bu = base_unit.get(lines.at[i, "product_code"], "")
                if unit_key.iloc[i] and bu and unit_key.iloc[i] != bu:
                    unknown += 1
                fac[i] = 1.0
        computed = lines["quantity"].astype("Float64") * pd.Series(fac, dtype="Float64")
        lines["quantity_base"] = (
            lines["quantity_base"].astype("Float64").where(lines["quantity_base"].notna(), computed)
        )
        if unknown:
            store.warnings.append(
                f"{unknown} dòng bán có đơn vị khác đơn vị cơ bản nhưng không có hệ số quy đổi (coi hệ số 1)"
            )
    name_norm = lines["product_name"].map(norm_name)
    lines["is_service_fee"] = (
        lines["is_service_fee"].astype("boolean").where(lines["is_service_fee"].notna(), name_norm == "phi phuc vu")
    )

    # --- orders
    orders = _concat(parts.get("orders", []), "orders")
    orders = orders.dropna(subset=["order_id"]).drop_duplicates("order_id", keep="first").reset_index(drop=True)
    smap = {norm_name(k): v for k, v in mapping.status_map.items()}
    orders["status_raw"] = orders["status"]
    orders["status"] = orders["status_raw"].map(
        lambda v: None if v is None or pd.isna(v) else smap.get(norm_name(v), mapping.default_status)
    )

    payments = _concat(parts.get("payments", []), "payments")
    expenses = _concat(parts.get("expenses", []), "expenses")
    moves = _concat(parts.get("stock_movements", []), "stock_movements")

    # --- bí danh tên
    alias_src = pd.concat(
        [
            lines[["product_code", "product_name"]],
            purchases[["product_code", "product_name"]],
            products[["product_code", "product_name"]],
        ],
        ignore_index=True,
    ).dropna()
    aliases = alias_src.rename(columns={"product_name": "alias"}).drop_duplicates().reset_index(drop=True)

    conv = conv[["product_code", "unit", "factor_to_base"]].reset_index(drop=True)
    store.tables = {
        "orders": orders,
        "order_lines": lines[list(CANONICAL["order_lines"])],
        "products": products,
        "product_aliases": aliases,
        "unit_conversions": conv,
        "payments": payments,
        "purchases": purchases[list(CANONICAL["purchases"])],
        "stock_movements": moves,
        "expenses": expenses,
    }
    for name, df in store.tables.items():
        store.tables[name] = _coerce(df, name)
    store.capabilities = _capabilities(store, mapping, biz)
    return store


_DTYPE = {
    "str": "object",
    "money": "Int64",
    "int": "Int64",
    "float": "Float64",
    "bool": "boolean",
    "date": "datetime64[ns]",
    "datetime": "datetime64[ns]",
}


def _coerce(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Mọi cột chuẩn đúng dtype theo `CANONICAL` (kể cả bảng rỗng), để validator/executor không gặp object lẫn kiểu."""
    cols = CANONICAL.get(table)
    if cols is None:
        return df
    df = df.copy()
    for c, kind in cols.items():
        if c in df.columns:
            df[c] = df[c].astype(_DTYPE[kind])
    return df


def _has(df: pd.DataFrame, col: str) -> bool:
    return col in df.columns and bool(df[col].notna().any())


def _range(s: pd.Series) -> tuple:
    s = s.dropna()
    return (s.min().date(), s.max().date())


def _capabilities(store: CanonicalStore, mapping: ShopMapping, biz: BusinessData) -> Capabilities:
    t = store.tables
    o, ln, p = t["orders"], t["order_lines"], t["products"]
    ranges: dict = {}
    for name, df, col in (
        ("orders", o, "order_datetime"),
        ("purchases", t["purchases"], "receipt_date"),
        ("payments", t["payments"], "pay_date"),
        ("expenses", t["expenses"], "date"),
    ):
        if _has(df, col):
            ranges[name] = _range(df[col])
    has_time = _has(o, "order_datetime") and bool(
        (o["order_datetime"].dropna() != o["order_datetime"].dropna().dt.normalize()).any()
    )
    notes = list(mapping.notes)
    if biz.readme.cutoff_date:
        notes.append(f"README: dữ liệu có đến hết {biz.readme.cutoff_date}")
    return Capabilities(
        has_customer_code=_has(o, "customer_code"),
        has_customer_name=_has(o, "customer_name"),
        has_line_cost=_has(ln, "line_cost_per_unit"),
        has_catalog_cost=_has(p, "catalog_cost"),
        has_purchases=not t["purchases"].empty,
        has_batches_expiry=_has(t["purchases"], "expiry_date") or _has(t["purchases"], "batch_no"),
        has_payments=not t["payments"].empty,
        has_expenses=not t["expenses"].empty,
        has_staff=_has(o, "staff"),
        has_order_time=has_time,
        has_channel=_has(o, "channel"),
        has_unit_conversions=not t["unit_conversions"].empty,
        date_ranges=ranges,
        notes=notes,
    )
