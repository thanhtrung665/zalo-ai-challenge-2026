#!/usr/bin/env bash
# Benchmark LLM (T09) cho một hoặc nhiều model đã tải trong models/<tên>.
#   MODELS="qwen3.5-9b qwen3-14b" PROFILE=rtx5090x2 bash remote/run_bench.sh
#   MODELS=qwen3-14b PROFILE=rtx5090x2_tp2 bash remote/run_bench.sh
#   EXTRA="--tp 2 --max-model-len 8192" ...        # ghi đè tham số hồ sơ
# Mỗi model chạy trong tiến trình riêng để trả VRAM. Chạy trong tmux (xem remote/README.md).
set -euo pipefail
cd "$(dirname "$0")/.."

MODELS="${MODELS:-qwen3.5-9b}"
PROFILE="${PROFILE:-rtx5090x2}"
N_SHOPS="${N_SHOPS:-5}"
EXTRA="${EXTRA:-}"
SPLIT=".cache/split/train"

[ -d "$SPLIT/data" ] || { echo "chưa có $SPLIT: chạy bash remote/fetch_data.sh trước" >&2; exit 1; }
mkdir -p runs/llm_bench

for m in $MODELS; do
  [ -d "models/$m" ] || { echo "chưa có models/$m: uv run python scripts/fetch_model.py $m" >&2; exit 1; }
  echo "=============== $m (profile $PROFILE $EXTRA)"
  # shellcheck disable=SC2086
  uv run python -m datamate.tools.llm_bench \
    --model "models/$m" --split "$SPLIT" --profile "$PROFILE" --n-shops "$N_SHOPS" $EXTRA \
    --out "runs/llm_bench/$m.json" 2>&1 | tee "runs/llm_bench/$m.log"
done

echo
echo "Kết quả: runs/llm_bench/*.md (bảng) và *.json (chi tiết)"
