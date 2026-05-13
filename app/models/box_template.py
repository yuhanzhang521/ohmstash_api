from sqlalchemy import Column, DateTime, Enum, Integer, JSON, String, func

from app.database import Base

layout_type_enum = Enum("grid", "irregular", name="layout_type_enum")


class BoxTemplate(Base):
    __tablename__ = "box_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    physical_dimensions = Column(JSON)
    layout_type = Column(layout_type_enum, nullable=False)
    layout_definition = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
