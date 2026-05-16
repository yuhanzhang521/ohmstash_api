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
