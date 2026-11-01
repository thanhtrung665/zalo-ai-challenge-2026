from __future__ import annotations

from datamate.ingest.header import detect_header


def test_detect_header_row_0() -> None:
    rows = [
        ["Mã đơn", "Ngày bán", "Tên sản phẩm", "Số lượng", "Đơn giá", "Thành tiền"],
        ["DH001", "2025-05-01", "Coca Cola", "2", "10000", "20000"],
        ["DH002", "2025-05-02", "Mì Hảo Hảo", "5", "5000", "25000"],
    ]
    guess = detect_header(rows)
    assert guess.row_index == 0
    assert guess.headers == ["Mã đơn", "Ngày bán", "Tên sản phẩm", "Số lượng", "Đơn giá", "Thành tiền"]
    assert guess.preamble == []


def test_detect_header_offset_with_preamble() -> None:
    rows = [
        ["CỬA HÀNG TẠP HOÁ BÌNH AN", "", "", ""],
        ["BÁO CÁO CHI TIẾT BÁN HÀNG NĂM 2025", "", "", ""],
        ["", "", "", ""],  # Dòng trống
        ["Mã HD", "Ngày tạo", "Khách hàng", "Tổng tiền"],
        ["HD01", "2025-01-10", "Nguyễn Văn X", "150000"],
        ["HD02", "2025-01-11", "Trần Thị Y", "200000"],
    ]
    guess = detect_header(rows)
    assert guess.row_index == 3
    assert guess.headers == ["Mã HD", "Ngày tạo", "Khách hàng", "Tổng tiền"]
    assert len(guess.preamble) == 3
    assert guess.preamble[0][0] == "CỬA HÀNG TẠP HOÁ BÌNH AN"
    assert "2025" in guess.preamble[1][0]


def test_detect_header_empty_columns() -> None:
    rows = [
        ["Mã đơn", "", "Tên hàng", "", "Thành tiền"],
        ["DH01", "x", "Bánh quy", "y", "50000"],
    ]
    guess = detect_header(rows)
    assert guess.row_index == 0
    assert guess.headers[0] == "Mã đơn"
    assert guess.headers[1] == "col_1"
    assert guess.headers[2] == "Tên hàng"
    assert guess.headers[3] == "col_3"
    assert guess.headers[4] == "Thành tiền"
