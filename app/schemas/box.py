from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class BoxBase(BaseModel):
    readable_id: Optional[str] = None
    name: Optional[str] = None
    template_id: int


class BoxCreate(BoxBase):
    pass


class BoxUpdate(BaseModel):
    readable_id: Optional[str] = None
    name: Optional[str] = None
    template_id: Optional[int] = None


class BoxInDBBase(BoxBase):
    id: int
    readable_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Box(BoxInDBBase):
    pass
