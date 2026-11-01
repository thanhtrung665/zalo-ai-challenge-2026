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
