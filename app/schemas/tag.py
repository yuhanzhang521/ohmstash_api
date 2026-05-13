from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .attribute_definition import AttributeDefinition


class TagBase(BaseModel):
    name: str


class TagCreate(TagBase):
    attribute_definitions: List[str] = Field(default_factory=list)


class TagUpdate(TagBase):
    attribute_definitions: Optional[List[str]] = None


class Tag(TagBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TagWithAttributes(Tag):
    attribute_definitions: List[AttributeDefinition] = Field(default_factory=list)


class BulkCreateResponse(BaseModel):
    created: List[Tag]
    skipped_duplicates: List[TagBase]
