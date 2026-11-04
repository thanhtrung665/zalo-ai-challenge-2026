#!/usr/bin/env bash
# Chạy MỘT lần trên máy GPU thuê, trong thư mục repo:  bash remote/setup.sh
# Cài uv, đồng bộ môi trường (dev + data + llm), in báo cáo GPU và hồ sơ LLM đề xuất.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== GPU"
if ! command -v nvidia-smi >/dev/null; then
  echo "Không thấy nvidia-smi: máy này không có driver NVIDIA (hoặc không phải máy GPU)." >&2
  exit 1
fi
nvidia-smi --query-gpu=index,name,memory.total,compute_cap,driver_version --format=csv

if ! command -v uv >/dev/null; then
  echo "== cài uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "== đồng bộ môi trường (có thể mất vài phút do torch/vLLM)"
uv sync --extra dev --extra data --extra llm

echo "== báo cáo môi trường"
uv run python scripts/env_report.py --out runs/env_report.json

echo
echo "Xong. Đọc 'recommended_profile' và 'notes' ở trên."
echo "Nếu vLLM không import được hoặc báo thiếu kernel (Blackwell cần CUDA >= 12.8), xem remote/README.md mục 'Sự cố thường gặp'."
