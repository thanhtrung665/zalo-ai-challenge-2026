"""Cache các bảng RawTable thành Parquet theo SHA-256 của các file nguồn."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from datamate.ingest.tables import RawTable

logger = logging.getLogger(__name__)

# Tăng khi đổi định dạng cache; bản cũ (meta là list, file đặt theo tên bảng) bị coi là không hợp lệ.
CACHE_VERSION = 2


def compute_dir_hash(biz_dir: Path) -> str:
    """Tính mã băm SHA-256 đại diện cho toàn bộ các file dữ liệu trong thư mục shop."""
    h = hashlib.sha256()
    data_files = sorted(
        p
        for p in biz_dir.iterdir()
        if p.is_file() and p.suffix.lower() in (".csv", ".xlsx", ".xlsm", ".xls", ".sqlite", ".db", ".sqlite3")
    )
    for p in data_files:
        h.update(p.name.encode("utf-8"))
        # Băm kích thước và nội dung file (hoặc mtime)
        stat = p.stat()
        h.update(str(stat.st_size).encode("utf-8"))
        h.update(str(stat.st_mtime_ns).encode("utf-8"))
    return h.hexdigest()[:16]


def get_cached_tables(
    biz_dir: Path,
    cache_dir: Path = Path("/tmp/datamate_cache"),
) -> list[RawTable] | None:
    """Đọc các bảng đã lưu trong cache nếu hợp lệ."""
    h = compute_dir_hash(biz_dir)
    target = cache_dir / biz_dir.name / h
    meta_path = target / "meta.json"

    if not meta_path.exists():
        return None

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not isinstance(meta, dict) or meta.get("version") != CACHE_VERSION:
            return None
        tables: list[RawTable] = []
        for item in meta["tables"]:
            parquet_path = target / item["file"]
            if not parquet_path.exists():
                return None
            df = pd.read_parquet(parquet_path)
            # Mọi cột là chuỗi (ô trống = ""), trừ _src_row là int
            for col in df.columns:
                if col != "_src_row":
                    df[col] = df[col].fillna("").astype(str)
            tables.append(
                RawTable(
                    name=item["name"],
                    df=df,
                    source_files=item.get("source_files", []),
                    header_row=item.get("header_row", 0),
                    preambles=item.get("preambles", []),
                )
            )
        return tables
    except (OSError, ValueError, KeyError) as e:  # cache hỏng → đọc lại từ file gốc, không làm hỏng lần chạy
        logger.warning("cache %s không dùng được (%s: %s), đọc lại từ file gốc", target, type(e).__name__, e)
        return None


def save_cached_tables(
    biz_dir: Path,
    tables: list[RawTable],
    cache_dir: Path = Path("/tmp/datamate_cache"),
) -> None:
    """Lưu danh sách RawTable vào cache Parquet."""
    h = compute_dir_hash(biz_dir)
    target = cache_dir / biz_dir.name / h
    target.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    for i, t in enumerate(tables):
        # Tên file theo thứ tự, không theo tên bảng: nhiều file có thể cùng tên logic (vd. "Sheet1")
        fname = f"table_{i:03d}.parquet"
        t.df.to_parquet(target / fname, index=False)
        items.append(
            {
                "file": fname,
                "name": t.name,
                "source_files": t.source_files,
                "header_row": t.header_row,
                "preambles": t.preambles,
            }
        )

    meta = {"version": CACHE_VERSION, "tables": items}
    (target / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
