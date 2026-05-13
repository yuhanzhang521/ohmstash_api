from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator


class StockModeEnum(str, Enum):
    exact = "exact"
    fuzzy = "fuzzy"


class QuantityFuzzyEnum(str, Enum):
    充足 = "充足"
    少量 = "少量"
    紧张 = "紧张"
    未知 = "未知"
    用尽 = "用尽"


class InventoryBase(BaseModel):
    sub_box_id: int
    component_id: int
    stock_mode: StockModeEnum
    quantity_exact: Optional[int] = None
    quantity_fuzzy: Optional[QuantityFuzzyEnum] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_quantity_fields(self) -> "InventoryBase":
        if self.stock_mode == StockModeEnum.exact:
            if self.quantity_exact is None:
                raise ValueError("quantity_exact is required when stock_mode is 'exact'")
            if self.quantity_fuzzy is not None:
                raise ValueError("quantity_fuzzy must be empty when stock_mode is 'exact'")

        if self.stock_mode == StockModeEnum.fuzzy:
            if self.quantity_fuzzy is None:
                raise ValueError("quantity_fuzzy is required when stock_mode is 'fuzzy'")
            if self.quantity_exact is not None:
                raise ValueError("quantity_exact must be empty when stock_mode is 'fuzzy'")

        return self


class InventoryCreate(InventoryBase):
    pass


class InventoryUpdate(BaseModel):
    sub_box_id: Optional[int] = None
    component_id: Optional[int] = None
    stock_mode: Optional[StockModeEnum] = None
    quantity_exact: Optional[int] = None
    quantity_fuzzy: Optional[QuantityFuzzyEnum] = None
    notes: Optional[str] = None


class Inventory(InventoryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
