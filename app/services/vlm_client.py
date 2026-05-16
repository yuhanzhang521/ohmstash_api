import base64
import ipaddress
import json
import logging
import re
import socket
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.core.log_sanitizer import redact_sensitive_text
from app.models.vlm_provider_config import VlmProviderConfig

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TIMEOUT_SECONDS = 90.0

logger = logging.getLogger(__name__)


class VlmClientError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body


def validate_base_url(base_url: str) -> None:
    parsed_url = urlparse(base_url)
    if parsed_url.scheme != "https":
        raise VlmClientError("VLM base_url must use https")
    if not parsed_url.hostname:
        raise VlmClientError("VLM base_url must include a hostname")
    if _is_private_hostname(parsed_url.hostname):
        raise VlmClientError("VLM base_url cannot target private network hosts")


def _is_private_hostname(hostname: str) -> bool:
    try:
        addresses = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise VlmClientError("VLM base_url hostname cannot be resolved") from exc

    for address in addresses:
        ip_address = ipaddress.ip_address(address[4][0])
        if ip_address.is_loopback or ip_address.is_link_local:
            return True
    return False


def get_base_url(config: VlmProviderConfig) -> str:
    if config.base_url:
        base_url = config.base_url.rstrip("/")
        validate_base_url(base_url)
        return base_url

    if config.provider == "openai":
        return DEFAULT_OPENAI_BASE_URL

    raise VlmClientError("VLM base_url is required for this provider")


def build_image_data_url(content: bytes, content_type: str) -> str:
    encoded_content = base64.b64encode(content).decode("ascii")
    return f"data:{content_type};base64,{encoded_content}"


def request_chat_completion(
    *,
    config: VlmProviderConfig,
    messages: List[Dict[str, Any]],
    max_tokens: Optional[int] = None,
) -> Tuple[Dict[str, Any], int]:
    if not config.is_active:
        raise VlmClientError("VLM config is disabled")
    if not config.model_name:
        raise VlmClientError("VLM model_name is required")

    extra_config = config.extra_config or {}
    timeout_seconds = float(extra_config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
    request_max_tokens = max_tokens or int(extra_config.get("max_tokens", 800))
    payload: Dict[str, Any] = {
        "model": config.model_name,
        "messages": messages,
        "temperature": extra_config.get("temperature", 0),
        "max_tokens": request_max_tokens,
    }

    for key in ("top_p", "response_format"):
        if key in extra_config:
            payload[key] = extra_config[key]

    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    logger.info(
        "VLM request started provider=%s model=%s timeout_seconds=%s max_tokens=%s",
        config.provider,
        config.model_name,
        timeout_seconds,
        request_max_tokens,
    )
    started_at = perf_counter()
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(
                f"{get_base_url(config)}/chat/completions",
                headers=headers,
                json=payload,
            )
    except httpx.RequestError as exc:
        logger.warning("VLM request failed provider=%s error=%s", config.provider, exc)
        raise VlmClientError(f"VLM request failed: {exc}") from exc

    latency_ms = int((perf_counter() - started_at) * 1000)
    logger.info(
        "VLM response received provider=%s model=%s status=%s latency_ms=%s",
        config.provider,
        config.model_name,
        response.status_code,
        latency_ms,
    )
    if response.status_code >= 400:
        response_body = redact_sensitive_text(response.text)[:1000]
        logger.warning(
            "VLM request returned HTTP error provider=%s status=%s body=%s",
            config.provider,
            response.status_code,
            response_body[:500],
        )
        raise VlmClientError(
            f"VLM request returned HTTP {response.status_code}",
            status_code=response.status_code,
            response_body=response_body,
        )

    try:
        return response.json(), latency_ms
    except json.JSONDecodeError as exc:
        raise VlmClientError("VLM response is not valid JSON") from exc


def extract_message_text(response: Dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""

    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                text_parts.append(part["text"])
        return "\n".join(text_parts)
    return ""


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    stripped_text = text.strip()
    fenced_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        stripped_text,
        re.DOTALL,
    )
    if fenced_match:
        stripped_text = fenced_match.group(1)

    candidates = [stripped_text]
    start = stripped_text.find("{")
    end = stripped_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(stripped_text[start:end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
