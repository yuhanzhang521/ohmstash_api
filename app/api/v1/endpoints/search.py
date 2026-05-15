import json
import re
from time import perf_counter
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session, joinedload

from app import crud, models, schemas
from app.api import deps
from app.models.search_provider_config import (
    SearchProviderConfig as SearchProviderConfigModel,
)
from app.services import vlm_client, web_search

router = APIRouter()
SUPPORTED_SEARCH_PROVIDERS = {
    "brave",
    "tavily",
    "openai_web_search",
    "duckduckgo",
}


def _ensure_unique_search_config_name(
    db: Session,
    *,
    name: str,
    current_config_id: Optional[int] = None,
) -> None:
    existing_config = crud.search_provider_config.get_by_name(db=db, name=name)
    if existing_config and existing_config.id != current_config_id:
        raise HTTPException(status_code=400, detail="Search provider name already exists")


def _validate_search_provider(provider: str) -> None:
    if provider not in SUPPORTED_SEARCH_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported search provider")


def _get_search_provider_for_use(
    db: Session,
    *,
    config_id: Optional[int] = None,
) -> Optional[SearchProviderConfigModel]:
    if config_id is None:
        return crud.search_provider_config.get_default(db=db)

    config = crud.search_provider_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Search provider config not found")
    return config


def _build_transient_search_config(
    config_in: schemas.SearchProviderConfigCreate,
) -> SearchProviderConfigModel:
    return SearchProviderConfigModel(**config_in.model_dump())


def build_web_search_provider_settings(
    config: Optional[SearchProviderConfigModel],
) -> Optional[web_search.SearchProviderSettings]:
    if not config:
        return None
    return web_search.SearchProviderSettings(
        name=config.name,
        provider=config.provider,
        api_key=config.api_key,
        extra_config=config.extra_config or {},
    )


def _run_search_provider_test(
    config: Optional[SearchProviderConfigModel],
    *,
    query: str,
) -> schemas.SearchProviderConnectionTestResult:
    provider = config.provider if config else "duckduckgo"
    started_at = perf_counter()
    try:
        results = web_search.fetch_search_snippets(
            query,
            limit=3,
            provider_settings=build_web_search_provider_settings(config),
        )
    except web_search.SearchProviderError as exc:
        return schemas.SearchProviderConnectionTestResult(
            ok=False,
            provider=provider,
            status_code=exc.status_code,
            message=str(exc),
            latency_ms=int((perf_counter() - started_at) * 1000),
        )
    return schemas.SearchProviderConnectionTestResult(
        ok=bool(results),
        provider=provider,
        message="Search provider test succeeded" if results else "No search results returned",
        latency_ms=int((perf_counter() - started_at) * 1000),
        results=results,
    )


def _quantity_text(inventory_item: models.Inventory) -> str:
    if inventory_item.stock_mode == "exact":
        return str(inventory_item.quantity_exact)
    return str(inventory_item.quantity_fuzzy)


def _component_haystack(component: models.Component) -> str:
    parts = [
        component.name or "",
        component.description or "",
        json.dumps(component.attributes or {}, ensure_ascii=False),
    ]
    parts.extend(tag.name for tag in component.tags)
    return " ".join(parts).lower()


def _serialize_component_result(
    component: models.Component,
) -> schemas.ComponentSearchResult:
    locations: List[schemas.ComponentLocation] = []
    for inventory_item in component.inventory:
        sub_box = inventory_item.sub_box
        if not sub_box or not sub_box.box:
            continue
        locations.append(
            schemas.ComponentLocation(
                inventory_id=inventory_item.id,
                box_id=sub_box.box.id,
                box_readable_id=sub_box.box.readable_id,
                box_name=sub_box.box.name,
                sub_box_id=sub_box.id,
                sub_box_readable_id=sub_box.readable_id,
                position_identifier=sub_box.position_identifier,
                stock_mode=inventory_item.stock_mode,
                quantity=_quantity_text(inventory_item),
                notes=inventory_item.notes,
            )
        )
    return schemas.ComponentSearchResult(
        component_id=component.id,
        name=component.name,
        description=component.description,
        tags=[tag.name for tag in component.tags],
        attributes=component.attributes or {},
        locations=locations,
    )


@router.post("/providers/test", response_model=schemas.SearchProviderConnectionTestResult)
def test_search_provider_form(
    *,
    test_in: Optional[schemas.SearchProviderConnectionTestRequest] = None,
) -> object:
    request_data = test_in or schemas.SearchProviderConnectionTestRequest()
    config = (
        _build_transient_search_config(request_data.config)
        if request_data.config
        else None
    )
    if config:
        _validate_search_provider(config.provider)
    return _run_search_provider_test(config=config, query=request_data.query)


@router.post("/providers/", response_model=schemas.SearchProviderConfig)
def create_search_provider_config(
    *,
    db: Session = Depends(deps.get_db),
    config_in: schemas.SearchProviderConfigCreate,
) -> object:
    _validate_search_provider(config_in.provider)
    _ensure_unique_search_config_name(db=db, name=config_in.name)
    return crud.search_provider_config.create(db=db, obj_in=config_in)


@router.get("/providers/", response_model=List[schemas.SearchProviderConfig])
def read_search_provider_configs(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> object:
    return crud.search_provider_config.get_multi(db=db, skip=skip, limit=limit)


@router.get("/providers/default", response_model=schemas.SearchProviderConfig)
def read_default_search_provider_config(
    db: Session = Depends(deps.get_db),
) -> object:
    config = crud.search_provider_config.get_default(db=db)
    if not config:
        raise HTTPException(
            status_code=404,
            detail="Default search provider config not found",
        )
    return config


@router.get("/providers/{config_id}", response_model=schemas.SearchProviderConfig)
def read_search_provider_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
) -> object:
    config = crud.search_provider_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Search provider config not found")
    return config


@router.put("/providers/{config_id}", response_model=schemas.SearchProviderConfig)
def update_search_provider_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
    config_in: schemas.SearchProviderConfigUpdate,
) -> object:
    config = crud.search_provider_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Search provider config not found")
    if config_in.provider:
        _validate_search_provider(config_in.provider)
    if config_in.name:
        _ensure_unique_search_config_name(
            db=db,
            name=config_in.name,
            current_config_id=config.id,
        )
    config_data = config_in.model_dump(exclude_unset=True)
    if "api_key" in config_data and not config_data["api_key"]:
        config_data.pop("api_key", None)
    return crud.search_provider_config.update(
        db=db,
        db_obj=config,
        obj_in=config_data,
    )


@router.post(
    "/providers/{config_id}/set_default",
    response_model=schemas.SearchProviderConfig,
)
def set_default_search_provider_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
) -> object:
    config = crud.search_provider_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Search provider config not found")
    return crud.search_provider_config.set_default(db=db, db_obj=config)


@router.post(
    "/providers/{config_id}/test",
    response_model=schemas.SearchProviderConnectionTestResult,
)
def test_search_provider_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
    test_in: Optional[schemas.SearchProviderConnectionTestRequest] = None,
) -> object:
    request_data = test_in or schemas.SearchProviderConnectionTestRequest()
    config = _get_search_provider_for_use(db=db, config_id=config_id)
    return _run_search_provider_test(config=config, query=request_data.query)


@router.delete("/providers/{config_id}", response_model=schemas.SearchProviderConfig)
def delete_search_provider_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
) -> object:
    config = crud.search_provider_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Search provider config not found")
    return crud.search_provider_config.remove(db=db, id=config_id)


def _search_components(
    db: Session,
    *,
    query: str,
    limit: int,
) -> List[schemas.ComponentSearchResult]:
    terms = [term for term in query.split() if term.strip()]
    component_query = db.query(models.Component).options(
        joinedload(models.Component.tags),
        joinedload(models.Component.inventory)
        .joinedload(models.Inventory.sub_box)
        .joinedload(models.SubBox.box),
    )
    for term in terms:
        pattern = f"%{term}%"
        component_query = component_query.filter(
            or_(
                models.Component.name.ilike(pattern),
                models.Component.description.ilike(pattern),
                cast(models.Component.attributes, String).ilike(pattern),
                models.Component.tags.any(models.Tag.name.ilike(pattern)),
                models.Component.inventory.any(
                    models.Inventory.notes.ilike(pattern),
                ),
                models.Component.inventory.any(
                    models.Inventory.sub_box.has(
                        or_(
                            models.SubBox.readable_id.ilike(pattern),
                            models.SubBox.position_identifier.ilike(pattern),
                            models.SubBox.box.has(
                                or_(
                                    models.Box.readable_id.ilike(pattern),
                                    models.Box.name.ilike(pattern),
                                )
                            ),
                        )
                    )
                ),
            )
        )
    components = component_query.order_by(models.Component.id.desc()).limit(limit).all()
    return [_serialize_component_result(component) for component in components]


@router.get("/", response_model=List[schemas.ComponentSearchResult])
def keyword_search(
    db: Session = Depends(deps.get_db),
    q: str = Query("", min_length=0, max_length=200),
    limit: int = Query(50, ge=1, le=100),
) -> object:
    return _search_components(db=db, query=q, limit=limit)


@router.post("/semantic", response_model=schemas.SemanticSearchResponse)
def semantic_search(
    *,
    db: Session = Depends(deps.get_db),
    search_in: schemas.SemanticSearchRequest,
) -> object:
    if search_in.use_llm:
        return _semantic_search_with_llm(db=db, search_in=search_in)

    results = _search_components(
        db=db,
        query=search_in.query,
        limit=search_in.limit,
    )
    return schemas.SemanticSearchResponse(
        query=search_in.query,
        parsed_query={
            "keywords": [term for term in search_in.query.split() if term.strip()],
            "llm_used": False,
        },
        results=results,
    )


def _semantic_search_with_llm(
    *,
    db: Session,
    search_in: schemas.SemanticSearchRequest,
) -> schemas.SemanticSearchResponse:
    fallback_results = _search_components(
        db=db,
        query=search_in.query,
        limit=search_in.limit,
    )
    config = crud.vlm_provider_config.get_default(db=db)
    if not config:
        return schemas.SemanticSearchResponse(
            query=search_in.query,
            parsed_query={
                "llm_used": False,
                "llm_error": "Default VLM config not found",
            },
            results=fallback_results,
        )

    candidates = _search_components(db=db, query="", limit=200)
    prompt = _build_semantic_search_prompt(
        query=search_in.query,
        candidates=candidates,
        limit=search_in.limit,
    )
    try:
        response, _latency_ms = vlm_client.request_chat_completion(
            config=config,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
    except vlm_client.VlmClientError as exc:
        return schemas.SemanticSearchResponse(
            query=search_in.query,
            parsed_query={"llm_used": False, "llm_error": exc.message},
            results=fallback_results,
        )

    raw_text = vlm_client.extract_message_text(response)
    parsed = vlm_client.extract_json_object(raw_text) or {}
    component_ids = parsed.get("component_ids") or []
    if not isinstance(component_ids, list):
        component_ids = []

    results_by_id = {item.component_id: item for item in candidates}
    parsed_component_ids = []
    for component_id in component_ids:
        try:
            parsed_component_ids.append(int(component_id))
        except (TypeError, ValueError):
            continue

    llm_results = [
        results_by_id[component_id]
        for component_id in parsed_component_ids
        if component_id in results_by_id
    ][:search_in.limit]
    return schemas.SemanticSearchResponse(
        query=search_in.query,
        parsed_query={
            "llm_used": True,
            "raw": parsed,
            "raw_text": raw_text,
        },
        results=llm_results or fallback_results,
    )


def _build_semantic_search_prompt(
    *,
    query: str,
    candidates: List[schemas.ComponentSearchResult],
    limit: int,
) -> str:
    candidate_payload = [
        candidate.model_dump(mode="json")
        for candidate in candidates
    ]
    return (
        "你是个人电子元器件库的选型搜索助手。"
        "用户会用自然语言描述需求，请只从候选库存中选择最合适的已有元器件。"
        "不要推荐候选列表之外的器件。\n"
        "请只返回 JSON 对象，格式为："
        '{"keywords": ["关键词"], "component_ids": [1, 2], '
        '"reason": "简短理由"}\n\n'
        f"用户需求：{query}\n"
        f"最多返回 {limit} 个。\n"
        f"候选库存：{json.dumps(candidate_payload, ensure_ascii=False)}"
    )


@router.post(
    "/recommend_locations",
    response_model=schemas.LocationRecommendationResponse,
)
def recommend_locations(
    *,
    db: Session = Depends(deps.get_db),
    recommendation_in: schemas.LocationRecommendationRequest,
) -> object:
    occupied_sub_box_ids = {
        row[0]
        for row in db.query(models.Inventory.sub_box_id).distinct().all()
    }
    query = db.query(models.SubBox).options(
        joinedload(models.SubBox.box).joinedload(models.Box.template),
    )
    if recommendation_in.preferred_box_id is not None:
        query = query.filter(models.SubBox.box_id == recommendation_in.preferred_box_id)

    empty_sub_boxes = [
        sub_box
        for sub_box in query.order_by(
            models.SubBox.box_id,
            models.SubBox.position_identifier,
        ).all()
        if sub_box.id not in occupied_sub_box_ids
    ]
    ai_analysis = _analyze_location_recommendation_with_llm(
        db=db,
        recommendation_in=recommendation_in,
        candidates=empty_sub_boxes,
    )
    ai_reasons = _ai_slot_reasons(ai_analysis)
    ranked_sub_boxes = sorted(
        empty_sub_boxes,
        key=lambda sub_box: _recommendation_sort_key(
            db=db,
            sub_box=sub_box,
            recommendation_in=recommendation_in,
            ai_analysis=ai_analysis,
        ),
    )
    recommendations: List[schemas.LocationRecommendation] = []
    for sub_box in ranked_sub_boxes[:recommendation_in.limit]:
        nearby_components = _nearby_component_names(db=db, sub_box=sub_box)
        matched_components = _matched_nearby_component_names(
            db=db,
            sub_box=sub_box,
            recommendation_in=recommendation_in,
            ai_analysis=ai_analysis,
        )
        reason = ai_reasons.get(sub_box.id) or "该子格为空"
        if sub_box.id in ai_reasons:
            reason = f"AI 分析：{reason}"
        elif matched_components:
            reason = f"该子格为空，同盒已有相近器件：{', '.join(matched_components[:3])}"
        elif nearby_components:
            reason = f"该子格为空，同盒已有器件：{', '.join(nearby_components[:3])}"
        recommendations.append(
            schemas.LocationRecommendation(
                sub_box_id=sub_box.id,
                sub_box_readable_id=sub_box.readable_id,
                box_id=sub_box.box.id,
                box_readable_id=sub_box.box.readable_id,
                box_name=sub_box.box.name,
                position_identifier=sub_box.position_identifier,
                reason=reason,
                nearby_components=nearby_components,
            )
        )

    return schemas.LocationRecommendationResponse(
        recommendations=recommendations,
        analysis_used=bool(ai_analysis.get("llm_used")),
        analysis_note=ai_analysis.get("analysis_note"),
    )


def _recommendation_sort_key(
    *,
    db: Session,
    sub_box: models.SubBox,
    recommendation_in: schemas.LocationRecommendationRequest,
    ai_analysis: Dict[str, Any],
) -> tuple[int, int, str, tuple[Any, ...]]:
    score = _recommendation_score(
        db=db,
        sub_box=sub_box,
        recommendation_in=recommendation_in,
        ai_analysis=ai_analysis,
    )
    return (
        -score,
        sub_box.box_id,
        sub_box.box.readable_id if sub_box.box else "",
        _position_sort_key(sub_box.position_identifier),
    )


def _recommendation_score(
    *,
    db: Session,
    sub_box: models.SubBox,
    recommendation_in: schemas.LocationRecommendationRequest,
    ai_analysis: Dict[str, Any],
) -> int:
    terms = _recommendation_terms(recommendation_in, ai_analysis=ai_analysis)
    if not terms:
        return 0

    score = 0
    ai_order = _ai_slot_order(ai_analysis)
    if sub_box.id in ai_order:
        score += 1000 - ai_order[sub_box.id]

    preferred_box_ids = _int_set(ai_analysis.get("preferred_box_ids"))
    preferred_box_names = {
        str(item).lower()
        for item in ai_analysis.get("preferred_box_readable_ids", [])
        if str(item).strip()
    }
    if sub_box.box_id in preferred_box_ids:
        score += 40
    if sub_box.box and sub_box.box.readable_id.lower() in preferred_box_names:
        score += 40

    box_text = " ".join(
        [
            sub_box.box.readable_id if sub_box.box else "",
            sub_box.box.name if sub_box.box and sub_box.box.name else "",
        ]
    ).lower()
    score += sum(2 for term in terms if term in box_text)

    preferred_names = {
        str(item).lower()
        for item in ai_analysis.get("preferred_nearby_component_names", [])
        if str(item).strip()
    }
    for component in _nearby_components(db=db, sub_box=sub_box):
        haystack = _component_haystack(component)
        matched_terms = sum(1 for term in terms if term in haystack)
        if matched_terms:
            score += 5 + matched_terms
        if component.name and component.name.lower() in preferred_names:
            score += 30
    return score


def _recommendation_terms(
    recommendation_in: schemas.LocationRecommendationRequest,
    *,
    ai_analysis: Optional[Dict[str, Any]] = None,
) -> List[str]:
    raw_text = " ".join(
        [recommendation_in.text or "", " ".join(recommendation_in.tag_names)]
    )
    raw_terms = [
        term.lower()
        for term in re.split(r"[\s,，/;；]+", raw_text)
        if len(term.strip()) >= 2
    ]
    ai_terms: List[str] = []
    for key in ("keywords", "category_terms", "preferred_tags"):
        for item in (ai_analysis or {}).get(key, []):
            term = str(item).strip().lower()
            if len(term) >= 2:
                ai_terms.append(term)
    return list(dict.fromkeys(raw_terms + ai_terms))


def _matched_nearby_component_names(
    *,
    db: Session,
    sub_box: models.SubBox,
    recommendation_in: schemas.LocationRecommendationRequest,
    ai_analysis: Dict[str, Any],
) -> List[str]:
    terms = _recommendation_terms(recommendation_in, ai_analysis=ai_analysis)
    if not terms:
        return []
    matched_names: List[str] = []
    for component in _nearby_components(db=db, sub_box=sub_box):
        haystack = _component_haystack(component)
        if any(term in haystack for term in terms):
            matched_names.append(component.name)
    return matched_names


def _analyze_location_recommendation_with_llm(
    *,
    db: Session,
    recommendation_in: schemas.LocationRecommendationRequest,
    candidates: List[models.SubBox],
) -> Dict[str, Any]:
    if not candidates or not (recommendation_in.text or recommendation_in.tag_names):
        return {"llm_used": False}

    config = crud.vlm_provider_config.get_default(db=db)
    if not config:
        return {"llm_used": False, "analysis_note": "Default VLM config not found"}

    prompt = _build_location_recommendation_prompt(
        recommendation_in=recommendation_in,
        candidates=candidates[:120],
        db=db,
    )
    try:
        response, _latency_ms = vlm_client.request_chat_completion(
            config=config,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
        )
    except vlm_client.VlmClientError as exc:
        return {"llm_used": False, "analysis_note": exc.message}

    raw_text = vlm_client.extract_message_text(response)
    parsed = vlm_client.extract_json_object(raw_text) or {}
    if not isinstance(parsed, dict):
        parsed = {}
    parsed["llm_used"] = True
    parsed["raw_text"] = raw_text
    return parsed


def _build_location_recommendation_prompt(
    *,
    recommendation_in: schemas.LocationRecommendationRequest,
    candidates: List[models.SubBox],
    db: Session,
) -> str:
    candidate_payload = []
    for sub_box in candidates:
        nearby_components = []
        for component in _nearby_components(db=db, sub_box=sub_box):
            nearby_components.append(
                {
                    "name": component.name,
                    "tags": [tag.name for tag in component.tags],
                    "attributes": component.attributes or {},
                }
            )
        candidate_payload.append(
            {
                "sub_box_id": sub_box.id,
                "sub_box_readable_id": sub_box.readable_id,
                "box_id": sub_box.box_id,
                "box_readable_id": sub_box.box.readable_id if sub_box.box else None,
                "box_name": sub_box.box.name if sub_box.box else None,
                "position_identifier": sub_box.position_identifier,
                "nearby_components": nearby_components,
            }
        )

    return (
        "你是个人电子元器件库的入库位置规划助手。"
        "请分析新器件文本和标签，把新器件推荐到同类别元件旁边的空位，"
        "不要只是选择第一个空位。只能从候选空位中选择。\n"
        "请只返回 JSON 对象，格式为："
        '{"keywords": ["关键词"], "category_terms": ["类别"], '
        '"preferred_box_ids": [1], "preferred_box_readable_ids": ["BOX-0001"], '
        '"preferred_nearby_component_names": ["AHT20"], '
        '"recommendations": [{"sub_box_id": 1, "reason": "同盒已有温湿度传感器"}], '
        '"analysis_note": "简短分析"}\n\n'
        f"新器件文本：{recommendation_in.text or ''}\n"
        f"新器件标签：{json.dumps(recommendation_in.tag_names, ensure_ascii=False)}\n"
        f"候选空位：{json.dumps(candidate_payload, ensure_ascii=False)}"
    )


def _ai_slot_order(ai_analysis: Dict[str, Any]) -> Dict[int, int]:
    order: Dict[int, int] = {}
    for index, item in enumerate(ai_analysis.get("recommendations", [])):
        if not isinstance(item, dict):
            continue
        sub_box_id = _safe_int(item.get("sub_box_id"))
        if sub_box_id is not None and sub_box_id not in order:
            order[sub_box_id] = index
    return order


def _ai_slot_reasons(ai_analysis: Dict[str, Any]) -> Dict[int, str]:
    reasons: Dict[int, str] = {}
    for item in ai_analysis.get("recommendations", []):
        if not isinstance(item, dict):
            continue
        sub_box_id = _safe_int(item.get("sub_box_id"))
        reason = str(item.get("reason") or "").strip()
        if sub_box_id is not None and reason:
            reasons[sub_box_id] = reason
    return reasons


def _int_set(values: Any) -> set[int]:
    if not isinstance(values, list):
        return set()
    return {value for value in (_safe_int(item) for item in values) if value is not None}


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _nearby_component_names(db: Session, *, sub_box: models.SubBox) -> List[str]:
    return [
        component.name
        for component in _nearby_components(db=db, sub_box=sub_box)
    ]


def _nearby_components(db: Session, *, sub_box: models.SubBox) -> List[models.Component]:
    inventory_items = (
        db.query(models.Inventory)
        .join(models.SubBox)
        .join(models.Component)
        .filter(models.SubBox.box_id == sub_box.box_id)
        .options(
            joinedload(models.Inventory.component).joinedload(models.Component.tags),
        )
        .limit(5)
        .all()
    )
    return [item.component for item in inventory_items if item.component]


def _position_sort_key(value: str) -> tuple[Any, ...]:
    text = str(value or "")
    grid_match = re.fullmatch(r"R(\d+)C(\d+)", text, flags=re.IGNORECASE)
    if grid_match:
        return ("grid", int(grid_match.group(1)), int(grid_match.group(2)))
    column_match = re.fullmatch(r"([A-Za-z]+)(\d+)", text)
    if column_match:
        return ("column", column_match.group(1).upper(), int(column_match.group(2)))
    return ("text", text)
