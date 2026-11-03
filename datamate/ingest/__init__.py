"""Tầng Ingest dữ liệu của DataMate (CSV, XLSX, SQLite, dò header, gộp bảng, cache, parse số/ngày, fill-down)."""

from datamate.ingest.cache import get_cached_tables, save_cached_tables
from datamate.ingest.dates import parse_vn_date
from datamate.ingest.grouping import CleanResult, clean_order_table, detect_order_id_column
from datamate.ingest.header import HeaderGuess, detect_header
from datamate.ingest.loader import BusinessData, load_business
from datamate.ingest.numbers import parse_percent, parse_quantity, parse_vn_number
from datamate.ingest.readers import RawSheet, read_csv_raw, read_raw_file, read_sqlite_raw, read_xlsx_raw
from datamate.ingest.tables import RawTable, assemble_tables

__all__ = [
    "RawSheet",
    "RawTable",
    "HeaderGuess",
    "BusinessData",
    "CleanResult",
    "read_csv_raw",
    "read_xlsx_raw",
    "read_sqlite_raw",
    "read_raw_file",
    "detect_header",
    "assemble_tables",
    "get_cached_tables",
    "save_cached_tables",
    "load_business",
    "parse_vn_number",
    "parse_quantity",
    "parse_percent",
    "parse_vn_date",
    "clean_order_table",
    "detect_order_id_column",
]
