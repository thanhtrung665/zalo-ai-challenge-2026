"""Bộ nạp dữ liệu cấp cửa hàng (BusinessData): kết hợp Ingest tables, ReadmeFacts và Cache."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from datamate.ingest.cache import get_cached_tables, save_cached_tables
from datamate.ingest.grouping import clean_order_table, detect_order_id_column
from datamate.ingest.readers import RawSheet, read_raw_file
from datamate.ingest.tables import RawTable, assemble_tables
from datamate.schema.readme import ReadmeFacts, parse_readme

logger = logging.getLogger(__name__)


@dataclass
class BusinessData:
    """Toàn bộ dữ liệu của một shop sau khi nạp."""

    biz_id: str
    tables: list[RawTable]
    readme: ReadmeFacts
    source_sheets: list[RawSheet] = field(default_factory=list)
    # Cột mã đơn của từng bảng (None = bảng không ghi theo đơn) — tầng schema dùng lại
    order_columns: dict[str, str | None] = field(default_factory=dict)

    def get_table(self, name: str) -> RawTable | None:
        """Tìm bảng theo tên."""
        for t in self.tables:
            if t.name.lower() == name.lower():
                return t
        return None


def load_business(
    biz_dir: Path,
    use_cache: bool = True,
    vocab_path: Path | None = None,
) -> BusinessData:
    """Nạp toàn bộ dữ liệu của một shop từ thư mục `data/<biz_id>`."""
    biz_id = biz_dir.name

    # 1. Đọc và phân tích README.md
    readme_path = biz_dir / "README.md"
    readme = parse_readme(readme_path) if readme_path.exists() else ReadmeFacts()

    # 2. Kiểm tra cache nếu bật
    if use_cache:
        cached = get_cached_tables(biz_dir)
        if cached is not None:
            order_columns = {t.name: detect_order_id_column(t.df) for t in cached}
            return BusinessData(biz_id=biz_id, tables=cached, readme=readme, order_columns=order_columns)

    # 3. Quét và đọc tất cả các file dữ liệu trong thư mục shop
    data_extensions = (".csv", ".xlsx", ".xlsm", ".xls", ".sqlite", ".db", ".sqlite3")
    data_files = sorted(p for p in biz_dir.iterdir() if p.is_file() and p.suffix.lower() in data_extensions)

    all_sheets: list[RawSheet] = []
    for df_path in data_files:
        sheets = read_raw_file(df_path)
        all_sheets.extend(sheets)

    # 4. Xác định header, gộp bảng
    tables = assemble_tables(all_sheets, vocab_path=vocab_path)

    # 5. Làm sạch bảng ghi theo đơn: dedupe dòng trùng trong cùng đơn + fill-down cột cấp đơn
    order_columns: dict[str, str | None] = {}
    for t in tables:
        result = clean_order_table(t.df)
        order_columns[t.name] = result.order_col
        if result.dropped_duplicates or result.filled_cells:
            logger.debug(
                "%s/%s: bỏ %d dòng trùng, điền %d ô cấp đơn (cột đơn=%s)",
                biz_id,
                t.name,
                result.dropped_duplicates,
                result.filled_cells,
                result.order_col,
            )
        t.df = result.df

    # 6. Lưu vào cache
    if use_cache and tables:
        save_cached_tables(biz_dir, tables)

    return BusinessData(
        biz_id=biz_id,
        tables=tables,
        readme=readme,
        source_sheets=all_sheets,
        order_columns=order_columns,
    )
