---
name: docker-release
description: Build, kiểm tra và đóng gói image Docker nộp bài DataMate (predict.sh, offline, logs, checksum). Dùng cho task T40, T41, T43, hoặc khi người dùng muốn tạo bản nộp.
disable-model-invocation: true
argument-hint: "[build|test|package]"
---

# /docker-release

Đặc tả: SPEC §4, `.claude/rules/60-docker.md`. Hướng dẫn Docker của BTC (nếu đã có) **đè lên** mọi mặc định ở đây.

## build

1. Kiểm tra `docs/DECISIONS.md` có tổ hợp phiên bản CUDA/PyTorch/vLLM đã chạy được trên RTX 5090.
2. Dockerfile (`docker/Dockerfile`) — khung:
   - `FROM <base image của BTC hoặc image CUDA ≥ 12.8>`
   - cài Python + phụ thuộc đã ghim (`uv sync --frozen --extra data --extra llm`), copy `datamate/`, `prompts/`, `configs/`, `artifacts/`
     (nhãn DSL, few-shot, gate), `training/`, `scripts/`, `README.md`, `MODELS.md`, `predict.sh`
   - copy weights vào `/models/...`
   - `ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1`
   - `ENTRYPOINT ["bash", "/app/predict.sh"]` (hoặc theo hướng dẫn BTC)
3. `predict.sh`:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   mkdir -p /result/logs
   python -m datamate.predict --data /data --out /result
   ```
4. `docker build -t datamate:<gitsha> -f docker/Dockerfile .`

## test

1. `docker run --rm --gpus all --network none -v $PWD/data/public_test:/data:ro -v $PWD/result:/result datamate:<gitsha>`
2. Validate output; đo thời gian tổng; kiểm logs; chạy lần 2 so khác biệt (< 1% câu).
3. Trên máy 2× RTX 5090 thuê (T41): lặp lại bước 1–2, ghi thời gian + VRAM vào PROGRESS.

## package (chỉ sau `/compliance-check` đạt)

```bash
docker save datamate:<gitsha> | gzip > datamate_<gitsha>.tar.gz
sha256sum datamate_<gitsha>.tar.gz > datamate_<gitsha>.sha256
```

Upload Google Drive, đặt quyền "ai có link đều xem được", ghi link + SHA-256 + commit vào `docs/PROGRESS.md`.
Nộp form "Solution Submission" **trong ngày 16/11** (00:00–23:59); nộp lần 1 buổi sáng, giữ lần 2 để sửa.
Từ sau khi nộp: **không** đổi image; private test chạy đúng image này (T50).
