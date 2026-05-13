from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.association import components_tags_association_table


class Component(Base):
    __tablename__ = "components"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    attributes = Column(JSON)
    display_attribute = Column(String(100))

    search_vector = Column(String().with_variant(TSVECTOR, "postgresql"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tags = relationship(
        "Tag",
        secondary=components_tags_association_table,
        back_populates="components",
    )

    inventory = relationship("Inventory", back_populates="component", cascade="all, delete-orphan")

