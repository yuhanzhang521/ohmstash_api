import json
from typing import Any

SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "cloudflare_api_token",
    "key",
    "password",
    "secret",
    "token",
)
REDACTED_VALUE = "[REDACTED]"


def redact_sensitive_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: REDACTED_VALUE if _is_sensitive_key(str(key)) else redact_sensitive_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    return value


def redact_sensitive_text(value: str) -> str:
    try:
        parsed = json.loads(value)
    except ValueError:
        return value
    return json.dumps(redact_sensitive_data(parsed), ensure_ascii=False)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)
