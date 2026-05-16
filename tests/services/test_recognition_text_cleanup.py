from app.services import recognition_text_cleanup


def test_recognition_text_cleanup_loads_rules_from_config() -> None:
    recognition_text_cleanup.load_cleanup_rules.cache_clear()
    recognition_text_cleanup.get_compiled_rules.cache_clear()

    rules = recognition_text_cleanup.load_cleanup_rules()

    assert "未找到" in rules["verification_warning_prefixes"]
    assert recognition_text_cleanup.extract_verification_warning("未找到可靠资料。") == "未找到可靠资料"
