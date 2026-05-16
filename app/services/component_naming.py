import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

TYPE_PASSIVE = "PASSIVE"
TYPE_IC = "IC"
TYPE_MODULE = "MODULE"
TYPE_OTHER = "OTHER"
NAMING_RULES_PATH = Path(__file__).with_name("component_naming_rules.json")


@lru_cache(maxsize=1)
def load_naming_rules() -> Dict[str, Any]:
    return json.loads(NAMING_RULES_PATH.read_text(encoding="utf-8"))


def normalize_component_names_in_parsed_result(
    parsed_result: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(parsed_result, dict):
        return parsed_result

    normalized = copy.deepcopy(parsed_result)
    cells = normalized.get("cells")
    if isinstance(cells, list):
        normalized["cells"] = [
            normalize_recognized_cell_payload(cell)
            if isinstance(cell, dict)
            else cell
            for cell in cells
        ]
        return normalized

    return normalize_recognized_cell_payload(normalized)


def normalize_recognized_cell_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    if normalized.get("is_empty"):
        return normalized

    component_type = _clean_text(normalized.get("component_type"))
    name_parts = normalized.get("name_parts")
    name_part_map = dict(name_parts) if isinstance(name_parts, dict) else {}
    attributes = normalized.get("attributes")
    attribute_map = dict(attributes) if isinstance(attributes, dict) else {}
    normalized["name_parts"] = name_part_map
    normalized["attributes"] = attribute_map

    if not _clean_text(normalized.get("name")):
        fallback_name = _fallback_name_from_parts(component_type, name_part_map)
        if fallback_name:
            normalized["name"] = fallback_name

    _sync_configured_attributes(
        attribute_map,
        component_type=component_type,
        name_part_map=name_part_map,
    )

    normalized["search_recommended"] = _decide_search_recommended(
        component_type=component_type,
        name_part_map=name_part_map,
        explicit_value=normalized.get("search_recommended"),
    )
    return normalized


def _fallback_name_from_parts(
    component_type: str,
    name_parts: Dict[str, Any],
) -> str:
    if component_type == TYPE_PASSIVE:
        package = _clean_text(name_parts.get("package"))
        value = _clean_text(name_parts.get("value"))
        if package and value:
            return f"{package} {value}"
        return value

    if component_type == TYPE_IC:
        return _clean_text(name_parts.get("model"))

    if component_type == TYPE_MODULE:
        model = _clean_text(name_parts.get("model"))
        suffix = _clean_text(name_parts.get("suffix"))
        function = _clean_text(name_parts.get("function"))
        if model and suffix:
            return f"{model}{suffix}"
        if model and function:
            return f"{model}{function}"
        return function or suffix

    function = _clean_text(name_parts.get("function"))
    spec = _clean_text(name_parts.get("spec"))
    model = _clean_text(name_parts.get("model"))
    if function and spec:
        return f"{function} {spec}"
    if function and model:
        return f"{function} {model}"
    return function


def _decide_search_recommended(
    *,
    component_type: str,
    name_part_map: Dict[str, Any],
    explicit_value: Any,
) -> bool:
    if component_type == TYPE_PASSIVE:
        return False
    if component_type == TYPE_IC:
        return True
    if component_type in (TYPE_MODULE, TYPE_OTHER):
        return bool(_clean_text(name_part_map.get("model")))
    return bool(explicit_value)


def _sync_configured_attributes(
    attributes: Dict[str, Any],
    *,
    component_type: str,
    name_part_map: Dict[str, Any],
) -> None:
    for rule in load_naming_rules().get("attribute_sync_rules", []):
        if rule.get("component_type") and rule["component_type"] != component_type:
            continue
        value = _clean_text(name_part_map.get(rule.get("name_part")))
        if not value and rule.get("fallback_name_part"):
            value = _clean_text(name_part_map.get(rule["fallback_name_part"]))
        _sync_attribute(attributes, str(rule.get("attribute") or ""), value)
def _sync_attribute(
    attributes: Dict[str, Any],
    key: str,
    value: Any,
) -> None:
    clean_value = _clean_text(value)
    if clean_value:
        attributes[key] = clean_value


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()
