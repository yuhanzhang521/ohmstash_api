from app.core.log_sanitizer import REDACTED_VALUE, redact_sensitive_data, redact_sensitive_text


def test_redact_sensitive_data_masks_nested_secret_fields() -> None:
    payload = {
        "api_key": "secret-api-key",
        "nested": {"password": "secret-password", "safe": "visible"},
        "items": [{"token": "secret-token"}],
    }

    redacted = redact_sensitive_data(payload)

    assert redacted["api_key"] == REDACTED_VALUE
    assert redacted["nested"]["password"] == REDACTED_VALUE
    assert redacted["nested"]["safe"] == "visible"
    assert redacted["items"][0]["token"] == REDACTED_VALUE


def test_redact_sensitive_text_masks_json_secret_fields() -> None:
    redacted = redact_sensitive_text('{"error": {"api_key": "secret", "message": "bad"}}')

    assert "secret" not in redacted
    assert REDACTED_VALUE in redacted
    assert "bad" in redacted
