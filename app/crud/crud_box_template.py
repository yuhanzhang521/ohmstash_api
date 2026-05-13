from app.crud.base import CRUDBase
from app.models.box_template import BoxTemplate
from app.schemas.box_template import BoxTemplateCreate, BoxTemplateUpdate

class CRUDBoxTemplate(CRUDBase[BoxTemplate, BoxTemplateCreate, BoxTemplateUpdate]):
    pass

box_template = CRUDBoxTemplate(BoxTemplate)

