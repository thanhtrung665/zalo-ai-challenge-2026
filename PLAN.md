# PLAN — kế hoạch thực thi từng bước

Quy ước: làm task theo thứ tự; chỉ bắt đầu task khi mọi task trong **Phụ thuộc** đã tick `[x]`.
Mỗi task xong phải đạt **toàn bộ** tiêu chí Chấp nhận, rồi tick `[x]` và ghi một dòng vào `docs/PROGRESS.md`.
Lệnh `/next-step` tự chọn task kế tiếp theo quy ước này.

Mốc chặn (gate) không đạt → dừng, báo người dùng, không chuyển giai đoạn.

---

## Giai đoạn P0 — Nền tảng (28/10 → 31/10)

- [x] **T00 — Khởi tạo môi trường**
  - Đầu ra: `uv sync --extra dev` chạy được; `make test`, `make lint`, `make compliance` chạy được; git init + commit đầu.
  - Chấp nhận: 3 lệnh trên exit 0 trên repo khung.
  - Phụ thuộc: —

- [x] **T01 — Đặt dữ liệu và kiểm kê** _(31/10: xong với dữ liệu train; chạy lại cho public_test khi có — kết quả trong `docs/DATA_FINDINGS.md`)_
  - Việc: người dùng giải nén train/public_test vào `data/train`, `data/public_test`. Viết `datamate/tools/inventory.py`: liệt kê shop, file, sheet,
    số dòng, 15 dòng đầu mỗi sheet, README; thống kê kiểu đáp án và **hình dạng trường `alias`** trong `answers.jsonl` (string / list / table).
  - Đầu ra: `runs/inventory/train.md`, `runs/inventory/public_test.md`.
  - Chấp nhận: inventory phủ 100% file; ghi vào `docs/DECISIONS.md` hình dạng alias thực tế; cập nhật SPEC nếu khác.
  - Phụ thuộc: T00

- [x] **T02 — Xác nhận scorer chính thức** _(31/10: D-003)_
  - Việc: scorer đã có sẵn trong `datamate/eval/scorer.py`. Điều chỉnh xử lý alias theo kết quả T01; thêm test cho các ca thực tế.
  - Chấp nhận: chấm `answers.jsonl` với chính nó ra PA = 1,0; file toàn abstain ra 0; test cạnh (sai kiểu, số dạng chuỗi, list 1 phần tử, table đảo cột/hàng) pass.
  - Phụ thuộc: T01

- [x] **T03 — Chia fold** _(31/10: D-004)_
  - Việc: `datamate/eval/folds.py` → `splits/folds.json`: 5 fold theo shop (cân bằng ngành, ngành gán từ README bằng từ khoá — chỉ để chia fold),
    kịch bản bỏ một ngành, tập khoá ~300 câu (chọn shop ngẫu nhiên seed=2026).
  - Chấp nhận: không shop nào nằm ở 2 fold; tập khoá không giao với 5 fold dev; script tất định.
  - Phụ thuộc: T01

- [x] **T04 — Loader đa định dạng** (skill `/build-ingest`)
  - Việc: `datamate/ingest/` đọc csv/xlsx/sqlite, dò header, preamble, gộp sheet cùng cột, cache parquet.
    Thêm `datamate/schema/readme.py` (D-006): trích mốc dữ liệu, bảng quy đổi văn bản, danh sách file, mô tả cột bằng regex.
  - Chấp nhận: đọc 30 shop train + toàn bộ public_test không exception; test header lệch dòng, sheet theo tháng, sqlite; ≤ 60 s/shop lớn nhất.
  - Phụ thuộc: T01

- [x] **T05 — Làm sạch và parse** _(04/11: 45+ test; train 0/8,83M ô lỗi, public_test 37/3,36M = 0,001% (toàn dòng ghi chú cuối bảng); null→0: 0)_
  - Việc: parse số, ngày (serial, "thg", thiếu năm), fill-down cột cấp đơn, dedupe trong cùng đơn.
    Số lượng = **số đầu tiên** trong ô (`"1 hộp 30"` → 1, đơn vị "hộp 30"); tiền dạng `"65,000.0000"` (D-005, DATA_FINDINGS §6).
  - Chấp nhận: ≥ 40 test parser; báo cáo tỉ lệ ô ngày/số không parse được < 0,5% trên cột đã nhận diện; không có giá trị null bị đổi thành 0.
  - Phụ thuộc: T04

- [x] **T06 — Pipeline đầu-cuối tối thiểu** _(04/11: public_test 1000 câu → validate HỢP LỆ; việc nộp thử leaderboard do người dùng làm: ghi vào PROGRESS)_
  - Việc: `datamate/predict.py` đọc `--data`, ghi `submission.jsonl` từng dòng + `logs/<id>.json`; hiện tại trả abstain cho mọi câu; đồng hồ tổng.
  - Chấp nhận: chạy trên public_test ra file hợp lệ theo `datamate.eval.validate`; nộp thử 1 lần lên leaderboard (PA kỳ vọng 0) để xác nhận format.
  - Phụ thuộc: T02, T05

> **Gate G0 (31/10):** T00–T06 xong. Báo cáo người dùng.

## Giai đoạn P1 — Bộ thực thi lõi (01/11 → 07/11)

- [ ] **T09 — Lớp LLM + chọn model** (skill `/llm-runtime`)
  - Việc: `datamate/llm/` backend vLLM offline (structured JSON, temperature 0, seed) + backend mock cho test; benchmark Qwen3.5-9B vs Qwen3-14B
    vs Qwen2.5-Coder-14B trên schema mapping 5 shop (độ đúng, tốc độ, VRAM). Chọn model tạm; xác nhận lại trên DSL ở T14.
  - Chấp nhận: `count_params` ≤ 15B cho tổ hợp chọn; quyết định ghi `docs/DECISIONS.md` + `MODELS.md` (tên, link, giấy phép, ngày phát hành, số tham số).
  - Phụ thuộc: T06

- [ ] **T10 — Schema chuẩn + mapping** (skill `/build-schema-mapping`)
  - Việc: `datamate/schema/` profile cột, prompt mapping, validators, retry, CanonicalStore, Capabilities theo `docs/CANONICAL_SCHEMA.md`.
  - Chấp nhận: 30 shop train map xong không lỗi; người dùng review ≥ 10 shop, độ đúng mapping ≥ 95% cột quan trọng; test validator.
  - Phụ thuộc: T05, T09

- [x] **T11 — Bộ quy đổi thời gian** _(04/11: 93 test, D-007)_
  - Việc: `datamate/timeutil/` mọi `PeriodKind` trong `docs/DSL.md`, Tết từ `calendar.csv`, tháng/quý thiếu năm, ca sáng/chiều, kỳ so sánh.
  - Chấp nhận: ≥ 60 test tính tay, gồm biên tháng 31→30/28, đầu năm, tuần qua năm, Tết.
  - Phụ thuộc: T00

- [ ] **T12 — Executor: doanh thu, số lượng, đơn, khách, xếp hạng, so sánh kỳ** (skill `/implement-rule`)
  - Chấp nhận: mỗi luật có test; chạy bằng DSL viết tay cho 100 câu train thuộc các intent này → đúng ≥ 95%;
    executor tái tạo đúng **111/111** câu của `research/reference_checks.py` (đã xác nhận đáp án tính tay khớp chuẩn).
  - Phụ thuộc: T10, T11

- [ ] **T13 — Entity linking**
  - Việc: gộp biến thể tên trong dữ liệu (khoảng trắng kép, bản không dấu — D-005) rồi mới link câu hỏi vào thực thể.
  - Chấp nhận: test viết tắt/không dấu/sai chính tả/khoảng trắng kép; trên câu train có tên thực thể, link đúng ≥ 95%.
  - Phụ thuộc: T10

- [ ] **T14 — DSL + NLU** (skill `/add-dsl-intent`)
  - Việc: `datamate/nlu/` Pydantic `Query` theo `docs/DSL.md`, prompt builder, few-shot BM25 (chỉ từ train), rulebook retriever.
  - Chấp nhận: JSON hợp lệ 100% (structured decoding); PA end-to-end trên fold dev được đo và ghi PROGRESS.
  - Phụ thuộc: T09, T12, T13

- [ ] **T15 — Gán nhãn DSL bằng thực thi**
  - Việc: `scripts/label_dsl.py` sinh 8 ứng viên/câu train, giữ ứng viên ra đúng đáp án → `artifacts/dsl_labels.jsonl`.
  - Chấp nhận: ≥ 1.500 câu có nhãn (mục tiêu 2.000); few-shot dùng nhãn này; không dùng câu test.
  - Phụ thuộc: T14

- [ ] **T16 — Executor: công nợ, nhập hàng, kho, giá vốn, lãi, luật ngành train**
  - Chấp nhận: như T12 cho các intent này.
  - Phụ thuộc: T12

> **Gate G1 (07/11):** PA trung bình 5 fold ≥ 0,50. Chấm tập khoá một lần. Không đạt → họp lại phạm vi.

## Giai đoạn P2 — Mở rộng và dự phòng (05/11 → 11/11)

- [ ] **T20 — Codegen + sandbox** (skill `/build-codegen`)
  - Chấp nhận: test AST guard chặn os/subprocess/socket/open ghi; timeout hoạt động; trên câu DSL không biểu diễn được, codegen đúng ≥ 50% câu nó trả lời.
  - Phụ thuộc: T14

- [ ] **T21 — Rulebook runtime diff**
  - Việc: `datamate/rulebook/` parse + hash; `configs/implemented_rules.yaml`; đánh dấu câu chạm luật mới.
  - Chấp nhận: diff train vs public_test liệt kê đúng các luật thêm/đổi (kiểm tay).
  - Phụ thuộc: T14

- [ ] **T22 — Phát hiện unanswerable**
  - Chấp nhận: trên train, precision của `unanswerable` ≥ 90% (sai ít hơn 1/10 lần dùng).
  - Phụ thuộc: T10, T14

- [ ] **T23 — Luật mới của rulebook public** (mẹ & bé, sửa xe, điện thoại, khách trung thành/sộp/hay đổi ý, giờ cao điểm, NCC chính, topping…)
  - Việc: hiện thực **từ văn bản rulebook public** (được phép: rulebook là tài liệu, không phải đáp án); không nhìn câu hỏi public để chỉnh.
  - Chấp nhận: mỗi luật có test tính tay trên fixture tự tạo.
  - Phụ thuộc: T16, T21

- [ ] **T24 — Fine-tune LoRA (tuỳ chọn)** (skill `/finetune-lora`)
  - Chấp nhận: chỉ giữ nếu PA 5 fold tăng ≥ 0,02 so với few-shot; đã gộp LoRA; `count_params` không đổi.
  - Phụ thuộc: T15

## Giai đoạn P3 — Hiệu chỉnh và làm cứng (10/11 → 13/11)

- [ ] **T30 — Gate + hiệu chỉnh τ** (skill `/calibrate-gate`)
  - Chấp nhận: τ chọn trên out-of-fold; báo cáo PA theo τ; kiểm tra trên kịch bản bỏ ngành; lưu `configs/gate.yaml`.
  - Phụ thuộc: T20, T22

- [ ] **T31 — Tính tất định**
  - Chấp nhận: chạy toàn bộ public_test hai lần cùng cấu hình → số câu đổi đáp án < 1%.
  - Phụ thuộc: T30

- [ ] **T32 — Tốc độ + watchdog**
  - Chấp nhận: public_test (~1.000 câu) ≤ 3 giờ trên GPU tương đương; watchdog 5h30 đã test bằng giới hạn giả lập nhỏ.
  - Phụ thuộc: T30

> **Gate G2 — khoá code (13/11):** PA 5 fold ≥ 0,70 (mục tiêu nội bộ), T31, T32 đạt. Sau mốc này chỉ sửa lỗi chặn.

## Giai đoạn P4 — Đóng gói và nộp (12/11 → 16/11)

- [ ] **T40 — Dockerfile + predict.sh** (skill `/docker-release`)
  - Chấp nhận: `docker run --rm --gpus all --network none -v <public_test>:/data:ro -v ./result:/result` ra submission hợp lệ + logs.
  - Phụ thuộc: G2

- [ ] **T41 — Chạy thử trên 2× RTX 5090 thuê**
  - Chấp nhận: chạy hết public_test bằng đúng image; ghi thời gian, VRAM, PA (nộp public) vào PROGRESS.
  - Phụ thuộc: T40

- [ ] **T42 — Kiểm tra tuân thủ** (skill `/compliance-check` + agent `compliance-reviewer`)
  - Chấp nhận: checklist trong skill tick đủ; README image khai báo model; không còn mục đỏ.
  - Phụ thuộc: T41

- [ ] **T43 — Nộp image (chỉ trong ngày 16/11)**
  - Việc: `docker save | gzip`, `sha256sum`, upload Drive công khai, nộp form lần 1 buổi sáng; giữ lần 2 để sửa.
  - Chấp nhận: xác nhận nộp thành công; lưu link + checksum vào PROGRESS.
  - Phụ thuộc: T42

## Giai đoạn P5 — Private test (20/11 → 23/11)

- [ ] **T50 — Chạy image đã nộp trên private test**
  - Việc: **không sửa gì**; chạy đúng image đã nộp với `/data` = private_test; validate; upload `submission.jsonl` trước 23/11 23:59; lưu log.
  - Chấp nhận: file hợp lệ, đã upload; log lưu đủ để giải trình nếu BTC chạy lại lệch.
  - Phụ thuộc: T43
