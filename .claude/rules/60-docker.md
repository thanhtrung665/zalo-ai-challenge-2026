---
paths:
  - "docker/**"
  - "Dockerfile"
  - "predict.sh"
  - "datamate/predict.py"
---

# Docker và entrypoint

Đặc tả: SPEC §4 (R3, R5, R7, R8).

- Base image theo hướng dẫn Docker của BTC (CUDA ≥ 12.8, hỗ trợ RTX 5090). Chưa có hướng dẫn → image CUDA ≥ 12.8 chính thức, ghi rõ trong DECISIONS.
- Weights copy sẵn vào `/models`; đặt `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `VLLM_NO_USAGE_STATS=1`, `DO_NOT_TRACK=1`.
- `predict.sh`: `set -euo pipefail`; gọi `python -m datamate.predict --data /data --out /result`; không cần tham số khác.
- `/data` read-only; file tạm vào `/tmp`. Tạo `/result/logs/` nếu chưa có.
- `submission.jsonl` ghi + flush từng dòng; câu lỗi → abstain + log lỗi; watchdog 5h30 → abstain phần còn lại rồi thoát 0.
- Image phải chạy được với `docker run --network none`. Kiểm tra bằng lệnh trong skill `/docker-release` trước mỗi lần build nộp.
- Image chứa mã huấn luyện + inference + README (có bảng model từ `MODELS.md`).
- Phiên bản thư viện ghim cố định; không `pip install` lúc container chạy.
