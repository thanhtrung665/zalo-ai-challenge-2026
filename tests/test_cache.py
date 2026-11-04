from __future__ import annotations

from pathlib import Path

import pandas as pd

from datamate.ingest.cache import get_cached_tables, save_cached_tables
from datamate.ingest.tables import RawTable


def test_cache_save_and_load(tmp_path: Path) -> None:
    biz_dir = tmp_path / "biz_test"
    biz_dir.mkdir()
    # Tạo một file giả để tính hash
    (biz_dir / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    df = pd.DataFrame({"col_a": ["val1", "val2"], "col_b": ["100", "200"], "_src_row": [1, 2]})
    table = RawTable(
        name="test_table",
        df=df,
        source_files=["data.csv"],
        header_row=0,
        preambles=[{"src_file": "data.csv", "sheet": "-", "preamble": []}],
    )

    cache_dir = tmp_path / "cache"
    assert get_cached_tables(biz_dir, cache_dir=cache_dir) is None

    save_cached_tables(biz_dir, [table], cache_dir=cache_dir)

    loaded = get_cached_tables(biz_dir, cache_dir=cache_dir)
    assert loaded is not None
    assert len(loaded) == 1
    t = loaded[0]
    assert t.name == "test_table"
    assert t.num_rows == 2
    assert list(t.df["col_a"]) == ["val1", "val2"]
    assert list(t.df["col_b"]) == ["100", "200"]


def test_cache_keeps_same_named_tables_distinct(tmp_path: Path) -> None:
    """Hồi quy: nhiều file cùng tên bảng logic ("Sheet1") không được ghi đè nhau trong cache."""
    biz_dir = tmp_path / "biz_dup"
    biz_dir.mkdir()
    (biz_dir / "a.csv").write_text("x\n1\n", encoding="utf-8")

    t1 = RawTable(
        name="Sheet1",
        df=pd.DataFrame({"a": ["1", "2", "3"], "_src_row": [1, 2, 3]}),
        source_files=["a.csv"],
        header_row=0,
    )
    t2 = RawTable(name="Sheet1", df=pd.DataFrame({"b": ["x"], "_src_row": [1]}), source_files=["b.csv"], header_row=0)
    cache_dir = tmp_path / "cache"
    save_cached_tables(biz_dir, [t1, t2], cache_dir=cache_dir)

    loaded = get_cached_tables(biz_dir, cache_dir=cache_dir)
    assert loaded is not None and len(loaded) == 2
    assert list(loaded[0].df.columns) == ["a", "_src_row"] and loaded[0].num_rows == 3
    assert list(loaded[1].df.columns) == ["b", "_src_row"] and loaded[1].num_rows == 1
    assert loaded[0].source_files == ["a.csv"] and loaded[1].source_files == ["b.csv"]


def test_cache_does_not_turn_blank_into_none_string(tmp_path: Path) -> None:
    biz_dir = tmp_path / "biz_blank"
    biz_dir.mkdir()
    (biz_dir / "a.csv").write_text("x\n1\n", encoding="utf-8")
    t = RawTable(
        name="t", df=pd.DataFrame({"a": ["1", "", None], "_src_row": [1, 2, 3]}), source_files=["a.csv"], header_row=0
    )
    cache_dir = tmp_path / "cache"
    save_cached_tables(biz_dir, [t], cache_dir=cache_dir)
    loaded = get_cached_tables(biz_dir, cache_dir=cache_dir)
    assert loaded is not None
    assert list(loaded[0].df["a"]) == ["1", "", ""]
