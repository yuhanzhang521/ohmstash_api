from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.box import _validate_box_name
from app.schemas.box_template import LayoutDefinition, LayoutType
from app.schemas.inventory import QuantityFuzzyEnum, StockModeEnum
from app.schemas.vlm_provider_config import VlmProviderConfigCreate


class VlmConnectionTestRequest(BaseModel):
    config: Optional[VlmProviderConfigCreate] = None
    prompt: str = "Return exactly this JSON: {\"ok\": true}"


class VlmConnectionTestResult(BaseModel):
    ok: bool
    provider: str
    model_name: str
    latency_ms: Optional[int] = None
    status_code: Optional[int] = None
    message: str
    response_text: Optional[str] = None


class ImageRecognitionResponse(BaseModel):
    config_id: Optional[int] = None
    filename: str
    content_type: str
    prompt: str
    raw_text: str
    parsed_result: Optional[Dict[str, Any]] = None
    latency_ms: int


class RecognizedCell(BaseModel):
    position_identifier: str
    is_empty: bool = False
    name: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    display_attribute: Optional[str] = None
    confidence: Optional[float] = None
    notes: Optional[str] = None
    verification_warning: Optional[str] = None
    stock_mode: StockModeEnum = StockModeEnum.fuzzy
    quantity_exact: Optional[int] = None
    quantity_fuzzy: Optional[QuantityFuzzyEnum] = QuantityFuzzyEnum.未知


class ConfirmBoxRecognitionRequest(BaseModel):
    box_id: int
    cells: List[RecognizedCell]
    overwrite_existing: bool = False


class ConfirmNewBoxRecognitionRequest(BaseModel):
    template_id: int
    box_name: Optional[str] = None
    readable_id: Optional[str] = None
    cells: List[RecognizedCell]

    _validate_box_name = field_validator("box_name")(
        lambda cls, value: _validate_box_name(value)
    )


class ConfirmAutoBoxRecognitionRequest(BaseModel):
    template_name: str
    layout_type: LayoutType
    layout_definition: LayoutDefinition
    physical_dimensions: Optional[Dict[str, Any]] = None
    box_name: Optional[str] = None
    readable_id: Optional[str] = None
    cells: List[RecognizedCell]

    _validate_box_name = field_validator("box_name")(
        lambda cls, value: _validate_box_name(value)
    )


class ConfirmBoxRecognitionResult(BaseModel):
    created_components: int
    created_inventory_items: int
    updated_inventory_items: int
    skipped_empty_cells: int
    skipped_missing_sub_boxes: List[str] = Field(default_factory=list)
    template_id: Optional[int] = None
    box_id: Optional[int] = None
    box_readable_id: Optional[str] = None


class ComponentVerificationRequest(BaseModel):
    items: List[RecognizedCell]
    config_id: Optional[int] = None
    search_provider_config_id: Optional[int] = None
    use_web: bool = True
    additional_prompt: str = ""


class ComponentVerificationResponse(BaseModel):
    config_id: Optional[int] = None
    verified_items: List[RecognizedCell]
    raw_text: str
    latency_ms: int
    web_used: bool = False
    web_contexts: List[Dict[str, Any]] = Field(default_factory=list)


class RecognitionSession(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_kind: str
    owner_id: int
    owner_name: str
    mode: str
    status: str
    verification_status: str
    filename: str
    content_type: str
    config_id: Optional[int] = None
    search_provider_config_id: Optional[int] = None
    box_id: Optional[int] = None
    template_id: Optional[int] = None
    layout_type: Optional[str] = None
    additional_prompt: str = ""
    overwrite_existing: bool = False
    result: Optional[Dict[str, Any]] = None
    verification_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    verification_error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
