from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.database import Base


class AttributeDefinition(Base):
    __tablename__ = "attribute_definitions"

    id = Column(Integer, primary_key=True, index=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)
    attribute_name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tag = relationship("Tag", back_populates="attribute_definitions")

    __table_args__ = (
        UniqueConstraint("tag_id", "attribute_name", name="uq_tag_attribute_name"),
    )
