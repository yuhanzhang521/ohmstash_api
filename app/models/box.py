import hashlib
import json

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base


class Box(Base):
    __tablename__ = "boxes"

    id = Column(Integer, primary_key=True, index=True)
    readable_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(255))
    template_id = Column(Integer, ForeignKey("box_templates.id"), nullable=False)

    printed_label_signature = Column(Text)
    printed_label_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    template = relationship("BoxTemplate")
    sub_boxes = relationship("SubBox", back_populates="box", cascade="all, delete-orphan")

    @property
    def current_label_signature(self) -> str:
        from app.services.box_labeling import compute_box_category_summary

        payload = {
            "name": self.name or "",
            "template_id": self.template_id,
            "template_name": self.template.name if self.template else None,
            "summary": compute_box_category_summary(self),
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @property
    def category_summary(self) -> list[str]:
        from app.services.box_labeling import compute_box_category_summary

        return compute_box_category_summary(self)

    @property
    def label_needs_reprint(self) -> bool:
        if not self.printed_label_signature:
            return False
        return self.printed_label_signature != self.current_label_signature

