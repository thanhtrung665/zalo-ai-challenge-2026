#!/usr/bin/env bash
# Chạy trong notebook Kaggle:  !bash kaggle/bootstrap.sh
# Cài phụ thuộc, in thông tin GPU và phiên bản để ghi lại. Không tải model/dữ liệu ở đây.
set -euo pipefail
cd "$(dirname "$0")/.."

pip install -q -r kaggle/requirements-kaggle.txt
pip install -q -e . --no-deps

python - <<'PY'
import importlib
import platform
import subprocess

print("python", platform.python_version())
for m in ("torch", "transformers", "pandas", "pydantic"):
    try:
        print(m, importlib.import_module(m).__version__)
    except Exception as e:  # noqa: BLE001 - chỉ để in chẩn đoán
        print(m, "KHÔNG CÓ:", e)
try:
    import torch

    print("cuda", torch.version.cuda, "| gpus:", torch.cuda.device_count())
    for i in range(torch.cuda.device_count()):
        p = torch.cuda.get_device_properties(i)
        print(f"  [{i}] {p.name} {p.total_memory / 1e9:.1f} GB compute {p.major}.{p.minor}",
              "| bf16:", torch.cuda.is_bf16_supported())
except Exception as e:  # noqa: BLE001
    print("torch/cuda lỗi:", e)
out = subprocess.run(["bash", "-c", "df -h /kaggle/working /kaggle/temp /tmp 2>/dev/null | cat"],
                     capture_output=True, text=True)
print(out.stdout)
PY
