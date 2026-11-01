from __future__ import annotations

from datamate.ingest.readers import RawSheet
from datamate.ingest.tables import assemble_tables


def test_assemble_tables_single_sheet() -> None:
    s = RawSheet(
        name="Sheet1",
        rows=[
            ["Mã SP", "Tên SP", "Đơn giá"],
            ["SP01", "Bánh mì", "15000"],
            ["SP02", "Sữa tươi", "12000"],
        ],
        src_file="san_pham.xlsx",
        source_type="xlsx",
    )
    tables = assemble_tables([s])
    assert len(tables) == 1
    t = tables[0]
    assert t.name == "Sheet1"
    assert t.num_rows == 2
    assert "_src_file" in t.df.columns
    assert "_src_sheet" in t.df.columns
    assert "_src_row" in t.df.columns
    assert list(t.df["_src_row"]) == [2, 3]


def test_assemble_tables_merge_monthly_sheets() -> None:
    s1 = RawSheet(
        name="T01_2025",
        rows=[
            ["Mã đơn", "Ngày bán", "Thành tiền"],
            ["DH01", "2025-01-05", "100000"],
        ],
        src_file="ban_hang.xlsx",
        source_type="xlsx",
    )
    s2 = RawSheet(
        name="T02_2025",
        rows=[
            ["Mã đơn", "Ngày bán", "Thành tiền"],
            ["DH02", "2025-02-10", "200000"],
        ],
        src_file="ban_hang.xlsx",
        source_type="xlsx",
    )
    # Khác cấu trúc cột -> bảng riêng
    s3 = RawSheet(
        name="KhachHang",
        rows=[
            ["Mã KH", "Tên KH", "SĐT"],
            ["KH01", "Trần Bình", "0901234567"],
        ],
        src_file="khach_hang.xlsx",
        source_type="xlsx",
    )

    tables = assemble_tables([s1, s2, s3])
    # s1 và s2 phải được gộp thành 1 bảng logic
    assert len(tables) == 2

    merged = next(t for t in tables if "Mã đơn" in t.df.columns)
    assert merged.num_rows == 2
    assert list(merged.df["_src_sheet"]) == ["T01_2025", "T02_2025"]
    assert list(merged.df["Mã đơn"]) == ["DH01", "DH02"]

    kh_table = next(t for t in tables if "Mã KH" in t.df.columns)
    assert kh_table.num_rows == 1
    assert kh_table.name == "KhachHang"
