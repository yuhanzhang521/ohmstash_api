from app.crud.base import CRUDBase
from app.models.attribute_definition import AttributeDefinition
from app.schemas.attribute_definition import AttributeDefinitionCreate


class CRUDAttributeDefinition(CRUDBase[AttributeDefinition, AttributeDefinitionCreate, AttributeDefinitionCreate]):
    pass


attribute_definition = CRUDAttributeDefinition(AttributeDefinition)
