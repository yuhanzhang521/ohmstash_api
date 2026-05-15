import copy
from typing import Any, Dict, Optional

TYPE_PASSIVE = "PASSIVE"
TYPE_IC = "IC"
TYPE_MODULE = "MODULE"
TYPE_OTHER = "OTHER"


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

    _sync_attribute(attribute_map, "封装", name_part_map.get("package"))
    _sync_attribute(attribute_map, "型号", name_part_map.get("model"))
    if component_type == TYPE_MODULE:
        function_value = _clean_text(name_part_map.get("function")) or _clean_text(
            name_part_map.get("suffix"),
        )
        _sync_attribute(attribute_map, "功能", function_value)

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
