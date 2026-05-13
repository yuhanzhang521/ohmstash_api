from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base

stock_mode_enum = Enum("exact", "fuzzy", name="stock_mode_enum")
quantity_fuzzy_enum = Enum("充足", "少量", "紧张", "未知", "用尽", name="quantity_fuzzy_enum")


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    sub_box_id = Column(Integer, ForeignKey("sub_boxes.id", ondelete="CASCADE"), nullable=False)
    component_id = Column(Integer, ForeignKey("components.id", ondelete="CASCADE"), nullable=False)

    stock_mode = Column(stock_mode_enum, nullable=False)
    quantity_exact = Column(Integer)
    quantity_fuzzy = Column(quantity_fuzzy_enum)
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    sub_box = relationship("SubBox", back_populates="inventory")
    component = relationship("Component", back_populates="inventory")

    __table_args__ = (
        UniqueConstraint("sub_box_id", "component_id", name="uq_sub_box_component"),
        CheckConstraint(
            "("
            "stock_mode = 'exact' "
            "AND quantity_exact IS NOT NULL "
            "AND quantity_fuzzy IS NULL"
            ") OR ("
            "stock_mode = 'fuzzy' "
            "AND quantity_fuzzy IS NOT NULL "
            "AND quantity_exact IS NULL"
            ")",
            name="check_quantity_mode",
        ),
    )
