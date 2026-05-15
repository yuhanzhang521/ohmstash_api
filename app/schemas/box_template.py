from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, model_validator

LayoutDefinition = Union[Dict[str, Any], List[Dict[str, Any]]]
MAX_GRID_ROWS = 40
MAX_GRID_COLS = 40
MAX_LAYOUT_CELLS = 400


class LayoutType(str, Enum):
    grid = "grid"
    irregular = "irregular"


class BoxTemplateBase(BaseModel):
    name: str
    physical_dimensions: Optional[Dict[str, Any]] = None
    layout_type: LayoutType
    layout_definition: LayoutDefinition

    @model_validator(mode="after")
    def validate_layout_definition(self) -> "BoxTemplateBase":
        validate_layout_definition(self.layout_type, self.layout_definition)
        return self


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


def validate_layout_definition(
    layout_type: LayoutType,
    layout_definition: LayoutDefinition,
) -> None:
    if layout_type == LayoutType.grid:
        if not isinstance(layout_definition, dict):
            raise ValueError("Grid layout_definition must be an object")
        rows = layout_definition.get("rows")
        cols = layout_definition.get("cols")
        if not isinstance(rows, int) or not isinstance(cols, int):
            raise ValueError("Grid rows and cols must be integers")
        if rows < 1 or rows > MAX_GRID_ROWS or cols < 1 or cols > MAX_GRID_COLS:
            raise ValueError("Grid rows and cols are out of range")
        if rows * cols > MAX_LAYOUT_CELLS:
            raise ValueError("Grid layout has too many cells")
        return

    definitions = layout_definition
    if isinstance(definitions, dict):
        definitions = definitions.get("cells", [])
    if not isinstance(definitions, list):
        raise ValueError("Irregular layout_definition must be a list or cells object")
    if len(definitions) > MAX_LAYOUT_CELLS:
        raise ValueError("Irregular layout has too many cells")
    for item in definitions:
        if not isinstance(item, dict):
            raise ValueError("Irregular cells must be objects")
        position = item.get("id") or item.get("position_identifier")
        if not isinstance(position, str) or not position.strip():
            raise ValueError("Irregular cells must include id or position_identifier")
