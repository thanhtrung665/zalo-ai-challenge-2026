"""Backend giả: trả lần lượt các phản hồi đã định sẵn, ghi lại prompt để test kiểm tra."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from datamate.llm.base import LLMError


class MockBackend:
    def __init__(self, responses: Sequence[str] | Callable[[str], str]) -> None:
        self._responses = responses
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, schema: dict[str, Any], *, max_tokens: int = 4096) -> str:
        self.prompts.append(prompt)
        if callable(self._responses):
            return self._responses(prompt)
        i = len(self.prompts) - 1
        if i >= len(self._responses):
            raise LLMError("MockBackend hết phản hồi")
        return self._responses[i]
