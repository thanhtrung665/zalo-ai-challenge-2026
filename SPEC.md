# SPEC — DataMate Agent (Zalo AI Challenge 2026, bảng DataMate)

> Đặc tả kỹ thuật chuẩn của dự án. Mọi quyết định thiết kế, code và kiểm thử phải khớp tài liệu này.
> Khi tài liệu này mâu thuẫn với **trang chính thức của cuộc thi** (https://challenge.zalo.ai/portal/datamate)
> hoặc **rulebook của split đang chạy** (`<split>/rulebook.md`), nguồn chính thức thắng và SPEC phải được sửa lại
> (ghi vào `docs/DECISIONS.md`).

Phiên bản: 1.0 · Ngày: 2026-10-27 · Nguồn: bản "DataMate — Chiến lược Top 10 & vào chung kết".

---

## 1. Mục tiêu

| Mục tiêu | Chỉ số | Ngưỡng |
|---|---|---|
| Vào Top 10 bảng chung cuộc, nhắm top 2 (chung kết) | PA khi BTC chạy lại image trên private test | Cao nhất có thể |
| Mốc nội bộ G1 (07/11) | PA holdout chia theo shop | ≥ 0,50 |
| Mốc nội bộ G2 — khoá code (13/11) | PA holdout chia theo shop | ≥ 0,70 |
| Tái lập | Số câu đổi đáp án giữa 2 lần chạy | < 1% (luật cho phép lệch PA ≤ 0,03) |
| Tốc độ | Thời gian toàn bộ ~500 câu private gồm load model, trên 2× RTX 5090 | ≤ 2 giờ (luật: ≤ 6 giờ) |

Không phải mục tiêu: tối ưu leaderboard public bằng mọi giá; điểm public chỉ để đo độ lệch phân phối.

## 2. Bài toán

Với mỗi câu hỏi, agent nhận:

- gói dữ liệu của **một** doanh nghiệp: `data/<business_id>/` gồm một hoặc nhiều file `.csv`, `.xlsx`, `.sqlite` + `README.md`
  (chất lượng README rất khác nhau, có shop gần như không có);
- câu hỏi tiếng Việt khẩu ngữ (không dấu, viết tắt, sai chính tả);
- `as_of_date` = "hôm nay" để quy đổi mọi mốc thời gian tương đối;
- `rulebook.md` + `calendar.csv` (lịch âm–dương) dùng chung cho cả split.

Agent trả về **một** đáp án có kiểu, hoặc `unanswerable` (dữ liệu không đủ), hoặc `abstain` (tự chọn không trả lời).

### 2.1. Cấu trúc split

```
<split>/
├── data/<business_id>/   *.csv | *.xlsx | *.sqlite  +  README.md
├── rulebook.md           luật mặc định của split (KHÁC NHAU giữa các split)
├── calendar.csv          lịch âm–dương
├── questions.jsonl       {"id","business_id","question","as_of_date"}
└── answers.jsonl         chỉ có ở train: {"id","type","answer","alias"}; unanswerable có "answer": null
```

| Split | Số shop | Số câu | Đáp án |
|---|---|---|---|
| train | 30 | ~3.000 | có |
| public_test | 10–20 | ~1.000 | ẩn (leaderboard) |
| private_test | 10–20 | ~500 | ẩn; **có ngành mới** |

Mỗi shop 12–30 tháng dữ liệu, vài trăm đến ~300.000 dòng. **Đã xác minh trên dữ liệu train thật (31/10) — chi tiết `docs/DATA_FINDINGS.md`:**

- 30 shop, 339 bảng/sheet (21 csv, 107 xlsx, 1 sqlite), ~4 triệu dòng vật lý, đọc được hết. Ngành: 6 tạp hoá, 5 cà phê, 6 VLXD, 6 nhà thuốc,
  6 nhà hàng, 1 không rõ. Shop 40 câu là shop một file phẳng; shop 118–119 câu có nhiều file/bảng.
- Header có thể ở dòng 2–4 (preamble "SỔ CHI TIẾT BÁN HÀNG"…); ngày lẫn định dạng ("1 thg 6 2025", dd/mm/yyyy, serial); tiền lẫn định dạng
  ("38,000", "20000", "65,000.0000"); **ô số lượng lẫn chữ** ("1 chai") và **đơn vị chứa số** ("1 hộp 30", "1 bao 25kg");
  **tên cùng mặt hàng có biến thể** (khoảng trắng kép, bản không dấu); tên trạng thái khác nhau giữa các shop ("Đổi trả", "Đã hoàn hàng",
  "Đang giao dịch"…); khách lẻ ghi "Khách lẻ"/"lẻ"; sổ chia sheet theo tháng; file tách `_1`, `_2`, `_2026`.
- **README luôn có** `## File`, `## Quy ước` và câu "Dữ liệu có đến hết dd/mm/yyyy"; 18/30 README ghi quy đổi đơn vị dạng "1 thùng = 24 lon".
- `as_of_date`: 79% câu bằng đúng mốc README, 21% sớm hơn; không câu nào sau mốc.
- Phân bố kiểu đáp án train: number 62,8% (100% số nguyên) · percent 19,3% · list 6,4% · date 4,8% (16 câu dạng YYYY-MM) · string 2,9% ·
  unanswerable 2,3% · boolean 0,8% · table 0,6% (đều là top khách nợ).
- 111 câu đã được tính tay theo rulebook và **khớp 111/111** với đáp án chuẩn (`research/reference_checks.py`).

## 3. Đầu ra và luật chấm (chính thức)

Mỗi dòng `submission.jsonl`: `{"id": "...", "type": "...", "answer": ...}`. Câu thiếu = abstain. `reason` tuỳ chọn, phải là chuỗi.

| type | Format bắt buộc | So khớp |
|---|---|---|
| `number` | JSON number, không đơn vị, không dấu nghìn; tiền là số nguyên VND | Khớp tuyệt đối (tham chiếu là số nguyên hoặc làm tròn 2 chữ số) |
| `percent` | JSON number là số phần trăm: 12,4% → `12.4` | Khớp sau khi làm tròn 2 chữ số, đúng dấu |
| `string` | Tên nguyên văn từ dữ liệu, đủ dấu | Chuẩn hoá: NFC → chữ thường → mọi ký tự không phải chữ/số/khoảng trắng thành khoảng trắng → gộp khoảng trắng. **Không bỏ dấu.** Chấp nhận mọi cách viết có trong dữ liệu của shop và **mã** |
| `date` | `"YYYY-MM-DD"`; câu hỏi theo tháng `"YYYY-MM"` | Khớp tuyệt đối |
| `boolean` | `true` / `false` | Khớp tuyệt đối |
| `list` | Mảng JSON có thứ tự; một phần tử vẫn là mảng | Khớp đúng độ dài và từng vị trí (luật string/number) |
| `table` | `{"columns": [...], "rows": [[...], ...]}`, ô số là JSON number | Cột so theo tên chuẩn hoá, không khớp tên thì theo vị trí; hàng so như tập hợp |
| `unanswerable` | `{"type": "unanswerable", "reason": "..."}` | Đúng khi và chỉ khi tham chiếu là unanswerable |
| `abstain` | `{"type": "abstain"}` | Luôn 0 điểm |

**Trường `alias` trong answers.jsonl (đã xác nhận, D-003):** string → list phẳng (mã + cách viết khác); list tên → list-các-list theo
vị trí; table → list-các-list theo **hàng**, áp cho ô tên; kiểu khác → `[]`. Vì vậy trả **mã** hoặc **tên có trong dữ liệu** đều được chấm đúng.

**Penalized Accuracy:** PA = (1/N) Σ sᵢ, sᵢ = +1 đúng, 0 abstain, −1 sai. Trả lời bất kỳ cho câu unanswerable là sai.
Bằng điểm → ít thời gian inference hơn thắng → nộp sớm hơn thắng.

**Hệ quả thiết kế:** kỳ vọng mỗi câu trả lời = 2p − 1 ⇒ chỉ trả lời khi p > 0,5 (thận trọng: τ ≈ 0,6 cho ngành mới).
`unanswerable` cũng là một câu trả lời: chỉ dùng khi có bằng chứng cứng (§6.7).

**Xếp hạng:** theo tiêu chí trong câu hỏi hoặc mặc định của rulebook, giảm dần, chỉ trên đơn hợp lệ; bằng nhau xếp theo **mã tăng dần**
(không có mã thì theo tên). Câu có hoà ở biên top-k đã bị BTC loại. Ít hơn k ứng viên thì trả tất cả.

## 4. Ràng buộc cứng (vi phạm = loại)

| # | Ràng buộc | Cách đảm bảo trong dự án |
|---|---|---|
| R1 | Model: weights công khai trước **01/10/2026**, giấy phép cho phép dùng; được fine-tune | Ghi model card, giấy phép, ngày phát hành vào `MODELS.md` |
| R2 | **Tổng tham số mọi model dùng lúc inference ≤ 15B** (LLM, embedding, reranker, classifier; MoE tính đủ; tải cùng lúc hay không) | `python -m datamate.tools.count_params` đọc safetensors, tính cả vision encoder |
| R3 | **Không dịch vụ ngoài**: inference offline hoàn toàn, image chạy với mạng tắt | Không có `requests/httpx/openai/anthropic` trong code runtime; test `docker run --network none` |
| R4 | **Không có người can thiệp**; cấm hard-code đáp án, cấm logic theo `business_id` hay `id` câu hỏi | Hook + `scripts/check_compliance.py` chặn literal `biz_\d+`, `q_[0-9a-f]+` trong code runtime |
| R5 | Agent được sinh và chạy code trong container; `/data` **read-only** | File tạm vào `/tmp`; sandbox cho code sinh ra |
| R6 | Chỉ dùng train, dữ liệu tự tổng hợp, dữ liệu/model công khai. **Cấm** dùng public/private test để huấn luyện hoặc dò đáp án | Không đọc `questions.jsonl` của test trong code huấn luyện; không gán nhãn tay câu test |
| R7 | Máy chấm 2× RTX 5090 (32 GB/card), 512 GB RAM; **≤ 6 giờ** cho toàn bộ private gồm load model; CUDA ≥ 12.8 | Đồng hồ tổng 5h30 rồi abstain phần còn lại |
| R8 | Điểm chung cuộc = BTC chạy lại image; lệch \|PA nộp − PA chạy lại\| > 0,03 không giải thích được → loại. Quá giờ thì chỉ chấm phần đã ghi | Tất định; ghi `submission.jsonl` từng dòng + log từng câu |

**Docker nộp bài:** chứa mã huấn luyện + inference, weights, `predict.sh`, README. `predict.sh` đọc `/data` (mount read-only),
ghi `/result/submission.jsonl` và log từng câu vào `/result/logs/` (tối thiểu: id, đáp án cuối, thời gian; nên có DSL, code sinh ra, output).

**Mốc thời gian (GMT+7):** nộp public 26/10–16/11 (5 lần/ngày) · **form nộp image chỉ mở 16/11 00:00–23:59**, tối đa 2 lần, lấy lần cuối,
gửi link Drive công khai + checksum · private test phát hành 20/11 09:00 · nộp `submission.jsonl` private trước 23/11 23:59 ·
khoá thành viên từ 17/11 · công bố top 2 ngày 02/12 · kết quả 12/12.

## 5. Kiến trúc

```
                     ┌──────────────── Mỗi shop · một lần khi khởi động ────────────────┐
 data/<biz>/ ──► [1] ingest ──► [2] schema mapping (LLM + validator) ──► CanonicalStore + Capabilities
                     └───────────────────────────────────────────────────────────────────┘
                                                                     │ dùng chung
 question + as_of ──► [3] entity linking ──► [4] NLU → DSL (LLM) ──► [5] executor (code, theo rulebook) ──┐
                                               │ ngoài DSL / đối chiếu                                     ▼
                                               └──► [6] codegen (LLM viết pandas, sandbox) ──────► [7] gate ──► formatter ──► submission.jsonl
                                                                                                    p < τ → abstain      + logs/
```

Nguyên tắc: **mọi con số do code tính**; LLM chỉ dùng ở [2], [4], [6] với giải mã có ràng buộc và temperature 0.

### 5.1. Cấu trúc mã nguồn

```
datamate/
├── config.py            # hằng số, đường dẫn, ngưỡng (đọc từ configs/*.yaml)
├── io/                  # đọc questions/answers/submission, ghi jsonl từng dòng
├── ingest/              # [1] loaders (csv/xlsx/sqlite), header detect, parse số/ngày, fill-down, dedupe
├── schema/              # [2] profile cột, mapping LLM, validators, CanonicalStore, Capabilities
├── entities/            # [3] chỉ mục tên, chuẩn hoá, rapidfuzz, từ điển viết tắt
├── nlu/                 # [4] DSL (Pydantic), prompt builder, few-shot BM25, rulebook retriever
├── timeutil/            # quy đổi period theo as_of_date, tuần, tháng, quý, Tết (calendar.csv)
├── executor/            # [5] rule library + metric functions + DuckDB
├── codegen/             # [6] prompt, sandbox runner, AST guard
├── gate/                # [7] features, calibrator, decision
├── format/              # ép kiểu đầu ra, làm tròn
├── llm/                 # backend vLLM offline + backend mock cho test
├── rulebook/            # parse rulebook thành rule rows, diff với rule đã hiện thực
├── eval/                # scorer chính thức, validator, báo cáo
├── tools/               # count_params, inventory, ...
└── predict.py           # entrypoint: python -m datamate.predict --data /data --out /result
```

## 6. Đặc tả từng tầng

### 6.1. [1] Ingest — `datamate/ingest`

- Đọc CSV với `dtype=str` (giữ chuỗi gốc), dò encoding (utf-8-sig → utf-8 → cp1258) bằng charset-normalizer.
- XLSX: python-calamine đọc mọi sheet; openpyxl `read_only=True` chỉ để lấy number format các cột nghi là ngày.
- SQLite: mọi bảng qua `sqlite3` (mở `mode=ro` bằng URI).
- **Dò header** trong 12 dòng đầu: điểm = tỉ lệ ô chữ + tỉ lệ ô khác nhau + số ô khớp từ vựng cột (ngày, mã, tên, sl, đơn giá, thành tiền, trạng thái…).
  Dòng phía trên header là preamble → metadata (vd. năm của sheet).
- Gộp các sheet/file cùng tập cột (vd. sheet theo tháng) thành một bảng logic, giữ cột nguồn `_src_file`, `_src_sheet`, `_src_row`.
- **Fill-down** cột cấp đơn: cột trống đúng ở các dòng tiếp nối của cùng đơn (rulebook §8).
- **Dedupe**: chỉ bỏ dòng giống hệt nhau **trong cùng một đơn**. Bảng không ghi theo đơn: giữ nguyên mọi dòng.
- **Parse số**: "1.250.000", "1,250,000", "1.250.000đ", "65,000.0000", "(50.000)", "-50.000"; không parse được → null, **không bao giờ thành 0**.
- **Parse số lượng**: lấy **số đầu tiên** trong ô; phần chữ còn lại là đơn vị và có thể chứa số ("1 hộp 30" → 1 × "hộp 30"; "1 bao 25kg").
- **Parse ngày**: Excel serial 30000–60000; chuỗi ưu tiên ngày trước tháng; "thg"; ngày thiếu năm → năm của sheet.
- Cache parquet `/tmp/datamate_cache/<sha256-file>/`.
- Đầu ra: `RawTable(name, df, source, header_row, notes)`.

**Chấp nhận:** đọc 100% file train không lỗi; test đơn vị cho mọi parser; báo cáo inventory `runs/inventory/*.md`.

### 6.2. [2] Schema mapping — `datamate/schema`

Map mọi shop về schema chuẩn (`docs/CANONICAL_SCHEMA.md`). Quy trình:
0. **Parse README bằng regex** (`schema/readme.py`, D-006): mốc "Dữ liệu có đến hết", bảng quy đổi "1 X = N Y", danh sách file,
   mô tả cột trong `## Cột trong <file>`, các câu quy ước (nối qua mã/tên, sheet theo tháng, thông tin đơn lặp lại).
1. Profile từng cột: tên, kiểu suy ra, tỉ lệ null, số giá trị khác nhau, 5 giá trị mẫu, min/max.
2. LLM nhận README + profile → JSON mapping (Pydantic `ShopMapping`), giải mã có ràng buộc.
3. Validator bằng code: khoá duy nhất; Σ thành tiền dòng ≈ tổng đơn (khi có); SL > 0 (trừ dòng trả); giá trị trạng thái map đủ vào 4 loại
   (hoàn thành, huỷ, trả hàng, đang giao — sổ không có cột trạng thái thì đọc Ghi chú); đơn vị quy đổi hợp lệ.
4. Validator fail → gọi lại LLM kèm lỗi (tối đa 2 lần) → vẫn fail thì đánh dấu khái niệm đó **không khả dụng**.
5. Sinh `Capabilities`: có/không mã khách, giá vốn dòng, giá vốn danh mục, phiếu nhập, lô/hạn dùng, công nợ/thanh toán, chi phí, nhân viên,
   giờ tạo đơn, kênh bán, … + khoảng ngày có dữ liệu theo từng loại sự kiện.

Mapping chạy một lần mỗi shop lúc khởi động và được log đầy đủ. **Không** có mapping viết tay theo `business_id`.

**Chấp nhận:** 30 shop train map xong; báo cáo độ chính xác mapping do người review trên ≥ 10 shop; test validator.

### 6.3. [3] Entity linking — `datamate/entities`

- **Gộp biến thể tên trong dữ liệu trước** (D-005): khoá = bỏ dấu + chữ thường + gộp khoảng trắng; tên hiển thị = cách viết phổ biến nhất
  hoặc mã. Cảnh báo nếu một khoá gom nhiều mã hàng khác nhau. Mọi phép tính theo mặt hàng/khách dùng khoá đã gộp.
- Chỉ mục cho hàng, nhóm hàng, khách, nhân viên, NCC, chi nhánh, hoạt chất… từ CanonicalStore.
- Khoá tìm: NFC → chữ thường → bỏ dấu (NFD bỏ combining, đ→d) → gộp khoảng trắng. Bản bỏ dấu **chỉ để tìm**.
- Từ điển viết tắt: `sp, dc/đc, ko/k, cf, ts, sl, tr (triệu), k (nghìn), hn (hôm nay), ...` trong `configs/abbreviations.yaml`.
- rapidfuzz `WRatio`: ≥ 90 nhận; 75–90 nhận + hạ độ tin cậy; < 75 không tìm thấy. Có mã → khớp mã trước.
- Đáp án luôn là **tên nguyên văn trong dữ liệu** (hoặc mã).

### 6.4. [4] NLU → DSL — `datamate/nlu`

DSL đặc tả trong `docs/DSL.md` (Pydantic `Query`). LLM chỉ điền cấu trúc; thời gian là ký hiệu (`this_month`, `last_week`, `tet`, …),
code quy ra ngày. Prompt = đặc tả DSL + tóm tắt schema/capabilities của shop + ≤ 10 dòng rulebook liên quan (BM25) + 8 few-shot (BM25 trên câu train
đã có nhãn DSL) + câu hỏi + as_of_date. Giải mã có ràng buộc JSON; `max_tokens=512`; thinking tắt.

Nhãn DSL cho train sinh bằng **execution-guided labeling**: model sinh 8 ứng viên (temperature 0,8), chạy executor, giữ ứng viên ra đúng đáp án.

### 6.5. [5] Executor — `datamate/executor`

- DuckDB in-memory trên CanonicalStore; mỗi luật rulebook là một hàm có tham số + test.
- Tiền: int64; làm tròn bằng `decimal` (ROUND_HALF_UP cho giá trị trung bình đơn; tiền làm tròn về đồng; % và trung bình khác 2 chữ số).
- Luật bắt buộc (rulebook train, đối chiếu lại rulebook của split khi chạy):
  - Đơn tính doanh thu: không huỷ **và** không trả (trả một phần cũng loại cả đơn); đơn đang giao vẫn tính; kỳ theo **ngày đặt**.
  - Doanh thu đơn = Σ thành tiền dòng (đã trừ giảm giá dòng); **không** trừ voucher/giảm giá cấp đơn, **không** cộng VAT, **không** gồm phí ship.
  - Bản ghi có ngày sau `as_of_date` coi như chưa xảy ra; riêng trạng thái huỷ/trả lấy theo trạng thái ghi trên đơn.
  - Tuần bắt đầu thứ Hai; "tuần này" = thứ Hai đến hôm nay; "tuần trước" = cả tuần liền trước.
  - "Tháng này" = ngày 1 đến hôm nay; so với tháng trước lấy **cùng số ngày** (tháng trước thiếu ngày thì đến hết tháng).
  - "N ngày gần nhất" gồm hôm nay; "quá/hơn/trên/dưới N" **không** gồm N; "từ N trở lên" gồm N; "từ X đến Y" gồm hai đầu.
  - Tháng/quý không ghi năm: năm nay nếu không sau hôm nay, ngược lại năm trước.
  - Tết năm Y = dương lịch của 23 tháng Chạp (năm âm Y−1) đến hết mùng 10 tháng Giêng (năm âm Y), tra `calendar.csv`; "trước Tết" = cùng số ngày ngay trước.
  - Ca sáng 06:00–13:59, ca chiều 14:00–21:59.
  - Bán chạy = SL quy về đơn vị cơ bản; "Phí phục vụ" không phải mặt hàng nhưng vẫn tính vào doanh thu.
  - Khách: có mã thì theo mã; không có mã thì theo tên (khác cách viết = cùng khách); khách lẻ không phải khách.
  - Công nợ: đơn không huỷ (đơn trả vẫn tính nếu còn nợ); nợ = phần chưa trả của **tổng đơn** (đã trừ giảm giá đơn, **gồm phí ship**);
    COD và đơn sàn không phải nợ; tuổi nợ tính từ ngày đặt (đặt hôm nay = 0 ngày).
  - Giá vốn/lãi gộp: dùng **giá vốn ghi trên dòng bán**; giá trị tồn kho dùng giá vốn danh mục; lãi ròng tháng trừ mọi chi phí trong sổ.
  - Phần trăm thay đổi so với kỳ trước, giảm ra số âm; chênh lệch = kỳ hỏi − kỳ so.
  - Không có dữ liệu ≠ 0: kỳ nằm hoàn toàn ngoài khoảng dữ liệu → unanswerable; kỳ có một phần → tính trên phần có dữ liệu.
- Luật ngành (cà phê size M/L, nhà thuốc, VLXD giao nhiều đợt, và luật mới ở public: mẹ & bé, sửa xe, điện thoại, khách trung thành/sộp/hay đổi ý,
  mặt hàng ưa chuộng, nhân viên chăm chỉ, ngày đắt khách, giờ cao điểm, nhà cung cấp chính, topping ghi chung ô…) là module riêng `executor/rules/industry_*.py`.

### 6.6. [6] Codegen — `datamate/codegen`

LLM viết một hàm `solve(store, ctx) -> Answer` dùng API thư viện luật (`valid_orders()`, `period()`, `to_base_unit()`…), không đọc file thô.
Sandbox: tiến trình con, timeout 20 s, `RLIMIT_AS` 8 GB, AST guard (chỉ import pandas, numpy, datetime, math, decimal; cấm os, sys, subprocess,
socket, open ghi, eval/exec). Dùng khi DSL không biểu diễn được, hoặc để đối chiếu với executor.

### 6.7. [7] Gate + formatter — `datamate/gate`, `datamate/format`

Features: đồng thuận executor vs codegen; log-prob DSL; điểm entity; kiểm tra hợp lý (kỳ có dữ liệu, doanh thu ≥ 0, list đủ k, kiểu đáp án khớp câu hỏi);
tỉ lệ đúng lịch sử của intent; câu chạm luật mới của rulebook. LogisticRegression cross-fitted theo fold shop → p. Trả lời khi p ≥ τ (quét 0,40–0,90).

`unanswerable` chỉ khi: Capabilities thiếu khái niệm câu hỏi cần, **hoặc** kỳ hỏi nằm hoàn toàn ngoài khoảng dữ liệu. Không chắc → abstain.
Hai dạng thấy trong 70 câu unanswerable train: kỳ hỏi **trước ngày bắt đầu** dữ liệu của shop (lấy từ dữ liệu, README chỉ ghi ngày kết thúc);
và thông tin shop không ghi (địa chỉ khách, đánh giá nhân viên, giá vốn, phiếu nhập, hạn dùng ở quán cà phê…).

Formatter: số là JSON number (không chuỗi), phần trăm dạng `12.4`, list luôn là mảng, ngày ISO, tên nguyên văn; `orjson`, flush từng dòng.

### 6.8. Rulebook runtime — `datamate/rulebook`

Tách `rulebook.md` thành rule rows (mục, tên luật, nội dung) + hash. So với `configs/implemented_rules.yaml` (hash các luật đã hiện thực):
luật mới/đổi → đưa vào prompt codegen, đánh dấu câu chạm luật đó để gate hạ p.

## 7. LLM và hạ tầng

| Phương án | Model | Tham số (đếm thận trọng) | Giấy phép |
|---|---|---|---|
| A (thử trước) | Qwen3.5-9B (+ multilingual-e5-small tuỳ chọn) | ~10,1B | Apache-2.0 / MIT |
| B | Qwen3-14B | ~14,8B | Apache-2.0 |
| C | Qwen2.5-Coder-14B-Instruct | ~14,7B | Apache-2.0 |

Chốt bằng benchmark trên holdout (task T09). Số tham số **phải** kiểm bằng `count_params` trên safetensors thực tế.

vLLM offline: `dtype=bfloat16`, `seed=0`, `temperature=0`, `enable_prefix_caching=True`, `max_model_len=16384`, `gpu_memory_utilization=0.85`;
TP=1 cho ~10B, TP=2 cho 14B bf16. Một instance duy nhất. Xếp câu theo shop để tận dụng prefix cache. Tên API structured output
thay đổi theo phiên bản vLLM — dùng đúng bản đã ghim.

Fine-tune LoRA (tuỳ chọn, chỉ giữ nếu PA holdout tăng): r=16, α=32, dropout 0,05, mọi lớp linear, lr 1e-4 cosine, warmup 3%, 2–3 epoch,
seq 4096, batch hiệu dụng 32, bf16 (QLoRA 4-bit nếu GPU < 40 GB), loss chỉ trên completion; `merge_and_unload` trước khi đóng gói.

## 8. Đánh giá

- 5 fold chia **theo shop** (6 shop/fold, cân bằng ngành) + kịch bản bỏ cả một ngành + tập khoá ~300 câu (chỉ chấm ở mốc G1, G2).
- Scorer `datamate/eval/scorer.py` hiện thực đúng §3; mọi thay đổi scorer phải có test.
- Mỗi lần chạy lưu `runs/<YYYYMMDD-HHMM>-<gitsha>/`: `predictions.jsonl`, `logs/`, `report.md` (PA, coverage, precision theo intent/kiểu đáp án, thời gian/câu).
- Merge chỉ khi PA trên các fold không giảm (cho phép nhiễu ≤ 0,005 nếu lý do rõ).
- Public leaderboard: chỉ nộp output của đúng pipeline offline, 1–2 lần/ngày, ghi vào `docs/PROGRESS.md`.

## 9. Câu hỏi mở (gửi aichallenge@zalo.me)

1. Base image Docker chính thức và cách gọi `predict.sh`.
2. Đếm tham số khi dùng LoRA (đã gộp) hoặc hai bản sao cùng model.
3. Giới hạn dung lượng image.
4. Dùng API thương mại để **sinh dữ liệu huấn luyện** (không phải inference) có được phép không.
