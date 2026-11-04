"""Kiểm thẻ model theo luật thi (Rule 1, 2): giới hạn tham số, ngày công khai, giấy phép. Hàm thuần, không gọi mạng."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

PARAM_LIMIT = 15_000_000_000
PUBLIC_BEFORE = dt.date(2026, 10, 1)
PERMISSIVE = ("apache-2.0", "mit", "bsd-2-clause", "bsd-3-clause", "cc-by-4.0", "openrail++", "llama")


@dataclass(frozen=True)
class Finding:
    level: Literal["fail", "warn", "ok"]
    message: str


def check_model_info(
    license_id: str | None,
    created: dt.date | None,
    params: int | None,
    *,
    quantized: bool = False,
) -> list[Finding]:
    out: list[Finding] = []
    if quantized:
        out.append(Finding("warn", "đây là bản lượng tử: số tham số trong metadata có thể đếm thiếu, đo trên bản gốc"))
    if params is None:
        out.append(Finding("warn", "metadata không có số tham số: đo bằng count_params sau khi tải"))
    elif params > PARAM_LIMIT:
        out.append(Finding("fail", f"{params:,} tham số vượt giới hạn {PARAM_LIMIT:,}"))
    else:
        out.append(Finding("ok", f"{params:,} tham số (<= {PARAM_LIMIT:,})"))
    if created is None:
        out.append(Finding("warn", "không biết ngày tạo repo: tự kiểm tra ngày công khai trên model card"))
    elif created >= PUBLIC_BEFORE:
        out.append(
            Finding("fail", f"tạo ngày {created} không trước {PUBLIC_BEFORE} (luật: công khai trước 01/10/2026)")
        )
    else:
        out.append(Finding("ok", f"tạo ngày {created} (< {PUBLIC_BEFORE}); ngày tạo repo chỉ là xấp xỉ ngày công khai"))
    if not license_id:
        out.append(Finding("warn", "metadata không ghi giấy phép: đọc model card"))
    elif license_id.lower() in PERMISSIVE:
        out.append(Finding("ok", f"giấy phép {license_id}"))
    else:
        out.append(Finding("warn", f"giấy phép {license_id} không thuộc nhóm đã biết là thoáng: đọc kỹ điều khoản"))
    return out


def passes(findings: list[Finding]) -> bool:
    return not any(f.level == "fail" for f in findings)
