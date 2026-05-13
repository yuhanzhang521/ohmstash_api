from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List


class AttributeDefinitionBase(BaseModel):
    attribute_name: str


class AttributeDefinitionCreate(AttributeDefinitionBase):
    pass


class AttributeDefinition(AttributeDefinitionBase):
    id: int
    tag_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkAttributeCreateResponse(BaseModel):
    created: List[AttributeDefinition]
    skipped_duplicates: List[AttributeDefinitionBase]
