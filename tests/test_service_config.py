import os
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.core.service_config import build_caddyfile, save_server_config


def test_save_server_config_updates_env_and_runtime_settings(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql://user:password@host/db\n"
        "SERVER_HOST=0.0.0.0\n"
        "HTTP_PORT=8000\n",
        encoding="utf-8",
    )
    runtime_settings = Settings(DATABASE_URL="postgresql://user:password@host/db")
    runtime_settings.CADDY_CONFIG_PATH = (tmp_path / "Caddyfile").as_posix()
    monkeypatch.setattr("app.core.service_config.ENV_FILE", env_file)
    monkeypatch.setattr("app.core.service_config.settings", runtime_settings)

    save_server_config(
        host="127.0.0.1",
        http_port=9000,
        https_enabled=True,
        https_port=9443,
        ssl_certfile="/tmp/cert.pem",
        ssl_keyfile="/tmp/key.pem",
        ssl_cert_pem=None,
        ssl_key_pem=None,
    )

    content = env_file.read_text(encoding="utf-8")
    assert "SERVER_HOST=127.0.0.1" in content
    assert "HTTP_PORT=9000" in content
    assert "HTTPS_ENABLED=true" in content
    assert "HTTPS_PORT=9443" in content
    assert "HTTPS_CERTIFICATE_SOURCE=path" in content
    assert "SSL_CERTFILE=/tmp/cert.pem" in content
    assert "SSL_KEYFILE=/tmp/key.pem" in content
    assert runtime_settings.SERVER_HOST == "127.0.0.1"
    assert runtime_settings.HTTP_PORT == 9000
    assert runtime_settings.HTTPS_ENABLED
    assert runtime_settings.HTTPS_PORT == 9443


def test_save_server_config_writes_pasted_certificate_pair(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    certfile = tmp_path / "certs" / "uploaded.crt"
    keyfile = tmp_path / "certs" / "uploaded.key"
    runtime_settings = Settings(DATABASE_URL="postgresql://user:password@host/db")
    runtime_settings.CADDY_CONFIG_PATH = (tmp_path / "Caddyfile").as_posix()
    monkeypatch.setattr("app.core.service_config.ENV_FILE", env_file)
    monkeypatch.setattr("app.core.service_config.UPLOADED_CERT_FILE", certfile)
    monkeypatch.setattr("app.core.service_config.UPLOADED_KEY_FILE", keyfile)
    monkeypatch.setattr("app.core.service_config.CERT_DIR", certfile.parent)
    monkeypatch.setattr("app.core.service_config.settings", runtime_settings)

    save_server_config(
        host="0.0.0.0",
        http_port=8000,
        https_enabled=True,
        https_port=8443,
        ssl_certfile=None,
        ssl_keyfile=None,
        ssl_cert_pem="-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----",
        ssl_key_pem="-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
    )

    assert certfile.read_text(encoding="utf-8").endswith("-----END CERTIFICATE-----\n")
    assert keyfile.read_text(encoding="utf-8").endswith("-----END PRIVATE KEY-----\n")
    if os.name != "nt":
        assert keyfile.stat().st_mode & 0o777 == 0o600
    content = env_file.read_text(encoding="utf-8")
    assert "HTTPS_CERTIFICATE_SOURCE=path" in content
    assert f"SSL_CERTFILE={certfile.as_posix()}" in content
    assert f"SSL_KEYFILE={keyfile.as_posix()}" in content


def test_save_server_config_keeps_backend_http_port_for_acme(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    caddy_file = tmp_path / "Caddyfile"
    runtime_settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        CADDY_CONFIG_PATH=caddy_file.as_posix(),
        CADDY_BACKEND_HOST="api",
    )
    monkeypatch.setattr("app.core.service_config.ENV_FILE", env_file)
    monkeypatch.setattr("app.core.service_config.settings", runtime_settings)

    save_server_config(
        host="0.0.0.0",
        http_port=8000,
        https_enabled=True,
        https_port=8443,
        ssl_certfile="/tmp/old.crt",
        ssl_keyfile="/tmp/old.key",
        ssl_cert_pem=None,
        ssl_key_pem=None,
        certificate_source="acme",
        acme_challenge_type="http-01",
        acme_domain="ohmstash.example.com",
        acme_email="admin@example.com",
        acme_cloudflare_api_token=None,
    )

    content = env_file.read_text(encoding="utf-8")
    assert "HTTP_PORT=8000" in content
    assert "HTTPS_PORT=443" in content
    assert "HTTPS_CERTIFICATE_SOURCE=acme" in content
    assert "ACME_CHALLENGE_TYPE=http-01" in content
    assert "ACME_DOMAIN=ohmstash.example.com" in content
    assert "SSL_CERTFILE=" in content
    assert "SSL_KEYFILE=" in content
    assert runtime_settings.HTTP_PORT == 8000
    assert runtime_settings.HTTPS_PORT == 443
    assert caddy_file.read_text(encoding="utf-8") == (
        "{\n"
        "    email admin@example.com\n"
        "}\n"
        "\n"
        "ohmstash.example.com {\n"
        "    encode zstd gzip\n"
        "    reverse_proxy http://api:8000\n"
        "}\n"
    )


def test_save_server_config_writes_acme_dns_cloudflare_config(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    caddy_file = tmp_path / "Caddyfile"
    runtime_settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        CADDY_CONFIG_PATH=caddy_file.as_posix(),
        CADDY_BACKEND_HOST="api",
    )
    monkeypatch.setattr("app.core.service_config.ENV_FILE", env_file)
    monkeypatch.setattr("app.core.service_config.settings", runtime_settings)

    save_server_config(
        host="0.0.0.0",
        http_port=8000,
        https_enabled=True,
        https_port=8443,
        ssl_certfile=None,
        ssl_keyfile=None,
        ssl_cert_pem=None,
        ssl_key_pem=None,
        certificate_source="acme",
        acme_challenge_type="dns-01",
        acme_domain="ohmstash.example.com",
        acme_email=None,
        acme_cloudflare_api_token="cf-token",
    )

    assert runtime_settings.HTTP_PORT == 8000
    assert runtime_settings.HTTPS_PORT == 443
    assert runtime_settings.ACME_CLOUDFLARE_API_TOKEN == "cf-token"
    caddy_content = caddy_file.read_text(encoding="utf-8")
    assert "dns cloudflare {env.ACME_CLOUDFLARE_API_TOKEN}" in caddy_content
    assert "reverse_proxy http://api:8000" in caddy_content


def test_build_caddyfile_proxies_to_https_backend_when_not_acme() -> None:
    runtime_settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        HTTPS_ENABLED=True,
        HTTPS_PORT=8443,
        SSL_CERTFILE="/etc/ssl/cert.pem",
        SSL_KEYFILE="/etc/ssl/key.pem",
        CADDY_BACKEND_HOST="api",
    )

    caddyfile = build_caddyfile(runtime_settings)

    assert "reverse_proxy https://api:8443" in caddyfile
    assert "tls_insecure_skip_verify" in caddyfile


def test_save_server_config_rejects_updates_in_reverse_proxy_mode(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    caddy_file = tmp_path / "Caddyfile"
    runtime_settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        DEPLOYMENT_MODE="reverse_proxy",
        CADDY_CONFIG_PATH=caddy_file.as_posix(),
    )
    monkeypatch.setattr("app.core.service_config.ENV_FILE", env_file)
    monkeypatch.setattr("app.core.service_config.settings", runtime_settings)

    with pytest.raises(ValueError, match="reverse proxy"):
        save_server_config(
            host="0.0.0.0",
            http_port=8000,
            https_enabled=True,
            https_port=8443,
            ssl_certfile=None,
            ssl_keyfile=None,
            ssl_cert_pem=None,
            ssl_key_pem=None,
        )

    assert not caddy_file.exists()
    assert not env_file.exists()


def test_reverse_proxy_mode_disables_ssl_and_acme_properties() -> None:
    runtime_settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        DEPLOYMENT_MODE="reverse_proxy",
        HTTPS_ENABLED=True,
        HTTPS_PORT=8443,
        HTTPS_CERTIFICATE_SOURCE="acme",
        SSL_CERTFILE="/etc/ssl/cert.pem",
        SSL_KEYFILE="/etc/ssl/key.pem",
    )

    assert runtime_settings.behind_reverse_proxy
    assert runtime_settings.service_scheme == "http"
    assert runtime_settings.service_port == runtime_settings.HTTP_PORT
    assert not runtime_settings.ssl_enabled
    assert not runtime_settings.uses_caddy_acme

