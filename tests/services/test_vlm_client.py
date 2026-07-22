from app.services.vlm_client import DEFAULT_TIMEOUT_SECONDS, resolve_timeout_seconds


def test_resolve_timeout_seconds_uses_default_when_missing() -> None:
    assert resolve_timeout_seconds({}) == DEFAULT_TIMEOUT_SECONDS
    assert resolve_timeout_seconds(None) == DEFAULT_TIMEOUT_SECONDS


def test_resolve_timeout_seconds_raises_legacy_short_timeouts() -> None:
    assert resolve_timeout_seconds({"timeout_seconds": 90}) == DEFAULT_TIMEOUT_SECONDS
    assert resolve_timeout_seconds({"timeout_seconds": "60"}) == DEFAULT_TIMEOUT_SECONDS


def test_resolve_timeout_seconds_allows_higher_values() -> None:
    assert resolve_timeout_seconds({"timeout_seconds": 600}) == 600.0


def test_resolve_timeout_seconds_rejects_invalid_values() -> None:
    assert resolve_timeout_seconds({"timeout_seconds": 0}) == DEFAULT_TIMEOUT_SECONDS
    assert resolve_timeout_seconds({"timeout_seconds": -1}) == DEFAULT_TIMEOUT_SECONDS
    assert resolve_timeout_seconds({"timeout_seconds": "fast"}) == DEFAULT_TIMEOUT_SECONDS
