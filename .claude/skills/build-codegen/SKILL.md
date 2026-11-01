---
name: build-codegen
description: Hướng dẫn xây đường dự phòng sinh code của DataMate — LLM viết hàm pandas gọi thư viện luật, chạy trong sandbox an toàn, dùng khi DSL không biểu diễn được hoặc để đối chiếu. Dùng cho task T20.
---

# /build-codegen

Đặc tả: SPEC §6.6.

## Hợp đồng code sinh ra

```python
def solve(store, ctx):
    """store: CanonicalStore (chỉ đọc); ctx: as_of_date, rules (API thư viện luật), entity_links.
    Trả về dict {"type": ..., "answer": ...} hoặc {"type": "unanswerable", "reason": ...}."""
```

API thư viện luật cung cấp cho LLM (mô tả ngắn trong prompt, không đưa toàn bộ mã): `ctx.rules.valid_orders(period)`,
`ctx.rules.period(kind, **kw)`, `ctx.rules.to_base_unit(df)`, `ctx.rules.revenue(df)`, `ctx.rules.rank(df, by, k, ties="code")`, …

## Sandbox (`datamate/codegen/sandbox.py`)

1. AST guard trước khi chạy: chỉ cho `import pandas|numpy|datetime|math|decimal`; cấm `os, sys, subprocess, socket, shutil, pathlib, builtins,
   importlib, ctypes`, cấm `open`, `eval`, `exec`, `compile`, `__import__`, `getattr` với chuỗi dunder, thuộc tính bắt đầu `__`.
2. Chạy trong tiến trình con (`multiprocessing` start method `spawn`), `resource.setrlimit(RLIMIT_AS, 8 GB)`, timeout 20 s → kill.
3. Truyền store qua file parquet trong `/tmp` (đã có sẵn từ cache), không qua pickle đối tượng tuỳ ý.
4. Kết quả qua JSON; validate bằng Pydantic `Answer`.

## Prompt

Đặc tả nhiệm vụ + API thư viện luật + tóm tắt schema/capabilities của shop + **toàn bộ luật mới/đổi** của rulebook split (từ diff) +
5 ví dụ code đã kiểm (từ train) + câu hỏi + as_of_date. Thinking: thử cả bật (giới hạn token) và tắt, chọn theo PA.

## Kiểm tra

- Test AST guard với ≥ 10 mẫu độc hại; test timeout; test bộ nhớ.
- Đo trên câu dev mà DSL ra `custom`: tỉ lệ chạy được, tỉ lệ đúng trên câu trả lời.
- Đo tỉ lệ đồng thuận executor vs codegen trên câu cả hai trả lời được → feature cho gate.
