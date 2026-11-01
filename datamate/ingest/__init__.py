"""Tầng Ingest dữ liệu của DataMate (CSV, XLSX, SQLite, dò header, gộp bảng, cache)."""

from datamate.ingest.cache import get_cached_tables, save_cached_tables
from datamate.ingest.header import HeaderGuess, detect_header
from datamate.ingest.loader import BusinessData, load_business
from datamate.ingest.readers import RawSheet, read_csv_raw, read_raw_file, read_sqlite_raw, read_xlsx_raw
from datamate.ingest.tables import RawTable, assemble_tables

__all__ = [
    "RawSheet",
    "RawTable",
    "HeaderGuess",
    "BusinessData",
    "read_csv_raw",
    "read_xlsx_raw",
    "read_sqlite_raw",
    "read_raw_file",
    "detect_header",
    "assemble_tables",
    "get_cached_tables",
    "save_cached_tables",
    "load_business",
]
