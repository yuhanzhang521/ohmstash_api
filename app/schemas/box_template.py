from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict

LayoutDefinition = Union[Dict[str, Any], List[Dict[str, Any]]]


class LayoutType(str, Enum):
    grid = "grid"
    irregular = "irregular"


class BoxTemplateBase(BaseModel):
    name: str
    physical_dimensions: Optional[Dict[str, Any]] = None
    layout_type: LayoutType
    layout_definition: LayoutDefinition


class BoxTemplateCreate(BoxTemplateBase):
    pass


class BoxTemplateUpdate(BaseModel):
    name: Optional[str] = None
    physical_dimensions: Optional[Dict[str, Any]] = None
    layout_type: Optional[LayoutType] = None
    layout_definition: Optional[LayoutDefinition] = None


class BoxTemplateInDBBase(BoxTemplateBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class BoxTemplate(BoxTemplateInDBBase):
    pass
