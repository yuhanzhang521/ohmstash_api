from typing import List

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models import Component, Tag
from app.schemas.component import ComponentCreate, ComponentUpdate
from app.services.component_display import choose_component_display_attribute


class CRUDComponent(CRUDBase[Component, ComponentCreate, ComponentUpdate]):
    def create(self, db: Session, *, obj_in: ComponentCreate) -> Component:
        # Create the component object without the tags
        component_data = obj_in.model_dump(exclude={"tag_ids"})
        component_data["display_attribute"] = choose_component_display_attribute(
            component_data.get("attributes"),
            component_data.get("display_attribute"),
        )
        db_obj = Component(**component_data)

        # Handle tags if they are provided
        if obj_in.tag_ids:
            tags = db.query(Tag).filter(Tag.id.in_(obj_in.tag_ids)).all()
            db_obj.tags = tags

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, *, db_obj: Component, obj_in: ComponentUpdate) -> Component:
        # Update standard fields
        update_data = obj_in.model_dump(exclude_unset=True, exclude={"tag_ids"})
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        if "attributes" in update_data or "display_attribute" in update_data:
            db_obj.display_attribute = choose_component_display_attribute(
                db_obj.attributes,
                db_obj.display_attribute,
            )

        # Update tags if provided
        if obj_in.tag_ids is not None:
            tags = db.query(Tag).filter(Tag.id.in_(obj_in.tag_ids)).all()
            db_obj.tags = tags

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_multi_by_tags(self, db: Session, *, tag_ids: List[int], skip: int = 0, limit: int = 100) -> List[Component]:
        """
        Retrieve components that are associated with ALL of the given tag IDs.
        """
        query = db.query(Component)
        for tag_id in tag_ids:
            query = query.filter(Component.tags.any(id=tag_id))

        return query.offset(skip).limit(limit).all()


component = CRUDComponent(Component)

