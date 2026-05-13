from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ComponentBase(BaseModel):
    name: str
    description: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None
    display_attribute: Optional[str] = None


class ComponentCreate(ComponentBase):
    tag_ids: List[int] = Field(default_factory=list)


class ComponentUpdate(ComponentBase):
    name: Optional[str] = None
    tag_ids: Optional[List[int]] = None


class Component(ComponentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    tags: List["Tag"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


from .tag import Tag

Component.model_rebuild()
