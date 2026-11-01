from __future__ import annotations

from datamate.schema.readme import parse_readme


def test_parse_readme_full_features() -> None:
    text = """
# Cửa Hàng Tạp Hoá Ánh Dương

Dữ liệu có đến hết 31/08/2026.

## File
- `HoaDon.xlsx`: danh sách đơn bán hàng
- `ChiTietHoaDon.csv`: chi tiết từng mặt hàng
- `BangGia.xlsx`: danh sách giá

## Quy ước
- Nối ChiTietHoaDon với HoaDon qua Mã đơn hàng.
- Bảng quy đổi đơn vị:
  - Coca Cola 330ml: 1 thùng = 24 lon
  - Bia Heineken bạc: 1 két = 20 chai
  - Mì Hảo Hảo: 1 thùng = 30 gói

## Cột trong HoaDon.xlsx
- `MaHD`: mã định danh hoá đơn duy nhất
- `NgayLap`: thời gian tạo hoá đơn (dd/mm/yyyy)
- `TongTien`: tổng tiền thanh toán sau chiết khấu

## Cột trong ChiTietHoaDon.csv
- `MaHD`: mã hoá đơn
- `MaSP`: mã sản phẩm
- `SoLuong`: số lượng bán ra
"""

    facts = parse_readme(text)

    # 1. Cutoff date
    assert facts.cutoff_date == "2026-08-31"

    # 2. Files
    assert "HoaDon.xlsx" in facts.files
    assert "ChiTietHoaDon.csv" in facts.files
    assert "BangGia.xlsx" in facts.files

    # 3. Unit conversions
    assert len(facts.unit_conversions) == 3
    conv0 = facts.unit_conversions[0]
    assert conv0.product == "Coca Cola 330ml"
    assert conv0.large_unit == "thùng"
    assert conv0.ratio == 24
    assert conv0.small_unit == "lon"

    conv1 = facts.unit_conversions[1]
    assert conv1.product == "Bia Heineken bạc"
    assert conv1.large_unit == "két"
    assert conv1.ratio == 20
    assert conv1.small_unit == "chai"

    # 4. Column descriptions
    assert "HoaDon.xlsx" in facts.column_descriptions
    hd_cols = facts.column_descriptions["HoaDon.xlsx"]
    assert hd_cols.get("MaHD") == "mã định danh hoá đơn duy nhất"
    assert hd_cols.get("TongTien") == "tổng tiền thanh toán sau chiết khấu"

    assert "ChiTietHoaDon.csv" in facts.column_descriptions
    ct_cols = facts.column_descriptions["ChiTietHoaDon.csv"]
    assert ct_cols.get("SoLuong") == "số lượng bán ra"

    # 5. Conventions
    assert len(facts.conventions) >= 1
    assert any("Nối ChiTietHoaDon" in c for c in facts.conventions)
