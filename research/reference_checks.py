"""Tính tay tham chiếu theo rulebook cho 2 shop train và so với đáp án chuẩn (docs/DATA_FINDINGS.md §7).

Mục đích: bằng chứng cách hiểu rulebook đúng, và **bộ hồi quy cho executor** (T12):
executor phải ra đúng các đáp án này.
Đây là code nghiên cứu, KHÔNG thuộc runtime: có nhắc tên shop cụ thể; thư mục research/
không bị quét tuân thủ và không được đưa vào image.

Dùng: uv run --extra data python research/reference_checks.py --split data/train
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd
from python_calamine import CalamineWorkbook

MONTH_RE = re.compile(r"(?:tháng|thang|thangs)\s*(\d{1,2})(?:/| năm | nam )(\d{4})")


def money(s: str) -> int | None:
    s = re.sub(r"\.0+$", "", str(s).strip())
    s = re.sub(r"[^\d\-]", "", s)
    return int(s) if s not in ("", "-") else None


def first_number(s: str) -> float | None:
    """'1 hộp 30' → 1.0: số lượng là số ĐẦU TIÊN; phần sau là tên đơn vị (có thể chứa số)."""
    m = re.match(r"\s*(\d+(?:\.\d+)?)", str(s))
    return float(m[1]) if m else None


def vn_date(s: str) -> date:
    if m := re.match(r"(\d{1,2}) thg (\d{1,2}),? (\d{4})", s):
        return date(int(m[3]), int(m[2]), int(m[1]))
    if m := re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s):
        return date(int(m[3]), int(m[2]), int(m[1]))
    if m := re.match(r"(\d{4})-(\d{2})-(\d{2})", s):
        return date(int(m[1]), int(m[2]), int(m[3]))
    raise ValueError(s)


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower()).replace("đ", "d")
    return re.sub(r"\s+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def month_range(y: int, m: int) -> tuple[date, date]:
    return date(y, m, 1), date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)


def round_vnd(x: Decimal) -> int:
    return int(x.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def load_qa(split: Path, biz: str) -> list[tuple[dict, dict]]:
    qs = [json.loads(ln) for ln in (split / "questions.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    ans = {
        json.loads(ln)["id"]: json.loads(ln)
        for ln in (split / "answers.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    }
    return [(q, ans[q["id"]]) for q in qs if q["business_id"] == biz]


class Shop:
    """Bảng dòng hàng đã chuẩn hoá.

    Cột: order, d (ngày đặt), product, amt, qb (SL quy về đơn vị cơ bản), cancelled, bad (đơn huỷ/trả).
    """

    def __init__(self, lines: pd.DataFrame):
        self.all = lines
        self.valid = lines[~lines["bad"]]

    def window(self, d0: date, d1: date) -> pd.DataFrame:
        v = self.valid
        return v[(v.d >= d0) & (v.d <= d1)]

    def revenue(self, d0: date, d1: date) -> int:
        return int(self.window(d0, d1).amt.sum())

    def n_orders(self, d0: date, d1: date) -> int:
        return int(self.window(d0, d1)["order"].nunique())

    def avg_order(self, d0: date, d1: date) -> int:
        w = self.window(d0, d1)
        return round_vnd(Decimal(int(w.amt.sum())) / w["order"].nunique())

    def top_products(self, d0: date, d1: date, k: int) -> list[str]:
        s = self.window(d0, d1).groupby("product").qb.sum().reset_index()
        s = s.sort_values(["qb", "product"], ascending=[False, True])
        return s["product"].head(k).tolist()

    def best_day(self, d0: date, d1: date) -> str:
        s = self.window(d0, d1).groupby("d").amt.sum()
        return s.idxmax().isoformat()

    def n_cancelled(self, d0: date, d1: date) -> int:
        """Rulebook §1: đơn huỷ = trạng thái huỷ (đơn trả hàng KHÔNG phải đơn huỷ); kỳ theo ngày đặt."""
        a = self.all
        return int(a[(a.d >= d0) & (a.d <= d1) & a.cancelled]["order"].nunique())

    def product_revenue(self, product: str, d0: date, d1: date) -> int:
        w = self.window(d0, d1)
        return int(w[w["product"] == product].amt.sum())

    def find_product(self, question: str) -> str | None:
        """Tên hàng dài nhất xuất hiện trong câu (so sánh không dấu, chữ thường)."""
        qn = strip_accents(question)
        hits = [p for p in self.all["product"].unique() if strip_accents(p) in qn]
        return max(hits, key=len) if hits else None


def load_biz101(split: Path) -> Shop:
    df = pd.read_csv(split / "data/biz_101/ban_hang.csv", dtype=str, keep_default_na=False)
    out = pd.DataFrame(
        {
            "order": df["Mã hóa đơn"],
            "d": df["Ngày tháng"].map(vn_date),
            "product": df["Nội dung"],
            "amt": df["Thanh tien"].map(money),
            "qb": df["Quy ra ĐV lẻ"].map(first_number),
            "status": df["Kết quả"],
        }
    )
    return _finish(out, cancelled={"Đã hủy"}, returned={"Đổi trả"})


def _finish(out: pd.DataFrame, *, cancelled: set[str], returned: set[str]) -> Shop:
    """Đánh dấu đơn huỷ/trả ở mức ĐƠN (một dòng trả → cả đơn là đơn trả, rulebook §1).

    Gộp biến thể tên hàng (rulebook §8: các tên cùng chỉ một thứ là cùng một thứ): khoá = bỏ dấu + chữ thường + gộp
    khoảng trắng; tên hiển thị = cách viết xuất hiện nhiều nhất.
    Vd. "Coca  Cola 330ml" (2 dấu cách) gộp vào "Coca Cola 330ml".
    """
    key = out["product"].map(strip_accents)
    canonical = out.groupby(key)["product"].agg(lambda s: s.value_counts().index[0])
    out["product"] = key.map(canonical)
    canc_orders = set(out.loc[out.status.isin(cancelled), "order"])
    bad_orders = canc_orders | set(out.loc[out.status.isin(returned), "order"])
    out["cancelled"] = out["order"].isin(canc_orders)
    out["bad"] = out["order"].isin(bad_orders)
    return Shop(out)


def load_biz102(split: Path) -> Shop:
    biz = split / "data/biz_102"
    wb = CalamineWorkbook.from_path(str(biz / "DonHang_ChiTiet.xlsx"))
    frames = []
    for sn in wb.sheet_names:
        rows = wb.get_sheet_by_name(sn).to_python()
        frames.append(pd.DataFrame(rows[1:], columns=rows[0]))
    df = pd.concat(frames, ignore_index=True).astype(str)
    conv_rows = CalamineWorkbook.from_path(str(biz / "DanhSachQuyDoi.xlsx")).get_sheet_by_name("Sheet1").to_python()[1:]
    factor = {(r[0], r[1]): float(r[2]) for r in conv_rows}
    q = df["Số lượng sản phẩm"].map(first_number)
    f = [factor.get((p, u), 1.0) for p, u in zip(df["Tên sản phẩm"], df["Đơn vị tính"], strict=True)]
    out = pd.DataFrame(
        {
            "order": df["Mã đơn hàng"],
            "d": pd.to_datetime(df["Ngày đặt hàng"], format="%d/%m/%Y").dt.date,
            "product": df["Tên sản phẩm"],
            "amt": df["Tổng tiền"].map(money),
            "qb": q * pd.Series(f),
            "status": df["Trạng thái đơn hàng"],
        }
    )
    return _finish(out, cancelled={"Đã hủy"}, returned={"Đã hoàn hàng"})


def answer_question(shop: Shop, q: dict, gold_type: str) -> tuple[str, object] | None:
    """Bộ định tuyến regex tối giản chỉ đủ cho các dạng câu đã kiểm — KHÔNG phải NLU của hệ thống."""
    t = q["question"].lower()
    asof = date.fromisoformat(q["as_of_date"])
    yday = asof - timedelta(days=1)
    mm = MONTH_RE.search(t)
    is_orders = re.search(r"(đơn|don|bill)", t)
    if re.search(r"(huỷ|hủy|\bhuy\b)", t) and is_orders and mm and gold_type == "number":
        return "số đơn bị huỷ", shop.n_cancelled(*month_range(int(mm[2]), int(mm[1])))
    if re.search(r"(hqua|hôm qua|bua qua|hom qua)", t) and is_orders:
        return "số đơn hôm qua", shop.n_orders(yday, yday)
    if re.search(r"(hqua|hôm qua|hom qua)", t):
        return "doanh thu hôm qua", shop.revenue(yday, yday)
    if re.search(r"(hôm nay|bua nay)", t) and is_orders:
        return "số đơn hôm nay", shop.n_orders(asof, asof)
    if re.search(r"(hôm nay|bua nay)", t):
        return "doanh thu hôm nay", shop.revenue(asof, asof)
    if m := re.search(r"quy (\d)/(\d{4})", t):
        qn, y = int(m[1]), int(m[2])
        return "số đơn quý", shop.n_orders(date(y, 3 * qn - 2, 1), month_range(y, 3 * qn)[1])
    if not mm:
        return None
    d0, d1 = month_range(int(mm[2]), int(mm[1]))
    if re.search(r"(bình qu|binh quan|trung bình|trung binh)", t):
        return "TB mỗi đơn", shop.avg_order(d0, d1)
    if re.search(r"(ngày nào|ngay nao)", t):
        return "ngày doanh thu cao nhất", shop.best_day(d0, d1)
    if re.search(r"(chạy nhất|chay nhat|bán nhiều nhất|ban nhieu nhat)", t):
        km = re.search(r"(\d+) (?:mặt hàng|mat hang|sp|sản phẩm|hàng|món|mon)", t)
        top = shop.top_products(d0, d1, int(km[1]) if km else 1)
        return "bán chạy", (top[0] if gold_type == "string" else top)
    product = shop.find_product(q["question"])
    if product and re.search(r"\bkg\b", t):
        w = shop.window(d0, d1)
        return "số kg của mặt hàng", int(w[w["product"] == product].qb.sum())
    if product and gold_type == "number" and re.search(r"(tiền|tien|tieenf|doanh thu|dthu)", t):
        return "doanh thu mặt hàng", shop.product_revenue(product, d0, d1)
    if product or gold_type != "number" or re.search(r"(nhóm|nhom|khách|khach|giá|gia ban|đơn|don|bill)", t):
        return None  # dạng câu chưa hỗ trợ trong bộ kiểm này
    return "doanh thu tháng", shop.revenue(d0, d1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="data/train")
    args = ap.parse_args(argv)
    split = Path(args.split)
    total = ok = 0
    for biz, loader in (("biz_101", load_biz101), ("biz_102", load_biz102)):
        shop = loader(split)
        for q, a in load_qa(split, biz):
            r = answer_question(shop, q, a["type"])
            if r is None:
                continue
            kind, got = r
            hit = got == a["answer"]
            total += 1
            ok += hit
            print(f"{'OK' if hit else 'XX'} {biz} {kind:24s} tính={got} | chuẩn={a['answer']} | {q['question'][:60]}")
    print(f"\nKhớp {ok}/{total}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
