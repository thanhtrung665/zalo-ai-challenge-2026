"""Giao diện backend LLM (skill /llm-runtime). Backend vLLM (GPU) và HF (dự phòng) cài đúng giao diện này.

Mọi lời gọi LLM trong dự án đi qua đây; gọi theo batch, thứ tự kết quả = thứ tự prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Backend không sinh được kết quả (hết bộ nhớ, timeout, ...). Tầng gọi chuyển sang phương án dự phòng."""


@dataclass(frozen=True)
class GenResult:
    text: str
    parsed: BaseModel | None = None  # None nếu không parse được theo schema (text vẫn giữ để gửi lại cho LLM sửa)
    mean_logprob: float | None = None  # feature cho gate (T30)
    latency_s: float = 0.0
    error: str | None = None  # lý do không parse được


class LLMBackend(Protocol):
    def generate_json(self, prompts: list[str], schema: type[T], *, max_tokens: int = 4096) -> list[GenResult]:
        """Sinh JSON theo `schema` (giải mã có ràng buộc nếu backend hỗ trợ), temperature 0, seed cố định."""
        ...

    def generate_text(
        self, prompts: list[str], *, max_tokens: int = 1024, stop: list[str] | None = None
    ) -> list[GenResult]: ...


def parse_result(text: str, schema: type[T], *, mean_logprob: float | None = None, latency_s: float = 0.0) -> GenResult:
    """Parse `text` thành `schema`; lỗi → `parsed=None` kèm `error` (không ném)."""
    try:
        parsed = schema.model_validate_json(text)
    except (ValidationError, ValueError) as e:
        return GenResult(text=text, parsed=None, mean_logprob=mean_logprob, latency_s=latency_s, error=str(e)[:600])
    return GenResult(text=text, parsed=parsed, mean_logprob=mean_logprob, latency_s=latency_s)
