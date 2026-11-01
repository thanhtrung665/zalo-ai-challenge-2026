"""Trích xuất thông tin cấu trúc từ README của shop bằng regex (D-006).

Bao gồm:
- Mốc "Dữ liệu có đến hết dd/mm/yyyy"
- Bảng quy đổi đơn vị văn bản (vd: "- Coca Cola 330ml: 1 thùng = 24 lon")
- Danh sách file trong mục `## File`
- Mô tả ý nghĩa từng cột trong `## Cột trong <file>`
- Các câu quy ước trong `## Quy ước`
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UnitConversion:
    """Quy đổi đơn vị cho một sản phẩm."""

    product: str  # Tên sản phẩm hoặc "" nếu là quy đổi chung
    large_unit: str  # Đơn vị lớn (vd: "thùng", "hộp", "bao")
    ratio: int  # Tỉ lệ quy đổi (vd: 24)
    small_unit: str  # Đơn vị nhỏ / đơn vị lẻ (vd: "lon", "gói", "kg")


@dataclass
class ReadmeFacts:
    """Thông tin đã phân tích từ README của shop."""

    cutoff_date: str | None = None  # Định dạng 'YYYY-MM-DD'
    unit_conversions: list[UnitConversion] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    column_descriptions: dict[str, dict[str, str]] = field(default_factory=dict)  # file -> {col: desc}
    conventions: list[str] = field(default_factory=list)
    raw_text: str = ""


_RE_CUTOFF = re.compile(r"Dữ liệu có đến hết\s+(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", re.IGNORECASE)

# Mẫu 1: "- Coca Cola 330ml: 1 thùng = 24 lon" hoặc "* Mì Hảo Hảo: 1 thùng = 30 gói"
_RE_CONV_NAMED = re.compile(
    r"[-*•]\s*(?:(?P<product>[^:\n]+):\s*)?1\s+(?P<large>[^\d=\n]+?)\s*=\s*(?P<ratio>\d+)\s+(?P<small>[^\n,.]+)",
    re.IGNORECASE,
)

# Mẫu 2: "1 thùng = 24 lon" đứng riêng
_RE_CONV_SIMPLE = re.compile(
    r"(?:^|\n)\s*1\s+(?P<large>[^\d=\n]+?)\s*=\s*(?P<ratio>\d+)\s+(?P<small>[^\n,.]+)",
    re.IGNORECASE,
)


def _format_date(d: str, m: str, y: str) -> str:
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def parse_readme(text_or_path: str | Path) -> ReadmeFacts:
    """Phân tích nội dung README bằng regex tất định."""
    if isinstance(text_or_path, Path):
        text = text_or_path.read_text(encoding="utf-8", errors="replace")
    elif Path(text_or_path).is_file():
        text = Path(text_or_path).read_text(encoding="utf-8", errors="replace")
    else:
        text = str(text_or_path)

    facts = ReadmeFacts(raw_text=text)

    # 1. Trích xuất mốc cutoff date
    m_cut = _RE_CUTOFF.search(text)
    if m_cut:
        d, m, y = m_cut.groups()
        facts.cutoff_date = _format_date(d, m, y)

    # 2. Trích xuất danh sách file từ mục `## File`
    # Tìm vùng từ "## File" đến header "##" tiếp theo
    m_files_sec = re.search(r"##\s*File\b(.*?)(?=\n##|\Z)", text, re.DOTALL | re.IGNORECASE)
    if m_files_sec:
        sec_text = m_files_sec.group(1)
        for line in sec_text.splitlines():
            line_s = line.strip()
            # Khớp tên file có đuôi mở rộng phổ biến
            m_fn = re.search(
                r"[`'\"]?([\w\-.]+\.(?:csv|xlsx|xlsm|xls|sqlite|db|sqlite3))[`'\"]?",
                line_s,
                re.IGNORECASE,
            )
            if m_fn:
                fn = m_fn.group(1)
                if fn not in facts.files:
                    facts.files.append(fn)

    # 3. Trích xuất bảng quy đổi đơn vị văn bản
    # Tìm vùng chứa quy đổi (thường ở mục Quy ước hoặc Bảng quy đổi)
    for m in _RE_CONV_NAMED.finditer(text):
        prod = (m.group("product") or "").strip()
        large = m.group("large").strip()
        ratio = int(m.group("ratio"))
        small = m.group("small").strip()
        # Lọc nhiễu
        if large and small and ratio > 0 and len(large) < 30 and len(small) < 30:
            facts.unit_conversions.append(UnitConversion(product=prod, large_unit=large, ratio=ratio, small_unit=small))

    # 4. Trích xuất mô tả cột: `## Cột trong <file>` hoặc `### <file>`
    col_sections = re.finditer(
        r"##+\s*(?:Cột trong\s+)?([^\n]+)\n(.*?)(?=\n##|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    for c_sec in col_sections:
        title = c_sec.group(1).strip()
        body = c_sec.group(2)
        # Chỉ nhận nếu tiêu đề có chứa tên file hoặc từ "cột"
        if not (any(ext in title.lower() for ext in (".csv", ".xlsx", ".sqlite", ".db")) or "cột" in title.lower()):
            continue

        file_key = re.sub(r"^(?:cột trong\s+|bảng\s+|file\s+)", "", title, flags=re.IGNORECASE).strip(" `*:")
        col_dict: dict[str, str] = {}

        for line in body.splitlines():
            line_s = line.strip()
            # Mẫu: - `Tên cột`: mô tả
            # hoặc: - Tên cột: mô tả
            # hoặc: * Tên cột - mô tả
            m_col = re.match(r"^[-*•]\s*[`'\"]?([^:`'\"]+)[`'\"]?\s*[:\-–]\s*(.+)$", line_s)
            if m_col:
                col_name = m_col.group(1).strip()
                col_desc = m_col.group(2).strip()
                col_dict[col_name] = col_desc

        if col_dict:
            facts.column_descriptions[file_key] = col_dict

    # 5. Trích xuất các câu quy ước trong `## Quy ước`
    m_conv_sec = re.search(r"##\s*Quy ước\b(.*?)(?=\n##|\Z)", text, re.DOTALL | re.IGNORECASE)
    if m_conv_sec:
        sec_text = m_conv_sec.group(1)
        for line in sec_text.splitlines():
            line_s = line.strip()
            if line_s.startswith(("-", "*", "•")) or (len(line_s) > 10 and not line_s.startswith("#")):
                cleaned = re.sub(r"^[-*•]\s*", "", line_s)
                if cleaned:
                    facts.conventions.append(cleaned)

    return facts
