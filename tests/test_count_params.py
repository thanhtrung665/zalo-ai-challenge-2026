from __future__ import annotations

import json
import struct

from datamate.tools.count_params import count_dir, main


def _fake_safetensors(path, tensors: dict[str, list[int]]) -> None:
    header = {"__metadata__": {"format": "pt"}}
    offset = 0
    for name, shape in tensors.items():
        n = 1
        for d in shape:
            n *= d
        header[name] = {"dtype": "BF16", "shape": shape, "data_offsets": [offset, offset + 2 * n]}
        offset += 2 * n
    raw = json.dumps(header).encode()
    path.write_bytes(struct.pack("<Q", len(raw)) + raw + b"\x00" * offset)


def test_count_sharded_model(tmp_path) -> None:
    m = tmp_path / "m"
    m.mkdir()
    _fake_safetensors(m / "model-00001.safetensors", {"a": [10, 20], "b": [5]})
    _fake_safetensors(m / "model-00002.safetensors", {"visual.c": [3, 3, 3]})
    n, warns = count_dir(m)
    assert n == 200 + 5 + 27
    assert warns == []


def test_limit_exit_code(tmp_path) -> None:
    _fake_safetensors(tmp_path / "x.safetensors", {"w": [100]})
    assert main([str(tmp_path), "--limit", "1000"]) == 0
    assert main([str(tmp_path), "--limit", "50"]) == 1


def test_warns_on_non_safetensors(tmp_path) -> None:
    (tmp_path / "pytorch_model.bin").write_bytes(b"x")
    _, warns = count_dir(tmp_path)
    assert any("KHÔNG được đếm" in w for w in warns)
