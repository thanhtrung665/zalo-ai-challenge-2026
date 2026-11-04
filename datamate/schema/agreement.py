"""Độ khớp giữa hai ShopMapping (dự đoán vs chuẩn).

Theo từng ô (bảng nguồn, bảng chuẩn, cột chuẩn, cột nguồn) và theo bảng trạng thái.
"""

from __future__ import annotations

from dataclasses import dataclass

from datamate.ingest.header import _normalize_text
from datamate.schema.mapping import ShopMapping

Cell = tuple[str, str, str, str]


def mapping_cells(m: ShopMapping) -> set[Cell]:
    return {
        (tm.source, t, canon, src) for tm in m.tables for t, cols in tm.targets.items() for canon, src in cols.items()
    }


@dataclass(frozen=True)
class Agreement:
    precision: float
    recall: float
    f1: float
    status_accuracy: float
    missing: list[Cell]
    extra: list[Cell]


def agreement(pred: ShopMapping, gold: ShopMapping) -> Agreement:
    p, g = mapping_cells(pred), mapping_cells(gold)
    tp = len(p & g)
    prec = tp / len(p) if p else 0.0
    rec = tp / len(g) if g else 1.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    gs = {_normalize_text(k): v for k, v in gold.status_map.items()}
    ps = {_normalize_text(k): v for k, v in pred.status_map.items()}
    st = sum(ps.get(k) == v for k, v in gs.items()) / len(gs) if gs else 1.0
    return Agreement(prec, rec, f1, st, sorted(g - p), sorted(p - g))
