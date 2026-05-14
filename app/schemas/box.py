from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.box_name_rules import (
    BOX_NAME_MAX_DISPLAY_WIDTH,
    compute_display_width,
)


def _validate_box_name(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    width = compute_display_width(trimmed)
    if width > BOX_NAME_MAX_DISPLAY_WIDTH:
        raise ValueError(
            f"Box name display width must be <= {BOX_NAME_MAX_DISPLAY_WIDTH} "
            f"(Chinese char = 2, ASCII char = 1); got width {width}"
        )
    return trimmed


class BoxBase(BaseModel):
    readable_id: Optional[str] = None
    name: Optional[str] = None
    template_id: int

    _validate_name = field_validator("name")(lambda cls, value: _validate_box_name(value))


class BoxCreate(BoxBase):
    pass


class BoxUpdate(BaseModel):
    readable_id: Optional[str] = None
    name: Optional[str] = None
    template_id: Optional[int] = None

    _validate_name = field_validator("name")(lambda cls, value: _validate_box_name(value))


class BoxInDBBase(BoxBase):
    id: int
    readable_id: str
    category_summary: List[str] = Field(default_factory=list)
    label_needs_reprint: bool = False
    printed_label_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Box(BoxInDBBase):
    pass

