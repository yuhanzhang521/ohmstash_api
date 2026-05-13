from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class Box(Base):
    __tablename__ = "boxes"

    id = Column(Integer, primary_key=True, index=True)
    readable_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(255))
    template_id = Column(Integer, ForeignKey("box_templates.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    template = relationship("BoxTemplate")
    sub_boxes = relationship("SubBox", back_populates="box", cascade="all, delete-orphan")
