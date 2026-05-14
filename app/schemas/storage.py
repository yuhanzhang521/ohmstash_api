from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.inventory import Inventory


class SubBoxOverview(BaseModel):
    id: int
    readable_id: str
    position_identifier: str
    inventory: List[Dict[str, Any]] = Field(default_factory=list)


class BoxOverview(BaseModel):
    id: int
    readable_id: str
    name: Optional[str] = None
    template: Dict[str, Any]
    sub_boxes: List[SubBoxOverview]
    category_summary: List[str] = Field(default_factory=list)
    label_needs_reprint: bool = False
    printed_label_at: Optional[datetime] = None


class MoveInventoryRequest(BaseModel):
    source_sub_box_id: int
    target_sub_box_id: int
    allow_merge: bool = False


class SwapInventoryRequest(BaseModel):
    first_sub_box_id: int
    second_sub_box_id: int


class InventoryMoveResult(BaseModel):
    source_sub_box_id: int
    target_sub_box_id: int
    moved_items: List[Inventory]
