"""Test scorer theo luật chấm chính thức (SPEC §3). Ví dụ lấy từ bảng Evaluation và rulebook §9."""

from __future__ import annotations

import json

import pytest

from datamate.eval.scorer import (
    Gold,
    load_gold,
    load_predictions,
    match_list,
    match_number,
    match_percent,
    match_string,
    match_table,
    normalize_str,
    score,
    score_one,
)


# ---------------------------------------------------------------- normalize
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Sting dâu 330ml", "sting dâu 330ml"),
        ("  STING   Dâu-330ml!! ", "sting dâu 330ml"),
        ("SP0042", "sp0042"),
        ("Cà phê sữa (M)", "cà phê sữa m"),
        ("snake_case_name", "snake case name"),
        ("Chị Lan - 0901.234.567", "chị lan 0901 234 567"),
    ],
)
def test_normalize_keeps_diacritics(raw: str, expected: str) -> None:
    assert normalize_str(raw) == expected


def test_normalize_nfc_vs_nfd() -> None:
    import unicodedata

    nfd = unicodedata.normalize("NFD", "Bạc xỉu")
    assert normalize_str(nfd) == normalize_str("Bạc xỉu")


# ---------------------------------------------------------------- number / percent
def test_number_exact_and_float_tolerance() -> None:
    assert match_number(48250000, 48250000)
    assert match_number(48250000.0, 48250000)
    assert match_number(18.6, 18.6)
    assert not match_number(48250001, 48250000)
    assert not match_number("48250000", 48250000)  # số dạng chuỗi là sai format
    assert not match_number(True, 1)


def test_percent_rounding_and_sign() -> None:
    assert match_percent(-12.45, -12.45)
    assert match_percent(-12.449999999, -12.45)
    assert match_percent(12.4, 12.40)
    assert not match_percent(12.45, -12.45)
    assert not match_percent(0.124, 12.4)  # phải là số phần trăm, không phải tỉ lệ
    assert not match_percent("12.4", 12.4)


# ---------------------------------------------------------------- string
def test_string_alias_and_code() -> None:
    assert match_string("sting dâu 330ml", "Sting dâu 330ml", ["SP0042"])
    assert match_string("SP0042", "Sting dâu 330ml", ["SP0042"])
    assert not match_string("Sting dầu 330ml", "Sting dâu 330ml", ["SP0042"])  # sai dấu
    assert not match_string(["Sting dâu 330ml"], "Sting dâu 330ml")


# ---------------------------------------------------------------- list
def test_list_order_matters() -> None:
    ref = ["Cà phê sữa", "Bạc xỉu", "Trà đào"]
    assert match_list(["cà phê sữa", "BẠC XỈU", "Trà đào"], ref)
    assert not match_list(["Bạc xỉu", "Cà phê sữa", "Trà đào"], ref)
    assert not match_list(["Cà phê sữa", "Bạc xỉu"], ref)
    assert not match_list("Cà phê sữa, Bạc xỉu, Trà đào", ref)


def test_list_single_element_and_numbers() -> None:
    assert match_list(["Cà phê sữa"], ["Cà phê sữa"])
    assert match_list([3, 10], [3, 10])
    assert not match_list([3, 11], [3, 10])


def test_list_aliases_per_position_and_flat_single() -> None:
    assert match_list(["SP1", "B"], ["A", "B"], [["SP1"], []])
    assert match_list(["SP9"], ["Xi măng"], ["SP9"])
    assert not match_list(["SP9", "B"], ["A", "B"], ["SP9"])  # alias phẳng không áp dụng cho list nhiều phần tử


# ---------------------------------------------------------------- table
REF_TABLE = {"columns": ["khach_hang", "so_tien_no"], "rows": [["Chị Lan", 3200000], ["Anh Tú", 1500000]]}


def test_table_rows_as_set_and_columns_by_name() -> None:
    swapped_rows = {"columns": ["khach_hang", "so_tien_no"], "rows": [["Anh Tú", 1500000], ["chị lan", 3200000]]}
    assert match_table(swapped_rows, REF_TABLE)
    swapped_cols = {"columns": ["so_tien_no", "khach_hang"], "rows": [[3200000, "Chị Lan"], [1500000, "Anh Tú"]]}
    assert match_table(swapped_cols, REF_TABLE)


def test_table_positional_when_names_differ() -> None:
    other_names = {"columns": ["khách", "nợ"], "rows": [["Chị Lan", 3200000], ["Anh Tú", 1500000]]}
    assert match_table(other_names, REF_TABLE)
    other_names_wrong_order = {"columns": ["nợ", "khách"], "rows": [[3200000, "Chị Lan"], [1500000, "Anh Tú"]]}
    assert not match_table(other_names_wrong_order, REF_TABLE)


def test_table_value_errors() -> None:
    bad_cell = {"columns": ["khach_hang", "so_tien_no"], "rows": [["Chị Lan", "3.200.000đ"], ["Anh Tú", 1500000]]}
    assert not match_table(bad_cell, REF_TABLE)
    missing_row = {"columns": ["khach_hang", "so_tien_no"], "rows": [["Chị Lan", 3200000]]}
    assert not match_table(missing_row, REF_TABLE)


def test_table_row_aliases_from_real_format() -> None:
    # Hình dạng alias thật trong answers.jsonl train: một danh sách cho mỗi hàng, áp cho ô tên.
    ref = {"columns": ["khach_hang", "so_tien_no"], "rows": [["Mai Trang Dũng", 174667], ["Lưu Hà An", 90000]]}
    aliases = [["KH0190"], ["KH0056", "Luu Ha An"]]
    by_code = {"columns": ["khach_hang", "so_tien_no"], "rows": [["KH0056", 90000], ["KH0190", 174667]]}
    assert match_table(by_code, ref, aliases)
    by_variant = {"columns": ["khach_hang", "so_tien_no"], "rows": [["Mai Trang Dũng", 174667], ["luu ha an", 90000]]}
    assert match_table(by_variant, ref, aliases)
    assert not match_table(by_code, ref)  # không có alias thì mã không được nhận
    swapped_alias = {"columns": ["khach_hang", "so_tien_no"], "rows": [["KH0190", 90000], ["KH0056", 174667]]}
    assert not match_table(swapped_alias, ref, aliases)  # alias của hàng này không dùng cho hàng khác


def test_table_duplicate_rows_need_full_matching() -> None:
    ref = {"columns": ["a", "b"], "rows": [["X", 1], ["X", 1], ["Y", 2]]}
    assert match_table({"columns": ["a", "b"], "rows": [["Y", 2], ["X", 1], ["X", 1]]}, ref)
    assert not match_table({"columns": ["a", "b"], "rows": [["Y", 2], ["Y", 2], ["X", 1]]}, ref)


# ---------------------------------------------------------------- score_one
def test_score_one_rules() -> None:
    g_num = Gold("q1", "number", 4820000)
    assert score_one({"id": "q1", "type": "number", "answer": 4820000}, g_num) == 1
    assert score_one({"id": "q1", "type": "number", "answer": "4820000"}, g_num) == -1
    assert score_one({"id": "q1", "type": "percent", "answer": 4820000}, g_num) == -1  # sai type
    assert score_one({"id": "q1", "type": "abstain"}, g_num) == 0
    assert score_one(None, g_num) == 0
    assert score_one({"id": "q1", "type": "unanswerable"}, g_num) == -1

    g_un = Gold("q2", "unanswerable", None)
    assert score_one({"id": "q2", "type": "unanswerable", "reason": "không có giá vốn"}, g_un) == 1
    assert score_one({"id": "q2", "type": "number", "answer": 0}, g_un) == -1
    assert score_one({"id": "q2", "type": "abstain"}, g_un) == 0

    g_date = Gold("q3", "date", "2025-09")
    assert score_one({"id": "q3", "type": "date", "answer": "2025-09"}, g_date) == 1
    assert score_one({"id": "q3", "type": "date", "answer": "2025-09-01"}, g_date) == -1

    g_bool = Gold("q4", "boolean", True)
    assert score_one({"id": "q4", "type": "boolean", "answer": True}, g_bool) == 1
    assert score_one({"id": "q4", "type": "boolean", "answer": 1}, g_bool) == -1


# ---------------------------------------------------------------- end-to-end trên file
def _write_jsonl(path, rows) -> None:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def test_score_files(tmp_path) -> None:
    gold_rows = [
        {"id": "a", "type": "string", "answer": "Xi măng Hà Tiên PCB40 bao 50kg", "alias": ["SP0001"]},
        {"id": "b", "type": "number", "answer": 48250000},
        {"id": "c", "type": "unanswerable", "answer": None},
        {"id": "d", "type": "percent", "answer": -12.45},
    ]
    _write_jsonl(tmp_path / "gold.jsonl", gold_rows)
    gold = load_gold(tmp_path / "gold.jsonl")

    # Gold chấm chính nó → PA = 1
    _write_jsonl(tmp_path / "self.jsonl", [{k: v for k, v in r.items() if k != "alias"} for r in gold_rows])
    preds, _ = load_predictions(tmp_path / "self.jsonl")
    assert score(preds, gold).pa == pytest.approx(1.0)

    # Toàn abstain → 0
    _write_jsonl(tmp_path / "abst.jsonl", [{"id": r["id"], "type": "abstain"} for r in gold_rows])
    preds, _ = load_predictions(tmp_path / "abst.jsonl")
    assert score(preds, gold).pa == 0.0

    # Hỗn hợp: a đúng (mã), b sai, c thiếu, d đúng → (2 - 1) / 4
    _write_jsonl(
        tmp_path / "mix.jsonl",
        [
            {"id": "a", "type": "string", "answer": "sp0001"},
            {"id": "b", "type": "number", "answer": 1},
            {"id": "d", "type": "percent", "answer": -12.45},
        ],
    )
    preds, _ = load_predictions(tmp_path / "mix.jsonl")
    rep = score(preds, gold)
    assert (rep.correct, rep.wrong, rep.abstain) == (2, 1, 1)
    assert rep.pa == pytest.approx(0.25)
    assert score(preds, gold, ids={"a", "d"}).pa == pytest.approx(1.0)


def test_bad_lines_are_abstain(tmp_path) -> None:
    (tmp_path / "p.jsonl").write_text(
        '{"id": "x", "type": "number", "answer": 1}\n'
        "not json\n"
        '{"id": "y", "type": "unanswerable", "reason": 123}\n'
        '{"id": "x", "type": "number", "answer": 2}\n',
        encoding="utf-8",
    )
    preds, warnings = load_predictions(tmp_path / "p.jsonl")
    assert preds["x"]["answer"] == 1  # giữ dòng đầu
    assert "y" not in preds
    assert len(warnings) == 3
