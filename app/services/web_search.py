import ipaddress
import json
import logging
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from threading import Lock
from time import monotonic, perf_counter, sleep
from typing import Any, List, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx

from app.core.log_sanitizer import redact_sensitive_data

DEFAULT_DUCKDUCKGO_LITE_URL = "https://lite.duckduckgo.com/lite/?q={query}"
DEFAULT_DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/?q={query}"
DEFAULT_BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
DEFAULT_TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_WEB_SEARCH_MODEL = "gpt-4.1-mini"
DEFAULT_SEARCH_TIMEOUT_SECONDS = 60.0
DEFAULT_SEARCH_REQUEST_INTERVAL_SECONDS = 2.0
DEFAULT_SEARCH_RETRY_DELAY_SECONDS = 4.0
DEFAULT_SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

logger = logging.getLogger(__name__)
request_lock = Lock()
last_request_at = 0.0


class SearchProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        errors: Optional[List[str]] = None,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.errors = errors or [message]
        self.status_code = status_code


def validate_search_url(url: str) -> None:
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https":
        raise SearchProviderError("Search provider URL must use https")
    if not parsed_url.hostname:
        raise SearchProviderError("Search provider URL must include a hostname")
    if _is_private_hostname(parsed_url.hostname):
        raise SearchProviderError("Search provider URL cannot target private network hosts")


def _is_private_hostname(hostname: str) -> bool:
    try:
        addresses = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SearchProviderError("Search provider URL hostname cannot be resolved") from exc

    for address in addresses:
        ip_address = ipaddress.ip_address(address[4][0])
        if not ip_address.is_global:
            return True
    return False


def _validated_search_url(url: str) -> str:
    validate_search_url(url)
    return url


@dataclass
class SearchProviderSettings:
    name: str
    provider: str
    api_key: Optional[str] = None
    extra_config: dict[str, Any] = field(default_factory=dict)


class SearchSnippetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: List[dict[str, str]] = []
        self.current_link: Optional[dict[str, str]] = None
        self.in_result_link = False
        self.in_snippet = False
        self.text_parts: List[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, Optional[str]]],
    ) -> None:
        attr_map = dict(attrs)
        class_name = attr_map.get("class") or ""
        if tag == "a" and (
            "result-link" in class_name or "result__a" in class_name
        ):
            self.in_result_link = True
            self.text_parts = []
            self.current_link = {
                "url": _normalize_result_url(attr_map.get("href") or "")
            }
        elif (
            tag in {"a", "td", "div"}
            and (
                "result-snippet" in class_name
                or "result__snippet" in class_name
            )
        ):
            self.in_snippet = True
            self.text_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.in_result_link:
            title = _normalize_text(" ".join(self.text_parts))
            if self.current_link is not None:
                self.current_link["title"] = title
                self.results.append(self.current_link)
            self.in_result_link = False
            self.current_link = None
            self.text_parts = []
        elif tag in {"a", "td", "div"} and self.in_snippet:
            snippet = _normalize_text(" ".join(self.text_parts))
            if snippet and self.results:
                self.results[-1]["snippet"] = snippet
            self.in_snippet = False
            self.text_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_result_link or self.in_snippet:
            self.text_parts.append(data)


def fetch_search_snippets(
    query: str,
    *,
    limit: int = 5,
    url_template: Optional[str] = None,
    provider_settings: Optional[SearchProviderSettings] = None,
) -> List[dict[str, str]]:
    provider_name = (provider_settings.provider if provider_settings else "duckduckgo").lower()
    if provider_name == "brave":
        return _fetch_brave_search_snippets(
            query,
            limit=limit,
            provider_settings=_require_provider_settings(provider_settings),
        )
    if provider_name == "tavily":
        return _fetch_tavily_search_snippets(
            query,
            limit=limit,
            provider_settings=_require_provider_settings(provider_settings),
        )
    if provider_name == "openai_web_search":
        return _fetch_openai_web_search_snippets(
            query,
            limit=limit,
            provider_settings=_require_provider_settings(provider_settings),
        )
    return _fetch_duckduckgo_snippets(
        query,
        limit=limit,
        url_template=url_template,
    )


def _fetch_duckduckgo_snippets(
    query: str,
    *,
    limit: int,
    url_template: Optional[str],
) -> List[dict[str, str]]:
    templates = (
        [url_template]
        if url_template
        else [DEFAULT_DUCKDUCKGO_LITE_URL, DEFAULT_DUCKDUCKGO_HTML_URL]
    )
    snippets: List[dict[str, str]] = []
    errors: List[str] = []
    with httpx.Client(timeout=DEFAULT_SEARCH_TIMEOUT_SECONDS) as client:
        for template in templates:
            if not template:
                continue
            url = _validated_search_url(template.format(query=quote_plus(query)))
            response: Optional[httpx.Response] = None
            for attempt in range(1, 3):
                _wait_for_rate_limit()
                started_at = perf_counter()
                try:
                    response = client.get(
                        url,
                        headers=DEFAULT_SEARCH_HEADERS,
                        follow_redirects=True,
                    )
                except httpx.RequestError as exc:
                    message = f"{_host_label(url)} request failed: {exc}"
                    errors.append(message)
                    logger.warning(
                        "Web search request failed query=%r attempt=%s error=%s",
                        query,
                        attempt,
                        exc,
                    )
                    continue

                latency_ms = int((perf_counter() - started_at) * 1000)
                logger.info(
                    "Web search response query=%r host=%s status=%s latency_ms=%s attempt=%s",
                    query,
                    _host_label(url),
                    response.status_code,
                    latency_ms,
                    attempt,
                )
                if response.status_code not in {202, 429} or attempt == 2:
                    break

                retry_delay = _retry_delay_seconds(response)
                logger.warning(
                    "Web search throttled query=%r status=%s retry_delay=%s",
                    query,
                    response.status_code,
                    retry_delay,
                )
                sleep(retry_delay)

            if response is None:
                continue
            if response.status_code != 200:
                message = f"{_host_label(url)} HTTP {response.status_code}"
                errors.append(message)
                logger.warning(
                    "Web search returned non-200 status query=%r status=%s host=%s",
                    query,
                    response.status_code,
                    _host_label(url),
                )
                continue

            parser = SearchSnippetParser()
            parser.feed(response.text)
            snippets = _deduplicate_results(parser.results)
            logger.info(
                "Web search parsed query=%r host=%s results=%s",
                query,
                _host_label(url),
                len(snippets),
            )
            if snippets:
                break

    if not snippets and errors:
        raise SearchProviderError("; ".join(errors), errors=errors)

    return snippets[:limit]


def _fetch_brave_search_snippets(
    query: str,
    *,
    limit: int,
    provider_settings: SearchProviderSettings,
) -> List[dict[str, str]]:
    if not provider_settings.api_key:
        raise SearchProviderError("Brave Search API key is required")
    url = _validated_search_url(provider_settings.extra_config.get("base_url") or DEFAULT_BRAVE_SEARCH_URL)
    params = {
        "q": query,
        "count": min(max(limit, 1), 20),
        "country": provider_settings.extra_config.get("country", "US"),
        "search_lang": provider_settings.extra_config.get("search_lang", "en"),
        "safesearch": provider_settings.extra_config.get("safesearch", "off"),
    }
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": provider_settings.api_key,
    }
    data = _request_json(
        method="GET",
        url=url,
        headers=headers,
        params=params,
        provider_label="brave",
        query=query,
    )
    results = data.get("web", {}).get("results", [])
    snippets = [
        {
            "title": _normalize_text(item.get("title") or ""),
            "url": item.get("url") or "",
            "snippet": _normalize_text(
                item.get("description")
                or item.get("snippet")
                or ""
            ),
        }
        for item in results
        if isinstance(item, dict)
    ]
    return _deduplicate_results(snippets)[:limit]


def _fetch_tavily_search_snippets(
    query: str,
    *,
    limit: int,
    provider_settings: SearchProviderSettings,
) -> List[dict[str, str]]:
    if not provider_settings.api_key:
        raise SearchProviderError("Tavily API key is required")
    url = _validated_search_url(provider_settings.extra_config.get("base_url") or DEFAULT_TAVILY_SEARCH_URL)
    payload = {
        "query": query,
        "max_results": min(max(limit, 1), 20),
        "search_depth": provider_settings.extra_config.get("search_depth", "basic"),
        "include_answer": False,
        "include_raw_content": False,
    }
    headers = {
        "Authorization": f"Bearer {provider_settings.api_key}",
        "Content-Type": "application/json",
    }
    data = _request_json(
        method="POST",
        url=url,
        headers=headers,
        json=payload,
        provider_label="tavily",
        query=query,
    )
    snippets = [
        {
            "title": _normalize_text(item.get("title") or ""),
            "url": item.get("url") or "",
            "snippet": _normalize_text(item.get("content") or ""),
        }
        for item in data.get("results", [])
        if isinstance(item, dict)
    ]
    return _deduplicate_results(snippets)[:limit]


def _fetch_openai_web_search_snippets(
    query: str,
    *,
    limit: int,
    provider_settings: SearchProviderSettings,
) -> List[dict[str, str]]:
    if not provider_settings.api_key:
        raise SearchProviderError("OpenAI API key is required")
    base_url = _validated_search_url(
        provider_settings.extra_config.get("base_url") or DEFAULT_OPENAI_BASE_URL,
    )
    model_name = (
        provider_settings.extra_config.get("model_name")
        or DEFAULT_OPENAI_WEB_SEARCH_MODEL
    )
    timeout_seconds = float(
        provider_settings.extra_config.get(
            "timeout_seconds",
            DEFAULT_SEARCH_TIMEOUT_SECONDS,
        )
    )
    payload = {
        "model": model_name,
        "tools": [{"type": "web_search"}],
        "input": (
            "Search the web for this electronic component query. "
            "Return a concise Chinese summary of official or datasheet-like "
            f"sources, including key specs when available: {query}"
        ),
    }
    logger.info(
        "OpenAI web search request prepared base_url=%s model=%s timeout_seconds=%s",
        base_url,
        model_name,
        timeout_seconds,
    )
    headers = {
        "Authorization": f"Bearer {provider_settings.api_key}",
        "Content-Type": "application/json",
    }
    data = _request_json(
        method="POST",
        url=f"{base_url.rstrip('/')}/responses",
        headers=headers,
        json=payload,
        provider_label="openai_web_search",
        query=query,
        timeout_seconds=timeout_seconds,
    )
    summary_text = _extract_openai_response_text(data)
    sources = _extract_openai_sources(data)
    if not summary_text and not sources:
        return []
    if not sources:
        return [
            {
                "title": "OpenAI web search summary",
                "url": "",
                "snippet": _normalize_text(summary_text),
            }
        ][:limit]
    snippets = [
        {
            "title": source.get("title") or "OpenAI web search source",
            "url": source.get("url") or "",
            "snippet": _normalize_text(summary_text),
        }
        for source in sources
    ]
    return _deduplicate_results(snippets)[:limit]


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _require_provider_settings(
    provider_settings: Optional[SearchProviderSettings],
) -> SearchProviderSettings:
    if not provider_settings:
        return SearchProviderSettings(name="DuckDuckGo HTML", provider="duckduckgo")
    return provider_settings


def _request_json(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    provider_label: str,
    query: str,
    params: Optional[dict[str, Any]] = None,
    json: Optional[dict[str, Any]] = None,
    timeout_seconds: float = DEFAULT_SEARCH_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    started_at = perf_counter()
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
            )
    except httpx.RequestError as exc:
        logger.warning(
            "Search API request failed provider=%s query=%r error=%s",
            provider_label,
            query,
            exc,
        )
        raise SearchProviderError(f"{provider_label} request failed: {exc}") from exc

    latency_ms = int((perf_counter() - started_at) * 1000)
    logger.info(
        "Search API response provider=%s query=%r status=%s latency_ms=%s",
        provider_label,
        query,
        response.status_code,
        latency_ms,
    )
    if response.status_code >= 400:
        body = _format_response_body(response)
        request_id = response.headers.get("x-request-id") or response.headers.get(
            "X-Request-Id"
        )
        message = f"{provider_label} HTTP {response.status_code}"
        if request_id:
            message = f"{message} request_id={request_id}"
        if body:
            message = f"{message}: {body}"
        logger.warning(
            "Search API error response provider=%s query=%r status=%s request_id=%s body=%s",
            provider_label,
            query,
            response.status_code,
            request_id or "",
            body,
        )
        raise SearchProviderError(
            message,
            errors=[message],
            status_code=response.status_code,
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise SearchProviderError(
            f"{provider_label} response is not valid JSON",
            status_code=response.status_code,
        ) from exc
    if not isinstance(data, dict):
        raise SearchProviderError(f"{provider_label} response is not a JSON object")
    return data


def _format_response_body(
    response: httpx.Response,
    *,
    max_length: int = 800,
) -> str:
    text = response.text or ""
    try:
        data = response.json()
    except ValueError:
        pass
    else:
        if isinstance(data, dict):
            text = json.dumps(redact_sensitive_data(data), ensure_ascii=False)
    return _normalize_text(text)[:max_length]


def _normalize_result_url(value: str) -> str:
    parsed = urlparse(value)
    query = parse_qs(parsed.query)
    redirect_target = query.get("uddg", [""])[0]
    if redirect_target:
        return unquote(redirect_target)
    return value


def _host_label(value: str) -> str:
    return urlparse(value).netloc or value


def _extract_openai_response_text(data: dict[str, Any]) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str):
        return output_text
    text_parts: List[str] = []
    for output_item in data.get("output", []):
        if not isinstance(output_item, dict):
            continue
        for content_item in output_item.get("content", []):
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str):
                text_parts.append(text)
    return "\n".join(text_parts)


def _extract_openai_sources(data: dict[str, Any]) -> List[dict[str, str]]:
    sources: List[dict[str, str]] = []
    for source in data.get("sources", []):
        if isinstance(source, dict) and source.get("url"):
            sources.append(
                {
                    "title": source.get("title") or source.get("url") or "",
                    "url": source.get("url") or "",
                }
            )
    for output_item in data.get("output", []):
        if not isinstance(output_item, dict):
            continue
        for content_item in output_item.get("content", []):
            if not isinstance(content_item, dict):
                continue
            for annotation in content_item.get("annotations", []):
                if not isinstance(annotation, dict):
                    continue
                url = annotation.get("url")
                if url:
                    sources.append(
                        {
                            "title": annotation.get("title") or url,
                            "url": url,
                        }
                    )
    return _deduplicate_results(sources)


def _retry_delay_seconds(response: httpx.Response) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(float(retry_after), DEFAULT_SEARCH_RETRY_DELAY_SECONDS)
        except ValueError:
            return DEFAULT_SEARCH_RETRY_DELAY_SECONDS
    return DEFAULT_SEARCH_RETRY_DELAY_SECONDS


def _wait_for_rate_limit() -> None:
    global last_request_at
    with request_lock:
        now = monotonic()
        elapsed = now - last_request_at
        if elapsed < DEFAULT_SEARCH_REQUEST_INTERVAL_SECONDS:
            sleep(DEFAULT_SEARCH_REQUEST_INTERVAL_SECONDS - elapsed)
        last_request_at = monotonic()


def _deduplicate_results(results: List[dict[str, str]]) -> List[dict[str, str]]:
    deduplicated: List[dict[str, str]] = []
    seen_urls: set[str] = set()
    for result in results:
        url = result.get("url", "")
        title = result.get("title", "")
        if not title:
            continue
        key = url or title
        if key in seen_urls:
            continue
        seen_urls.add(key)
        deduplicated.append(result)
    return deduplicated
