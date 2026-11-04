# Chạy trên máy GPU thuê (SSH / Antigravity)

Mục đích: chạy T09 (chọn model), sau đó T10/T14/T15/T20 và bài thử T41 trên GPU thật. Máy thuê nên càng gần máy chấm càng tốt:
**2× RTX 5090 (32 GB/card), CUDA ≥ 12.8, bf16**. Nếu máy khác (A100/H100/4090...) thì `scripts/env_report.py` đề xuất hồ sơ phù hợp
và kết quả vẫn dùng được để chọn model, nhưng số cuối cùng phải xác nhận lại trên 2× 5090 (T41).

Giả định: Linux có driver NVIDIA, có Internet (chỉ để phát triển: cài gói, tải model, git pull). Lúc *inference* trong Docker thì tắt mạng
và code trong `datamate/` không có lời gọi mạng nào.

## 1. Kết nối

Trong `~/.ssh/config` trên máy bạn (Antigravity đọc file này như VS Code Remote-SSH; nếu giao diện khác thì dùng `ssh dm-gpu` thường):

```
Host dm-gpu
    HostName <IP máy thuê>
    User <user>
    Port <cổng SSH>
    IdentityFile ~/.ssh/<khoá>
    ServerAliveInterval 30
    ServerAliveCountMax 6
```

Mở thư mục repo trên máy từ xa trong Antigravity (Connect to Host → `dm-gpu`). Terminal tích hợp chạy thẳng trên máy GPU.

**Mọi lệnh dài phải chạy trong `tmux`** để SSH rớt không giết tiến trình:

```bash
tmux new -s t09          # vào phiên; thoát giữ nguyên: Ctrl-b rồi d
tmux attach -t t09       # vào lại
```

## 2. Lấy mã (repo private)

Cách an toàn nhất là **deploy key chỉ-đọc** (không để token cá nhân trên máy thuê):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/datamate_deploy -N ""
cat ~/.ssh/datamate_deploy.pub        # dán vào GitHub: repo → Settings → Deploy keys (KHÔNG tick "Allow write access")
GIT_SSH_COMMAND='ssh -i ~/.ssh/datamate_deploy -o IdentitiesOnly=yes' \
  git clone -b claude/bold-pascal-alulq0 git@github.com:thanhtrung665/zalo-ai-challenge-2026.git
cd zalo-ai-challenge-2026
git config core.sshCommand 'ssh -i ~/.ssh/datamate_deploy -o IdentitiesOnly=yes'   # để git pull sau này dùng khoá đó
```

Mã mới đang ở nhánh `claude/bold-pascal-alulq0` (chưa vào `main`); sau khi merge thì clone `main`.
Không dán token/khoá vào chat, không ghi vào file trong repo (`.env` đã được `.gitignore`).

## 3. Chạy

Cách nhanh — một lệnh, dừng ngay khi một bước hỏng:

```bash
bash remote/setup.sh                     # lần đầu: cài uv + môi trường + báo cáo GPU
tmux new -s t09
MODELS="qwen3.5-9b" bash remote/run_t09.sh
```

`run_t09.sh` chạy lần lượt: báo cáo môi trường → ghép dữ liệu → **xác minh thẻ model rồi tải** → smoke test → benchmark.
Chạy từng bước riêng khi cần gỡ lỗi:

| Bước | Lệnh | Cho ra |
|---|---|---|
| Môi trường | `uv run python scripts/env_report.py` | `runs/env_report.json`: GPU, bf16, phiên bản torch/vLLM, hồ sơ đề xuất |
| Dữ liệu | `bash remote/fetch_data.sh` | `.cache/split/train`, `.cache/split/public_test` |
| Model | `uv run python scripts/fetch_model.py qwen3.5-9b` | kiểm giấy phép / ngày tạo / số tham số **trước khi tải**, rồi `models/<tên>/MODEL_INFO.json` |
| Smoke | `uv run python scripts/llm_smoke.py --model models/qwen3.5-9b --profile rtx5090x2` | nạp được không, JSON hợp lệ, **tất định**, độc lập batch, VRAM |
| Bench | `MODELS=qwen3.5-9b PROFILE=rtx5090x2 bash remote/run_bench.sh` | `runs/llm_bench/<tên>.{json,md}` |

Model ~14B bf16 (≈ 30 GB) phải chia 2 card: `PROFILE=rtx5090x2_tp2` (hoặc `EXTRA="--tp 2"`).
Hồ sơ nằm ở `configs/llm.yaml`; ghi đè nhanh bằng `--tp --dtype --max-model-len --gpu-util --quantization`.

## 4. Đọc kết quả

- **Smoke**: `json_valid` phải là `4/4`, `deterministic_repeat` phải `true`. Nếu `batch_invariant` là `false` thì kết quả của một câu phụ thuộc
  vào các câu cùng batch → BTC chạy lại có thể lệch; phải cố định thứ tự và kích thước batch ở `predict` (T31). Đây không phải lỗi chặn nhưng phải ghi lại.
- **Bench**: `json_valid_rate` (JSON đúng ngay lần đầu), `mean_errors` (lỗi validator, tín hiệu độc lập), `mean_f1` (khớp mapping tham chiếu — tham chiếu là
  bản nháp heuristic chưa được duyệt, xem D-008, nên chỉ để tham khảo), thời gian/shop, VRAM đỉnh.
- **Luật thi**: `fetch_model.py` loại model vượt 15B hoặc tạo từ 01/10/2026; ngày tạo repo chỉ là xấp xỉ ngày công khai, vẫn phải đọc model card.
  Chỉ ghi vào `MODELS.md` những gì các script in ra.

## 5. Lấy kết quả về

Tải bằng Antigravity (chuột phải file → Download) hoặc từ máy bạn:

```bash
scp -r dm-gpu:~/zalo-ai-challenge-2026/runs/{env_report.json,llm_smoke_*.json,llm_bench} ./runs_remote/
scp -r dm-gpu:~/zalo-ai-challenge-2026/models/*/MODEL_INFO.json ./runs_remote/
```

Rồi dán nội dung các file `.md` / `.json` cho tôi (hoặc copy vào repo và push). Tôi sẽ ghi vào `docs/DECISIONS.md`, `MODELS.md` và chọn model tạm cho T10/T14.

## Sự cố thường gặp

| Triệu chứng | Hướng xử lý |
|---|---|
| `no kernel image is available` / lỗi sm_120 | Blackwell cần torch + vLLM build với CUDA ≥ 12.8. Kiểm `runs/env_report.json` (`cuda_runtime`), cập nhật driver/torch/vLLM. |
| Lỗi attention backend | Thử `VLLM_ATTENTION_BACKEND=FLASHINFER` (hoặc `FLASH_ATTN`) trước lệnh chạy; FA3 không hỗ trợ Blackwell tiêu dùng. |
| CUDA out of memory khi nạp | Hạ `--max-model-len` / `--gpu-util`, hoặc dùng `rtx5090x2_tp2` cho model 14B. |
| vLLM không cài/chạy được | Dùng `--profile hf_fallback` (Transformers, không giải mã ràng buộc, chậm): chỉ để so sánh tương đối. |
| `fetch_model.py` báo không đọc được thẻ | Máy không ra được `huggingface.co` hoặc tên repo sai; model gated cần `export HF_TOKEN=...` (đừng ghi vào file). |
| SSH rớt giữa chừng | Chạy lại trong tmux; `llm_bench` ghi kết quả khi xong từng model. |

Ghim phiên bản chạy được (torch, vLLM, CUDA, driver trong `runs/env_report.json`) vào `docs/DECISIONS.md` — T40 cần đúng tổ hợp này trong Dockerfile.

## Chi phí

Dừng/xoá instance khi không chạy. Model và `.cache/` nằm trên đĩa máy thuê và mất theo máy: lấy kết quả về trước khi huỷ.
