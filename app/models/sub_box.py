from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SubBox(Base):
    __tablename__ = "sub_boxes"

    id = Column(Integer, primary_key=True, index=True)
    box_id = Column(Integer, ForeignKey("boxes.id", ondelete="CASCADE"), nullable=False)
    readable_id = Column(String(150), unique=True, nullable=False, index=True)
    position_identifier = Column(String(50), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    box = relationship("Box", back_populates="sub_boxes")
    inventory = relationship("Inventory", back_populates="sub_box", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("box_id", "position_identifier", name="uq_box_position"),)
