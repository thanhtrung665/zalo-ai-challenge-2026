"""Giao diện tối thiểu của backend LLM. Backend vLLM thật (T09) cài đúng giao diện này."""

from __future__ import annotations

from typing import Any, Protocol


class LLMError(RuntimeError):
    """Backend không sinh được kết quả (hết bộ nhớ, timeout, ...). Tầng gọi chuyển sang phương án dự phòng."""


class LLMBackend(Protocol):
    def generate_json(self, prompt: str, schema: dict[str, Any], *, max_tokens: int = 4096) -> str:
        """Sinh một chuỗi JSON theo `schema` (giải mã có ràng buộc), temperature 0, seed cố định."""
        ...
