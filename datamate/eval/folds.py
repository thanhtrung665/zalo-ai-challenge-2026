"""Chia fold đánh giá theo shop (SPEC §8, PLAN T03). Chỉ dùng thư viện chuẩn.

- Ngành của shop suy ra bằng đếm từ khoá trong README + câu hỏi train của shop đó. Nhãn này **chỉ** dùng để cân bằng
  fold và tạo kịch bản bỏ một ngành; tuyệt đối không dùng để rẽ nhánh lúc inference.
- Tập khoá (locked): một số shop cố định, chọn ngẫu nhiên có seed, ưu tiên mỗi ngành một shop.
- Các shop còn lại chia 5 fold theo vòng tròn trong từng ngành (shop nhiều câu xếp trước) để cân bằng ngành và số câu.

Dùng: python -m datamate.eval.folds --split data/train --out splits/folds.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

SEED = 2026
N_FOLDS = 5

# Từ khoá đã bỏ dấu, chữ thường. Thứ tự không quan trọng; ngành có điểm cao nhất thắng.
INDUSTRY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "pharmacy": ("thuoc", "hoat chat", "ke don", "vien nang", "vi x", "siro", "han dung", "lo thuoc", "mg"),
    "cafe": ("ca phe", "tra sua", "tra dao", "bac xiu", "topping", "size m", "(m)", "(l)", "ly", "sinh to", "matcha"),
    "building_materials": (
        "xi mang",
        "gach",
        "thep",
        "cat ",
        "ton ",
        "ong pvc",
        "son ",
        "da 1x2",
        "giao hang",
        "dot giao",
    ),
    "restaurant": (
        "dia ",
        "nuong",
        "xao",
        "chien",
        "lau ",
        "hai san",
        "phi phuc vu",
        "ban an",
        "goi cuon",
        "com chien",
        "mon an",
    ),
    # Không dùng "nuoc mam", "thung", "goi": trùng với nhà hàng (món nước mắm, thùng bia, gỏi/gọi món).
    "grocery": ("tap hoa", "mi ", "dau an", "sua tuoi", "banh", "keo", "loc ", "xa bong", "bot ngot", "trung ga"),
}


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def industry_scores(text: str) -> Counter:
    t = strip_accents(text)
    sc: Counter = Counter()
    for ind, kws in INDUSTRY_KEYWORDS.items():
        for kw in kws:
            sc[ind] += len(re.findall(re.escape(kw), t))
    return sc


def infer_industry(text: str, min_margin: float = 1.2) -> str:
    sc = industry_scores(text)
    if not sc or sc.most_common(1)[0][1] == 0:
        return "unknown"
    (best, b), *rest = sc.most_common(2) + [("", 0)]
    second = rest[0][1]
    return best if b >= min_margin * max(second, 1) else "unknown"


def load_split(split_dir: Path) -> tuple[dict[str, list[dict]], dict[str, str]]:
    by_biz: dict[str, list[dict]] = defaultdict(list)
    with open(split_dir / "questions.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                q = json.loads(line)
                by_biz[q["business_id"]].append(q)
    readmes = {}
    for biz in by_biz:
        p = split_dir / "data" / biz / "README.md"
        readmes[biz] = p.read_text(encoding="utf-8") if p.exists() else ""
    return dict(by_biz), readmes


def make_folds(
    by_biz: dict[str, list[dict]],
    industries: dict[str, str],
    *,
    n_folds: int = N_FOLDS,
    n_locked: int = 3,
    seed: int = SEED,
) -> dict:
    rng = random.Random(seed)
    groups: dict[str, list[str]] = defaultdict(list)
    for biz in sorted(by_biz):
        groups[industries[biz]].append(biz)

    # Tập khoá: lấy lần lượt 1 shop từ các ngành lớn nhất cho đến đủ n_locked (chỉ shop đủ ~118 câu).
    locked: list[str] = []
    for ind in sorted(groups, key=lambda k: (-len(groups[k]), k)):
        if len(locked) >= n_locked:
            break
        big = [b for b in groups[ind] if len(by_biz[b]) >= 100]
        if len(groups[ind]) >= 3 and big:
            locked.append(rng.choice(big))

    folds: list[list[str]] = [[] for _ in range(n_folds)]
    sizes = [0] * n_folds
    for ind in sorted(groups):
        members = [b for b in groups[ind] if b not in locked]
        members.sort(key=lambda b: (-len(by_biz[b]), b))
        for b in members:
            k = min(range(n_folds), key=lambda i: (sizes[i], sum(industries[x] == ind for x in folds[i]), i))
            folds[k].append(b)
            sizes[k] += len(by_biz[b])

    def ids(bizs: list[str]) -> list[str]:
        return sorted(q["id"] for b in bizs for q in by_biz[b])

    return {
        "seed": seed,
        "industries": dict(sorted(industries.items())),
        "locked": {"businesses": sorted(locked), "n_questions": len(ids(locked)), "ids": ids(locked)},
        "folds": [
            {"fold": i, "businesses": sorted(f), "n_questions": len(ids(f)), "ids": ids(f)} for i, f in enumerate(folds)
        ],
        "leave_industry_out": {
            ind: sorted(b for b in members if b not in locked) for ind, members in sorted(groups.items())
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Chia fold theo shop")
    ap.add_argument("--split", default="data/train")
    ap.add_argument("--out", default="splits/folds.json")
    args = ap.parse_args(argv)

    split = Path(args.split)
    by_biz, readmes = load_split(split)
    industries = {
        b: infer_industry(readmes[b] + "\n" + "\n".join(q["question"] for q in qs)) for b, qs in by_biz.items()
    }
    res = make_folds(by_biz, industries)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Ngành:", dict(Counter(industries.values())))
    print("Tập khoá:", res["locked"]["businesses"], res["locked"]["n_questions"], "câu")
    for f in res["folds"]:
        inds = Counter(industries[b] for b in f["businesses"])
        print(f"Fold {f['fold']}: {f['n_questions']} câu, {len(f['businesses'])} shop, {dict(inds)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
