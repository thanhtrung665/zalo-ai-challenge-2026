"""Lớp LLM: giao diện backend, backend vLLM (chính) / HF (dự phòng) và backend giả cho test."""

from datamate.llm.base import GenResult, LLMBackend, LLMError, parse_result
from datamate.llm.config import LLMProfile, load_profile
from datamate.llm.mock import MockBackend

__all__ = ["GenResult", "LLMBackend", "LLMError", "LLMProfile", "MockBackend", "load_profile", "parse_result"]
