---
name: calibrate-gate
description: Hiệu chỉnh cổng trả lời/abstain của DataMate — sinh feature out-of-fold, học LogisticRegression, quét ngưỡng τ tối đa hoá PA, kiểm tra trên kịch bản bỏ một ngành. Dùng cho task T30 hoặc khi tỉ lệ sai có độ tin cậy cao tăng.
---

# /calibrate-gate

Đặc tả: SPEC §3 (PA), §6.7.

1. Chạy pipeline trên 5 fold dev với gate **tắt** (trả lời mọi câu có đáp án) → mỗi câu có features + nhãn đúng/sai.
   Few-shot/nhãn DSL của fold k không dùng shop của fold k.
2. Features: `agree_exec_codegen`, `dsl_mean_logprob`, `entity_min_score`, `period_has_data`, `sanity_ok`, `answer_type_matches_question`,
   `intent_prior_acc` (tính out-of-fold), `touches_new_rule`, `used_codegen_only`, `n_llm_retries`.
3. Cross-fitting: với mỗi fold k, học `LogisticRegression(C=1.0)` trên 4 fold còn lại, dự đoán p cho fold k.
4. Quét τ từ 0,40 đến 0,90 bước 0,01: PA(τ) = (Σ_{p≥τ} (+1 nếu đúng, −1 nếu sai)) / N. Vẽ bảng PA, coverage, precision theo τ.
5. Lặp lại trên kịch bản bỏ một ngành. Nếu τ tối ưu lệch nhiều → chọn τ trong khoảng mà PA ở cả hai kịch bản đều gần đỉnh (ưu tiên τ cao hơn).
6. Học lại mô hình trên toàn bộ dev, lưu hệ số + τ vào `configs/gate.yaml` (có hash run nguồn).
7. Riêng `unanswerable`: báo cáo precision; < 90% → siết điều kiện trong executor, không dựa vào gate.
8. Ghi `docs/DECISIONS.md` (τ chọn, lý do) và PROGRESS.
