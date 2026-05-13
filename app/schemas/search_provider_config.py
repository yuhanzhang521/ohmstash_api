from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class SearchProviderConfigBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(..., min_length=1, max_length=64)
    is_active: bool = True
    is_default: bool = False
    extra_config: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(str_strip_whitespace=True)


class SearchProviderConfigCreate(SearchProviderConfigBase):
    api_key: Optional[str] = None


class SearchProviderConfigUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    provider: Optional[str] = Field(default=None, min_length=1, max_length=64)
    api_key: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    extra_config: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class SearchProviderConfig(SearchProviderConfigBase):
    id: int
    has_api_key: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SearchProviderConnectionTestRequest(BaseModel):
    config: Optional[SearchProviderConfigCreate] = None
    query: str = "LIS3DHTR datasheet"


class SearchProviderConnectionTestResult(BaseModel):
    ok: bool
    provider: str
    status_code: Optional[int] = None
    message: str
    latency_ms: Optional[int] = None
    results: list[dict[str, str]] = Field(default_factory=list)
