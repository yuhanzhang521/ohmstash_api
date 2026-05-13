from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.run import build_uvicorn_config


def test_settings_use_http_port_by_default() -> None:
    settings = Settings(DATABASE_URL="postgresql://user:password@host/db")

    assert settings.service_scheme == "http"
    assert settings.service_port == 8000
    assert not settings.ssl_enabled


def test_settings_assembles_database_url_with_unmasked_password() -> None:
    settings = Settings(
        DATABASE_URL=None,
        POSTGRES_SERVER="db",
        POSTGRES_USER="ohmstash",
        POSTGRES_PASSWORD="secret-password",
        POSTGRES_DB="ohmstash",
    )

    assert "secret-password" in str(settings.DATABASE_URL)
    assert "***" not in str(settings.DATABASE_URL)


def test_settings_use_https_port_when_enabled() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        HTTPS_ENABLED=True,
        HTTPS_PORT=9443,
        SSL_CERTFILE="/etc/ssl/cert.pem",
        SSL_KEYFILE="/etc/ssl/key.pem",
    )

    assert settings.service_scheme == "https"
    assert settings.service_port == 9443
    assert settings.ssl_enabled


def test_uvicorn_config_uses_configured_server_settings(
    monkeypatch: Any,
) -> None:
    runtime_settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        SERVER_HOST="127.0.0.1",
        HTTP_PORT=9000,
    )
    monkeypatch.setattr("app.run.settings", runtime_settings)

    config = build_uvicorn_config()

    assert config == {
        "app": "app.main:app",
        "host": "127.0.0.1",
        "port": 9000,
    }


def test_uvicorn_config_generates_self_signed_certificate_for_https(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    runtime_settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        HTTPS_ENABLED=True,
        HTTPS_PORT=9443,
    )
    cert_dir = tmp_path / "certs"
    certfile = cert_dir / "selfsigned.crt"
    keyfile = cert_dir / "selfsigned.key"
    monkeypatch.setattr("app.run.settings", runtime_settings)
    monkeypatch.setattr("app.core.service_config.CERT_DIR", cert_dir)
    monkeypatch.setattr("app.core.service_config.SELF_SIGNED_CERT_FILE", certfile)
    monkeypatch.setattr("app.core.service_config.SELF_SIGNED_KEY_FILE", keyfile)

    config = build_uvicorn_config()

    assert config["port"] == 9443
    assert config["ssl_certfile"] == certfile.as_posix()
    assert config["ssl_keyfile"] == keyfile.as_posix()
    assert certfile.exists()
    assert keyfile.exists()


def test_uvicorn_config_adds_ssl_files_when_configured(
    monkeypatch: Any,
) -> None:
    runtime_settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        HTTPS_ENABLED=True,
        HTTPS_PORT=9443,
        SSL_CERTFILE="/etc/ssl/cert.pem",
        SSL_KEYFILE="/etc/ssl/key.pem",
    )
    monkeypatch.setattr("app.run.settings", runtime_settings)

    config = build_uvicorn_config()

    assert config["port"] == 9443
    assert config["ssl_certfile"] == "/etc/ssl/cert.pem"
    assert config["ssl_keyfile"] == "/etc/ssl/key.pem"


def test_uvicorn_config_uses_http_backend_for_caddy_acme(
    monkeypatch: Any,
) -> None:
    runtime_settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        HTTPS_ENABLED=True,
        HTTPS_PORT=443,
        HTTPS_CERTIFICATE_SOURCE="acme",
        HTTP_PORT=80,
    )
    monkeypatch.setattr("app.run.settings", runtime_settings)

    config = build_uvicorn_config()

    assert config == {
        "app": "app.main:app",
        "host": "0.0.0.0",
        "port": 80,
    }
