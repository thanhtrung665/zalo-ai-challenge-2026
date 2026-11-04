"""Test fill-down cột cấp đơn và dedupe trong cùng đơn — rulebook §8."""

from __future__ import annotations

import pandas as pd

from datamate.ingest.grouping import clean_order_table, detect_order_id_column


def _df(rows: list[dict[str, str]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, dtype=str)
    df["_src_file"] = "f.csv"
    df["_src_sheet"] = "-"
    df["_src_row"] = range(2, len(df) + 2)
    return df


class TestDetectOrderId:
    def test_detects_order_column_with_repeats(self) -> None:
        df = _df(
            [
                {"Mã đơn": "DH01", "Tên hàng": "A", "SL": "1"},
                {"Mã đơn": "DH01", "Tên hàng": "B", "SL": "2"},
                {"Mã đơn": "DH02", "Tên hàng": "C", "SL": "1"},
            ]
        )
        assert detect_order_id_column(df) == "Mã đơn"

    def test_no_order_column_returns_none(self) -> None:
        df = _df(
            [
                {"Ngày": "2025-01-01", "Diễn giải": "Thu tiền", "Số tiền": "100"},
                {"Ngày": "2025-01-02", "Diễn giải": "Chi tiền", "Số tiền": "50"},
            ]
        )
        assert detect_order_id_column(df) is None

    def test_ignores_src_columns(self) -> None:
        df = _df([{"Mã đơn": "DH01", "Tên hàng": "A"}])
        assert detect_order_id_column(df) != "_src_file"


class TestCleanOrderTable:
    def test_fill_down_order_level_columns(self) -> None:
        """Ô trống ở dòng sau của cùng đơn = giá trị dòng đầu (khách, trạng thái)."""
        df = _df(
            [
                {"Mã đơn": "DH01", "Tên hàng": "A", "SL": "1", "Khách hàng": "Chị Lan", "Trạng thái": "Hoàn thành"},
                {"Mã đơn": "DH01", "Tên hàng": "B", "SL": "2", "Khách hàng": "", "Trạng thái": ""},
                {"Mã đơn": "DH02", "Tên hàng": "C", "SL": "1", "Khách hàng": "Anh Huy", "Trạng thái": "Huỷ"},
            ]
        )
        out = clean_order_table(df)
        assert list(out.df["Khách hàng"]) == ["Chị Lan", "Chị Lan", "Anh Huy"]
        assert list(out.df["Trạng thái"]) == ["Hoàn thành", "Hoàn thành", "Huỷ"]
        # Cột cấp dòng không bị fill
        assert list(out.df["Tên hàng"]) == ["A", "B", "C"]
        assert out.dropped_duplicates == 0

    def test_fill_down_first_column_of_group_when_id_blank(self) -> None:
        """Mã đơn chỉ ghi ở dòng đầu: dòng sau trống vẫn thuộc đơn đó."""
        df = _df(
            [
                {"Mã đơn": "DH01", "Tên hàng": "A", "SL": "1", "Khách hàng": "Chị Lan"},
                {"Mã đơn": "", "Tên hàng": "B", "SL": "2", "Khách hàng": ""},
                {"Mã đơn": "DH02", "Tên hàng": "C", "SL": "1", "Khách hàng": "Anh Huy"},
            ]
        )
        out = clean_order_table(df)
        assert list(out.df["Mã đơn"]) == ["DH01", "DH01", "DH02"]
        assert list(out.df["Khách hàng"]) == ["Chị Lan", "Chị Lan", "Anh Huy"]

    def test_dedupe_identical_rows_within_same_order(self) -> None:
        """Hai dòng giống hệt trong cùng đơn = lỗi xuất file, tính một lần."""
        df = _df(
            [
                {"Mã đơn": "DH01", "Tên hàng": "A", "SL": "1"},
                {"Mã đơn": "DH01", "Tên hàng": "A", "SL": "1"},
                {"Mã đơn": "DH01", "Tên hàng": "B", "SL": "2"},
            ]
        )
        out = clean_order_table(df)
        assert out.num_rows == 2
        assert out.dropped_duplicates == 1
        assert list(out.df["Tên hàng"]) == ["A", "B"]

    def test_identical_rows_in_different_orders_both_kept(self) -> None:
        """Hai dòng giống nhau của hai đơn khác nhau là hai lần bán, tính cả hai."""
        df = _df(
            [
                {"Mã đơn": "DH01", "Tên hàng": "A", "SL": "1"},
                {"Mã đơn": "DH02", "Tên hàng": "A", "SL": "1"},
            ]
        )
        out = clean_order_table(df)
        assert out.num_rows == 2
        assert out.dropped_duplicates == 0

    def test_table_without_order_column_untouched(self) -> None:
        """Bảng không ghi theo đơn: mọi dòng giữ nguyên, kể cả dòng trùng hệt."""
        df = _df(
            [
                {"Ngày": "2025-01-01", "Diễn giải": "Thu tiền", "Số tiền": "100"},
                {"Ngày": "2025-01-01", "Diễn giải": "Thu tiền", "Số tiền": "100"},
                {"Ngày": "2025-01-02", "Diễn giải": "Chi tiền", "Số tiền": "50"},
            ]
        )
        out = clean_order_table(df)
        assert out.num_rows == 3
        assert out.order_col is None
        assert out.dropped_duplicates == 0

    def test_item_level_column_with_blanks_not_filled(self) -> None:
        """Cột có nhiều giá trị khác nhau trong cùng đơn (cấp dòng) không được fill."""
        df = _df(
            [
                {"Mã đơn": "DH01", "Tên hàng": "A", "Ghi chú dòng": "ít đá"},
                {"Mã đơn": "DH01", "Tên hàng": "B", "Ghi chú dòng": "nhiều đá"},
                {"Mã đơn": "DH01", "Tên hàng": "C", "Ghi chú dòng": ""},
            ]
        )
        out = clean_order_table(df)
        assert list(out.df["Ghi chú dòng"]) == ["ít đá", "nhiều đá", ""]

    def test_single_value_plus_blank_in_order_is_order_level(self) -> None:
        """Một đơn có đúng một giá trị khác rỗng + ô trống → đó là cột cấp đơn, fill."""
        df = _df(
            [
                {"Mã đơn": "DH01", "Tên hàng": "A", "Kênh bán": "Facebook"},
                {"Mã đơn": "DH01", "Tên hàng": "B", "Kênh bán": ""},
            ]
        )
        out = clean_order_table(df)
        assert list(out.df["Kênh bán"]) == ["Facebook", "Facebook"]

    def test_preserves_src_trace_columns(self) -> None:
        df = _df(
            [
                {"Mã đơn": "DH01", "Tên hàng": "A"},
                {"Mã đơn": "DH01", "Tên hàng": "A"},
            ]
        )
        out = clean_order_table(df)
        assert out.num_rows == 1
        # Giữ dòng nguồn đầu tiên
        assert list(out.df["_src_row"]) == [2]

    def test_does_not_mutate_input(self) -> None:
        df = _df(
            [
                {"Mã đơn": "DH01", "Tên hàng": "A", "Khách hàng": "Chị Lan"},
                {"Mã đơn": "DH01", "Tên hàng": "B", "Khách hàng": ""},
            ]
        )
        before = df.copy(deep=True)
        clean_order_table(df)
        pd.testing.assert_frame_equal(df, before)


def test_order_column_named_ma_don_hang_not_rejected_by_hang_keyword():
    """Hồi quy: 'Mã đơn hàng' chứa 'hàng' nhưng là cột mã đơn; không được chọn nhầm 'Đơn vị tính'."""
    df = pd.DataFrame(
        {
            "Mã đơn hàng": ["ORD1", "", "", "ORD2", "ORD3", ""],
            "Tên sản phẩm": ["a", "b", "c", "d", "e", "f"],
            "Đơn vị tính": ["gói", "gói", "chai", "gói", "chai", "gói"],
        }
    )
    assert detect_order_id_column(df) == "Mã đơn hàng"
    cleaned = clean_order_table(df.assign(**{"Tên khách hàng": ["An", "", "", "Bình", "Chi", ""]}))
    assert cleaned.order_col == "Mã đơn hàng"
    assert cleaned.df["Tên khách hàng"].tolist() == ["An", "An", "An", "Bình", "Chi", "Chi"]
