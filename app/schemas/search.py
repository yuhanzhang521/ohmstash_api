from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ComponentLocation(BaseModel):
    inventory_id: int
    box_id: int
    box_readable_id: str
    box_name: Optional[str] = None
    sub_box_id: int
    sub_box_readable_id: str
    position_identifier: str
    stock_mode: str
    quantity: Optional[str] = None
    notes: Optional[str] = None


class ComponentSearchResult(BaseModel):
    component_id: int
    name: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    locations: List[ComponentLocation] = Field(default_factory=list)


class SemanticSearchRequest(BaseModel):
    query: str
    use_llm: bool = False
    limit: int = Field(default=50, ge=1, le=100)


class SemanticSearchResponse(BaseModel):
    query: str
    parsed_query: Dict[str, Any]
    results: List[ComponentSearchResult]


class LocationRecommendationRequest(BaseModel):
    text: Optional[str] = None
    tag_names: List[str] = Field(default_factory=list)
    preferred_box_id: Optional[int] = None
    limit: int = 5


class LocationRecommendation(BaseModel):
    sub_box_id: int
    sub_box_readable_id: str
    box_id: int
    box_readable_id: str
    box_name: Optional[str] = None
    position_identifier: str
    reason: str
    nearby_components: List[str] = Field(default_factory=list)


class LocationRecommendationResponse(BaseModel):
    recommendations: List[LocationRecommendation]
    analysis_used: bool = False
    analysis_note: Optional[str] = None
