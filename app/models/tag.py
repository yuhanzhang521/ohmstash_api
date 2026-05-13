from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.association import components_tags_association_table


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    attribute_definitions = relationship("AttributeDefinition", back_populates="tag", cascade="all, delete-orphan")

    components = relationship(
        "Component",
        secondary=components_tags_association_table,
        back_populates="tags",
    )
