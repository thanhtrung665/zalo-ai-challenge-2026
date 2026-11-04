from __future__ import annotations

import json
from pathlib import Path

from datamate.llm import MockBackend
from datamate.schema.agreement import agreement, mapping_cells
from datamate.schema.mapping import ShopMapping, TableMapping
from datamate.tools.llm_bench import pick_shops, run_bench, to_markdown


def make_split(tmp_path: Path, n: int = 3) -> Path:
    for i in range(n):
        d = tmp_path / "data" / f"biz_{i}"
        d.mkdir(parents=True)
        (d / "README.md").write_text("# x\n\n## File\n- `so.csv` (csv)\n", encoding="utf-8")
        (d / "so.csv").write_text(
            "Mã hóa đơn,Ngày,Trạng thái,Mặt hàng,Số lượng,Thành tiền\n"
            'O1,02/01/2026,Xong,Mì,2,"10,000"\nO2,03/01/2026,Huỷ,Mì,1,"5,000"\n',
            encoding="utf-8",
        )
    return tmp_path


GOOD = ShopMapping(
    tables=[
        TableMapping(
            source="so",
            targets={
                "orders": {"order_id": "Mã hóa đơn", "order_datetime": "Ngày", "status": "Trạng thái"},
                "order_lines": {
                    "order_id": "Mã hóa đơn",
                    "product_name": "Mặt hàng",
                    "quantity": "Số lượng",
                    "line_amount": "Thành tiền",
                },
            },
        )
    ],
    status_map={"Xong": "completed", "Huỷ": "cancelled"},
)


def test_agreement_perfect_and_partial():
    a = agreement(GOOD, GOOD)
    assert a.f1 == 1.0 and a.status_accuracy == 1.0 and not a.missing and not a.extra
    worse = ShopMapping(
        tables=[TableMapping(source="so", targets={"orders": {"order_id": "Mã hóa đơn", "status": "Ngày"}})],
        status_map={"Xong": "completed"},
    )
    b = agreement(worse, GOOD)
    assert b.recall < 1 and b.precision < 1 and b.status_accuracy == 0.5
    assert ("so", "orders", "status", "Ngày") in b.extra and ("so", "orders", "status", "Trạng thái") in b.missing
    assert len(mapping_cells(GOOD)) == 7


def test_pick_shops_even_and_deterministic(tmp_path: Path):
    split = make_split(tmp_path, 10)
    assert pick_shops(split, 5) == ["biz_0", "biz_2", "biz_4", "biz_6", "biz_8"]
    assert pick_shops(split, 50) == sorted(f"biz_{i}" for i in range(10))


def test_run_bench_counts_validity_and_writes_report(tmp_path: Path):
    split = make_split(tmp_path)
    gold = tmp_path / "gold"
    gold.mkdir()
    (gold / "biz_0.json").write_text(GOOD.model_dump_json(), encoding="utf-8")
    # shop 0: JSON hỏng rồi đúng; shop 1: đúng ngay; shop 2: đúng ngay
    ok = GOOD.model_dump_json()
    backend = MockBackend(["{broken", ok, ok, ok])
    rep = run_bench(backend, split, ["biz_0", "biz_1", "biz_2"], gold_dir=gold)
    assert rep["llm_calls"] == 4 and rep["json_valid_rate"] == 0.75
    assert [r["rounds"] for r in rep["shops"]] == [2, 1, 1] and rep["used_llm_result"] == 3
    assert rep["shops"][0]["f1"] == 1.0 and "f1" not in rep["shops"][1]  # chỉ shop có mapping chuẩn mới có F1
    md = to_markdown("m", 9_000_000_000, rep)
    assert "9,000,000,000" in md and "biz_0" in md and "0.75" in md
    json.dumps(rep, ensure_ascii=False)  # serialisable
