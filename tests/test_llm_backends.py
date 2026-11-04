"""Backend vLLM kiểm bằng module `vllm` giả (không cần GPU): tham số, thứ tự, logprob, bọc lỗi."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from datamate.llm import LLMError, MockBackend, load_profile
from datamate.llm.config import LLMProfile
from datamate.llm.vllm_backend import VLLMBackend, extract_json


class Out(BaseModel):
    x: int


def fake_vllm(monkeypatch: pytest.MonkeyPatch, *, new_api: bool = True, fail_chat: bool = False) -> SimpleNamespace:
    calls = SimpleNamespace(llm_kwargs=None, chat=[], sampling=[])

    class SamplingParams:
        def __init__(self, **kw: Any) -> None:
            self.kw = kw
            calls.sampling.append(kw)

    class Structured:
        def __init__(self, json: Any) -> None:
            self.json = json

    class LLM:
        def __init__(self, **kw: Any) -> None:
            calls.llm_kwargs = kw

        def chat(self, messages: Any, params: Any, **kw: Any) -> list[Any]:
            calls.chat.append((messages, params, kw))
            if fail_chat:
                raise RuntimeError("CUDA out of memory")
            structured = bool(params.kw.get("structured_outputs") or params.kw.get("guided_decoding"))
            outs = []
            for i, _m in enumerate(messages):
                text = f'{{"x": {i + 1}}}' if structured else "free"
                outs.append(
                    SimpleNamespace(
                        outputs=[
                            SimpleNamespace(text=text, cumulative_logprob=-2.0, token_ids=[1, 2, 3, 4], logprobs=None)
                        ]
                    )
                )
            return outs

    mod = types.ModuleType("vllm")
    mod.LLM, mod.SamplingParams = LLM, SamplingParams  # type: ignore[attr-defined]
    sp = types.ModuleType("vllm.sampling_params")
    if new_api:
        sp.StructuredOutputsParams = Structured  # type: ignore[attr-defined]
    else:
        sp.GuidedDecodingParams = Structured  # type: ignore[attr-defined]
    mod.sampling_params = sp  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "vllm", mod)
    monkeypatch.setitem(sys.modules, "vllm.sampling_params", sp)
    return calls


@pytest.mark.parametrize("new_api", [True, False])
def test_vllm_params_and_order(monkeypatch, new_api):
    calls = fake_vllm(monkeypatch, new_api=new_api)
    prof = load_profile("gpu_fp16")
    b = VLLMBackend("/models/m", prof)
    k = calls.llm_kwargs
    assert k["dtype"] == "float16" and k["tensor_parallel_size"] == 1 and k["seed"] == 0
    assert k["max_model_len"] == 8192 and k["enable_prefix_caching"] is True and k["trust_remote_code"] is False
    res = b.generate_json(["a", "b", "c"], Out)
    assert [r.parsed.x for r in res] == [1, 2, 3]  # thứ tự = thứ tự prompt
    sp = calls.sampling[-1]
    assert sp["temperature"] == 0.0 and sp["top_p"] == 1.0 and sp["seed"] == 0 and sp["logprobs"] == 1
    key = "structured_outputs" if new_api else "guided_decoding"
    assert key in sp and sp[key].json == Out.model_json_schema()
    assert calls.chat[-1][2]["chat_template_kwargs"] == {"enable_thinking": False}  # thinking tắt
    assert res[0].mean_logprob == pytest.approx(-0.5)  # -2.0 / 4 token


def test_vllm_text_has_no_structured_output(monkeypatch):
    calls = fake_vllm(monkeypatch)
    out = VLLMBackend("/m", LLMProfile()).generate_text(["q"], stop=["###"])
    assert out[0].text == "free"
    assert "structured_outputs" not in calls.sampling[-1] and calls.sampling[-1]["stop"] == ["###"]


def test_vllm_unparseable_output_keeps_text(monkeypatch):
    fake_vllm(monkeypatch)

    class Other(BaseModel):
        y: str

    r = VLLMBackend("/m", LLMProfile()).generate_json(["q"], Other)[0]
    assert r.parsed is None and r.text == '{"x": 1}' and r.error


def test_vllm_runtime_error_wrapped(monkeypatch):
    fake_vllm(monkeypatch, fail_chat=True)
    with pytest.raises(LLMError, match="out of memory"):
        VLLMBackend("/m", LLMProfile()).generate_json(["q"], Out)


def test_missing_vllm_gives_llm_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "vllm", None)  # import -> ImportError
    with pytest.raises(LLMError, match="vLLM"):
        VLLMBackend("/m", LLMProfile())


def test_profiles_load_and_validate(tmp_path: Path, monkeypatch):
    assert load_profile("rtx5090x2").dtype == "bfloat16"
    assert load_profile("gpu_fp16").dtype == "float16"  # GPU không có bf16
    assert load_profile("rtx5090x2_tp2").tensor_parallel_size == 2
    assert load_profile("hf_fallback").backend == "hf"
    monkeypatch.setenv("DATAMATE_LLM_PROFILE", "hf_fallback")
    assert load_profile().backend == "hf"
    monkeypatch.delenv("DATAMATE_LLM_PROFILE")
    with pytest.raises(KeyError):
        load_profile("khong_co")
    bad = tmp_path / "c.yaml"
    bad.write_text("default_profile: a\nprofiles:\n  a: {backend: vllm, dtypo: float16}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_profile(None, bad)


def test_extract_json():
    assert extract_json('Đây: {"x": 1} xong') == '{"x": 1}'
    assert extract_json("không có json") == "không có json"
    assert extract_json('{"x": ') == '{"x": '  # hỏng → giữ nguyên để parse báo lỗi


def test_mock_backend_batch_and_exhaustion():
    b = MockBackend(['{"x": 1}', '{"x": 2}'])
    assert [r.parsed.x for r in b.generate_json(["a", "b"], Out)] == [1, 2]
    with pytest.raises(LLMError):
        b.generate_json(["c"], Out)
