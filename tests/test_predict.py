import json
from pathlib import Path

from datamate.eval.validate import validate
from datamate.io import JsonlWriter, read_jsonl
from datamate.predict import Answer, Question, run_predict


def _make_data(tmp_path: Path, n: int = 3) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    with open(d / "questions.jsonl", "w", encoding="utf-8") as f:
        for i in range(n):
            f.write(
                json.dumps({"id": f"q{i}", "business_id": "b", "question": "Doanh thu?", "as_of_date": "2025-01-01"})
                + "\n"
            )
    return d


def test_writer_flushes_each_line(tmp_path: Path) -> None:
    p = tmp_path / "x" / "o.jsonl"
    w = JsonlWriter(p)
    w.write({"id": "a", "type": "abstain"})
    # chưa close nhưng dòng đã nằm trên đĩa
    assert read_jsonl(p) == [{"id": "a", "type": "abstain"}]
    w.close()


def test_default_all_abstain_and_valid(tmp_path: Path) -> None:
    d = _make_data(tmp_path)
    out = tmp_path / "res"
    stats = run_predict(d, out)
    assert stats["total"] == 3 and stats["abstain"] == 3
    errs, _ = validate(out / "submission.jsonl", d / "questions.jsonl")
    assert errs == []
    assert [r["id"] for r in read_jsonl(out / "submission.jsonl")] == ["q0", "q1", "q2"]
    log = json.loads((out / "logs" / "q1.json").read_text(encoding="utf-8"))
    assert log["id"] == "q1" and log["final"]["type"] == "abstain" and "elapsed_s" in log


def test_error_in_one_question_abstains_only_that(tmp_path: Path) -> None:
    d = _make_data(tmp_path)

    def answerer(q: Question) -> Answer:
        if q.id == "q1":
            raise ValueError("boom")
        return Answer(type="number", answer=5)

    run_predict(d, tmp_path / "res", answerer=answerer)
    rows = read_jsonl(tmp_path / "res" / "submission.jsonl")
    assert [r["type"] for r in rows] == ["number", "abstain", "number"]
    log = json.loads((tmp_path / "res" / "logs" / "q1.json").read_text(encoding="utf-8"))
    assert "boom" in log["error"]


def test_watchdog_abstains_remainder(tmp_path: Path) -> None:
    d = _make_data(tmp_path, 4)
    t = {"now": 0.0}

    def clock() -> float:
        return t["now"]

    def answerer(q: Question) -> Answer:
        t["now"] += 10
        return Answer(type="number", answer=1)

    stats = run_predict(d, tmp_path / "res", answerer=answerer, time_limit_s=15, clock=clock)
    rows = read_jsonl(tmp_path / "res" / "submission.jsonl")
    assert [r["type"] for r in rows] == ["number", "number", "abstain", "abstain"]
    assert stats["timed_out"] == 2
    assert "reason" in rows[2] and isinstance(rows[2]["reason"], str)
