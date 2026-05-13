from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models import AttributeDefinition
from app.models.tag import Tag
from app.schemas.tag import TagCreate, TagUpdate


class CRUDTag(CRUDBase[Tag, TagCreate, TagUpdate]):
    def get_by_name(self, db: Session, *, name: str) -> Optional[Tag]:
        return db.query(Tag).filter(Tag.name == name).first()

    def get(self, db: Session, id: int) -> Optional[Tag]:
        return db.query(Tag).options(joinedload(Tag.attribute_definitions)).filter(Tag.id == id).first()

    def create(self, db: Session, *, obj_in: TagCreate) -> Tag:
        # Create the Tag object first
        db_obj = Tag(name=obj_in.name)

        # If there are attribute definitions, create them
        if obj_in.attribute_definitions:
            for attr_name in obj_in.attribute_definitions:
                db_obj.attribute_definitions.append(AttributeDefinition(attribute_name=attr_name))

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, *, db_obj: Tag, obj_in: TagUpdate | Dict[str, Any]) -> Tag:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        # Update tag name
        if 'name' in update_data:
            db_obj.name = update_data['name']

        # Handle attribute definitions update
        if 'attribute_definitions' in update_data and update_data['attribute_definitions'] is not None:
            # This is a full replacement. Clear existing attributes and add new ones.
            db_obj.attribute_definitions.clear()
            for attr_name in update_data['attribute_definitions']:
                db_obj.attribute_definitions.append(AttributeDefinition(attribute_name=attr_name))

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create_multiple(self, db: Session, *, tags_in: List[TagCreate]) -> dict:
        created_tags = []
        skipped_tags = []

        for tag_in in tags_in:
            existing_tag = self.get_by_name(db, name=tag_in.name)
            if existing_tag:
                skipped_tags.append(tag_in)
            else:
                # Avoid processing duplicates within the same batch
                if not any(t.name == tag_in.name for t in created_tags):
                    created_tag = self.create(db, obj_in=tag_in)
                    created_tags.append(created_tag)

        return {"created": created_tags, "skipped_duplicates": skipped_tags}


tag = CRUDTag(Tag)
