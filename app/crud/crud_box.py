from typing import List

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.box import Box
from app.models.sub_box import SubBox
from app.schemas.box import BoxCreate, BoxUpdate


class CRUDBox(CRUDBase[Box, BoxCreate, BoxUpdate]):
    def create(self, db: Session, *, obj_in: BoxCreate) -> Box:
        db_obj = super().create(db, obj_in=obj_in)

        template = db_obj.template
        if not template:
            return db_obj

        sub_boxes_to_create: List[SubBox] = []
        template_dimensions = template.physical_dimensions or {}
        if template_dimensions.get("container_type") == "bulk":
            position = "CONTENTS"
            readable_id = f"SUB-{db_obj.readable_id}-{position}"
            sub_boxes_to_create.append(
                SubBox(
                    box_id=db_obj.id,
                    readable_id=readable_id,
                    position_identifier=position,
                )
            )
        elif template.layout_type == "grid":
            rows = template.layout_definition.get("rows", 0)
            cols = template.layout_definition.get("cols", 0)
            for row in range(1, rows + 1):
                for col in range(1, cols + 1):
                    position = f"R{row}C{col}"
                    readable_id = f"SUB-{db_obj.readable_id}-{position}"
                    sub_box = SubBox(
                        box_id=db_obj.id,
                        readable_id=readable_id,
                        position_identifier=position,
                    )
                    sub_boxes_to_create.append(sub_box)
        elif template.layout_type == "irregular":
            definitions = template.layout_definition
            if isinstance(definitions, dict):
                definitions = definitions.get("cells", [])
            if isinstance(definitions, list):
                for item in definitions:
                    position = item.get("id") or item.get("position_identifier")
                    if position:
                        readable_id = f"SUB-{db_obj.readable_id}-{position}"
                        sub_box = SubBox(
                            box_id=db_obj.id,
                            readable_id=readable_id,
                            position_identifier=position,
                        )
                        sub_boxes_to_create.append(sub_box)

        if sub_boxes_to_create:
            db.add_all(sub_boxes_to_create)
            db.commit()
            db.refresh(db_obj)

        return db_obj


box = CRUDBox(Box)
