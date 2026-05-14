import copy
import re
from typing import Any, Dict, Iterable, List, Optional

PASSIVE_RULES = (
    (("电阻", "resistor"), ("阻值", "电阻值", "Resistance")),
    (("电容", "capacitor"), ("容值", "容量", "电容量", "Capacitance")),
    (("电感", "inductor"), ("电感值", "感值", "Inductance")),
)
MODEL_ATTRIBUTE_KEYS = (
    "型号",
    "料号",
    "订货号",
    "MPN",
    "Part Number",
    "Manufacturer Part Number",
)
PACKAGE_ATTRIBUTE_KEYS = ("封装", "Package", "封装规格")
THROUGH_HOLE_TERMS = ("插件", "直插", "through hole", "tht", "dip", "轴向")
SMD_PACKAGE_PATTERN = re.compile(
    r"^(?:0[2468]02|0201|0402|0603|0805|1206|1210|1812|2010|2512|"
    r"sot-[0-9a-z-]+|sod-[0-9a-z-]+|qfn-[0-9a-z-]+|dfn-[0-9a-z-]+|"
    r"soic-[0-9a-z-]+|tssop-[0-9a-z-]+|msop-[0-9a-z-]+)$",
    re.IGNORECASE,
)
MODEL_TOKEN_PATTERN = re.compile(
    r"[A-Z]{1,}[A-Z0-9._/-]*\d[A-Z0-9._/-]*"
)
VOLTAGE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*V\b", re.IGNORECASE)
LEADING_CODE_PATTERN = re.compile(r"^[A-Za-z0-9._/-]{2,}$")
FUNCTION_MODEL_PREFIX_PHRASES = ("舵机",)
FUNCTION_TYPE_ATTRIBUTE_KEYS = ("类型", "功能", "器件类型")
VOLTAGE_ATTRIBUTE_KEYS = ("供电电压", "工作电压", "额定电压", "电压", "Voltage")
FUNCTION_PHRASES = (
    "薄膜压力传感器",
    "压力传感器",
    "温湿度传感器",
    "温度传感器",
    "湿度传感器",
    "霍尔传感器",
    "红外传感器",
    "光电传感器",
    "距离传感器",
    "触摸开关模块",
    "触摸开关",
    "开关模块",
    "按键开关",
    "拨动开关",
    "船型开关",
    "微动开关",
    "继电器模块",
    "电源模块",
    "升压模块",
    "降压模块",
    "充电模块",
    "功放模块",
    "放大器模块",
    "转换模块",
    "开发板",
    "离心风扇",
    "轴流风扇",
    "散热风扇",
    "风扇",
    "传感器",
    "开关",
    "连接器",
    "接线端子",
    "端子",
    "蜂鸣器",
    "步进电机",
    "直流电机",
    "电机",
    "舵机",
    "摄像头",
    "显示屏",
    "屏幕",
    "电池座",
    "保险丝",
    "继电器",
)


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

    name = _clean_text(normalized.get("name"))
    if not name:
        return normalized

    tags = _clean_texts(normalized.get("tags") or [])
    attributes = normalized.get("attributes")
    attribute_map = dict(attributes) if isinstance(attributes, dict) else {}
    normalized["attributes"] = attribute_map
    source_text = _build_source_text(
        name,
        tags,
        attribute_map,
        normalized.get("notes"),
    )

    passive_name = _build_passive_name(name, source_text, attribute_map)
    if passive_name:
        normalized["name"] = passive_name
        _ensure_passive_attributes(attribute_map, passive_name, source_text)
        return normalized

    if _is_integrated_circuit(source_text) and not _is_functional_component(source_text):
        model_name = _extract_model_name(name, attribute_map)
        if model_name:
            normalized["name"] = model_name
            _ensure_attribute_value(
                attribute_map,
                MODEL_ATTRIBUTE_KEYS,
                "型号",
                model_name,
            )
            return normalized

    phrase = _extract_function_phrase(source_text)
    functional_name = _build_functional_name(
        name,
        source_text,
        attribute_map,
        phrase=phrase,
    )
    if functional_name:
        normalized["name"] = functional_name
        _ensure_functional_attributes(
            attribute_map,
            phrase=phrase or _extract_function_phrase(functional_name),
            source_name=name,
        )

    return normalized


def _build_passive_name(
    name: str,
    source_text: str,
    attributes: Dict[str, Any],
) -> Optional[str]:
    for terms, value_keys in PASSIVE_RULES:
        if not any(term.lower() in source_text.lower() for term in terms):
            continue
        value = _first_attribute_value(attributes, value_keys)
        if not value:
            value = _extract_passive_value_from_name(name)
        if not value:
            return None
        package = _extract_smd_package(name, attributes, source_text)
        return f"{value} {package}".strip() if package else value
    return None


def _extract_passive_value_from_name(name: str) -> str:
    match = re.search(
        r"\b\d+(?:\.\d+)?\s*(?:[kKmM]?Ω|[kKmMrR]|pF|nF|uF|µF|mF|uH|µH|mH|H)\b",
        name,
    )
    return _clean_text(match.group(0)) if match else ""


def _extract_smd_package(
    name: str,
    attributes: Dict[str, Any],
    source_text: str,
) -> str:
    if any(term in source_text.lower() for term in THROUGH_HOLE_TERMS):
        return ""

    package = _first_attribute_value(attributes, PACKAGE_ATTRIBUTE_KEYS)
    if package and SMD_PACKAGE_PATTERN.match(package):
        return package.upper() if package.isalpha() else package

    package_pattern = (
        r"\b[0-9]{4}\b|"
        r"\b(?:SOT|SOD|QFN|DFN|SOIC|TSSOP|MSOP)-[0-9A-Za-z-]+\b"
    )
    for token in re.findall(package_pattern, name):
        if SMD_PACKAGE_PATTERN.match(token):
            return token
    return ""


def _is_integrated_circuit(source_text: str) -> bool:
    text = source_text.lower()
    return (
        "芯片" in source_text
        or "集成电路" in source_text
        or re.search(r"\bic\b", text) is not None
    )


def _is_functional_component(source_text: str) -> bool:
    return _extract_function_phrase(source_text) is not None


def _extract_model_name(name: str, attributes: Dict[str, Any]) -> str:
    for key in MODEL_ATTRIBUTE_KEYS:
        value = _clean_text(attributes.get(key))
        token = _choose_model_token(value)
        if token:
            return token

    return _choose_model_token(name)


def _choose_model_token(value: str) -> str:
    tokens = MODEL_TOKEN_PATTERN.findall(value.upper())
    return max(tokens, key=len) if tokens else ""


def _build_functional_name(
    name: str,
    source_text: str,
    attributes: Dict[str, Any],
    *,
    phrase: Optional[str] = None,
) -> Optional[str]:
    if not phrase:
        return None

    model = _extract_model_name(name, attributes)
    if phrase in FUNCTION_MODEL_PREFIX_PHRASES and model:
        return f"{model}{phrase}"

    voltage = _extract_voltage(name, attributes)
    if "风扇" in phrase and voltage:
        return f"{voltage}{phrase}"

    if phrase in name:
        return _strip_nonessential_prefix(name, phrase)

    return phrase


def _ensure_passive_attributes(
    attributes: Dict[str, Any],
    passive_name: str,
    source_text: str,
) -> None:
    for terms, value_keys in PASSIVE_RULES:
        if not any(term.lower() in source_text.lower() for term in terms):
            continue
        value = _extract_passive_value_from_name(passive_name)
        if value:
            _ensure_attribute_value(attributes, value_keys, value_keys[0], value)
        package = _extract_smd_package(passive_name, attributes, source_text)
        if package:
            _ensure_attribute_value(
                attributes,
                PACKAGE_ATTRIBUTE_KEYS,
                "封装",
                package,
            )
        return


def _ensure_functional_attributes(
    attributes: Dict[str, Any],
    *,
    phrase: Optional[str],
    source_name: str,
) -> None:
    if phrase:
        _ensure_attribute_value(
            attributes,
            FUNCTION_TYPE_ATTRIBUTE_KEYS,
            "类型",
            phrase,
        )

    model = _extract_model_name(source_name, attributes)
    if phrase in FUNCTION_MODEL_PREFIX_PHRASES and model:
        _ensure_attribute_value(
            attributes,
            MODEL_ATTRIBUTE_KEYS,
            "型号",
            model,
        )

    voltage = _extract_voltage(source_name, attributes)
    if phrase and "风扇" in phrase and voltage:
        _ensure_attribute_value(
            attributes,
            VOLTAGE_ATTRIBUTE_KEYS,
            "供电电压",
            voltage,
        )


def _extract_function_phrase(source_text: str) -> Optional[str]:
    compact_text = source_text.replace("\n", " ")
    for phrase in FUNCTION_PHRASES:
        if phrase in compact_text:
            return phrase
    return None


def _strip_nonessential_prefix(name: str, phrase: str) -> str:
    phrase_index = name.find(phrase)
    if phrase_index <= 0:
        return phrase

    prefix = name[:phrase_index].strip(" -_/，,")
    suffix = name[phrase_index + len(phrase):].strip()
    if not prefix:
        return f"{phrase}{suffix}".strip()

    tokens = [token for token in re.split(r"\s+", prefix) if token]
    if tokens and all(LEADING_CODE_PATTERN.match(token) for token in tokens):
        return f"{phrase}{suffix}".strip()
    return name


def _extract_voltage(name: str, attributes: Dict[str, Any]) -> str:
    for value in [name, *(_clean_text(item) for item in attributes.values())]:
        match = VOLTAGE_PATTERN.search(value)
        if match:
            return match.group(0).replace(" ", "").upper()
    return ""


def _ensure_attribute_value(
    attributes: Dict[str, Any],
    keys: Iterable[str],
    default_key: str,
    value: str,
) -> None:
    if not value:
        return
    if _first_attribute_value(attributes, keys):
        return
    attributes[default_key] = value


def _first_attribute_value(
    attributes: Dict[str, Any],
    keys: Iterable[str],
) -> str:
    for key in keys:
        value = _clean_text(attributes.get(key))
        if value:
            return value
    return ""


def _build_source_text(
    name: str,
    tags: List[str],
    attributes: Dict[str, Any],
    notes: Any,
) -> str:
    parts = [name, *tags]
    for key, value in attributes.items():
        parts.append(_clean_text(key))
        parts.append(_clean_text(value))
    parts.append(_clean_text(notes))
    return " ".join(part for part in parts if part)


def _clean_texts(values: Iterable[Any]) -> List[str]:
    cleaned_values: List[str] = []
    for value in values:
        cleaned_value = _clean_text(value)
        if cleaned_value:
            cleaned_values.append(cleaned_value)
    return cleaned_values


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())
