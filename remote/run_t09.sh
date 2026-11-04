#!/usr/bin/env bash
# Chạy trọn quy trình T09 trên máy GPU thuê, dừng ngay khi một bước hỏng:
#   môi trường -> dữ liệu -> xác minh + tải model -> smoke test -> benchmark
#   MODELS="qwen3.5-9b" bash remote/run_t09.sh
# Biến: MODELS (mặc định qwen3.5-9b), PROFILE (mặc định lấy từ env_report), EXTRA (ghi đè tham số), N_SHOPS.
# Chạy trong tmux/nohup để không mất khi SSH rớt:  tmux new -s t09   rồi chạy lệnh trên.
set -euo pipefail
cd "$(dirname "$0")/.."

MODELS="${MODELS:-qwen3.5-9b}"
N_SHOPS="${N_SHOPS:-5}"
EXTRA="${EXTRA:-}"
mkdir -p runs/logs
log() { echo; echo "######## $(date '+%H:%M:%S') $*"; }

log "1/5 môi trường"
uv run python scripts/env_report.py --out runs/env_report.json >/dev/null
PROFILE="${PROFILE:-$(uv run python -c "import json;print(json.load(open('runs/env_report.json'))['recommended_profile'] or '')")}"
if [ -z "$PROFILE" ]; then
  echo "env_report không đề xuất được hồ sơ (xem runs/env_report.json: notes). Đặt PROFILE=... rồi chạy lại." >&2
  exit 1
fi
echo "profile = $PROFILE"

log "2/5 dữ liệu"
bash remote/fetch_data.sh

log "3/5 xác minh thẻ model + tải"
# shellcheck disable=SC2086
uv run python scripts/fetch_model.py $MODELS

for m in $MODELS; do
  log "4/5 smoke test $m"
  # shellcheck disable=SC2086
  uv run python scripts/llm_smoke.py --model "models/$m" --profile "$PROFILE" $EXTRA --out "runs/llm_smoke_$m.json" \
    2>&1 | tee "runs/logs/smoke_$m.log"
done

log "5/5 benchmark"
MODELS="$MODELS" PROFILE="$PROFILE" EXTRA="$EXTRA" N_SHOPS="$N_SHOPS" bash remote/run_bench.sh

log "XONG. Lấy về: runs/env_report.json runs/llm_smoke_*.json runs/llm_bench/*.md models/*/MODEL_INFO.json"
