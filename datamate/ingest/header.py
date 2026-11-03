"""Dò tìm dòng header trong bảng dữ liệu thô (tỉ lệ ô chữ, tỉ lệ phân biệt, khớp từ vựng)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def _normalize_text(s: str) -> str:
    """Bỏ dấu tiếng Việt, chữ thường, gộp khoảng trắng để so khớp từ vựng."""
    if not s:
        return ""
    s = s.replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFKD", s)
    no_mark = "".join(c for c in nfkd if not unicodedata.combining(c))
    # "_" tách như dấu cách: tên cột kiểu "ngay_sinh" phải khớp từ vựng "ngay sinh"
    cleaned = re.sub(r"[\W_]", " ", no_mark).lower()
    return " ".join(cleaned.split())


def _is_number_like(s: str) -> bool:
    """Kiểm tra một ô có phải số thuần túy hay không."""
    s = s.strip()
    if not s:
        return False
    # Loại bỏ dấu phân cách hàng nghìn / thập phân / đơn vị tiền thường gặp
    cleaned = re.sub(r"[.,\sđvndVND%()\-]", "", s)
    return cleaned.isdigit() and len(cleaned) > 0


@dataclass
class HeaderGuess:
    """Kết quả dự đoán header."""

    row_index: int  # Chỉ số dòng được chọn làm header (0-indexed)
    score: float  # Điểm số của dòng header
    headers: list[str]  # Danh sách tên cột đã làm sạch
    preamble: list[list[str]]  # Các dòng nằm trên header (tiêu đề, năm, ghi chú...)


def load_column_vocab(config_path: Path | None = None) -> set[str]:
    """Nạp tập từ vựng tên cột chuẩn hoá."""
    vocab: set[str] = set()
    if config_path is None:
        # Tìm ở thư mục configs mặc định
        p = Path(__file__).resolve().parent.parent.parent / "configs" / "column_vocab.yaml"
        if p.exists():
            config_path = p

    if config_path and config_path.exists():
        try:
            data: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            for _group, words in data.items():
                if isinstance(words, list):
                    for w in words:
                        vocab.add(_normalize_text(str(w)))
        except Exception:
            pass

    # Nếu file rỗng hoặc chưa nạp được, dùng fallback từ vựng cơ bản
    if not vocab:
        fallbacks = [
            "ngay",
            "ngay dat",
            "ngay ban",
            "thoi gian",
            "date",
            "created",
            "ma",
            "ma don",
            "ma hd",
            "so hd",
            "id",
            "order id",
            "ten hang",
            "ten sp",
            "san pham",
            "mat hang",
            "item",
            "product",
            "ma hang",
            "ma sp",
            "sku",
            "code",
            "sl",
            "so luong",
            "qty",
            "quantity",
            "dvt",
            "don vi",
            "don vi tinh",
            "unit",
            "don gia",
            "gia",
            "gia ban",
            "price",
            "thanh tien",
            "tong tien",
            "tien hang",
            "amount",
            "total",
            "giam gia",
            "chiet khau",
            "ck",
            "khuyen mai",
            "khach",
            "khach hang",
            "ten khach",
            "ma kh",
            "customer",
            "trang thai",
            "tinh trang",
            "status",
            "ghi chu",
            "thanh toan",
            "hinh thuc",
            "payment",
            "nhan vien",
            "nv",
            "ncc",
            "nha cung cap",
            "nhom",
            "danh muc",
        ]
        vocab.update(_normalize_text(w) for w in fallbacks)
    return vocab


def _match_vocab(cell_norm: str, vocab: set[str]) -> bool:
    """Kiểm tra ô có khớp từ vựng không."""
    if not cell_norm:
        return False
    if cell_norm in vocab:
        return True
    # Khớp tiền tố hoặc từ ngữ quan trọng
    return any(v in cell_norm for v in vocab)


def detect_header(
    rows: list[list[str]],
    vocab_path: Path | None = None,
    max_scan: int = 12,
) -> HeaderGuess:
    """Dò tìm dòng header trong số tối đa max_scan dòng đầu tiên.

    Công thức chấm điểm:
    score = 0.4 * text_ratio + 0.3 * distinct_ratio + 0.3 * vocab_match_ratio
    """
    if not rows:
        return HeaderGuess(row_index=0, score=0.0, headers=[], preamble=[])

    vocab = load_column_vocab(vocab_path)
    scan_limit = min(len(rows), max_scan)
    best_idx = 0
    best_score = -1.0

    for idx in range(scan_limit):
        row = rows[idx]
        non_empty = [c for c in row if c.strip()]
        if not non_empty:
            continue

        total_cells = len(row)
        n_non_empty = len(non_empty)

        # Dòng có quá ít ô không rỗng so với bảng nhiều cột -> thường là tiêu đề lẻ loi
        if n_non_empty < 2 and total_cells > 2:
            continue

        # 1. Tỉ lệ ô có chứa chữ cái và không phải là số thuần túy
        text_count = sum(1 for c in non_empty if not _is_number_like(c))
        text_ratio = text_count / n_non_empty

        # 2. Tỉ lệ ô khác nhau (không lặp lại)
        distinct_count = len(set(non_empty))
        distinct_ratio = distinct_count / n_non_empty

        # 3. Tỉ lệ ô khớp từ vựng tên cột thường gặp
        vocab_count = 0
        for c in non_empty:
            c_norm = _normalize_text(c)
            if _match_vocab(c_norm, vocab):
                vocab_count += 1
        vocab_ratio = vocab_count / n_non_empty

        # Tỉ lệ ô là số thuần túy (số tiền, số lượng -> đặc trưng của dòng dữ liệu)
        num_count = sum(1 for c in non_empty if _is_number_like(c))
        num_ratio = num_count / n_non_empty

        # Công thức chấm điểm chuẩn hóa
        score = 0.4 * text_ratio + 0.3 * distinct_ratio + 0.3 * vocab_ratio
        if vocab_count >= 2:
            score += 0.25
        score -= 0.35 * num_ratio

        # Phạt nhẹ nếu quá nhiều ô trống trong dòng
        coverage_ratio = n_non_empty / total_cells if total_cells else 0.0
        if coverage_ratio < 0.3:
            score *= 0.7

        if score > best_score:
            best_score = score
            best_idx = idx

    # Header 2 tầng (ô gộp): kiểm tra nếu dòng tiếp theo (best_idx + 1) cũng là header con
    chosen_row = rows[best_idx]
    headers: list[str] = []
    seen: dict[str, int] = {}

    for c_idx, cell in enumerate(chosen_row):
        name = cell.strip()
        if not name:
            name = f"col_{c_idx}"
        # Đảm bảo tên cột không bị trùng lặp
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        headers.append(name)

    preamble = rows[:best_idx]
    return HeaderGuess(
        row_index=best_idx,
        score=max(best_score, 0.0),
        headers=headers,
        preamble=preamble,
    )
