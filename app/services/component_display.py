import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

DISPLAY_RULES_PATH = Path(__file__).with_name("component_display_rules.json")


@lru_cache(maxsize=1)
def load_display_attribute_priority() -> Sequence[str]:
    payload = json.loads(DISPLAY_RULES_PATH.read_text(encoding="utf-8"))
    values = payload.get("display_attribute_priority", [])
    return tuple(str(value) for value in values)


def stringify_display_value(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def choose_component_display_attribute(
    attributes: Optional[Mapping[str, Any]],
    preferred_attribute: Optional[str] = None,
) -> Optional[str]:
    normalized_attributes = attributes or {}
    preferred_key = str(preferred_attribute or "").strip()
    if (
        preferred_key
        and preferred_key in normalized_attributes
        and stringify_display_value(normalized_attributes.get(preferred_key))
    ):
        return preferred_key

    for key in load_display_attribute_priority():
        if (
            key in normalized_attributes
            and stringify_display_value(normalized_attributes.get(key))
        ):
            return key

    for key, value in normalized_attributes.items():
        if stringify_display_value(value):
            return str(key)

    return None


def build_component_display_name(
    attributes: Optional[Mapping[str, Any]],
    display_attribute: Optional[str],
) -> Optional[str]:
    normalized_attributes = attributes or {}
    attribute_key = choose_component_display_attribute(
        normalized_attributes,
        display_attribute,
    )
    if not attribute_key:
        return None
    return stringify_display_value(normalized_attributes.get(attribute_key))
