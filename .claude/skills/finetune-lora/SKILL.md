---
name: finetune-lora
description: Gán nhãn DSL cho câu train bằng thực thi (execution-guided labeling) và fine-tune LoRA cho LLM chính của DataMate, chỉ giữ nếu PA holdout tăng. Dùng cho task T15 và T24.
---

# /finetune-lora

Đặc tả: SPEC §6.4, §7. Chỉ dùng **dữ liệu train** và dữ liệu tự tổng hợp từ train.

## A. Gán nhãn DSL bằng thực thi (T15) — `scripts/label_dsl.py`

1. Với mỗi câu train: sinh 8 ứng viên DSL (temperature 0,8, seed theo id câu để tái lập).
2. Chạy executor từng ứng viên; giữ ứng viên đầu tiên ra **đúng** gold (scorer chính thức). Nhiều ứng viên đúng → chọn cái ngắn nhất.
3. Ghi `artifacts/dsl_labels.jsonl`: `{id, business_id, question, as_of_date, dsl, verified: true}`. Thống kê tỉ lệ có nhãn theo intent.
4. Câu không có nhãn: ghi vào `artifacts/dsl_unlabeled.jsonl` để phân tích (thiếu metric? luật sai?).

## B. Tăng cường

Mỗi câu có nhãn tạo 2–3 biến thể bằng **luật** (bỏ dấu, viết tắt từ `configs/abbreviations.yaml`, đổi trật tự cụm thời gian) — giữ nguyên DSL.

## C. LoRA (T24) — `training/sft_lora.py`

- transformers + peft + trl `SFTTrainer`; chat template của model; loss chỉ trên phần trả lời.
- r=16, α=32, dropout=0,05, target = q,k,v,o,gate,up,down; lr=1e-4 cosine, warmup 3%; 2–3 epoch; seq 4096; batch hiệu dụng 32; bf16;
  QLoRA 4-bit nếu GPU < 40 GB; seed=2026.
- Huấn luyện **theo fold** để đánh giá công bằng (model fold k không thấy shop fold k) — tối thiểu 2 fold để ước lượng lợi ích.
- Lợi ích ≥ +0,02 PA → huấn luyện bản cuối trên toàn bộ train, `merge_and_unload`, lưu safetensors bf16 vào `models/main-lora-merged/`.
- `count_params` lại; cập nhật `MODELS.md` (ghi "fine-tune LoRA đã gộp").
- Kiểm tra tái lập trên bản gộp.
