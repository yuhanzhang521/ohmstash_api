from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import settings


def test_system_config_can_be_read(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/system/config")

    assert response.status_code == 200
    content = response.json()
    assert content["host"] == settings.SERVER_HOST
    assert content["http_port"] == settings.HTTP_PORT
    assert content["https_enabled"] == settings.HTTPS_ENABLED
    assert content["https_port"] == settings.HTTPS_PORT
    assert content["certificate_source"] == settings.HTTPS_CERTIFICATE_SOURCE
    assert content["scheme"] == settings.service_scheme
    assert content["active_port"] == settings.service_port
    assert "using_self_signed_certificate" in content
    assert "acme_cloudflare_api_token_configured" in content
    assert "restart_required" in content


def test_system_config_can_be_updated(
    client: TestClient,
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    original_host = settings.SERVER_HOST
    original_http_port = settings.HTTP_PORT
    original_https_enabled = settings.HTTPS_ENABLED
    original_https_port = settings.HTTPS_PORT
    original_certificate_source = settings.HTTPS_CERTIFICATE_SOURCE
    original_certfile = settings.SSL_CERTFILE
    original_keyfile = settings.SSL_KEYFILE
    original_acme_challenge_type = settings.ACME_CHALLENGE_TYPE
    original_acme_domain = settings.ACME_DOMAIN
    original_acme_email = settings.ACME_EMAIL
    original_acme_cloudflare_api_token = settings.ACME_CLOUDFLARE_API_TOKEN
    original_caddy_config_path = settings.CADDY_CONFIG_PATH
    monkeypatch.setattr("app.core.service_config.ENV_FILE", env_file)
    settings.CADDY_CONFIG_PATH = (tmp_path / "Caddyfile").as_posix()

    try:
        response = client.put(
            f"{settings.API_V1_STR}/system/config",
            json={
                "host": "127.0.0.1",
                "http_port": 9000,
                "https_enabled": True,
                "https_port": 9443,
                "certificate_source": "path",
                "ssl_certfile": "/tmp/cert.pem",
                "ssl_keyfile": "/tmp/key.pem",
            },
        )

        assert response.status_code == 200
        content = response.json()
        assert content["host"] == "127.0.0.1"
        assert content["http_port"] == 9000
        assert content["https_enabled"]
        assert content["https_port"] == 9443
        assert content["restart_required"]
        assert "HTTP_PORT=9000" in env_file.read_text(encoding="utf-8")
    finally:
        settings.SERVER_HOST = original_host
        settings.HTTP_PORT = original_http_port
        settings.HTTPS_ENABLED = original_https_enabled
        settings.HTTPS_PORT = original_https_port
        settings.HTTPS_CERTIFICATE_SOURCE = original_certificate_source
        settings.SSL_CERTFILE = original_certfile
        settings.SSL_KEYFILE = original_keyfile
        settings.ACME_CHALLENGE_TYPE = original_acme_challenge_type
        settings.ACME_DOMAIN = original_acme_domain
        settings.ACME_EMAIL = original_acme_email
        settings.ACME_CLOUDFLARE_API_TOKEN = original_acme_cloudflare_api_token
        settings.CADDY_CONFIG_PATH = original_caddy_config_path


def test_logging_config_can_be_read_and_updated(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/system/logs/config")
    assert response.status_code == 200
    content = response.json()
    assert content["level"]
    assert content["log_file_path"].endswith("ohmstash.log")

    update_response = client.put(
        f"{settings.API_V1_STR}/system/logs/config",
        json={"level": "WARNING"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["level"] == "WARNING"

    logs_response = client.get(f"{settings.API_V1_STR}/system/logs?limit=10")
    assert logs_response.status_code == 200
    assert isinstance(logs_response.json()["lines"], list)
    assert isinstance(logs_response.json()["total_lines"], int)

    restore_response = client.put(
        f"{settings.API_V1_STR}/system/logs/config",
        json={"level": "INFO"},
    )
    assert restore_response.status_code == 200
