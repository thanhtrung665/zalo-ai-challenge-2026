"""Gộp các RawSheet thành RawTable logic, thêm cột truy vết nguồn (_src_file, _src_sheet, _src_row)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from datamate.ingest.header import _normalize_text, detect_header
from datamate.ingest.readers import RawSheet


@dataclass
class RawTable:
    """Bảng dữ liệu logic đã xác định header và gắn cột truy vết nguồn."""

    name: str  # Tên bảng logic
    df: pd.DataFrame  # DataFrame chứa dữ liệu dạng chuỗi + cột _src_*
    source_files: list[str]  # Danh sách file nguồn tạo nên bảng này
    header_row: int  # Vị trí header (nếu từ 1 sheet đơn)
    preambles: list[dict[str, Any]] = field(default_factory=list)  # Preamble lưu metadata

    @property
    def num_rows(self) -> int:
        return len(self.df)

    @property
    def num_cols(self) -> int:
        return len(self.df.columns)


def _canonical_col_key(cols: list[str]) -> tuple[str, ...]:
    """Tạo chữ ký đại diện cho tập cột để nhận diện các sheet/file có cùng cấu trúc."""
    return tuple(_normalize_text(c) for c in cols if not c.startswith("_src_"))


def _clean_table_name(name: str) -> str:
    """Lược bỏ hậu tố tháng/năm hoặc số thứ tự (_1, _2, T01_2025...) để tạo tên bảng logic chung."""
    # Xoá đuôi _1, _2, _part1, _2025, _2026
    cleaned = re.sub(r"[_\-\s]+(part\d+|\d{1,4}|T\d{1,2}[_\-]\d{4})$", "", name, flags=re.IGNORECASE)
    # Xoá đuôi mở rộng file nếu có
    cleaned = re.sub(r"\.(csv|xlsx|xls|sqlite|db)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or name


def assemble_tables(
    sheets: list[RawSheet],
    vocab_path: Path | None = None,
) -> list[RawTable]:
    """Biến đổi danh sách RawSheet thành các RawTable, tự động gộp các sheet có cùng cấu trúc cột."""
    intermediate_tables: list[dict[str, Any]] = []

    for sheet in sheets:
        if not sheet.rows:
            continue

        guess = detect_header(sheet.rows, vocab_path=vocab_path)
        header_idx = guess.row_index
        headers = guess.headers

        data_rows = sheet.rows[header_idx + 1 :]
        if not data_rows:
            # Tạo DataFrame rỗng với đúng các cột
            df = pd.DataFrame(columns=headers)
            df["_src_file"] = pd.Series(dtype=str)
            df["_src_sheet"] = pd.Series(dtype=str)
            df["_src_row"] = pd.Series(dtype=int)
        else:
            # Chuẩn hoá số lượng phần tử của mỗi dòng khớp với số cột
            num_cols = len(headers)
            aligned_rows: list[list[str]] = []
            src_rows: list[int] = []

            for r_i, r in enumerate(data_rows):
                # Bỏ qua các dòng hoàn toàn rỗng
                if not any(c.strip() for c in r):
                    continue
                if len(r) < num_cols:
                    aligned_rows.append(r + [""] * (num_cols - len(r)))
                else:
                    aligned_rows.append(r[:num_cols])
                # Vị trí dòng gốc trong file/sheet (1-indexed tính cả header/preamble)
                src_rows.append(header_idx + 1 + r_i + 1)

            df = pd.DataFrame(aligned_rows, columns=headers, dtype=str)
            df["_src_file"] = sheet.src_file
            df["_src_sheet"] = sheet.name
            df["_src_row"] = src_rows

        intermediate_tables.append(
            {
                "sheet": sheet,
                "df": df,
                "headers": headers,
                "col_key": _canonical_col_key(headers),
                "header_idx": header_idx,
                "preamble": guess.preamble,
            }
        )

    # Nhóm các bảng có cùng chữ ký cột logic (_canonical_col_key)
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for item in intermediate_tables:
        key = item["col_key"]
        grouped.setdefault(key, []).append(item)

    results: list[RawTable] = []
    for _col_key, group in grouped.items():
        if len(group) == 1:
            item = group[0]
            sheet = item["sheet"]
            tname = sheet.name if sheet.name != "-" else Path(sheet.src_file).stem
            results.append(
                RawTable(
                    name=tname,
                    df=item["df"],
                    source_files=[sheet.src_file],
                    header_row=item["header_idx"],
                    preambles=[{"src_file": sheet.src_file, "sheet": sheet.name, "preamble": item["preamble"]}],
                )
            )
        else:
            # Gộp nhiều sheet / file lại thành 1 bảng logic
            dfs = [it["df"] for it in group]
            merged_df = pd.concat(dfs, ignore_index=True)
            src_files = list(dict.fromkeys(it["sheet"].src_file for it in group))
            preambles = [
                {"src_file": it["sheet"].src_file, "sheet": it["sheet"].name, "preamble": it["preamble"]}
                for it in group
            ]

            # Đặt tên bảng logic gộp
            base_names = [
                _clean_table_name(it["sheet"].name if it["sheet"].name != "-" else Path(it["sheet"].src_file).stem)
                for it in group
            ]
            common_name = base_names[0] if len(set(base_names)) == 1 else group[0]["sheet"].src_file
            common_name = Path(common_name).stem

            results.append(
                RawTable(
                    name=common_name,
                    df=merged_df,
                    source_files=src_files,
                    header_row=group[0]["header_idx"],
                    preambles=preambles,
                )
            )

    return results
