"""Cache các bảng RawTable thành Parquet theo SHA-256 của các file nguồn."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from datamate.ingest.tables import RawTable


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
        meta: list[dict[str, Any]] = json.loads(meta_path.read_text(encoding="utf-8"))
        tables: list[RawTable] = []
        for item in meta:
            tname = item["name"]
            parquet_path = target / f"{tname}.parquet"
            if not parquet_path.exists():
                return None
            df = pd.read_parquet(parquet_path)
            # Đảm bảo các cột dữ liệu đều là str ngoại trừ _src_row là int
            for col in df.columns:
                if col != "_src_row":
                    df[col] = df[col].astype(str)
            tables.append(
                RawTable(
                    name=tname,
                    df=df,
                    source_files=item.get("source_files", []),
                    header_row=item.get("header_row", 0),
                    preambles=item.get("preambles", []),
                )
            )
        return tables
    except Exception:
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

    meta: list[dict[str, Any]] = []
    for t in tables:
        parquet_path = target / f"{t.name}.parquet"
        t.df.to_parquet(parquet_path, index=False)
        meta.append(
            {
                "name": t.name,
                "source_files": t.source_files,
                "header_row": t.header_row,
                "preambles": t.preambles,
            }
        )

    (target / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
