# Chạy T09 trên Kaggle

Mục đích: chọn model LLM (≤ 15B tham số) bằng cách đo trên bài map schema, và gỡ lỗi lớp `datamate/llm` trên GPU thật.
Kaggle chỉ là môi trường **phát triển**. Bản nộp vẫn là Docker chạy trên 2× RTX 5090 (bf16, CUDA ≥ 12.8).

## Việc cần làm (một lần)

1. **Tạo notebook mới** trên Kaggle → *Upload Notebook* → chọn `kaggle/t09_llm_benchmark.ipynb`.
2. Bên phải: **Accelerator = GPU T4 ×2** (nếu chỉ có P100 thì xem mục *Khi vLLM không chạy*), **Internet = On**.
3. Repo là private nên cần cách đưa mã vào, chọn **một** trong hai:
   - **A. Git clone (đơn giản):** tạo GitHub token chỉ-đọc cho repo (Fine-grained, quyền *Contents: read*), thêm vào
     *Add-ons → Secrets* với tên `GITHUB_TOKEN`, bật secret cho notebook. Để nguyên `CODE_DATASET = ""`. `BRANCH` mặc định là nhánh làm việc `claude/bold-pascal-alulq0` (mã mới chưa vào `main`);
     sau khi merge thì đổi về `main`.
   - **B. Dataset:** trên máy bạn chạy `bash kaggle/pack_repo.sh` → upload `kaggle/datamate_code.zip` làm Kaggle Dataset (private),
     gắn vào notebook, đặt `CODE_DATASET = "/kaggle/input/<tên-dataset>"`.
4. Chạy lần lượt các ô. Bắt đầu với `MODEL_KEYS = ["qwen3.5-9b"]`.

## Trong notebook

| Ô | Việc | Cần để ý |
|---|---|---|
| 0 Cấu hình | model, profile, số shop | chỉ sửa ô này |
| 1 Mã | clone/giải nén, `bootstrap.sh` | in phiên bản torch, GPU, compute capability, bf16, dung lượng đĩa |
| 2 Dữ liệu | ghép `train.zip.part_*` → `/kaggle/temp/split/train` | cần các phần split có trong nhánh/dataset |
| 3 vLLM | thử `import vllm`, không có thì `pip install vllm` | có thể kéo torch khác và làm hỏng image; lỗi → xem dưới |
| 4 Model | in **giấy phép, ngày tạo, số tham số (metadata)**, tải weights, chạy `count_params` | chỉ ghi vào `MODELS.md` những gì ô này in ra |
| 5 Benchmark | `datamate.tools.llm_bench` mỗi model một tiến trình | JSON hợp lệ, lỗi validator, F1, giây/shop, VRAM đỉnh |
| 6 Gói kết quả | `/kaggle/working/t09_results.zip` | tải về, hoặc dán nội dung các ô `.md` cho tôi |

## Giới hạn phần cứng cần nhớ (ước lượng — đối chiếu với ô 1)

- **T4 ×2 (2×16 GB)**: không có bf16 (dùng `float16`), không có FlashAttention-2. Model ~9–10B fp16 ≈ 18–20 GB → vừa khi
  tensor-parallel 2. Model ~14B fp16 ≈ 29–30 GB → **không vừa** (còn thiếu chỗ cho KV cache) → phải dùng bản AWQ
  (`USE_QUANTIZED = True`).
- Thiếu bf16 nghĩa là số học khác máy chấm: **không** dùng kết quả tuyệt đối trên T4 để kết luận về PA cuối.
  Dùng nó để (a) loại model hỏng, (b) so sánh tương đối giữa các model, (c) gỡ lỗi code.
- Đĩa: `/kaggle/working` chỉ ~20 GB và được lưu; weights tải vào `/kaggle/temp` (không lưu, dung lượng lớn hơn).
- Phiên Kaggle có giới hạn thời gian và quota GPU hằng tuần; benchmark 5 shop với 9B nên chạy trong vài chục phút.

## Luật thi liên quan (không được quên)

- **Tham số:** đo trên bản gốc (bf16/fp16). Bản AWQ/GPTQ đóng gói nhiều giá trị vào một tensor int32 nên `count_params`
  trên đó sẽ đếm **thiếu**. Khi dùng bản lượng tử để benchmark, vẫn phải chốt con số bằng bản gốc.
- **Ngày phát hành / giấy phép:** weights công khai trước 01/10/2026, giấy phép cho phép dùng — ô 4 in thông tin từ Hugging Face.
- **Offline lúc inference:** tải model, cài vLLM, clone repo chỉ là bước phát triển. Trong `datamate/` không có lời gọi mạng.

## Khi vLLM không chạy được

Triệu chứng thường gặp: `pip install vllm` đổi bản torch gây lỗi; vLLM bản mới không hỗ trợ T4/P100 (compute < 8.0); hết bộ nhớ khi nạp.

1. Đặt `USE_VLLM = False`, `PROFILE = "kaggle_hf"` và chạy lại → dùng backend Transformers.
   Chậm hơn nhiều và **không** giải mã JSON có ràng buộc, nên tỉ lệ "JSON hợp lệ ngay lần đầu" sẽ thấp hơn; vòng sửa lỗi
   của `map_shop` bù một phần. Chỉ dùng để so sánh tương đối.
2. Với T4 ×2 muốn thử vLLM: trong `configs/llm.yaml` hồ sơ `kaggle_t4x2` đã đặt `enforce_eager: true`, `float16`, `max_model_len: 8192`.
   Nếu vẫn lỗi attention backend, thử đặt biến môi trường `VLLM_ATTENTION_BACKEND` (ví dụ `XFORMERS`) trước khi chạy ô 5.
3. Ghi lại tổ hợp phiên bản chạy được (ô 1 + `vllm.__version__`) — cần để ghim trong Dockerfile ở T40.

## Gửi kết quả về

Dán nội dung các file `.md` trong `t09_results.zip` (hoặc cả zip). Tôi sẽ:
1. ghi số liệu vào `docs/DECISIONS.md` và `MODELS.md` (chỉ phần được ô 4 xác minh);
2. quyết định model tạm thời cho T10/T14;
3. sửa `datamate/llm` theo lỗi thật gặp trên GPU (code vLLM chưa từng chạy trên GPU thật — hiện mới được kiểm bằng module `vllm` giả).
