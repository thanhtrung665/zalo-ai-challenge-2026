"""Sinh notebook Kaggle cho T09:  python kaggle/make_notebook.py  ->  kaggle/t09_llm_benchmark.ipynb

Giữ nội dung notebook trong file này (diff đọc được) thay vì sửa JSON ipynb bằng tay.
"""

from __future__ import annotations

import json
from pathlib import Path

CELLS: list[tuple[str, str]] = []


def md(text: str) -> None:
    CELLS.append(("markdown", text.strip("\n")))


def code(text: str) -> None:
    CELLS.append(("code", text.strip("\n")))


md("""
# T09 — Benchmark LLM trên Kaggle (DataMate)

Đo từng model ứng viên trên bài **map schema** của 5 shop train: JSON hợp lệ, số lỗi validator, độ khớp mapping, thời gian, VRAM.

**Đọc trước khi chạy** (`kaggle/README.md`):
- Chỉ dùng để *chọn model và gỡ lỗi*. T4 không có bf16 → kết quả không đại diện cho 2×RTX 5090 bf16 của máy chấm.
- Chạy **từng model một** (mỗi model một tiến trình riêng để trả VRAM).
- Số tham số cho luật thi phải đo trên bản gốc, không phải bản AWQ.
- Bật **Internet** cho notebook (tải model/cài vLLM lúc phát triển là được phép; lúc inference thì không).
""")

code("""
# ===== CẤU HÌNH — chỉ sửa ô này =====
GITHUB_REPO = "thanhtrung665/zalo-ai-challenge-2026"
BRANCH = "claude/bold-pascal-alulq0"  # nhánh có mã mới nhất; đổi về "main" sau khi đã merge
CODE_DATASET = ""               # vd "/kaggle/input/datamate-code" nếu dùng Dataset (kaggle/pack_repo.sh) thay vì git clone
MODEL_KEYS = ["qwen3.5-9b"]     # chọn trong kaggle/models.yaml; chạy lần lượt, đừng gom nhiều model một lượt đầu tiên
USE_QUANTIZED = False           # True: tải bản AWQ (cho model 14B không vừa 2xT4 fp16)
USE_VLLM = True                 # False: dùng HF (chậm, không ràng buộc JSON) — khi vLLM không cài/chạy được
PROFILE = "kaggle_t4x2"         # kaggle_t4x2 (vLLM) | kaggle_hf (HF)
N_SHOPS = 5
# =====================================

import glob, os, pathlib, subprocess, sys, zipfile

WORK = pathlib.Path("/kaggle/working")
REPO = WORK / "datamate"
TEMP = pathlib.Path("/kaggle/temp") if pathlib.Path("/kaggle/temp").exists() else pathlib.Path("/tmp")
MODELS = TEMP / "models"
SPLIT = TEMP / "split" / "train"
RESULTS = WORK / "results"
for p in (MODELS, RESULTS):
    p.mkdir(parents=True, exist_ok=True)
print("PROFILE", PROFILE, "| temp:", TEMP)
""")

md("## 1. Lấy mã")
code("""
if REPO.exists():
    print("đã có", REPO)
elif CODE_DATASET:
    with zipfile.ZipFile(pathlib.Path(CODE_DATASET) / "datamate_code.zip") as z:
        z.extractall(WORK)
    print("giải nén từ Dataset")
else:
    # Repo private: cần secret GITHUB_TOKEN (Add-ons -> Secrets). Token chỉ dùng cho lệnh clone, không in ra.
    from kaggle_secrets import UserSecretsClient
    tok = UserSecretsClient().get_secret("GITHUB_TOKEN")
    url = f"https://x-access-token:{tok}@github.com/{GITHUB_REPO}.git"
    r = subprocess.run(["git", "clone", "--depth", "1", "--branch", BRANCH, url, str(REPO)], capture_output=True, text=True)
    subprocess.run(["git", "-C", str(REPO), "remote", "set-url", "origin", f"https://github.com/{GITHUB_REPO}.git"])
    print("clone:", "OK" if r.returncode == 0 else r.stderr.replace(tok, "***")[-400:])
print(subprocess.run(["git", "-C", str(REPO), "log", "--oneline", "-3"], capture_output=True, text=True).stdout)
""")
code("""
!cd {REPO} && bash kaggle/bootstrap.sh
""")

md("## 2. Dữ liệu train (ghép các phần split)")
code("""
parts = sorted(glob.glob(str(REPO / "data" / "train" / "train.zip.part_*")))
assert parts, "không thấy các phần train.zip.part_* — kiểm tra nhánh/dataset"
if not (SPLIT / "data").exists():
    zpath = TEMP / "train.zip"
    with open(zpath, "wb") as out:
        for p in parts:
            out.write(open(p, "rb").read())
    with zipfile.ZipFile(zpath) as z:
        z.extractall(TEMP / "split")
    zpath.unlink()
print("shop train:", len(list((SPLIT / "data").iterdir())), "| SPLIT =", SPLIT)
""")

md("## 3. vLLM (tuỳ chọn)")
code("""
vllm_ok = False
if USE_VLLM:
    try:
        import vllm
        vllm_ok = True
    except ImportError:
        # Cài vLLM có thể kéo bản torch khác và làm hỏng image Kaggle. Nếu lỗi: đặt USE_VLLM=False, PROFILE="kaggle_hf".
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "vllm"], capture_output=True, text=True)
        print(r.stdout[-600:], r.stderr[-600:])
        try:
            import importlib; vllm = importlib.import_module("vllm"); vllm_ok = True
        except Exception as e:
            print("vLLM không dùng được:", repr(e)[:300])
if vllm_ok:
    print("vLLM", vllm.__version__)
else:
    print("=> dùng HF: đặt PROFILE = 'kaggle_hf' và chạy lại ô cấu hình.")
    PROFILE = "kaggle_hf"
""")

md("""
## 4. Xác minh model, tải, đo tham số
In giấy phép, ngày tạo, số tham số từ metadata Hugging Face — **chỉ những gì in ra ở đây mới được ghi vào `MODELS.md`**.
""")
code("""
import yaml
from huggingface_hub import HfApi, snapshot_download

cands = {c["name"]: c for c in yaml.safe_load((REPO / "kaggle" / "models.yaml").read_text())["candidates"]}
paths = {}
for key in MODEL_KEYS:
    c = cands[key]
    orig = c["hf_id"]
    print("=" * 70, "\\n", key, "->", orig)
    try:
        info = HfApi().model_info(orig)
        lic = getattr(info.card_data, "license", None) if info.card_data else None
        total = getattr(info.safetensors, "total", None) if info.safetensors else None
        print(f"  tạo: {info.created_at}  | giấy phép: {lic}  | tham số (metadata): {total:,}" if total else f"  tạo: {info.created_at} | giấy phép: {lic} | tham số: không có metadata")
        if total and total > 15_000_000_000:
            print("  !!! VƯỢT 15B — loại")
    except Exception as e:
        print("  không đọc được metadata:", repr(e)[:200])
    repo_id = c.get("quantized_for_dev") if (USE_QUANTIZED and c.get("quantized_for_dev")) else orig
    dest = MODELS / (key + ("-q" if repo_id != orig else ""))
    patterns = ["*.json", "*.safetensors", "*.txt", "tokenizer*", "*.model", "*.jinja"]
    snapshot_download(repo_id, local_dir=dest, allow_patterns=patterns)
    paths[key] = dest
    print("  đã tải về", dest)
""")
code("""
for key, dest in paths.items():
    print(key)
    !cd {REPO} && python -m datamate.tools.count_params {dest}
""")

md("""
## 5. Benchmark
Mỗi model chạy trong tiến trình riêng. Lần đầu có thể mất vài phút để nạp model.
""")
code("""
for key, dest in paths.items():
    out = RESULTS / f"{key}.json"
    print("=" * 70, "\\n", key)
    !cd {REPO} && python -m datamate.tools.llm_bench --model {dest} --split {SPLIT} --profile {PROFILE} --n-shops {N_SHOPS} --out {out}
""")

md("## 6. Gói kết quả")
code("""
import shutil
zip_path = shutil.make_archive(str(WORK / "t09_results"), "zip", RESULTS)
print("Tải file này về:", zip_path)
for md_file in sorted(RESULTS.glob("*.md")):
    print(md_file.read_text())
""")


def build() -> dict:
    cells = []
    for kind, text in CELLS:
        base = {"cell_type": kind, "metadata": {}, "source": text.splitlines(keepends=True)}
        if kind == "code":
            base |= {"execution_count": None, "outputs": []}
        cells.append(base)
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


if __name__ == "__main__":
    out = Path(__file__).with_name("t09_llm_benchmark.ipynb")
    out.write_text(json.dumps(build(), ensure_ascii=False, indent=1), encoding="utf-8")
    print("→", out)
