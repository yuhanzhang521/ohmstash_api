from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text, func

from app.database import Base


class RecognitionSession(Base):
    __tablename__ = "recognition_sessions"

    id = Column(Integer, primary_key=True, index=True)
    owner_kind = Column(String(32), nullable=False, index=True)
    owner_id = Column(Integer, nullable=False, index=True)
    owner_name = Column(String(100), nullable=False)
    mode = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="queued", index=True)
    verification_status = Column(String(32), nullable=False, default="idle")
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    config_id = Column(Integer)
    search_provider_config_id = Column(Integer)
    box_id = Column(Integer)
    template_id = Column(Integer)
    layout_type = Column(String(32))
    additional_prompt = Column(Text, nullable=False, default="")
    overwrite_existing = Column(Boolean, nullable=False, default=False)
    result = Column(JSON)
    verification_result = Column(JSON)
    error_message = Column(Text)
    verification_error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at = Column(DateTime(timezone=True))
