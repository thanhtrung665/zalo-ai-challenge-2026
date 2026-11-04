"""Backend giả: trả lần lượt các phản hồi định sẵn (hoặc hàm prompt→text), ghi lại prompt để test kiểm tra."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from datamate.llm.base import GenResult, LLMError, T, parse_result


class MockBackend:
    def __init__(self, responses: Sequence[str] | Callable[[str], str]) -> None:
        self._responses = responses
        self.prompts: list[str] = []

    def _next(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if callable(self._responses):
            return self._responses(prompt)
        i = len(self.prompts) - 1
        if i >= len(self._responses):
            raise LLMError("MockBackend hết phản hồi")
        return self._responses[i]

    def generate_json(self, prompts: list[str], schema: type[T], *, max_tokens: int = 4096) -> list[GenResult]:
        return [parse_result(self._next(p), schema) for p in prompts]

    def generate_text(
        self, prompts: list[str], *, max_tokens: int = 1024, stop: list[str] | None = None
    ) -> list[GenResult]:
        return [GenResult(text=self._next(p)) for p in prompts]
