from app.services import component_naming


def test_component_naming_uses_configured_attribute_sync_rules() -> None:
    component_naming.load_naming_rules.cache_clear()

    normalized = component_naming.normalize_recognized_cell_payload(
        {
            "component_type": "MODULE",
            "name_parts": {"model": "PAM8403", "function": "功放模块"},
            "attributes": {},
        }
    )

    assert normalized["attributes"]["型号"] == "PAM8403"
    assert normalized["attributes"]["功能"] == "功放模块"


def test_module_fallback_name_preserves_spec() -> None:
    component_naming.load_naming_rules.cache_clear()

    normalized = component_naming.normalize_recognized_cell_payload(
        {
            "component_type": "MODULE",
            "name_parts": {"function": "FUNCTION", "spec": "SPEC"},
            "attributes": {},
        }
    )

    assert normalized["name"] == "SPECFUNCTION"
    assert normalized["attributes"]["规格"] == "SPEC"
    assert normalized["attributes"]["功能"] == "FUNCTION"


def test_component_naming_does_not_fill_default_tag_from_component_type() -> None:
    normalized = component_naming.normalize_recognized_cell_payload(
        {
            "component_type": "MODULE",
            "name_parts": {"function": "继电器模块"},
            "attributes": {},
            "tags": [],
        }
    )

    assert normalized["tags"] == []


def test_component_naming_keeps_empty_cell_empty() -> None:
    normalized = component_naming.normalize_recognized_cell_payload(
        {
            "is_empty": True,
            "component_type": "OTHER",
            "name": "USB功率计",
            "tags": ["工具"],
            "attributes": {"功能": "USB功率计"},
            "name_parts": {"function": "工具"},
            "search_recommended": True,
        }
    )

    assert normalized == {"is_empty": True}
