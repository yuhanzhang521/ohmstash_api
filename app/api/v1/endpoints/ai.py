import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.api.v1.endpoints.boxes import create_box_with_retry
from app.database import SessionLocal
from app.models.search_provider_config import (
    SearchProviderConfig as SearchProviderConfigModel,
)
from app.models.vlm_provider_config import VlmProviderConfig as VlmProviderConfigModel
from app.services import auth
from app.services import (
    recognition_prompt,
    recognition_text_cleanup,
    vlm_client,
    vlm_config_service,
    web_search,
)
from app.services.component_naming import (
    normalize_component_names_in_parsed_result,
    normalize_recognized_cell_payload,
)
from app.services.component_display import choose_component_display_attribute
from app.services.image_upload import normalize_upload_image, read_limited_upload

router = APIRouter()
logger = logging.getLogger(__name__)

VERIFICATION_CHUNK_SIZE = 6
SEARCH_RESULTS_PER_ITEM = 5
SINGLE_IMAGE_RECOGNITION_MAX_TOKENS = 1200
BOX_RECOGNITION_MIN_MAX_TOKENS = 3000
BOX_RECOGNITION_MAX_TOKENS = 10000
BOX_RECOGNITION_TOKENS_PER_CELL = 220
BOX_LAYOUT_RECOGNITION_MAX_TOKENS = 10000
RECOGNITION_SESSION_HISTORY_LIMIT = 50
RECOGNITION_SESSION_MODES = {
    "single_image",
    "existing_box",
    "new_box",
    "auto_template_box",
}


def _get_search_provider_config_for_use(
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


def _build_search_provider_settings(
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


def _recognize_image_with_config(
    *,
    config: VlmProviderConfigModel,
    filename: str,
    content_type: str,
    content: bytes,
    prompt: str,
    max_tokens: Optional[int] = None,
) -> schemas.ImageRecognitionResponse:
    data_url = vlm_client.build_image_data_url(content, content_type)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    try:
        response, latency_ms = vlm_client.request_chat_completion(
            config=config,
            messages=messages,
            max_tokens=max_tokens,
        )
    except vlm_client.VlmClientError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": exc.message,
                "status_code": exc.status_code,
                "response_body": exc.response_body,
            },
        ) from exc

    raw_text = vlm_client.extract_message_text(response)
    parsed_result = normalize_component_names_in_parsed_result(
        vlm_client.extract_json_object(raw_text),
    )
    return schemas.ImageRecognitionResponse(
        config_id=config.id,
        filename=filename,
        content_type=content_type,
        prompt=prompt,
        raw_text=raw_text,
        parsed_result=parsed_result,
        latency_ms=latency_ms,
    )


def _get_or_create_tag_ids(db: Session, *, tag_names: List[str]) -> List[int]:
    tag_ids: List[int] = []
    for raw_name in tag_names:
        tag_name = raw_name.strip()
        if not tag_name:
            continue
        tag = crud.tag.get_by_name(db=db, name=tag_name)
        if not tag:
            tag = crud.tag.create(
                db=db,
                obj_in=schemas.TagCreate(name=tag_name, attribute_definitions=[]),
            )
        tag_ids.append(tag.id)
    return tag_ids


def _sync_component_display_attribute(
    *,
    db: Session,
    component: models.Component,
    cell: schemas.RecognizedCell,
) -> None:
    if component.display_attribute:
        return
    display_attribute = choose_component_display_attribute(
        component.attributes or cell.attributes,
        cell.display_attribute,
    )
    if not display_attribute:
        return
    component.display_attribute = display_attribute
    db.add(component)
    db.commit()
    db.refresh(component)


def _persist_box_recognition_cells(
    *,
    db: Session,
    box_id: int,
    cells: List[schemas.RecognizedCell],
    overwrite_existing: bool,
) -> schemas.ConfirmBoxRecognitionResult:
    created_components = 0
    created_inventory_items = 0
    updated_inventory_items = 0
    skipped_empty_cells = 0
    skipped_missing_sub_boxes: List[str] = []
    cleared_sub_box_ids: set[int] = set()

    for cell in cells:
        sub_box = (
            db.query(models.SubBox)
            .filter(
                models.SubBox.box_id == box_id,
                models.SubBox.position_identifier == cell.position_identifier,
            )
            .first()
        )
        if not sub_box:
            skipped_missing_sub_boxes.append(cell.position_identifier)
            continue

        if overwrite_existing and sub_box.id not in cleared_sub_box_ids:
            db.query(models.Inventory).filter(
                models.Inventory.sub_box_id == sub_box.id,
            ).delete()
            db.commit()
            cleared_sub_box_ids.add(sub_box.id)

        if cell.is_empty or not cell.name:
            skipped_empty_cells += 1
            continue

        sanitized_notes = _sanitize_recognition_notes(cell.notes)

        tag_ids = _get_or_create_tag_ids(db=db, tag_names=cell.tags)
        component = (
            db.query(models.Component)
            .filter(models.Component.name == cell.name)
            .first()
        )
        if not component:
            component = crud.component.create(
                db=db,
                obj_in=schemas.ComponentCreate(
                    name=cell.name,
                    description=sanitized_notes,
                    attributes=cell.attributes,
                    display_attribute=cell.display_attribute,
                    tag_ids=tag_ids,
                ),
            )
            created_components += 1
        else:
            _sync_component_display_attribute(
                db=db,
                component=component,
                cell=cell,
            )

        inventory_item = crud.inventory.get_by_sub_box_and_component(
            db,
            sub_box_id=sub_box.id,
            component_id=component.id,
        )
        inventory_data = schemas.InventoryCreate(
            sub_box_id=sub_box.id,
            component_id=component.id,
            stock_mode=cell.stock_mode,
            quantity_exact=cell.quantity_exact,
            quantity_fuzzy=cell.quantity_fuzzy,
            notes=sanitized_notes,
        )
        if inventory_item:
            crud.inventory.update(
                db=db,
                db_obj=inventory_item,
                obj_in=schemas.InventoryUpdate(
                    stock_mode=inventory_data.stock_mode,
                    quantity_exact=inventory_data.quantity_exact,
                    quantity_fuzzy=inventory_data.quantity_fuzzy,
                    notes=inventory_data.notes,
                ),
            )
            updated_inventory_items += 1
        else:
            crud.inventory.create(db=db, obj_in=inventory_data)
            created_inventory_items += 1

    return schemas.ConfirmBoxRecognitionResult(
        created_components=created_components,
        created_inventory_items=created_inventory_items,
        updated_inventory_items=updated_inventory_items,
        skipped_empty_cells=skipped_empty_cells,
        skipped_missing_sub_boxes=skipped_missing_sub_boxes,
        box_id=box_id,
    )


def _normalize_search_value(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _append_unique(values: List[str], value: str) -> None:
    clean_value = _normalize_search_value(value)
    if clean_value and clean_value not in values:
        values.append(clean_value)


def _build_component_web_queries(
    item: schemas.RecognizedCell,
    *,
    additional_prompt: str = "",
) -> List[str]:
    names: List[str] = []
    _append_unique(names, item.name or "")
    for key, value in (item.attributes or {}).items():
        if key in {
            "型号",
            "料号",
            "订货号",
            "Part Number",
            "Manufacturer Part Number",
            "MPN",
        }:
            _append_unique(names, str(value))

    queries: List[str] = []
    for name in names:
        _append_unique(queries, f"{name} datasheet")
        _append_unique(queries, name)

    manufacturer = _normalize_search_value(
        (item.attributes or {}).get("Manufacturer")
        or (item.attributes or {}).get("制造商")
        or "",
    )
    if manufacturer and names:
        _append_unique(queries, f"{names[0]} {manufacturer} datasheet")

    if additional_prompt:
        for name in names[:1]:
            _append_unique(queries, f"{name} {additional_prompt}")

    return queries


def _extract_verification_warning(value: Any) -> Optional[str]:
    return recognition_text_cleanup.extract_verification_warning(value)


def _clean_verification_notes(value: Any) -> Optional[str]:
    return recognition_text_cleanup.clean_verification_notes(value)


def _sanitize_recognition_notes(value: Any) -> Optional[str]:
    text = recognition_text_cleanup.strip_photo_meta_phrases(value)
    return text or None


def _extract_corrected_component_name(
    value: Any,
    *,
    original_name: Optional[str] = None,
) -> Optional[str]:
    return recognition_text_cleanup.extract_corrected_component_name(
        value,
        original_name=original_name,
    )


def _clean_verified_attributes(
    attributes: Any,
) -> Tuple[Dict[str, Any], List[str]]:
    if not isinstance(attributes, dict):
        return {}, []

    cleaned_attributes: Dict[str, Any] = {}
    warnings: List[str] = []
    for key, value in attributes.items():
        if not isinstance(value, str):
            cleaned_attributes[key] = value
            continue

        clean_value = value
        value_warnings: List[str] = []
        for pattern in recognition_text_cleanup.ATTRIBUTE_UNCERTAINTY_PATTERNS:
            value_warnings.extend(match.group(0) for match in pattern.finditer(clean_value))
            clean_value = pattern.sub("", clean_value)
        clean_value = clean_value.strip("。；;，, \n\t")
        cleaned_attributes[key] = clean_value or value
        for warning in value_warnings:
            warning_text = _normalize_search_value(warning).strip("（）()")
            if warning_text:
                warnings.append(f"{key}: {warning_text}")
    return cleaned_attributes, warnings


def _merge_warning_parts(*parts: Optional[str]) -> Optional[str]:
    warnings: List[str] = []
    for part in parts:
        warning = _normalize_search_value(part)
        if warning and warning not in warnings:
            warnings.append(warning)
    return "；".join(warnings) if warnings else None


def _build_verification_prompt(
    *,
    items: List[schemas.RecognizedCell],
    web_contexts: List[Dict[str, Any]],
    additional_prompt: str = "",
) -> str:
    payload = [item.model_dump(mode="json") for item in items]
    extra_instruction = (
        f"\n用户补充描述：{additional_prompt}\n"
        if additional_prompt
        else ""
    )
    return (
        "你是电子元器件资料核对助手。请根据联网搜索摘要核对每个器件。\n"
        "重点修正芯片型号、完整订货号、封装、功能、供电/输入输出参数等。"
        "注意标签上换行的芯片型号可能被误拆，例如 RGER 这类后缀常常是完整型号的一部分，"
        "不要把它草率当作封装。\n"
        "如果搜索摘要不足以确认某个字段，请保留原值，不要编造。\n"
        "如果搜索结果明显指向另一个标准型号，说明原始识别可能有误，请把 name 和 attributes.型号 更新为可确认的标准型号；"
        "例如原始 IPS5450 但资料主要指向 TPS5450 时，应改为 TPS5450。\n"
        f"{recognition_prompt.COMPONENT_TYPE_RULE_TEXT}\n"
        f"{recognition_prompt.COMPONENT_NAME_RULE_TEXT}\n"
        "display_attribute 必须保留或更新为 attributes 中最适合缩略显示的属性名，"
        "阻容感优先使用阻值、容值或电感值，芯片类通常使用型号。\n"
        "不要把“未能从摘要唯一确认”“不同厂商版本不一致”“待确认”等不确定性说明写进 attributes 的值里，"
        "这些说明只能写入 verification_warning。\n"
        "notes 只写有用的器件补充信息，不要写“搜索摘要确认”“联网确认”等流程性文字。\n"
        "如果有型号纠错，notes 只写器件资料摘要；把“搜索结果指向 X，原始型号 Y 疑似识别/抄写误差”写入 verification_warning。\n"
        "如果没有检索到足够资料，请把原因写入 verification_warning，notes 保持为空或只保留器件说明。\n"
        "请只返回 JSON 对象，格式为：\n"
        '{"items": [{"position_identifier": "R1C1", "is_empty": false, '
        '"component_type": "IC", "name_parts": {"model": "BQ24195RGER"}, '
        '"name": "BQ24195RGER", "tags": ["IC", "IC/电源芯片"], '
        '"attributes": {"型号": "BQ24195RGER", "封装": "VQFN-24", '
        '"功能": "单节锂电池充电管理"}, "confidence": 0.9, '
        '"display_attribute": "型号", '
        '"notes": "支持单节锂电池充电管理", '
        '"verification_warning": null}]}\n\n'
        f"{extra_instruction}"
        f"待核对项目：{json.dumps(payload, ensure_ascii=False)}\n\n"
        f"联网搜索摘要：{json.dumps(web_contexts, ensure_ascii=False)}"
    )


def _parse_verified_items(
    *,
    raw_text: str,
    fallback_items: List[schemas.RecognizedCell],
) -> List[schemas.RecognizedCell]:
    parsed = vlm_client.extract_json_object(raw_text) or {}
    raw_items = parsed.get("items") or parsed.get("verified_items") or []
    if not isinstance(raw_items, list):
        return fallback_items

    raw_by_position: Dict[str, Dict[str, Any]] = {}
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        position = raw_item.get("position_identifier")
        if position:
            raw_by_position[str(position)] = raw_item

    verified_items: List[schemas.RecognizedCell] = []
    for base_item in fallback_items:
        raw_item = raw_by_position.get(base_item.position_identifier) or {}
        merged_data = base_item.model_dump(mode="json")
        merged_data.update(raw_item)
        warning = (
            merged_data.get("verification_warning")
            or _extract_verification_warning(merged_data.get("notes"))
        )
        cleaned_attributes, attribute_warnings = _clean_verified_attributes(
            merged_data.get("attributes")
        )
        merged_data["attributes"] = cleaned_attributes
        warning = _merge_warning_parts(
            warning,
            "；".join(attribute_warnings) if attribute_warnings else None,
        )
        corrected_name = _extract_corrected_component_name(
            warning or merged_data.get("notes"),
            original_name=base_item.name,
        )
        if corrected_name:
            merged_data["name"] = corrected_name
            if isinstance(merged_data.get("attributes"), dict):
                merged_data["attributes"]["型号"] = corrected_name
        merged_data["notes"] = _clean_verification_notes(merged_data.get("notes"))
        merged_data["verification_warning"] = warning
        merged_data = normalize_recognized_cell_payload(merged_data)
        try:
            verified_items.append(schemas.RecognizedCell(**merged_data))
        except ValueError:
            verified_items.append(base_item)

    return verified_items or fallback_items


def _chunk_list(
    values: List[Any],
    chunk_size: int,
) -> List[List[Any]]:
    return [
        values[index : index + chunk_size]
        for index in range(0, len(values), chunk_size)
    ]


def _verification_max_tokens(item_count: int) -> int:
    return min(8000, max(1800, item_count * 520))


def _box_recognition_max_tokens(cell_count: int) -> int:
    return min(
        BOX_RECOGNITION_MAX_TOKENS,
        max(
            BOX_RECOGNITION_MIN_MAX_TOKENS,
            cell_count * BOX_RECOGNITION_TOKENS_PER_CELL,
        ),
    )


def _count_layout_cells(layout_type: str, layout_definition: Any) -> int:
    if layout_type == "grid" and isinstance(layout_definition, dict):
        rows = max(int(layout_definition.get("rows") or 0), 0)
        cols = max(int(layout_definition.get("cols") or 0), 0)
        return rows * cols

    if isinstance(layout_definition, dict):
        cells = layout_definition.get("cells", [])
    else:
        cells = layout_definition
    return len(cells) if isinstance(cells, list) else 0


def _format_web_search_warning(errors: List[str]) -> str:
    if not errors:
        return "未检索到有效摘要，暂保留原标注"
    unique_errors: List[str] = []
    for error in errors:
        clean_error = _normalize_search_value(error)
        if clean_error and clean_error not in unique_errors:
            unique_errors.append(clean_error)
    summary = "；".join(unique_errors[:2])
    if len(unique_errors) > 2:
        summary = f"{summary}；另有 {len(unique_errors) - 2} 个错误"
    return f"联网搜索失败：{summary[:220]}"


def _is_search_throttle_error(errors: List[str]) -> bool:
    return any("HTTP 202" in error or "HTTP 429" in error for error in errors)


def _build_web_contexts(
    *,
    items: List[schemas.RecognizedCell],
    provider_settings: Optional[web_search.SearchProviderSettings],
    additional_prompt: str = "",
) -> tuple[List[Dict[str, Any]], bool]:
    web_contexts: List[Dict[str, Any]] = []
    web_used = False
    provider_throttled = False
    logger.info("Component web verification search started items=%s", len(items))
    for item in items:
        queries = _build_component_web_queries(
            item,
            additional_prompt=additional_prompt,
        )
        results: List[Dict[str, str]] = []
        errors: List[str] = []
        if provider_throttled:
            web_contexts.append(
                {
                    "position_identifier": item.position_identifier,
                    "queries": queries,
                    "query": queries[0] if queries else "",
                    "results": [],
                    "errors": ["Search provider throttled previous requests"],
                    "verification_warning": "联网搜索服务触发限流，已跳过后续查询",
                }
            )
            continue
        logger.info(
            "Component web search item position=%s name=%r queries=%s",
            item.position_identifier,
            item.name,
            queries,
        )
        for query in queries:
            try:
                results = web_search.fetch_search_snippets(
                    query,
                    limit=SEARCH_RESULTS_PER_ITEM,
                    provider_settings=provider_settings,
                )
            except web_search.SearchProviderError as exc:
                errors.extend(exc.errors)
                if _is_search_throttle_error(exc.errors):
                    provider_throttled = True
                logger.warning(
                    "Component web search provider error position=%s query=%r error=%s",
                    item.position_identifier,
                    query,
                    exc,
                )
                if provider_throttled:
                    break
                continue
            except Exception as exc:
                errors.append(str(exc))
                logger.exception(
                    "Component web search unexpected error position=%s query=%r",
                    item.position_identifier,
                    query,
                )
                continue
            if results:
                web_used = True
                logger.info(
                    "Component web search found results position=%s query=%r results=%s",
                    item.position_identifier,
                    query,
                    len(results),
                )
                break
        context: Dict[str, Any] = {
            "position_identifier": item.position_identifier,
            "queries": queries,
            "query": queries[0] if queries else "",
            "results": results,
        }
        if errors and not results:
            context["errors"] = errors
        if queries and not results:
            context["verification_warning"] = _format_web_search_warning(errors)
        if not queries:
            context["verification_warning"] = "缺少可检索的器件型号，暂保留原标注"
        web_contexts.append(context)

    logger.info(
        "Component web verification search finished items=%s web_used=%s",
        len(items),
        web_used,
    )
    return web_contexts, web_used


def _apply_context_warnings(
    *,
    items: List[schemas.RecognizedCell],
    web_contexts: List[Dict[str, Any]],
) -> List[schemas.RecognizedCell]:
    warning_by_position = {
        context.get("position_identifier"): context.get("verification_warning")
        for context in web_contexts
        if context.get("verification_warning")
    }
    cleaned_items: List[schemas.RecognizedCell] = []
    for item in items:
        data = item.model_dump(mode="json")
        data["notes"] = _clean_verification_notes(data.get("notes"))
        cleaned_attributes, attribute_warnings = _clean_verified_attributes(
            data.get("attributes")
        )
        data["attributes"] = cleaned_attributes
        data["verification_warning"] = _merge_warning_parts(
            data.get("verification_warning")
            or warning_by_position.get(item.position_identifier)
            or _extract_verification_warning(item.notes),
            "；".join(attribute_warnings) if attribute_warnings else None,
        )
        corrected_name = _extract_corrected_component_name(
            data.get("verification_warning") or item.notes,
            original_name=item.name,
        )
        if corrected_name:
            data["name"] = corrected_name
            data["attributes"]["型号"] = corrected_name
        data = normalize_recognized_cell_payload(data)
        cleaned_items.append(schemas.RecognizedCell(**data))
    return cleaned_items


def _verify_component_items(
    *,
    db: Session,
    verify_in: schemas.ComponentVerificationRequest,
) -> schemas.ComponentVerificationResponse:
    config = vlm_config_service.get_config_for_use(db=db, config_id=verify_in.config_id)
    logger.info(
        "Component verification started config_id=%s items=%s use_web=%s",
        config.id,
        len(verify_in.items),
        verify_in.use_web,
    )
    web_contexts: List[Dict[str, Any]] = []
    web_used = False
    search_provider_config = _get_search_provider_config_for_use(
        db=db,
        config_id=verify_in.search_provider_config_id,
    )
    search_provider_settings = _build_search_provider_settings(search_provider_config)

    if verify_in.use_web:
        web_contexts, web_used = _build_web_contexts(
            items=verify_in.items,
            provider_settings=search_provider_settings,
            additional_prompt=verify_in.additional_prompt,
        )

    context_by_position = {
        context.get("position_identifier"): context
        for context in web_contexts
    }
    verified_items: List[schemas.RecognizedCell] = []
    raw_text_parts: List[str] = []
    total_latency_ms = 0
    item_chunks = _chunk_list(verify_in.items, VERIFICATION_CHUNK_SIZE)
    for chunk_index, chunk_items in enumerate(item_chunks, start=1):
        chunk_contexts = [
            context_by_position[item.position_identifier]
            for item in chunk_items
            if item.position_identifier in context_by_position
        ]
        prompt = _build_verification_prompt(
            items=chunk_items,
            web_contexts=chunk_contexts,
            additional_prompt=verify_in.additional_prompt,
        )
        try:
            logger.info(
                "Component verification VLM chunk started chunk=%s/%s items=%s contexts=%s",
                chunk_index,
                len(item_chunks),
                len(chunk_items),
                len(chunk_contexts),
            )
            response, latency_ms = vlm_client.request_chat_completion(
                config=config,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=_verification_max_tokens(len(chunk_items)),
            )
        except vlm_client.VlmClientError as exc:
            logger.warning(
                "Component verification VLM chunk failed chunk=%s/%s status=%s message=%s",
                chunk_index,
                len(item_chunks),
                exc.status_code,
                exc.message,
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "message": exc.message,
                    "status_code": exc.status_code,
                    "response_body": exc.response_body,
                },
            ) from exc

        raw_text = vlm_client.extract_message_text(response)
        raw_text_parts.append(raw_text)
        total_latency_ms += latency_ms
        logger.info(
            "Component verification VLM chunk finished chunk=%s/%s latency_ms=%s",
            chunk_index,
            len(item_chunks),
            latency_ms,
        )
        verified_items.extend(
            _parse_verified_items(
                raw_text=raw_text,
                fallback_items=chunk_items,
            )
        )

    verified_items = _apply_context_warnings(
        items=verified_items,
        web_contexts=web_contexts,
    )
    return schemas.ComponentVerificationResponse(
        config_id=config.id,
        verified_items=verified_items,
        raw_text="\n".join(raw_text_parts),
        latency_ms=total_latency_ms,
        web_used=web_used,
        web_contexts=web_contexts,
    )


@router.get("/vlm_config", response_model=schemas.VlmProviderConfig)
def read_default_vlm_config(db: Session = Depends(deps.get_db)) -> object:
    return vlm_config_service.get_required_default_config(db=db)


@router.put("/vlm_config", response_model=schemas.VlmProviderConfig)
def upsert_default_vlm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_in: schemas.VlmProviderConfigCreate,
) -> object:
    return vlm_config_service.upsert_default_config(db=db, config_in=config_in)


@router.post("/vlm_config/test", response_model=schemas.VlmConnectionTestResult)
def test_default_vlm_config(
    *,
    db: Session = Depends(deps.get_db),
    test_in: Optional[schemas.VlmConnectionTestRequest] = None,
) -> object:
    request_data = test_in or schemas.VlmConnectionTestRequest()
    config = (
        vlm_config_service.build_transient_config(request_data.config)
        if request_data.config
        else vlm_config_service.get_required_default_config(db=db)
    )
    return vlm_config_service.run_connection_test(config=config, prompt=request_data.prompt)


@router.post("/vlm_configs/", response_model=schemas.VlmProviderConfig)
def create_vlm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_in: schemas.VlmProviderConfigCreate,
) -> object:
    vlm_config_service.ensure_unique_config_name(db=db, name=config_in.name)
    return crud.vlm_provider_config.create(db=db, obj_in=config_in)


@router.get("/vlm_configs/", response_model=List[schemas.VlmProviderConfig])
def read_vlm_configs(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> object:
    return crud.vlm_provider_config.get_multi(db=db, skip=skip, limit=limit)


@router.get("/vlm_configs/default", response_model=schemas.VlmProviderConfig)
def read_default_vlm_config_from_collection(
    db: Session = Depends(deps.get_db),
) -> object:
    return vlm_config_service.get_required_default_config(db=db)


@router.post(
    "/vlm_configs/{config_id}/test",
    response_model=schemas.VlmConnectionTestResult,
)
def test_vlm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
    test_in: Optional[schemas.VlmConnectionTestRequest] = None,
) -> object:
    request_data = test_in or schemas.VlmConnectionTestRequest()
    config = vlm_config_service.get_config_for_use(db=db, config_id=config_id)
    return vlm_config_service.run_connection_test(config=config, prompt=request_data.prompt)


@router.get("/vlm_configs/{config_id}", response_model=schemas.VlmProviderConfig)
def read_vlm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
) -> object:
    config = crud.vlm_provider_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="VLM config not found")
    return config


@router.put("/vlm_configs/{config_id}", response_model=schemas.VlmProviderConfig)
def update_vlm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
    config_in: schemas.VlmProviderConfigUpdate,
) -> object:
    config = crud.vlm_provider_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="VLM config not found")
    if config_in.name:
        vlm_config_service.ensure_unique_config_name(
            db=db,
            name=config_in.name,
            current_config_id=config.id,
        )
    return crud.vlm_provider_config.update(db=db, db_obj=config, obj_in=config_in)


@router.post(
    "/vlm_configs/{config_id}/set_default",
    response_model=schemas.VlmProviderConfig,
)
def set_default_vlm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
) -> object:
    config = crud.vlm_provider_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="VLM config not found")
    return crud.vlm_provider_config.set_default(db=db, db_obj=config)


@router.delete("/vlm_configs/{config_id}", response_model=schemas.VlmProviderConfig)
def delete_vlm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
) -> object:
    config = crud.vlm_provider_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="VLM config not found")
    return crud.vlm_provider_config.remove(db=db, id=config_id)


def _validate_recognition_session_request(
    *,
    db: Session,
    mode: str,
    box_id: Optional[int],
    template_id: Optional[int],
    layout_type: str,
) -> None:
    if mode not in RECOGNITION_SESSION_MODES:
        raise HTTPException(status_code=400, detail="Unsupported recognition mode")
    if mode == "existing_box":
        if not box_id:
            raise HTTPException(status_code=400, detail="Box is required")
        if not crud.box.get(db=db, id=box_id):
            raise HTTPException(status_code=404, detail="Box not found")
    if mode == "new_box":
        if not template_id:
            raise HTTPException(status_code=400, detail="Box template is required")
        if not crud.box_template.get(db=db, id=template_id):
            raise HTTPException(status_code=404, detail="Box template not found")
    if mode == "auto_template_box" and layout_type not in {"grid", "irregular"}:
        raise HTTPException(status_code=400, detail="Unsupported layout type")


def _get_owned_recognition_session(
    *,
    db: Session,
    session_id: int,
    principal: auth.AuthPrincipal,
) -> models.RecognitionSession:
    recognition_session = (
        db.query(models.RecognitionSession)
        .filter(
            models.RecognitionSession.id == session_id,
            models.RecognitionSession.owner_kind == principal.kind,
            models.RecognitionSession.owner_id == principal.id,
        )
        .first()
    )
    if not recognition_session:
        raise HTTPException(status_code=404, detail="Recognition session not found")
    return recognition_session


def _build_recognition_session_prompt(
    *,
    db: Session,
    recognition_session: models.RecognitionSession,
) -> Tuple[str, int]:
    if recognition_session.mode == "single_image":
        return (
            recognition_prompt.build_component_recognition_prompt(
                db,
                additional_prompt=recognition_session.additional_prompt,
            ),
            SINGLE_IMAGE_RECOGNITION_MAX_TOKENS,
        )

    if recognition_session.mode == "existing_box":
        box = crud.box.get(db=db, id=recognition_session.box_id)
        if not box:
            raise HTTPException(status_code=404, detail="Box not found")
        return (
            recognition_prompt.build_box_recognition_prompt(
                db,
                box=box,
                additional_prompt=recognition_session.additional_prompt,
            ),
            _box_recognition_max_tokens(len(box.sub_boxes)),
        )

    if recognition_session.mode == "new_box":
        template = crud.box_template.get(db=db, id=recognition_session.template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Box template not found")
        return (
            recognition_prompt.build_new_box_recognition_prompt(
                db,
                template=template,
                additional_prompt=recognition_session.additional_prompt,
            ),
            _box_recognition_max_tokens(
                _count_layout_cells(
                    template.layout_type,
                    template.layout_definition,
                ),
            ),
        )

    return (
        recognition_prompt.build_box_template_recognition_prompt(
            db,
            layout_type=recognition_session.layout_type or "grid",
            additional_prompt=recognition_session.additional_prompt,
        ),
        BOX_LAYOUT_RECOGNITION_MAX_TOKENS,
    )


def _run_recognition_session(
    *,
    session_id: int,
    content: bytes,
    content_type: str,
) -> None:
    db = SessionLocal()
    try:
        _run_recognition_session_with_db(
            db=db,
            session_id=session_id,
            content=content,
            content_type=content_type,
        )
    finally:
        db.close()


def _run_recognition_session_with_db(
    *,
    db: Session,
    session_id: int,
    content: bytes,
    content_type: str,
) -> None:
    recognition_session = (
        db.query(models.RecognitionSession)
        .filter(models.RecognitionSession.id == session_id)
        .first()
    )
    if not recognition_session:
        return

    recognition_session.status = "running"
    recognition_session.error_message = None
    recognition_session.verification_error_message = None
    db.add(recognition_session)
    db.commit()

    try:
        config = vlm_config_service.get_config_for_use(
            db=db,
            config_id=recognition_session.config_id,
        )
        prompt, max_tokens = _build_recognition_session_prompt(
            db=db,
            recognition_session=recognition_session,
        )
        response = _recognize_image_with_config(
            config=config,
            filename=recognition_session.filename,
            content_type=content_type,
            content=content,
            prompt=prompt,
            max_tokens=max_tokens,
        )
        result_data = response.model_dump(mode="json")
        selected_items = _extract_default_verification_items(
            result_data.get("parsed_result"),
        )
        if selected_items:
            recognition_session.result = result_data
            recognition_session.verification_status = "running"
            db.add(recognition_session)
            db.commit()
            _apply_automatic_verification(
                db=db,
                recognition_session=recognition_session,
                result_data=result_data,
                selected_items=selected_items,
            )
        else:
            recognition_session.result = result_data
            recognition_session.verification_status = "skipped"

        recognition_session.status = "succeeded"
    except Exception as exc:
        recognition_session.status = "failed"
        recognition_session.error_message = _format_recognition_session_error(exc)
        if recognition_session.verification_status == "running":
            recognition_session.verification_status = "failed"
    finally:
        recognition_session.completed_at = datetime.now(timezone.utc)
        db.add(recognition_session)
        db.commit()


def _apply_automatic_verification(
    *,
    db: Session,
    recognition_session: models.RecognitionSession,
    result_data: Dict[str, Any],
    selected_items: List[schemas.RecognizedCell],
) -> None:
    try:
        verification_result = _verify_component_items(
            db=db,
            verify_in=schemas.ComponentVerificationRequest(
                items=selected_items,
                config_id=recognition_session.config_id,
                search_provider_config_id=(
                    recognition_session.search_provider_config_id
                ),
                use_web=True,
                additional_prompt=recognition_session.additional_prompt,
            ),
        )
    except Exception as exc:
        recognition_session.verification_status = "failed"
        recognition_session.verification_error_message = (
            _format_recognition_session_error(exc)
        )
        return

    result_data["parsed_result"] = _merge_verified_items_into_parsed_result(
        parsed_result=result_data.get("parsed_result"),
        verified_items=verification_result.verified_items,
    )
    recognition_session.result = result_data
    recognition_session.verification_result = verification_result.model_dump(
        mode="json",
    )
    recognition_session.verification_status = "succeeded"
    recognition_session.verification_error_message = None


def _extract_default_verification_items(
    parsed_result: Any,
) -> List[schemas.RecognizedCell]:
    if not isinstance(parsed_result, dict):
        return []

    raw_cells = parsed_result.get("cells")
    if not isinstance(raw_cells, list):
        raw_cells = [parsed_result]

    selected_items: List[schemas.RecognizedCell] = []
    for index, raw_cell in enumerate(raw_cells):
        if not isinstance(raw_cell, dict):
            continue
        cell_data = normalize_recognized_cell_payload(dict(raw_cell))
        cell_data.setdefault(
            "position_identifier",
            "单图" if len(raw_cells) == 1 else f"#{index + 1}",
        )
        try:
            cell = schemas.RecognizedCell(**cell_data)
        except ValueError:
            continue
        if _should_verify_recognized_cell(cell):
            selected_items.append(cell)
    return selected_items


def _should_verify_recognized_cell(cell: schemas.RecognizedCell) -> bool:
    if cell.is_empty or not cell.name:
        return False
    return cell.search_recommended is True


def _merge_verified_items_into_parsed_result(
    *,
    parsed_result: Any,
    verified_items: List[schemas.RecognizedCell],
) -> object:
    if not isinstance(parsed_result, dict):
        return parsed_result

    verified_by_position = {
        item.position_identifier: item.model_dump(mode="json")
        for item in verified_items
    }
    merged_result = dict(parsed_result)
    raw_cells = merged_result.get("cells")
    if isinstance(raw_cells, list):
        merged_cells: List[Any] = []
        for index, raw_cell in enumerate(raw_cells):
            if not isinstance(raw_cell, dict):
                merged_cells.append(raw_cell)
                continue
            position = raw_cell.get("position_identifier") or f"#{index + 1}"
            verified = verified_by_position.get(str(position))
            merged_cell = {**raw_cell, **verified} if verified else dict(raw_cell)
            merged_cells.append(normalize_recognized_cell_payload(merged_cell))
        merged_result["cells"] = merged_cells
        return normalize_component_names_in_parsed_result(merged_result)

    verified = verified_items[0].model_dump(mode="json") if verified_items else {}
    merged_result.update(verified)
    return normalize_component_names_in_parsed_result(merged_result)


def _format_recognition_session_error(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            message = detail.get("message") or str(detail)
            status_code = detail.get("status_code")
            return f"{message} (HTTP {status_code})" if status_code else message
        return str(detail)
    return str(exc)


@router.post("/recognition_sessions", response_model=schemas.RecognitionSession)
def create_recognition_session(
    *,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    principal: auth.AuthPrincipal = Depends(deps.get_current_principal),
    file: UploadFile = File(...),
    mode: str = Form("existing_box"),
    box_id: Optional[int] = Form(None),
    template_id: Optional[int] = Form(None),
    layout_type: str = Form("grid"),
    config_id: Optional[int] = Form(None),
    search_provider_config_id: Optional[int] = Form(None),
    additional_prompt: str = Form(""),
    overwrite_existing: bool = Form(False),
) -> object:
    _validate_recognition_session_request(
        db=db,
        mode=mode,
        box_id=box_id,
        template_id=template_id,
        layout_type=layout_type,
    )
    content = read_limited_upload(file)
    try:
        normalized_content, normalized_content_type = normalize_upload_image(
            file,
            content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    config = vlm_config_service.get_config_for_use(db=db, config_id=config_id)
    search_provider_config = _get_search_provider_config_for_use(
        db=db,
        config_id=search_provider_config_id,
    )
    recognition_session = models.RecognitionSession(
        owner_kind=principal.kind,
        owner_id=principal.id,
        owner_name=principal.name,
        mode=mode,
        status="queued",
        verification_status="idle",
        filename=file.filename or "uploaded-recognition-image",
        content_type=normalized_content_type,
        config_id=config.id,
        search_provider_config_id=(
            search_provider_config.id if search_provider_config else None
        ),
        box_id=box_id,
        template_id=template_id,
        layout_type=layout_type,
        additional_prompt=additional_prompt,
        overwrite_existing=overwrite_existing,
    )
    db.add(recognition_session)
    db.commit()
    db.refresh(recognition_session)
    background_tasks.add_task(
        _run_recognition_session,
        session_id=recognition_session.id,
        content=normalized_content,
        content_type=normalized_content_type,
    )
    return recognition_session


@router.get("/recognition_sessions", response_model=List[schemas.RecognitionSession])
def read_recognition_sessions(
    *,
    db: Session = Depends(deps.get_db),
    principal: auth.AuthPrincipal = Depends(deps.get_current_principal),
    skip: int = Query(0, ge=0),
    limit: int = Query(RECOGNITION_SESSION_HISTORY_LIMIT, ge=1, le=RECOGNITION_SESSION_HISTORY_LIMIT),
) -> object:
    safe_limit = min(max(limit, 1), RECOGNITION_SESSION_HISTORY_LIMIT)
    safe_skip = max(skip, 0)
    return (
        db.query(models.RecognitionSession)
        .filter(
            models.RecognitionSession.owner_kind == principal.kind,
            models.RecognitionSession.owner_id == principal.id,
        )
        .order_by(models.RecognitionSession.created_at.desc())
        .offset(safe_skip)
        .limit(safe_limit)
        .all()
    )


@router.get(
    "/recognition_sessions/{session_id}",
    response_model=schemas.RecognitionSession,
)
def read_recognition_session(
    *,
    db: Session = Depends(deps.get_db),
    principal: auth.AuthPrincipal = Depends(deps.get_current_principal),
    session_id: int,
) -> object:
    return _get_owned_recognition_session(
        db=db,
        session_id=session_id,
        principal=principal,
    )


@router.delete("/recognition_sessions/{session_id}", status_code=204)
def delete_recognition_session(
    *,
    db: Session = Depends(deps.get_db),
    principal: auth.AuthPrincipal = Depends(deps.get_current_principal),
    session_id: int,
) -> Response:
    recognition_session = _get_owned_recognition_session(
        db=db,
        session_id=session_id,
        principal=principal,
    )
    if recognition_session.status not in {"succeeded", "failed"}:
        raise HTTPException(
            status_code=400,
            detail="正在识别的会话暂不能删除",
        )
    db.delete(recognition_session)
    db.commit()
    return Response(status_code=204)


@router.get("/recognition_prompt")
def read_recognition_prompt(
    db: Session = Depends(deps.get_db),
    additional_prompt: str = "",
) -> object:
    return {
        "prompt": recognition_prompt.build_component_recognition_prompt(
            db,
            additional_prompt=additional_prompt,
        )
    }


@router.post("/recognize_image", response_model=schemas.ImageRecognitionResponse)
def recognize_image(
    *,
    db: Session = Depends(deps.get_db),
    file: UploadFile = File(...),
    config_id: Optional[int] = Form(None),
    additional_prompt: str = Form(""),
) -> object:
    content = read_limited_upload(file)
    try:
        normalized_content, content_type = normalize_upload_image(file, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config = vlm_config_service.get_config_for_use(db=db, config_id=config_id)
    prompt = recognition_prompt.build_component_recognition_prompt(
        db,
        additional_prompt=additional_prompt,
    )
    return _recognize_image_with_config(
        config=config,
        filename=file.filename or "uploaded-image",
        content_type=content_type,
        content=normalized_content,
        prompt=prompt,
        max_tokens=SINGLE_IMAGE_RECOGNITION_MAX_TOKENS,
    )


@router.post("/recognize_box_image", response_model=schemas.ImageRecognitionResponse)
def recognize_box_image(
    *,
    db: Session = Depends(deps.get_db),
    file: UploadFile = File(...),
    box_id: int = Form(...),
    config_id: Optional[int] = Form(None),
    additional_prompt: str = Form(""),
) -> object:
    box = crud.box.get(db=db, id=box_id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")

    content = read_limited_upload(file)
    try:
        normalized_content, content_type = normalize_upload_image(file, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config = vlm_config_service.get_config_for_use(db=db, config_id=config_id)
    prompt = recognition_prompt.build_box_recognition_prompt(
        db,
        box=box,
        additional_prompt=additional_prompt,
    )
    return _recognize_image_with_config(
        config=config,
        filename=file.filename or "uploaded-box-image",
        content_type=content_type,
        content=normalized_content,
        prompt=prompt,
        max_tokens=_box_recognition_max_tokens(len(box.sub_boxes)),
    )


@router.post(
    "/recognize_box_template_image",
    response_model=schemas.ImageRecognitionResponse,
)
def recognize_box_template_image(
    *,
    db: Session = Depends(deps.get_db),
    file: UploadFile = File(...),
    template_id: int = Form(...),
    config_id: Optional[int] = Form(None),
    additional_prompt: str = Form(""),
) -> object:
    template = crud.box_template.get(db=db, id=template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Box template not found")

    content = read_limited_upload(file)
    try:
        normalized_content, content_type = normalize_upload_image(file, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config = vlm_config_service.get_config_for_use(db=db, config_id=config_id)
    prompt = recognition_prompt.build_new_box_recognition_prompt(
        db,
        template=template,
        additional_prompt=additional_prompt,
    )
    return _recognize_image_with_config(
        config=config,
        filename=file.filename or "uploaded-new-box-image",
        content_type=content_type,
        content=normalized_content,
        prompt=prompt,
        max_tokens=_box_recognition_max_tokens(
            _count_layout_cells(template.layout_type, template.layout_definition),
        ),
    )


@router.post(
    "/recognize_box_layout_image",
    response_model=schemas.ImageRecognitionResponse,
)
def recognize_box_layout_image(
    *,
    db: Session = Depends(deps.get_db),
    file: UploadFile = File(...),
    layout_type: str = Form("grid"),
    config_id: Optional[int] = Form(None),
    additional_prompt: str = Form(""),
) -> object:
    if layout_type not in {"grid", "irregular"}:
        raise HTTPException(status_code=400, detail="Unsupported layout type")

    content = read_limited_upload(file)
    try:
        normalized_content, content_type = normalize_upload_image(file, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config = vlm_config_service.get_config_for_use(db=db, config_id=config_id)
    prompt = recognition_prompt.build_box_template_recognition_prompt(
        db,
        layout_type=layout_type,
        additional_prompt=additional_prompt,
    )
    return _recognize_image_with_config(
        config=config,
        filename=file.filename or "uploaded-box-layout-image",
        content_type=content_type,
        content=normalized_content,
        prompt=prompt,
        max_tokens=BOX_LAYOUT_RECOGNITION_MAX_TOKENS,
    )


@router.post(
    "/box_recognitions/confirm",
    response_model=schemas.ConfirmBoxRecognitionResult,
)
def confirm_box_recognition(
    *,
    db: Session = Depends(deps.get_db),
    confirm_in: schemas.ConfirmBoxRecognitionRequest,
) -> object:
    box = crud.box.get(db=db, id=confirm_in.box_id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")

    result = _persist_box_recognition_cells(
        db=db,
        box_id=confirm_in.box_id,
        cells=confirm_in.cells,
        overwrite_existing=confirm_in.overwrite_existing,
    )
    result.box_readable_id = box.readable_id
    return result


@router.post(
    "/auto_box_recognitions/confirm",
    response_model=schemas.ConfirmBoxRecognitionResult,
)
def confirm_auto_box_recognition(
    *,
    db: Session = Depends(deps.get_db),
    confirm_in: schemas.ConfirmAutoBoxRecognitionRequest,
) -> object:
    template = crud.box_template.create(
        db=db,
        obj_in=schemas.BoxTemplateCreate(
            name=confirm_in.template_name,
            layout_type=confirm_in.layout_type,
            layout_definition=confirm_in.layout_definition,
            physical_dimensions=confirm_in.physical_dimensions or {},
        ),
    )
    box = create_box_with_retry(
        db=db,
        box_in=schemas.BoxCreate(
            readable_id=confirm_in.readable_id,
            name=confirm_in.box_name,
            template_id=template.id,
        ),
    )
    result = _persist_box_recognition_cells(
        db=db,
        box_id=box.id,
        cells=confirm_in.cells,
        overwrite_existing=True,
    )
    result.template_id = template.id
    result.box_id = box.id
    result.box_readable_id = box.readable_id
    return result


@router.post(
    "/new_box_recognitions/confirm",
    response_model=schemas.ConfirmBoxRecognitionResult,
)
def confirm_new_box_recognition(
    *,
    db: Session = Depends(deps.get_db),
    confirm_in: schemas.ConfirmNewBoxRecognitionRequest,
) -> object:
    template = crud.box_template.get(db=db, id=confirm_in.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Box template not found")

    box = create_box_with_retry(
        db=db,
        box_in=schemas.BoxCreate(
            readable_id=confirm_in.readable_id,
            name=confirm_in.box_name,
            template_id=confirm_in.template_id,
        ),
    )
    result = _persist_box_recognition_cells(
        db=db,
        box_id=box.id,
        cells=confirm_in.cells,
        overwrite_existing=True,
    )
    result.box_id = box.id
    result.box_readable_id = box.readable_id
    return result


@router.post(
    "/verify_components",
    response_model=schemas.ComponentVerificationResponse,
)
def verify_components(
    *,
    db: Session = Depends(deps.get_db),
    verify_in: schemas.ComponentVerificationRequest,
) -> object:
    return _verify_component_items(db=db, verify_in=verify_in)
