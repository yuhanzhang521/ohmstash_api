from typing import Any

import httpx
import pytest

from app.services import web_search
from app.services.web_search import SearchProviderSettings, SearchSnippetParser


def test_search_snippet_parser_reads_duckduckgo_lite_results() -> None:
    parser = SearchSnippetParser()
    parser.feed(
        """
        <a class="result-link" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpart">
            LIS3DHTR STMicroelectronics
        </a>
        <td class="result-snippet">
            Three-axis accelerometer in LGA package.
        </td>
        """
    )

    assert parser.results == [
        {
            "url": "https://example.com/part",
            "title": "LIS3DHTR STMicroelectronics",
            "snippet": "Three-axis accelerometer in LGA package.",
        }
    ]


def test_search_snippet_parser_reads_duckduckgo_html_results() -> None:
    parser = SearchSnippetParser()
    parser.feed(
        """
        <a class="result__a" href="https://example.com/mpu6050">
            MPU-6050 Product Specification
        </a>
        <a class="result__snippet" href="https://example.com/mpu6050">
            6-axis MotionTracking device with gyroscope and accelerometer.
        </a>
        """
    )

    assert parser.results == [
        {
            "url": "https://example.com/mpu6050",
            "title": "MPU-6050 Product Specification",
            "snippet": (
                "6-axis MotionTracking device with gyroscope and accelerometer."
            ),
        }
    ]


def test_brave_search_provider_maps_web_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request_json(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["provider_label"] == "brave"
        assert kwargs["headers"]["X-Subscription-Token"] == "brave-key"
        return {
            "web": {
                "results": [
                    {
                        "title": "LIS3DHTR - STMicroelectronics",
                        "url": "https://example.com/lis3dhtr",
                        "description": "MEMS digital output motion sensor.",
                    }
                ]
            }
        }

    monkeypatch.setattr(web_search, "_request_json", fake_request_json)
    results = web_search.fetch_search_snippets(
        "LIS3DHTR datasheet",
        provider_settings=SearchProviderSettings(
            name="Brave",
            provider="brave",
            api_key="brave-key",
        ),
    )

    assert results == [
        {
            "title": "LIS3DHTR - STMicroelectronics",
            "url": "https://example.com/lis3dhtr",
            "snippet": "MEMS digital output motion sensor.",
        }
    ]


def test_tavily_search_provider_maps_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request_json(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["provider_label"] == "tavily"
        assert kwargs["headers"]["Authorization"] == "Bearer tavily-key"
        return {
            "results": [
                {
                    "title": "AHT20 Datasheet",
                    "url": "https://example.com/aht20",
                    "content": "AHT20 is a digital humidity and temperature sensor.",
                }
            ]
        }

    monkeypatch.setattr(web_search, "_request_json", fake_request_json)
    results = web_search.fetch_search_snippets(
        "AHT20 datasheet",
        provider_settings=SearchProviderSettings(
            name="Tavily",
            provider="tavily",
            api_key="tavily-key",
        ),
    )

    assert results[0]["title"] == "AHT20 Datasheet"
    assert "humidity" in results[0]["snippet"]


def test_openai_web_search_provider_maps_response_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request_json(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["provider_label"] == "openai_web_search"
        assert kwargs["json"]["tools"] == [{"type": "web_search"}]
        return {
            "output_text": "INA226 is a current, voltage, and power monitor.",
            "sources": [
                {
                    "title": "INA226 product page",
                    "url": "https://example.com/ina226",
                }
            ],
        }

    monkeypatch.setattr(web_search, "_request_json", fake_request_json)
    results = web_search.fetch_search_snippets(
        "INA226 datasheet",
        provider_settings=SearchProviderSettings(
            name="OpenAI",
            provider="openai_web_search",
            api_key="openai-key",
            extra_config={"model_name": "gpt-4.1-mini"},
        ),
    )

    assert results == [
        {
            "title": "INA226 product page",
            "url": "https://example.com/ina226",
            "snippet": "INA226 is a current, voltage, and power monitor.",
        }
    ]


def test_request_json_surfaces_error_response_body(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def request(
            self,
            method: str,
            url: str,
            **_kwargs: Any,
        ) -> httpx.Response:
            return httpx.Response(
                400,
                json={"error": {"message": "Unsupported endpoint", "api_key": "secret-key"}},
                headers={"x-request-id": "req_123"},
                request=httpx.Request(method, url),
            )

    monkeypatch.setattr(web_search.httpx, "Client", FakeClient)
    caplog.set_level("WARNING", logger="app.services.web_search")

    with pytest.raises(web_search.SearchProviderError) as exc_info:
        web_search._request_json(
            method="POST",
            url="https://example.com/v1/responses",
            headers={},
            provider_label="openai_web_search",
            query="LIS3DHTR datasheet",
        )

    assert exc_info.value.status_code == 400
    assert "Unsupported endpoint" in str(exc_info.value)
    assert "request_id=req_123" in str(exc_info.value)
    assert "secret-key" not in str(exc_info.value)
    assert "[REDACTED]" in str(exc_info.value)


def test_validate_search_url_rejects_private_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_getaddrinfo(*_args: Any, **_kwargs: Any) -> list[tuple[Any, ...]]:
        return [(None, None, None, None, ("127.0.0.1", 443))]

    monkeypatch.setattr(web_search.socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(web_search.SearchProviderError, match="private network"):
        web_search.validate_search_url("https://metadata.local/search")


def test_validate_search_url_rejects_plain_http() -> None:
    with pytest.raises(web_search.SearchProviderError, match="must use https"):
        web_search.validate_search_url("http://example.com/search")
