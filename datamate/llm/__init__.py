"""Lớp LLM: giao diện backend (T09 cài đặt vLLM offline) và backend giả cho test."""

from datamate.llm.base import LLMBackend, LLMError
from datamate.llm.mock import MockBackend

__all__ = ["LLMBackend", "LLMError", "MockBackend"]
