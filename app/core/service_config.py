import ipaddress
import os
import re
import socket
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.core.config import Settings, settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
CERT_DIR = PROJECT_ROOT / "certs"
SELF_SIGNED_CERT_FILE = CERT_DIR / "ohmstash-selfsigned.crt"
SELF_SIGNED_KEY_FILE = CERT_DIR / "ohmstash-selfsigned.key"
UPLOADED_CERT_FILE = CERT_DIR / "ohmstash-ui.crt"
UPLOADED_KEY_FILE = CERT_DIR / "ohmstash-ui.key"
CERTIFICATE_SOURCE_MODES = {"self-signed", "path", "upload", "paste", "acme"}
ACME_CHALLENGE_TYPES = {"http-01", "dns-01"}
ACME_HTTPS_PORT = 443
PRIVATE_KEY_FILE_MODE = 0o600
SERVER_CONFIG_KEYS = (
    "SERVER_HOST",
    "HTTP_PORT",
    "HTTPS_ENABLED",
    "HTTPS_PORT",
    "HTTPS_CERTIFICATE_SOURCE",
    "SSL_CERTFILE",
    "SSL_KEYFILE",
    "ACME_CHALLENGE_TYPE",
    "ACME_DOMAIN",
    "ACME_EMAIL",
    "ACME_CLOUDFLARE_API_TOKEN",
    "CADDY_CONFIG_PATH",
    "CADDY_BACKEND_HOST",
)

restart_required = False


def get_effective_ssl_files(
    target_settings: Settings,
) -> tuple[Optional[str], Optional[str], bool]:
    if target_settings.behind_reverse_proxy:
        return None, None, False
    if (
        not target_settings.HTTPS_ENABLED
        or target_settings.HTTPS_CERTIFICATE_SOURCE.lower() == "acme"
    ):
        return None, None, False
    if target_settings.ssl_enabled:
        return target_settings.SSL_CERTFILE, target_settings.SSL_KEYFILE, False
    ensure_self_signed_certificate(target_settings.SERVER_HOST)
    return (
        SELF_SIGNED_CERT_FILE.as_posix(),
        SELF_SIGNED_KEY_FILE.as_posix(),
        True,
    )


def save_server_config(
    *,
    host: str,
    http_port: int,
    https_enabled: bool,
    https_port: int,
    ssl_certfile: Optional[str],
    ssl_keyfile: Optional[str],
    ssl_cert_pem: Optional[str],
    ssl_key_pem: Optional[str],
    certificate_source: str = "self-signed",
    acme_challenge_type: Optional[str] = None,
    acme_domain: Optional[str] = None,
    acme_email: Optional[str] = None,
    acme_cloudflare_api_token: Optional[str] = None,
) -> None:
    if settings.behind_reverse_proxy:
        raise ValueError(
            "Server configuration is managed by the external reverse proxy"
            " in reverse_proxy deployment mode",
        )
    source = normalize_certificate_source(certificate_source)
    challenge_type = normalize_acme_challenge_type(
        acme_challenge_type or settings.ACME_CHALLENGE_TYPE,
    )
    domain = (acme_domain if acme_domain is not None else settings.ACME_DOMAIN or "").strip()
    email = (acme_email if acme_email is not None else settings.ACME_EMAIL or "").strip()
    cloudflare_token = (
        acme_cloudflare_api_token
        if acme_cloudflare_api_token is not None
        else settings.ACME_CLOUDFLARE_API_TOKEN or ""
    ).strip()
    certfile = (ssl_certfile or "").strip()
    keyfile = (ssl_keyfile or "").strip()
    cert_pem = (ssl_cert_pem or "").strip()
    key_pem = (ssl_key_pem or "").strip()
    if source == "self-signed":
        if cert_pem or key_pem:
            source = "paste"
        elif certfile or keyfile:
            source = "path"

    if https_enabled and source == "acme":
        validate_acme_config(
            challenge_type=challenge_type,
            domain=domain,
            cloudflare_token=cloudflare_token,
        )
        certfile = ""
        keyfile = ""
        https_port = ACME_HTTPS_PORT
    elif cert_pem or key_pem:
        certfile, keyfile = save_certificate_pair(cert_pem, key_pem)
        source = "path"
    elif https_enabled and source == "path" and (not certfile or not keyfile):
        raise ValueError("SSL_CERTFILE and SSL_KEYFILE must be set together")
    elif https_enabled and source in {"upload", "paste"}:
        raise ValueError("Certificate and private key content must be provided together")
    elif https_enabled and source == "self-signed":
        certfile = ""
        keyfile = ""
    elif bool(certfile) != bool(keyfile):
        raise ValueError("SSL_CERTFILE and SSL_KEYFILE must be set together")

    values = {
        "SERVER_HOST": host.strip(),
        "HTTP_PORT": str(http_port),
        "HTTPS_ENABLED": str(https_enabled).lower(),
        "HTTPS_PORT": str(https_port),
        "HTTPS_CERTIFICATE_SOURCE": source,
        "SSL_CERTFILE": certfile,
        "SSL_KEYFILE": keyfile,
        "ACME_CHALLENGE_TYPE": challenge_type,
        "ACME_DOMAIN": domain,
        "ACME_EMAIL": email,
        "ACME_CLOUDFLARE_API_TOKEN": cloudflare_token,
        "CADDY_CONFIG_PATH": settings.CADDY_CONFIG_PATH,
        "CADDY_BACKEND_HOST": settings.CADDY_BACKEND_HOST,
    }
    write_env_values(values)
    apply_runtime_settings(values)
    try:
        write_caddy_config(settings)
    except OSError as exc:
        raise ValueError(f"Unable to write Caddy config: {exc}") from exc
    mark_restart_required()


def normalize_certificate_source(source: str) -> str:
    normalized = (source or "").strip().lower()
    if normalized not in CERTIFICATE_SOURCE_MODES:
        raise ValueError("Unsupported HTTPS certificate source")
    return normalized


def normalize_acme_challenge_type(challenge_type: str) -> str:
    normalized = (challenge_type or "").strip().lower()
    if normalized not in ACME_CHALLENGE_TYPES:
        raise ValueError("Unsupported ACME challenge type")
    return normalized


def validate_acme_config(
    *,
    challenge_type: str,
    domain: str,
    cloudflare_token: str,
) -> None:
    if not domain:
        raise ValueError("ACME_DOMAIN must be provided")
    if any(char.isspace() for char in domain) or "://" in domain or "/" in domain:
        raise ValueError("ACME_DOMAIN must be a hostname without scheme or path")
    if challenge_type == "http-01" and domain.startswith("*."):
        raise ValueError("HTTP-01 cannot issue wildcard certificates")
    if challenge_type == "dns-01" and not cloudflare_token:
        raise ValueError("Cloudflare API token must be provided for DNS-01")


def write_caddy_config(target_settings: Settings) -> None:
    if target_settings.behind_reverse_proxy:
        return
    config_file = resolve_caddy_config_file(target_settings)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(build_caddyfile(target_settings), encoding="utf-8")


def resolve_caddy_config_file(target_settings: Settings) -> Path:
    config_file = Path(target_settings.CADDY_CONFIG_PATH)
    if config_file.is_absolute():
        return config_file
    return PROJECT_ROOT / config_file


def build_caddyfile(target_settings: Settings) -> str:
    site_address = ":80"
    if target_settings.uses_caddy_acme and target_settings.ACME_DOMAIN:
        site_address = target_settings.ACME_DOMAIN

    lines: list[str] = []
    if target_settings.uses_caddy_acme and target_settings.ACME_EMAIL:
        lines.extend(
            [
                "{",
                f"    email {target_settings.ACME_EMAIL}",
                "}",
                "",
            ]
        )

    lines.append(f"{site_address} {{")
    lines.append("    encode zstd gzip")
    if (
        target_settings.uses_caddy_acme
        and target_settings.ACME_CHALLENGE_TYPE.lower() == "dns-01"
    ):
        lines.extend(
            [
                "    tls {",
                "        dns cloudflare {env.ACME_CLOUDFLARE_API_TOKEN}",
                "    }",
            ]
        )
    lines.extend(build_caddy_reverse_proxy_lines(target_settings))
    lines.append("}")
    return "\n".join(lines) + "\n"


def build_caddy_reverse_proxy_lines(target_settings: Settings) -> list[str]:
    backend_url = (
        f"{target_settings.backend_scheme}://"
        f"{target_settings.CADDY_BACKEND_HOST}:{target_settings.backend_port}"
    )
    if target_settings.backend_scheme != "https":
        return [f"    reverse_proxy {backend_url}"]

    return [
        f"    reverse_proxy {backend_url} {{",
        "        transport http {",
        "            tls_insecure_skip_verify",
        "        }",
        "    }",
    ]


def restrict_private_key_file(path: Path) -> None:
    try:
        path.chmod(PRIVATE_KEY_FILE_MODE)
    except OSError:
        return


def save_certificate_pair(cert_pem: str, key_pem: str) -> tuple[str, str]:
    if not cert_pem or not key_pem:
        raise ValueError("Certificate and private key content must be provided together")
    if "-----BEGIN CERTIFICATE-----" not in cert_pem:
        raise ValueError("Certificate content must be PEM encoded")
    if "-----BEGIN" not in key_pem or "PRIVATE KEY-----" not in key_pem:
        raise ValueError("Private key content must be PEM encoded")

    CERT_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADED_CERT_FILE.write_text(cert_pem.rstrip() + "\n", encoding="utf-8")
    UPLOADED_KEY_FILE.write_text(key_pem.rstrip() + "\n", encoding="utf-8")
    restrict_private_key_file(UPLOADED_KEY_FILE)
    return UPLOADED_CERT_FILE.as_posix(), UPLOADED_KEY_FILE.as_posix()


def ensure_self_signed_certificate(host: str) -> None:
    if SELF_SIGNED_CERT_FILE.exists() and SELF_SIGNED_KEY_FILE.exists():
        return

    CERT_DIR.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OhmStash"),
            x509.NameAttribute(NameOID.COMMON_NAME, "OhmStash Self-Signed"),
        ]
    )
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(build_subject_alt_names(host)), critical=False)
        .sign(private_key, hashes.SHA256())
    )
    SELF_SIGNED_CERT_FILE.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    SELF_SIGNED_KEY_FILE.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    restrict_private_key_file(SELF_SIGNED_KEY_FILE)


def build_subject_alt_names(host: str) -> list[x509.GeneralName]:
    names: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
    ]
    hostname = socket.gethostname().strip()
    if hostname:
        names.append(x509.DNSName(hostname))
    configured_host = host.strip()
    if configured_host and configured_host not in {"0.0.0.0", "::"}:
        try:
            names.append(x509.IPAddress(ipaddress.ip_address(configured_host)))
        except ValueError:
            names.append(x509.DNSName(configured_host))
    return names


def write_env_values(values: dict[str, str]) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    updated_lines: list[str] = []
    seen: set[str] = set()

    for line in lines:
        key = parse_env_key(line)
        if key in values:
            updated_lines.append(f"{key}={format_env_value(values[key])}")
            seen.add(key)
            continue
        updated_lines.append(line)

    for key in SERVER_CONFIG_KEYS:
        if key not in seen:
            updated_lines.append(f"{key}={format_env_value(values[key])}")

    ENV_FILE.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")


def parse_env_key(line: str) -> Optional[str]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key = stripped.split("=", 1)[0].strip()
    return key if key in SERVER_CONFIG_KEYS else None


def format_env_value(value: str) -> str:
    if value == "":
        return ""
    if re.search(r"\s|#|['\"\\]", value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def apply_runtime_settings(values: dict[str, str]) -> None:
    settings.SERVER_HOST = values["SERVER_HOST"]
    settings.HTTP_PORT = int(values["HTTP_PORT"])
    settings.HTTPS_ENABLED = values["HTTPS_ENABLED"] == "true"
    settings.HTTPS_PORT = int(values["HTTPS_PORT"])
    settings.HTTPS_CERTIFICATE_SOURCE = values["HTTPS_CERTIFICATE_SOURCE"]
    settings.SSL_CERTFILE = values["SSL_CERTFILE"] or None
    settings.SSL_KEYFILE = values["SSL_KEYFILE"] or None
    settings.ACME_CHALLENGE_TYPE = values["ACME_CHALLENGE_TYPE"]
    settings.ACME_DOMAIN = values["ACME_DOMAIN"] or None
    settings.ACME_EMAIL = values["ACME_EMAIL"] or None
    settings.ACME_CLOUDFLARE_API_TOKEN = values["ACME_CLOUDFLARE_API_TOKEN"] or None
    settings.CADDY_CONFIG_PATH = values["CADDY_CONFIG_PATH"]
    settings.CADDY_BACKEND_HOST = values["CADDY_BACKEND_HOST"]


def mark_restart_required() -> None:
    global restart_required
    restart_required = True


def clear_restart_required() -> None:
    global restart_required
    restart_required = False


def is_restart_required() -> bool:
    return restart_required


def schedule_restart() -> None:
    thread = threading.Thread(target=restart_process, daemon=True)
    thread.start()


def restart_process() -> None:
    time.sleep(0.8)
    os.execv(sys.executable, [sys.executable, *sys.argv])
