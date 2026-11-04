"""ShopMapping: cách đưa dữ liệu thô của một shop về bảng chuẩn (LLM sinh, hoặc viết tay để đối chiếu)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from datamate.schema.canonical import ORDER_STATUSES, target_columns


class TableMapping(BaseModel):
    """Một bảng nguồn cấp dữ liệu cho một hoặc nhiều bảng chuẩn (bảng phẳng cấp cho cả orders và order_lines)."""

    model_config = ConfigDict(frozen=True)

    source: str  # khoá bảng nguồn (xem `table_key`)
    # bảng chuẩn -> {cột chuẩn: tên cột nguồn}
    targets: dict[str, dict[str, str]]
    # bảng chuẩn -> {cột chuẩn: giá trị hằng}, vd. status="completed" khi file chỉ chứa đơn hoàn tất
    constants: dict[str, dict[str, str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_targets(self) -> TableMapping:
        for table, cols in self.targets.items():
            try:
                valid = target_columns(table)
            except KeyError as e:
                raise ValueError(f"bảng chuẩn không tồn tại: {table!r}") from e
            bad = [c for c in cols if c not in valid]
            if bad:
                raise ValueError(f"cột chuẩn không tồn tại trong {table}: {bad}")
        for table, cols in self.constants.items():
            valid = target_columns(table)
            bad = [c for c in cols if c not in valid]
            if bad:
                raise ValueError(f"cột hằng không tồn tại trong {table}: {bad}")
        return self


class ShopMapping(BaseModel):
    model_config = ConfigDict(frozen=True)

    tables: list[TableMapping]
    # giá trị trạng thái gốc (chuẩn hoá bỏ dấu, chữ thường) -> completed|cancelled|returned|delivering
    status_map: dict[str, str] = Field(default_factory=dict)
    # trạng thái cho giá trị không có trong status_map (None = để trống, validator báo)
    default_status: str | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_status(self) -> ShopMapping:
        allowed = set(ORDER_STATUSES)
        bad = {v for v in self.status_map.values() if v not in allowed}
        if bad:
            raise ValueError(f"status_map có giá trị ngoài {sorted(allowed)}: {sorted(bad)}")
        if self.default_status is not None and self.default_status not in allowed:
            raise ValueError(f"default_status không hợp lệ: {self.default_status!r}")
        return self
