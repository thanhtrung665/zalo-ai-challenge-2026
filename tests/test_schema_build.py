"""Build CanonicalStore từ bảng thô nhỏ tự tạo; mọi đáp án tính tay trong comment."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from datamate.ingest.loader import BusinessData
from datamate.ingest.tables import RawTable
from datamate.schema.build import MappingError, build_store, norm_name
from datamate.schema.mapping import ShopMapping, TableMapping
from datamate.schema.profile import profile_tables, table_key
from datamate.schema.readme import ReadmeFacts, UnitConversion
from datamate.schema.validate import validate_store


def raw(name: str, rows: list[dict[str, str]], file: str = "f.csv") -> RawTable:
    df = pd.DataFrame(rows)
    df["_src_file"], df["_src_sheet"], df["_src_row"] = file, "-", range(1, len(rows) + 1)
    return RawTable(name=name, df=df, source_files=[file], header_row=0)


def biz(tables: list[RawTable], readme: ReadmeFacts | None = None) -> BusinessData:
    return BusinessData(biz_id="x", tables=tables, readme=readme or ReadmeFacts())


STATUS = {"Xong": "completed", "Huỷ": "cancelled", "Trả": "returned", "Giao": "delivering"}


def flat_table() -> RawTable:
    # 3 đơn. O1: 2 dòng (Coca Cola 2 thùng, Pepsi 3 lon). O2: huỷ. O3: dòng có số lượng "1 lốc" (đơn vị trong ô).
    return raw(
        "ban_hang",
        [
            {
                "Ma": "O1",
                "Ngay": "02/01/2026",
                "TT": "Xong",
                "Hang": "Coca  Cola",
                "SL": "2",
                "DV": "thùng",
                "Gia": "240,000",
                "Tien": "480,000",
            },
            {
                "Ma": "O1",
                "Ngay": "02/01/2026",
                "TT": "Xong",
                "Hang": "Pepsi",
                "SL": "3",
                "DV": "lon",
                "Gia": "10,000",
                "Tien": "30,000",
            },
            {
                "Ma": "O2",
                "Ngay": "03/01/2026",
                "TT": "Huỷ",
                "Hang": "Coca Cola",
                "SL": "1",
                "DV": "lon",
                "Gia": "10,000",
                "Tien": "10,000",
            },
            {
                "Ma": "O3",
                "Ngay": "04/01/2026",
                "TT": "Xong",
                "Hang": "Pepsi",
                "SL": "1 lốc",
                "DV": "",
                "Gia": "60,000",
                "Tien": "60,000",
            },
        ],
    )


FLAT_MAP = ShopMapping(
    tables=[
        TableMapping(
            source="ban_hang",
            targets={
                "orders": {"order_id": "Ma", "order_datetime": "Ngay", "status": "TT"},
                "order_lines": {
                    "order_id": "Ma",
                    "product_name": "Hang",
                    "quantity": "SL",
                    "unit": "DV",
                    "unit_price": "Gia",
                    "line_amount": "Tien",
                },
            },
        )
    ],
    status_map=STATUS,
)
README = ReadmeFacts(
    unit_conversions=[
        UnitConversion(product="Coca Cola", large_unit="thùng", ratio=24, small_unit="lon"),
        UnitConversion(product="Pepsi", large_unit="lốc", ratio=6, small_unit="lon"),
    ]
)


def test_flat_table_splits_orders_and_lines_and_merges_name_variants():
    s = build_store(biz([flat_table()], README), FLAT_MAP)
    assert list(s["orders"]["order_id"]) == ["O1", "O2", "O3"]
    assert list(s["orders"]["status"]) == ["completed", "cancelled", "completed"]
    assert len(s["order_lines"]) == 4
    # "Coca  Cola" (2 dấu cách) và "Coca Cola" là cùng một mặt hàng (D-005)
    assert s["order_lines"]["product_code"].nunique() == 2
    assert len(s["products"]) == 2 and s["products"]["code_synthetic"].all()
    assert s["orders"]["order_datetime"].iloc[0] == pd.Timestamp("2026-01-02")  # ngày trước tháng


def test_quantity_first_number_and_unit_from_cell():
    s = build_store(biz([flat_table()], README), FLAT_MAP)
    last = s["order_lines"].iloc[3]
    assert last["quantity"] == 1 and last["unit"] == "lốc"  # "1 lốc" → 1, đơn vị lốc


def test_quantity_base_from_readme_conversion():
    s = build_store(biz([flat_table()], README), FLAT_MAP)
    ql = s["order_lines"]["quantity_base"].tolist()
    # Coca: 2 thùng × 24 = 48; Pepsi: 3 lon (không có hệ số cho "lon" → 1) = 3; Coca 1 lon = 1; Pepsi 1 lốc × 6 = 6
    assert ql == [48, 3, 1, 6]


def test_money_is_int():
    s = build_store(biz([flat_table()], README), FLAT_MAP)
    assert s["order_lines"]["line_amount"].tolist() == [480000, 30000, 10000, 60000]
    assert str(s["order_lines"]["line_amount"].dtype) == "Int64"


def test_validator_clean_on_good_data():
    s = build_store(biz([flat_table()], README), FLAT_MAP)
    assert [i for i in validate_store(s) if i.severity == "error"] == []


def test_unmapped_status_reported():
    bad = ShopMapping(tables=FLAT_MAP.tables, status_map={"Xong": "completed"})
    s = build_store(biz([flat_table()], README), bad)
    codes = [i.code for i in validate_store(s)]
    assert "unmapped_status" in codes


def test_default_status_applied():
    m = ShopMapping(tables=FLAT_MAP.tables, status_map={"Xong": "completed"}, default_status="cancelled")
    s = build_store(biz([flat_table()], README), m)
    assert s["orders"]["status"].tolist() == ["completed", "cancelled", "completed"]


def test_status_map_ignores_accents_and_case():
    m = ShopMapping(tables=FLAT_MAP.tables, status_map={"xong": "completed", "HUY": "cancelled"})
    s = build_store(biz([flat_table()], README), m)
    assert s["orders"]["status"].tolist() == ["completed", "cancelled", "completed"]


def test_junk_rows_dropped_and_counted():
    t = flat_table()
    extra = pd.DataFrame(
        [
            {
                "Ma": "Ma",
                "Ngay": "Ngay",
                "TT": "TT",
                "Hang": "Hang",
                "SL": "SL",
                "DV": "DV",
                "Gia": "Gia",
                "Tien": "Tien",
            },
            {
                "Ma": "Ghi chú: số liệu ghi tay",
                "Ngay": "",
                "TT": "",
                "Hang": "",
                "SL": "",
                "DV": "",
                "Gia": "",
                "Tien": "",
            },
        ]
    )
    extra["_src_file"], extra["_src_sheet"], extra["_src_row"] = "f.csv", "-", [98, 99]
    t.df = pd.concat([t.df, extra], ignore_index=True)
    s = build_store(biz([t], README), FLAT_MAP)
    assert s.dropped_junk_rows["ban_hang"] == 2
    assert len(s["order_lines"]) == 4 and "Ma" not in set(s["orders"]["order_id"])


def test_missing_source_column_raises():
    m = ShopMapping(tables=[TableMapping(source="ban_hang", targets={"orders": {"order_id": "KhongCo"}})])
    with pytest.raises(MappingError):
        build_store(biz([flat_table()]), m)


def test_missing_source_table_raises():
    m = ShopMapping(tables=[TableMapping(source="nope", targets={"orders": {"order_id": "Ma"}})])
    with pytest.raises(MappingError):
        build_store(biz([flat_table()]), m)


def test_mapping_rejects_unknown_canonical_column_or_status():
    with pytest.raises(ValueError):
        TableMapping(source="a", targets={"orders": {"khong_ton_tai": "x"}})
    with pytest.raises(ValueError):
        TableMapping(source="a", targets={"khong_bang": {"a": "x"}})
    with pytest.raises(ValueError):
        ShopMapping(tables=[], status_map={"x": "done"})


# ---------- nhiều bảng: POS ----------
def pos_biz() -> BusinessData:
    orders = raw(
        "DanhSachHoaDon",
        [
            {
                "id": "A",
                "date": "02/01/2026",
                "created": "2026-01-02 14:35:10",
                "st": "Xong",
                "total": "100,000",
                "disc": "10,000",
                "kh": "",
            },
            {
                "id": "B",
                "date": "45658",
                "created": "2026-01-03 06:05:00",
                "st": "Xong",
                "total": "55,000",
                "disc": "0",
                "kh": "KH1",
            },
        ],
    )
    lines = raw(
        "Sheet1",
        [
            {"id": "A", "ma": "SP1", "ten": "Bia Tiger", "sl": "2", "dv": "thùng", "tien": "110,000"},
            {"id": "B", "ma": "SP2", "ten": "Mì", "sl": "5", "dv": "gói", "tien": "50,000"},
        ],
        file="g.csv",
    )
    prods = raw(
        "SP",
        [
            {"ma": "SP1", "ten": "Bia Tiger", "dvt": "lon", "von": "9,500"},
            {"ma": "SP2", "ten": "Mì", "dvt": "gói", "von": ""},
        ],
        file="h.csv",
    )
    conv = raw("QD", [{"ma": "SP1", "dv": "thùng", "he": "24"}], file="i.csv")
    return biz([orders, lines, prods, conv])


POS_MAP = ShopMapping(
    tables=[
        TableMapping(
            source="DanhSachHoaDon",
            targets={
                "orders": {
                    "order_id": "id",
                    "order_datetime": "date",
                    "order_time": "created",
                    "status": "st",
                    "order_total": "total",
                    "order_discount": "disc",
                    "customer_code": "kh",
                }
            },
        ),
        TableMapping(
            source="Sheet1",
            targets={
                "order_lines": {
                    "order_id": "id",
                    "product_code": "ma",
                    "product_name": "ten",
                    "quantity": "sl",
                    "unit": "dv",
                    "line_amount": "tien",
                }
            },
        ),
        TableMapping(
            source="SP",
            targets={
                "products": {"product_code": "ma", "product_name": "ten", "base_unit": "dvt", "catalog_cost": "von"}
            },
        ),
        TableMapping(
            source="QD", targets={"unit_conversions": {"product_code": "ma", "unit": "dv", "factor_to_base": "he"}}
        ),
    ],
    status_map=STATUS,
)


def test_pos_multi_table_build():
    s = build_store(pos_biz(), POS_MAP)
    # quantity_base: SP1 2 thùng × 24 = 48; SP2 5 gói, cùng đơn vị cơ bản → 5
    assert s["order_lines"]["quantity_base"].tolist() == [48, 5]
    # giờ lấy từ cột "created": 14:35:10; ngày lấy từ cột date (serial 45658 = 2025-01-01)
    assert s["orders"]["order_datetime"].iloc[0] == pd.Timestamp("2026-01-02 14:35:10")
    assert s["orders"]["order_datetime"].iloc[1] == pd.Timestamp("2025-01-01 06:05:00")
    assert s["orders"]["customer_code"].tolist() == [None, "KH1"]  # khách không mã = null, không phải chuỗi rỗng
    assert s["products"]["catalog_cost"].tolist()[0] == 9500 and pd.isna(s["products"]["catalog_cost"].iloc[1])


def test_pos_capabilities():
    c = build_store(pos_biz(), POS_MAP).capabilities
    assert c.has_customer_code and c.has_catalog_cost and c.has_order_time and c.has_unit_conversions
    assert not c.has_line_cost and not c.has_payments and not c.has_purchases
    assert c.date_ranges["orders"] == (dt.date(2025, 1, 1), dt.date(2026, 1, 2))


def test_total_check_accepts_discount_and_flags_deficit():
    s = build_store(pos_biz(), POS_MAP)
    # A: Σ dòng 110.000 − giảm 10.000 = 100.000 = tổng ✓. B: 50.000 vs tổng 55.000 → dư 5.000 (phí giao?) = surcharge
    issues = {i.code: i for i in validate_store(s)}
    assert "total_mismatch" not in issues
    assert issues["unexplained_surcharge"].count == 1
    s["orders"].loc[s["orders"]["order_id"] == "A", "order_total"] = 1000  # tổng nhỏ hơn Σ dòng → sai thật
    codes = {i.code for i in validate_store(s)}
    assert "total_mismatch" in codes


def test_dup_order_id_in_lines_vs_orders_flagged():
    s = build_store(pos_biz(), POS_MAP)
    s["order_lines"].loc[0, "order_id"] = "ZZZ"
    s["order_lines"].loc[1, "order_id"] = "YYY"
    assert "lines_without_order" in {i.code for i in validate_store(s)}


def test_base_unit_inferred_when_only_one_unit_sold():
    t = raw(
        "b",
        [
            {"id": "1", "ten": "Gạo nếp", "sl": "2", "dv": "kg", "tien": "1"},
            {"id": "2", "ten": "Gạo nếp", "sl": "3", "dv": "KG", "tien": "1"},
        ],
    )
    m = ShopMapping(
        tables=[
            TableMapping(
                source="b",
                targets={
                    "order_lines": {
                        "order_id": "id",
                        "product_name": "ten",
                        "quantity": "sl",
                        "unit": "dv",
                        "line_amount": "tien",
                    }
                },
            )
        ]
    )
    s = build_store(biz([t]), m)
    assert s["products"]["base_unit"].tolist() == ["kg"]
    assert s.warnings == []


def test_purchase_header_joined_to_lines():
    hdr = raw("PN", [{"ma": "P1", "ngay": "05/01/2026", "ncc": "NCC1"}], file="p1.csv")
    det = raw("CT", [{"ma": "P1", "sp": "SP1", "sl": "4", "gia": "100,000", "hsd": "01/06/2027"}], file="p2.csv")
    m = ShopMapping(
        tables=[
            TableMapping(
                source="PN",
                targets={"purchase_headers": {"receipt_id": "ma", "receipt_date": "ngay", "supplier": "ncc"}},
            ),
            TableMapping(
                source="CT",
                targets={
                    "purchases": {
                        "receipt_id": "ma",
                        "product_code": "sp",
                        "quantity": "sl",
                        "unit_cost": "gia",
                        "expiry_date": "hsd",
                    }
                },
            ),
        ]
    )
    s = build_store(biz([hdr, det]), m)
    row = s["purchases"].iloc[0]
    assert (
        row["receipt_date"] == pd.Timestamp("2026-01-05") and row["supplier"] == "NCC1" and row["unit_cost"] == 100000
    )
    assert s.capabilities.has_purchases and s.capabilities.has_batches_expiry


def test_same_named_tables_get_distinct_keys():
    a, b = raw("Sheet1", [{"x": "1"}], file="a.csv"), raw("Sheet1", [{"y": "2"}], file="b.csv")
    keys = [table_key(t, [a, b]) for t in (a, b)]
    assert keys == ["Sheet1@a.csv", "Sheet1@b.csv"]
    assert table_key(a, [a]) == "Sheet1"


def test_profile_infers_types():
    t = raw("t", [{"d": "02/01/2026", "n": "10,000", "s": "abc", "h": "14:35", "e": ""}] * 5)
    cols = {c.name: c for c in profile_tables([t])[0].columns}
    assert cols["d"].inferred_type == "date" and cols["n"].inferred_type == "number"
    assert cols["s"].inferred_type == "text" and cols["h"].inferred_type == "time"
    assert cols["e"].inferred_type == "empty" and cols["e"].null_rate == 1.0


def test_norm_name_handles_na():
    assert norm_name(None) == "" and norm_name(pd.NA) == ""
    assert norm_name("Coca  Cola") == norm_name("coca cola") == "coca cola"
