from typing import List
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.sub_box import SubBox
from app.schemas.sub_box import SubBoxCreate, SubBoxUpdate


class CRUDSubBox(CRUDBase[SubBox, SubBoxCreate, SubBoxUpdate]):
    def get_multi_by_box(
        self, db: Session, *, box_id: int, skip: int = 0, limit: int = 100
    ) -> List[SubBox]:
        return (
            db.query(self.model)
            .filter(self.model.box_id == box_id)
            .offset(skip)
            .limit(limit)
            .all()
        )


sub_box = CRUDSubBox(SubBox)
