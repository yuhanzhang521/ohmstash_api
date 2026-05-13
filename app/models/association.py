from sqlalchemy import Column, ForeignKey, Integer, Table

from app.database import Base


components_tags_association_table = Table(
    "components_tags",
    Base.metadata,
    Column("component_id", Integer, ForeignKey("components.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)
