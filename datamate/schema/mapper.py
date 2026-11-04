"""Vòng lặp map một shop: nháp heuristic → LLM → kiểm bằng code → gửi lỗi cho LLM sửa (tối đa 2 vòng) → dự phòng.

Mọi lỗi của LLM (JSON hỏng, cột không tồn tại, đơn vị...) đều quay về vòng sửa; sau cùng chọn phương án ít lỗi nhất.
Kết quả lưu cache để tái dùng, và tất định: temperature 0 ở backend.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from datamate.ingest.cache import compute_dir_hash
from datamate.ingest.loader import BusinessData
from datamate.llm.base import LLMBackend, LLMError
from datamate.schema.build import MappingError, build_store
from datamate.schema.canonical import CanonicalStore
from datamate.schema.mapping import ShopMapping
from datamate.schema.profile import profile_tables
from datamate.schema.prompt import build_mapping_prompt
from datamate.schema.propose import propose_mapping
from datamate.schema.validate import Issue, validate_store

logger = logging.getLogger(__name__)

MAX_REPAIR_ROUNDS = 2


@dataclass
class MapResult:
    mapping: ShopMapping
    store: CanonicalStore
    issues: list[Issue]
    source: str  # "llm" | "heuristic" | "cache"
    rounds: int
    log: list[str] = field(default_factory=list)

    @property
    def n_errors(self) -> int:
        return sum(i.severity == "error" for i in self.issues)


def _try(biz: BusinessData, mapping: ShopMapping) -> tuple[CanonicalStore | None, list[Issue], str | None]:
    """Áp mapping; trả (store, issues, lỗi cấu trúc)."""
    try:
        store = build_store(biz, mapping)
    except MappingError as e:
        return None, [], str(e)
    return store, validate_store(store), None


def _cache_path(biz_dir: Path | None, cache_dir: Path) -> Path | None:
    if biz_dir is None:
        return None
    return cache_dir / biz_dir.name / compute_dir_hash(biz_dir) / "mapping.json"


def map_shop(
    biz: BusinessData,
    backend: LLMBackend | None,
    *,
    biz_dir: Path | None = None,
    cache_dir: Path = Path("/tmp/datamate_cache"),
    max_rounds: int = MAX_REPAIR_ROUNDS,
) -> MapResult:
    """Map một shop. `backend=None` → chỉ dùng bản nháp heuristic (không LLM)."""
    log: list[str] = []
    cpath = _cache_path(biz_dir, cache_dir)
    if cpath is not None and cpath.exists():
        try:
            cached = ShopMapping.model_validate_json(cpath.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.append(f"cache mapping hỏng ({type(e).__name__}), map lại")
        else:
            store, issues, err = _try(biz, cached)
            if store is not None and not any(i.severity == "error" for i in issues):
                return MapResult(cached, store, issues, "cache", 0, log)

    profiles = profile_tables(biz.tables)
    draft, _roles = propose_mapping(biz)
    candidates: list[tuple[str, ShopMapping, CanonicalStore, list[Issue]]] = []
    d_store, d_issues, d_err = _try(biz, draft)
    if d_store is not None:
        candidates.append(("heuristic", draft, d_store, d_issues))
    else:
        log.append(f"bản nháp heuristic lỗi cấu trúc: {d_err}")

    rounds = 0
    if backend is not None:
        prev: str | None = None
        issues_fb: list[Issue] | None = None
        err_fb: str | None = None
        base = draft if d_store is not None else None
        for rounds in range(1, max_rounds + 2):  # 1 lần sinh + tối đa max_rounds lần sửa
            prompt = build_mapping_prompt(biz, profiles, base, issues_fb, prev, err_fb)
            try:
                res = backend.generate_json([prompt], ShopMapping)[0]
            except LLMError as e:
                log.append(f"vòng {rounds}: backend lỗi: {e}")
                break
            prev, issues_fb, err_fb = res.text, None, None
            mapping = res.parsed
            if not isinstance(mapping, ShopMapping):
                err_fb = f"JSON không hợp lệ theo schema: {res.error or 'không parse được'}"
                log.append(f"vòng {rounds}: {err_fb[:120]}")
                continue
            store, issues, err = _try(biz, mapping)
            if store is None:
                err_fb = err
                log.append(f"vòng {rounds}: {err}")
                continue
            candidates.append(("llm", mapping, store, issues))
            errors = [i for i in issues if i.severity == "error"]
            if not errors:
                log.append(f"vòng {rounds}: đạt")
                break
            issues_fb = errors
            log.append(f"vòng {rounds}: {len(errors)} lỗi → gửi lại")

    if not candidates:
        raise MappingError("; ".join(log) or "không có mapping nào áp dụng được")

    # ít lỗi nhất thắng; hoà thì LLM (đã đọc README) hơn nháp; hoà tiếp thì phương án sau cùng
    def rank(c: tuple[str, ShopMapping, CanonicalStore, list[Issue]]) -> tuple[int, int]:
        return (sum(i.severity == "error" for i in c[3]), 0 if c[0] == "llm" else 1)

    source, mapping, store, issues = min(reversed(candidates), key=rank)
    if any(i.severity == "error" for i in issues):
        store.capabilities.notes.append(
            "mapping còn lỗi: " + "; ".join(i.code for i in issues if i.severity == "error")
        )
    if cpath is not None and not any(i.severity == "error" for i in issues):
        cpath.parent.mkdir(parents=True, exist_ok=True)
        cpath.write_text(mapping.model_dump_json(), encoding="utf-8")
    return MapResult(mapping, store, issues, source, rounds, log)
