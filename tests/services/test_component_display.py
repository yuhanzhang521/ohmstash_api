from app.services import component_display


def test_display_attribute_priority_loads_from_rules() -> None:
    component_display.load_display_attribute_priority.cache_clear()

    assert "阻值" in component_display.load_display_attribute_priority()


def test_choose_component_display_attribute_uses_configured_priority() -> None:
    component_display.load_display_attribute_priority.cache_clear()

    attribute = component_display.choose_component_display_attribute(
        {"备注": "note", "阻值": "10k"},
    )

    assert attribute == "阻值"
