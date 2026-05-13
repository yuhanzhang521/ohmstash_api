from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class VlmProviderConfigBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(..., min_length=1, max_length=64)
    base_url: Optional[str] = Field(default=None, max_length=1024)
    model_name: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True
    is_default: bool = False
    extra_config: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(str_strip_whitespace=True)


class VlmProviderConfigCreate(VlmProviderConfigBase):
    api_key: Optional[str] = None


class VlmProviderConfigUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    provider: Optional[str] = Field(default=None, min_length=1, max_length=64)
    base_url: Optional[str] = Field(default=None, max_length=1024)
    model_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    api_key: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    extra_config: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class VlmProviderConfig(VlmProviderConfigBase):
    id: int
    has_api_key: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
