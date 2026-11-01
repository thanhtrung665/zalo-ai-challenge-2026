from __future__ import annotations

import json

from datamate.eval.validate import check_record, validate


def test_check_record_formats() -> None:
    ok = [
        {"id": "q", "type": "number", "answer": 4820000},
        {"id": "q", "type": "percent", "answer": 12.4},
        {"id": "q", "type": "string", "answer": "Sting dâu 330ml"},
        {"id": "q", "type": "date", "answer": "2026-08-15"},
        {"id": "q", "type": "date", "answer": "2025-09"},
        {"id": "q", "type": "boolean", "answer": True},
        {"id": "q", "type": "list", "answer": ["Cà phê sữa"]},
        {"id": "q", "type": "list", "answer": [3, 10]},
        {"id": "q", "type": "table", "answer": {"columns": ["a", "b"], "rows": [["x", 1]]}},
        {"id": "q", "type": "unanswerable", "reason": "Dữ liệu không có giá vốn"},
        {"id": "q", "type": "abstain"},
    ]
    for r in ok:
        assert check_record(r) == [], r

    bad = [
        {"id": "q", "type": "number", "answer": "4820000"},
        {"id": "q", "type": "number", "answer": True},
        {"id": "q", "type": "percent", "answer": "12,4%"},
        {"id": "q", "type": "date", "answer": "15/08/2026"},
        {"id": "q", "type": "date", "answer": "2026-02-30"},
        {"id": "q", "type": "boolean", "answer": "có"},
        {"id": "q", "type": "list", "answer": "Cà phê sữa, Bạc xỉu"},
        {"id": "q", "type": "table", "answer": {"columns": ["a", "b"], "rows": [["x"]]}},
        {"id": "q", "type": "string", "answer": ""},
        {"id": "q", "type": "unanswerable", "reason": 1},
        {"id": "q", "type": "foo", "answer": 1},
        {"type": "number", "answer": 1},
    ]
    for r in bad:
        assert check_record(r), r


def test_validate_file(tmp_path) -> None:
    (tmp_path / "q.jsonl").write_text(
        "\n".join(
            json.dumps({"id": i, "business_id": "b", "question": "?", "as_of_date": "2026-01-01"}) for i in "abc"
        ),
        encoding="utf-8",
    )
    (tmp_path / "p.jsonl").write_text(
        '{"id": "a", "type": "number", "answer": 1}\n{"id": "a", "type": "abstain"}\n{"id": "z", "type": "abstain"}\n',
        encoding="utf-8",
    )
    errors, warnings = validate(tmp_path / "p.jsonl", tmp_path / "q.jsonl")
    assert any("trùng id" in e for e in errors)
    assert any("không có trong questions" in e for e in errors)
    assert any("thiếu 2/3" in w for w in warnings)
