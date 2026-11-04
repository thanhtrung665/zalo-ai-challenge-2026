"""Pipeline đầu-cuối: đọc questions → trả lời từng câu → ghi submission.jsonl và logs/<id>.json.

Hiện tại (T06) `default_answerer` abstain mọi câu; các tầng sau thay bằng pipeline thật qua tham số `answerer`.
Lỗi ở một câu → câu đó abstain + ghi lỗi vào log, không làm hỏng cả lần chạy.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from datamate.io import JsonlWriter, read_jsonl

logger = logging.getLogger(__name__)

# SPEC R7: ≤ 6 giờ tổng, watchdog 5h30 thì abstain phần còn lại.
DEFAULT_TIME_LIMIT_S = 5.5 * 3600


class Question(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str
    business_id: str
    question: str
    as_of_date: str | None = None


class Answer(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str
    answer: Any = None
    reason: str | None = None
    trace: dict[str, Any] | None = None  # DSL, code sinh ra, output... ghi vào log, không vào submission

    def to_submission(self, qid: str) -> dict[str, Any]:
        rec: dict[str, Any] = {"id": qid, "type": self.type}
        if self.type not in ("abstain", "unanswerable"):
            rec["answer"] = self.answer
        if self.reason:
            rec["reason"] = self.reason
        return rec


Answerer = Callable[[Question], Answer]


def abstain(reason: str) -> Answer:
    return Answer(type="abstain", reason=reason)


def default_answerer(q: Question) -> Answer:
    return abstain("chưa có pipeline")


def _write_log(logs_dir: Path, rec: dict[str, Any]) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / f"{rec['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")


def run_predict(
    data_dir: str | Path,
    out_dir: str | Path,
    answerer: Answerer = default_answerer,
    time_limit_s: float = DEFAULT_TIME_LIMIT_S,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, int]:
    """Chạy toàn bộ câu theo thứ tự file; trả thống kê."""
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    questions = [Question.model_validate(r) for r in read_jsonl(data_dir / "questions.jsonl")]
    logs_dir = out_dir / "logs"
    stats = {"total": len(questions), "answered": 0, "abstain": 0, "errors": 0, "timed_out": 0}
    start = clock()
    with JsonlWriter(out_dir / "submission.jsonl") as sub:
        for q in questions:
            t0 = clock()
            err: str | None = None
            if t0 - start >= time_limit_s:
                ans = abstain("hết thời gian (watchdog)")
                stats["timed_out"] += 1
            else:
                try:
                    ans = answerer(q)
                except Exception as e:  # noqa: BLE001 — lỗi một câu không được làm hỏng cả lần chạy
                    err = "".join(traceback.format_exception_only(type(e), e)).strip()
                    logger.error("lỗi ở câu %s: %s", q.id, err)
                    logger.debug(traceback.format_exc())
                    ans = abstain("lỗi nội bộ")
                    stats["errors"] += 1
            sub.write(ans.to_submission(q.id))
            if ans.type in ("abstain", "unanswerable"):
                stats["abstain"] += 1
            else:
                stats["answered"] += 1
            _write_log(
                logs_dir,
                {
                    "id": q.id,
                    "question": q.question,
                    "as_of_date": q.as_of_date,
                    "final": ans.to_submission(q.id),
                    "trace": ans.trace,
                    "error": err,
                    "elapsed_s": round(clock() - t0, 4),
                },
            )
    stats["total_elapsed_s"] = int(clock() - start)
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="DataMate: chạy dự đoán")
    ap.add_argument("--data", required=True, help="thư mục split (có questions.jsonl), chỉ đọc")
    ap.add_argument("--out", required=True, help="thư mục kết quả (submission.jsonl + logs/)")
    ap.add_argument("--time-limit", type=float, default=DEFAULT_TIME_LIMIT_S, help="giây; quá thì abstain phần còn lại")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stats = run_predict(args.data, args.out, time_limit_s=args.time_limit)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
