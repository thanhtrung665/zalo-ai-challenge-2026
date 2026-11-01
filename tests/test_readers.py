from __future__ import annotations

import sqlite3
from pathlib import Path

from datamate.ingest.readers import read_csv_raw, read_raw_file, read_sqlite_raw, read_xlsx_raw


def test_read_csv_raw_utf8(tmp_path: Path) -> None:
    csv_file = tmp_path / "test.csv"
    csv_text = "Mã đơn,Ngày bán,Khách hàng\nDH01,2025-01-01,Nguyễn Văn A\nDH02,2025-01-02,Lê Thị B\n"
    csv_file.write_text(csv_text, encoding="utf-8")
    sheets = read_csv_raw(csv_file)
    assert len(sheets) == 1
    s = sheets[0]
    assert s.name == "-"
    assert s.source_type == "csv"
    assert s.num_rows == 3
    assert s.rows[0] == ["Mã đơn", "Ngày bán", "Khách hàng"]
    assert s.rows[1] == ["DH01", "2025-01-01", "Nguyễn Văn A"]


def test_read_csv_raw_utf8_sig(tmp_path: Path) -> None:
    csv_file = tmp_path / "test_sig.csv"
    content = "Mã,Tên\nSP01,Sữa tươi\n"
    csv_file.write_bytes(content.encode("utf-8-sig"))
    sheets = read_csv_raw(csv_file)
    assert len(sheets) == 1
    assert sheets[0].rows[0] == ["Mã", "Tên"]


def test_read_sqlite_raw(tmp_path: Path) -> None:
    db_file = tmp_path / "test.sqlite"
    con = sqlite3.connect(db_file)
    con.execute("CREATE TABLE orders (id TEXT, amount REAL, customer TEXT)")
    con.execute("INSERT INTO orders VALUES ('DH100', 150000.0, 'Anh Nam')")
    con.execute("INSERT INTO orders VALUES ('DH101', 250000.0, 'Chị Mai')")
    con.commit()
    con.close()

    sheets = read_sqlite_raw(db_file)
    assert len(sheets) == 1
    s = sheets[0]
    assert s.name == "orders"
    assert s.source_type == "sqlite"
    assert s.rows[0] == ["id", "amount", "customer"]
    assert s.rows[1] == ["DH100", "150000.0", "Anh Nam"]
    assert s.rows[2] == ["DH101", "250000.0", "Chị Mai"]


def test_read_raw_file_dispatch(tmp_path: Path) -> None:
    csv_file = tmp_path / "sample.csv"
    csv_file.write_text("a,b\n1,2\n", encoding="utf-8")
    res = read_raw_file(csv_file)
    assert len(res) == 1
    assert res[0].rows == [["a", "b"], ["1", "2"]]


def test_read_xlsx_raw(tmp_path: Path) -> None:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(["Mã", "Số lượng", "Giá"])
    ws.append(["SP1", 5, 20000])
    xlsx_file = tmp_path / "test.xlsx"
    wb.save(xlsx_file)
    wb.close()

    sheets = read_xlsx_raw(xlsx_file)
    assert len(sheets) == 1
    assert sheets[0].name == "Sales"
    assert sheets[0].rows[0] == ["Mã", "Số lượng", "Giá"]
    assert sheets[0].rows[1] == ["SP1", "5", "20000"]
