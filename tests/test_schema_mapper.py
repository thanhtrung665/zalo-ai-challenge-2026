"""Vòng map shop với backend giả: sinh đúng, sửa lỗi theo phản hồi, rơi về nháp heuristic."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from datamate.ingest.loader import BusinessData
from datamate.ingest.tables import RawTable
from datamate.llm import LLMError, MockBackend
from datamate.schema.mapper import map_shop
from datamate.schema.profile import profile_tables
from datamate.schema.prompt import build_mapping_prompt, trim_readme
from datamate.schema.readme import ReadmeFacts


def shop() -> BusinessData:
    rows = [
        {
            "Mã hóa đơn": f"O{i}",
            "Ngày": "02/01/2026",
            "Trạng thái": st,
            "Mặt hàng": "Mì",
            "Số lượng": "2",
            "Thành tiền": "10,000",
        }
        for i, st in enumerate(["Xong", "Xong", "Huỷ"], start=1)
    ]
    df = pd.DataFrame(rows)
    df["_src_file"], df["_src_sheet"], df["_src_row"] = "so.csv", "-", range(1, 4)
    t = RawTable(name="so", df=df, source_files=["so.csv"], header_row=0)
    readme = ReadmeFacts(raw_text="# Dữ liệu\n\n## Cột\n- **Mặt hàng**: tên hàng\n  - Mì: 1 thùng = 30 gói\n")
    return BusinessData(biz_id="x", tables=[t], readme=readme)


GOOD = {
    "tables": [
        {
            "source": "so",
            "targets": {
                "orders": {"order_id": "Mã hóa đơn", "order_datetime": "Ngày", "status": "Trạng thái"},
                "order_lines": {
                    "order_id": "Mã hóa đơn",
                    "product_name": "Mặt hàng",
                    "quantity": "Số lượng",
                    "line_amount": "Thành tiền",
                },
            },
        }
    ],
    "status_map": {"Xong": "completed", "Huỷ": "cancelled"},
}


def test_heuristic_only_when_no_backend():
    r = map_shop(shop(), None)
    assert r.source == "heuristic" and r.n_errors == 0
    assert list(r.store["orders"]["status"]) == ["completed", "completed", "cancelled"]


def test_llm_first_response_accepted():
    b = MockBackend([json.dumps(GOOD)])
    r = map_shop(shop(), b)
    assert r.source == "llm" and r.rounds == 1 and len(b.prompts) == 1 and r.n_errors == 0


def test_invalid_json_triggers_repair_with_error_in_prompt():
    b = MockBackend(["{not json", json.dumps(GOOD)])
    r = map_shop(shop(), b)
    assert r.source == "llm" and r.rounds == 2
    assert "JSON không hợp lệ" in b.prompts[1] and "{not json" in b.prompts[1]


def test_nonexistent_column_is_fed_back():
    bad = json.loads(json.dumps(GOOD))
    bad["tables"][0]["targets"]["orders"]["order_id"] = "Cột ma"
    b = MockBackend([json.dumps(bad), json.dumps(GOOD)])
    r = map_shop(shop(), b)
    assert r.rounds == 2 and "Cột ma" in b.prompts[1] and r.n_errors == 0


def test_unmapped_status_is_fed_back_as_issue():
    bad = json.loads(json.dumps(GOOD))
    bad["status_map"] = {"Xong": "completed"}  # thiếu "Huỷ"
    b = MockBackend([json.dumps(bad), json.dumps(GOOD)])
    r = map_shop(shop(), b)
    assert r.rounds == 2 and "unmapped_status" in b.prompts[1] and r.n_errors == 0


def test_always_bad_llm_falls_back_to_heuristic_draft():
    b = MockBackend(lambda p: "{}garbage")
    r = map_shop(shop(), b, max_rounds=2)
    assert r.source == "heuristic" and len(b.prompts) == 3 and r.n_errors == 0


def test_backend_error_falls_back_without_raising():
    r = map_shop(shop(), MockBackend([]))  # hết phản hồi → LLMError
    assert r.source == "heuristic"


def test_cache_reuse(tmp_path: Path):
    biz_dir = tmp_path / "biz_x"
    biz_dir.mkdir()
    (biz_dir / "so.csv").write_text("a\n1\n", encoding="utf-8")
    b = MockBackend([json.dumps(GOOD)])
    first = map_shop(shop(), b, biz_dir=biz_dir, cache_dir=tmp_path / "c")
    assert first.source == "llm"
    b2 = MockBackend([])
    second = map_shop(shop(), b2, biz_dir=biz_dir, cache_dir=tmp_path / "c")
    assert second.source == "cache" and b2.prompts == []


def test_prompt_contents():
    biz = shop()
    p = build_mapping_prompt(biz, profile_tables(biz.tables))
    assert "tên hàng" in p and "`so`" in p and "completed" in p
    assert "Xong (2)" in p  # liệt kê đủ giá trị của cột ít giá trị
    assert "1 thùng = 30 gói" not in p  # danh sách quy đổi do code đọc, không đưa vào prompt


def test_trim_readme_drops_conversion_lines_and_truncates():
    assert "thùng" not in trim_readme("x\n  - Mì: 1 thùng = 30 gói\ny")
    assert len(trim_readme("a" * 20000)) < 6100


def test_llm_error_type_is_runtime_error():
    assert issubclass(LLMError, RuntimeError)
