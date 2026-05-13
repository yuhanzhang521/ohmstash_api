from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text, func

from app.database import Base


class VlmProviderConfig(Base):
    __tablename__ = "vlm_provider_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    provider = Column(String(64), nullable=False)
    base_url = Column(String(1024))
    model_name = Column(String(255), nullable=False)
    api_key = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    extra_config = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)
