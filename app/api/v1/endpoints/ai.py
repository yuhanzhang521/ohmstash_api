import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.models.search_provider_config import (
    SearchProviderConfig as SearchProviderConfigModel,
)
from app.models.vlm_provider_config import VlmProviderConfig as VlmProviderConfigModel
from app.services import recognition_prompt, vlm_client, web_search
from app.services.box_labeling import generate_next_box_readable_id
from app.services.component_display import choose_component_display_attribute
from app.services.image_upload import normalize_upload_image

router = APIRouter()
logger = logging.getLogger(__name__)

VERIFICATION_CHUNK_SIZE = 6
SEARCH_RESULTS_PER_ITEM = 5
SINGLE_IMAGE_RECOGNITION_MAX_TOKENS = 1200
BOX_RECOGNITION_MIN_MAX_TOKENS = 3000
BOX_RECOGNITION_MAX_TOKENS = 10000
BOX_RECOGNITION_TOKENS_PER_CELL = 220
BOX_LAYOUT_RECOGNITION_MAX_TOKENS = 10000
VERIFICATION_WARNING_PATTERNS = [
    re.compile(r"未检索到[^。；;，,\n]*(?:[。；;，,])?"),
    re.compile(r"未找到[^。；;，,\n]*(?:[。；;，,])?"),
    re.compile(r"没有可确认[^。；;，,\n]*(?:[。；;，,])?"),
    re.compile(r"无法确认[^。；;，,\n]*(?:[。；;，,])?"),
    re.compile(r"搜索结果不足[^。；;，,\n]*(?:[。；;，,])?"),
    re.compile(r"(?:暂)?保留原标注"),
]
MODEL_CORRECTION_PATTERN = re.compile(
    r"搜索结果指向\s*(?P<target>[^：:。；;，,\n]+)"
    r"(?:[：:]\s*(?P<summary>[^。；;\n]+))?"
    r"[。；;，,\s]*(?P<warning>原始[^。；;\n]*(?:疑似|可能)[^。；;\n]*)"
)
MODEL_MULTI_CORRECTION_PATTERN = re.compile(
    r"搜索结果(?:主要)?指向\s*(?P<targets>[^。；;\n]+?)"
    r"(?:等(?:其他)?型号)?[，,\s]*(?P<warning>原始[^。；;\n]*(?:疑似|可能|误差|抄写|识别)[^。；;\n]*)"
)
MODEL_CORRECTION_TARGET_PATTERN = re.compile(
    r"搜索结果(?:主要)?指向\s*(?P<target>[^：:。；;，,\n]+)"
)
MODEL_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9._/-]*\d[A-Za-z0-9._/-]*")
ATTRIBUTE_UNCERTAINTY_PATTERNS = [
    re.compile(r"[（(][^（）()]{0,30}(?:未能|不能|无法|不足|不确定|待确认|不同厂商|版本不一致)[^（）()]{0,40}[）)]"),
    re.compile(r"(?:未能|不能|无法|不足|不确定|待确认|不同厂商|版本不一致)[^。；;，,\n]*"),
]
PHOTO_META_KEYWORDS = (
    "拍摄角度",
    "拍照角度",
    "拍摄方向",
    "拍摄环境",
    "拍摄面",
    "在画面",
    "在图中",
    "标签可见",
    "标签显示",
    "标签含",
    "标签朝向",
    "标签朝",
    "标签清晰",
    "标签上",
    "标签为",
    "标签是",
    "标签写",
    "竖放",
    "横放",
    "竖立",
    "侧立",
    "倒置",
    "正面朝",
    "背面朝",
    "镜头",
    "照片",
    "图片中",
    "字体",
    "字号",
    "印刷字",
    "丝印",
    "丝网",
    "光线",
    "阴影",
    "反光",
    "倾斜放置",
    "斜放",
    "高亮",
    "包装袋",
    "包装上",
    "袋装",
    "纸标签",
)
PHOTO_META_SENTENCE_PATTERN = re.compile(
    r"[^。；;\n]*(?:"
    + "|".join(re.escape(keyword) for keyword in PHOTO_META_KEYWORDS)
    + r")[^。；;\n]*[。；;]?"
)


def _ensure_unique_config_name(
    db: Session,
    *,
    name: str,
    current_config_id: Optional[int] = None,
) -> None:
    existing_config = crud.vlm_provider_config.get_by_name(db=db, name=name)
    if existing_config and existing_config.id != current_config_id:
        raise HTTPException(status_code=400, detail="VLM config name already exists")


def _get_required_default_config(db: Session) -> VlmProviderConfigModel:
    config = crud.vlm_provider_config.get_default(db=db)
    if not config:
        raise HTTPException(status_code=404, detail="Default VLM config not found")
    return config


def _get_vlm_config_for_use(
    db: Session,
    *,
    config_id: Optional[int] = None,
) -> VlmProviderConfigModel:
    if config_id is None:
        return _get_required_default_config(db=db)

    config = crud.vlm_provider_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="VLM config not found")
    return config


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


def _build_transient_config(
    config_in: schemas.VlmProviderConfigCreate,
) -> VlmProviderConfigModel:
    return VlmProviderConfigModel(**config_in.model_dump())


def _run_vlm_test(
    config: VlmProviderConfigModel,
    *,
    prompt: str,
) -> schemas.VlmConnectionTestResult:
    try:
        response, latency_ms = vlm_client.request_chat_completion(
            config=config,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=64,
        )
    except vlm_client.VlmClientError as exc:
        return schemas.VlmConnectionTestResult(
            ok=False,
            provider=config.provider,
            model_name=config.model_name,
            status_code=exc.status_code,
            message=exc.message,
            response_text=exc.response_body,
        )

    response_text = vlm_client.extract_message_text(response)
    return schemas.VlmConnectionTestResult(
        ok=True,
        provider=config.provider,
        model_name=config.model_name,
        latency_ms=latency_ms,
        message="VLM config test succeeded",
        response_text=response_text,
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
    return schemas.ImageRecognitionResponse(
        config_id=config.id,
        filename=filename,
        content_type=content_type,
        prompt=prompt,
        raw_text=raw_text,
        parsed_result=vlm_client.extract_json_object(raw_text),
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
    text = str(value or "")
    if not text:
        return None
    _note, correction_warning = _split_model_correction_note(text)
    if correction_warning:
        return correction_warning
    multi_correction_warning = _extract_multi_correction_warning(text)
    if multi_correction_warning:
        return multi_correction_warning
    warnings: List[str] = []
    for pattern in VERIFICATION_WARNING_PATTERNS:
        warnings.extend(match.group(0) for match in pattern.finditer(text))
    if not warnings:
        return None
    warning = " ".join(warnings).strip("。；;，, \n\t")
    return warning or "联网搜索未取得可确认资料，已保留原标注"


def _clean_verification_notes(value: Any) -> Optional[str]:
    text = str(value or "")
    if not text:
        return None
    correction_note, _correction_warning = _split_model_correction_note(text)
    if correction_note:
        return _strip_photo_meta_phrases(correction_note) or None
    text = _remove_multi_correction_warning(text)
    for pattern in VERIFICATION_WARNING_PATTERNS:
        text = pattern.sub("", text)
    text = re.sub(r"(?:联网)?搜索摘要确认[:：]?\s*", "", text)
    text = re.sub(r"联网确认[:：]?\s*", "", text)
    text = _strip_photo_meta_phrases(text)
    text = text.strip("。；;，, \n\t")
    return text or None


def _strip_photo_meta_phrases(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    cleaned = PHOTO_META_SENTENCE_PATTERN.sub("", text)
    cleaned = re.sub(r"[\s。；;，,]+", lambda match: match.group(0)[0], cleaned)
    return cleaned.strip("。；;，, \n\t")


def _sanitize_recognition_notes(value: Any) -> Optional[str]:
    text = _strip_photo_meta_phrases(value)
    return text or None


def _split_model_correction_note(value: Any) -> Tuple[Optional[str], Optional[str]]:
    text = _normalize_search_value(value)
    if not text or "搜索结果指向" not in text:
        return None, None

    match = MODEL_CORRECTION_PATTERN.search(text)
    if not match:
        return None, None

    target = _normalize_search_value(match.group("target"))
    summary = _normalize_search_value(match.group("summary"))
    warning_tail = _normalize_search_value(match.group("warning"))
    note = f"{target}：{summary}" if target and summary else None
    warning = f"搜索结果指向 {target}，{warning_tail}" if target else warning_tail
    return note, warning


def _extract_multi_correction_warning(value: Any) -> Optional[str]:
    text = _normalize_search_value(value)
    if not text or "搜索结果" not in text:
        return None
    match = MODEL_MULTI_CORRECTION_PATTERN.search(text)
    if not match:
        return None
    target_text = _normalize_search_value(match.group("targets")).rstrip("，, ")
    warning_tail = _normalize_search_value(match.group("warning"))
    return f"搜索结果主要指向 {target_text}，{warning_tail}" if target_text else warning_tail


def _remove_multi_correction_warning(value: str) -> str:
    return MODEL_MULTI_CORRECTION_PATTERN.sub("", value)


def _extract_corrected_component_name(
    value: Any,
    *,
    original_name: Optional[str] = None,
) -> Optional[str]:
    text = str(value or "")
    multi_match = MODEL_MULTI_CORRECTION_PATTERN.search(text)
    if multi_match:
        tokens = MODEL_TOKEN_PATTERN.findall(multi_match.group("targets"))
        if tokens:
            return _choose_corrected_token(tokens, original_name=original_name)

    match = MODEL_CORRECTION_TARGET_PATTERN.search(text)
    if match:
        target = _normalize_search_value(match.group("target"))
        tokens = MODEL_TOKEN_PATTERN.findall(target)
        if tokens:
            return _choose_corrected_token(tokens, original_name=original_name)
        return target or None

    if "搜索结果" not in text:
        return None

    tokens = MODEL_TOKEN_PATTERN.findall(text)
    if tokens:
        return _choose_corrected_token(tokens, original_name=original_name)
    return None


def _choose_corrected_token(
    tokens: List[str],
    *,
    original_name: Optional[str] = None,
) -> Optional[str]:
    unique_tokens: List[str] = []
    for token in tokens:
        normalized_token = token.strip(".,;:，；：。")
        if normalized_token and normalized_token not in unique_tokens:
            unique_tokens.append(normalized_token)
    if not unique_tokens:
        return None

    original = _normalize_search_value(original_name).upper()
    if original:
        for token in unique_tokens:
            candidate = token.upper()
            if len(candidate) == len(original) and candidate[1:] == original[1:]:
                return token
        close_tokens = [
            token
            for token in unique_tokens
            if _edit_distance(token.upper(), original) <= 1
            and token.upper() != original
        ]
        if close_tokens:
            return close_tokens[-1]
    return unique_tokens[-1]


def _edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if abs(len(left) - len(right)) > 1:
        return 2
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    previous[right_index] + 1,
                    current[right_index - 1] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


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
        for pattern in ATTRIBUTE_UNCERTAINTY_PATTERNS:
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
        "display_attribute 必须保留或更新为 attributes 中最适合缩略显示的属性名，"
        "阻容感优先使用阻值、容值或电感值，芯片类通常使用型号。\n"
        "不要把“未能从摘要唯一确认”“不同厂商版本不一致”“待确认”等不确定性说明写进 attributes 的值里，"
        "这些说明只能写入 verification_warning。\n"
        "notes 只写有用的器件补充信息，不要写“搜索摘要确认”“联网确认”等流程性文字。\n"
        "如果有型号纠错，notes 只写器件资料摘要；把“搜索结果指向 X，原始型号 Y 疑似识别/抄写误差”写入 verification_warning。\n"
        "如果没有检索到足够资料，请把原因写入 verification_warning，notes 保持为空或只保留器件说明。\n"
        "请只返回 JSON 对象，格式为：\n"
        '{"items": [{"position_identifier": "R1C1", "is_empty": false, '
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
        cleaned_items.append(schemas.RecognizedCell(**data))
    return cleaned_items


@router.get("/vlm_config", response_model=schemas.VlmProviderConfig)
def read_default_vlm_config(db: Session = Depends(deps.get_db)) -> Any:
    return _get_required_default_config(db=db)


@router.put("/vlm_config", response_model=schemas.VlmProviderConfig)
def upsert_default_vlm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_in: schemas.VlmProviderConfigCreate,
) -> Any:
    default_config = crud.vlm_provider_config.get_default(db=db)
    if default_config:
        _ensure_unique_config_name(
            db=db,
            name=config_in.name,
            current_config_id=default_config.id,
        )
        config_data = config_in.model_dump()
        if "api_key" not in config_in.model_fields_set:
            config_data.pop("api_key", None)
        config_data["is_default"] = True
        update_data = schemas.VlmProviderConfigUpdate(**config_data)
        return crud.vlm_provider_config.update(
            db=db,
            db_obj=default_config,
            obj_in=update_data,
        )

    _ensure_unique_config_name(db=db, name=config_in.name)
    config_data = config_in.model_dump()
    config_data["is_default"] = True
    create_data = schemas.VlmProviderConfigCreate(**config_data)
    return crud.vlm_provider_config.create(db=db, obj_in=create_data)


@router.post("/vlm_config/test", response_model=schemas.VlmConnectionTestResult)
def test_default_vlm_config(
    *,
    db: Session = Depends(deps.get_db),
    test_in: Optional[schemas.VlmConnectionTestRequest] = None,
) -> Any:
    request_data = test_in or schemas.VlmConnectionTestRequest()
    config = (
        _build_transient_config(request_data.config)
        if request_data.config
        else _get_required_default_config(db=db)
    )
    return _run_vlm_test(config=config, prompt=request_data.prompt)


@router.post("/vlm_configs/", response_model=schemas.VlmProviderConfig)
def create_vlm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_in: schemas.VlmProviderConfigCreate,
) -> Any:
    _ensure_unique_config_name(db=db, name=config_in.name)
    return crud.vlm_provider_config.create(db=db, obj_in=config_in)


@router.get("/vlm_configs/", response_model=List[schemas.VlmProviderConfig])
def read_vlm_configs(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    return crud.vlm_provider_config.get_multi(db=db, skip=skip, limit=limit)


@router.get("/vlm_configs/default", response_model=schemas.VlmProviderConfig)
def read_default_vlm_config_from_collection(
    db: Session = Depends(deps.get_db),
) -> Any:
    return _get_required_default_config(db=db)


@router.post(
    "/vlm_configs/{config_id}/test",
    response_model=schemas.VlmConnectionTestResult,
)
def test_vlm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
    test_in: Optional[schemas.VlmConnectionTestRequest] = None,
) -> Any:
    request_data = test_in or schemas.VlmConnectionTestRequest()
    config = _get_vlm_config_for_use(db=db, config_id=config_id)
    return _run_vlm_test(config=config, prompt=request_data.prompt)


@router.get("/vlm_configs/{config_id}", response_model=schemas.VlmProviderConfig)
def read_vlm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
) -> Any:
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
) -> Any:
    config = crud.vlm_provider_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="VLM config not found")
    if config_in.name:
        _ensure_unique_config_name(
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
) -> Any:
    config = crud.vlm_provider_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="VLM config not found")
    return crud.vlm_provider_config.set_default(db=db, db_obj=config)


@router.delete("/vlm_configs/{config_id}", response_model=schemas.VlmProviderConfig)
def delete_vlm_config(
    *,
    db: Session = Depends(deps.get_db),
    config_id: int,
) -> Any:
    config = crud.vlm_provider_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="VLM config not found")
    return crud.vlm_provider_config.remove(db=db, id=config_id)


@router.get("/recognition_prompt")
def read_recognition_prompt(
    db: Session = Depends(deps.get_db),
    additional_prompt: str = "",
) -> Any:
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
) -> Any:
    content = file.file.read()
    try:
        normalized_content, content_type = normalize_upload_image(file, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config = _get_vlm_config_for_use(db=db, config_id=config_id)
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
) -> Any:
    box = crud.box.get(db=db, id=box_id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")

    content = file.file.read()
    try:
        normalized_content, content_type = normalize_upload_image(file, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config = _get_vlm_config_for_use(db=db, config_id=config_id)
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
) -> Any:
    template = crud.box_template.get(db=db, id=template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Box template not found")

    content = file.file.read()
    try:
        normalized_content, content_type = normalize_upload_image(file, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config = _get_vlm_config_for_use(db=db, config_id=config_id)
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
) -> Any:
    if layout_type not in {"grid", "irregular"}:
        raise HTTPException(status_code=400, detail="Unsupported layout type")

    content = file.file.read()
    try:
        normalized_content, content_type = normalize_upload_image(file, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config = _get_vlm_config_for_use(db=db, config_id=config_id)
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
) -> Any:
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
) -> Any:
    readable_id = confirm_in.readable_id or generate_next_box_readable_id(db)
    existing_box = (
        db.query(models.Box)
        .filter(models.Box.readable_id == readable_id)
        .first()
    )
    if existing_box:
        raise HTTPException(status_code=400, detail="Box readable_id already exists")

    template = crud.box_template.create(
        db=db,
        obj_in=schemas.BoxTemplateCreate(
            name=confirm_in.template_name,
            layout_type=confirm_in.layout_type,
            layout_definition=confirm_in.layout_definition,
            physical_dimensions=confirm_in.physical_dimensions or {},
        ),
    )
    box = crud.box.create(
        db=db,
        obj_in=schemas.BoxCreate(
            readable_id=readable_id,
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
) -> Any:
    template = crud.box_template.get(db=db, id=confirm_in.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Box template not found")

    readable_id = confirm_in.readable_id or generate_next_box_readable_id(db)
    existing_box = (
        db.query(models.Box)
        .filter(models.Box.readable_id == readable_id)
        .first()
    )
    if existing_box:
        raise HTTPException(status_code=400, detail="Box readable_id already exists")

    box = crud.box.create(
        db=db,
        obj_in=schemas.BoxCreate(
            readable_id=readable_id,
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
) -> Any:
    config = _get_vlm_config_for_use(db=db, config_id=verify_in.config_id)
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
