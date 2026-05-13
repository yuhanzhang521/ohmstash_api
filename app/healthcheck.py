import os
import ssl
import urllib.request
from pathlib import Path
from typing import Optional

ENV_FILE = Path("/app/.env")


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, value = parse_env_line(line)
        if key:
            values[key] = value
    return values


def parse_env_line(line: str) -> tuple[Optional[str], str]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None, ""

    key, value = stripped.split("=", 1)
    return key.strip(), unquote_env_value(value.strip())


def unquote_env_value(value: str) -> str:
    if len(value) < 2 or value[0] not in {"'", '"'} or value[-1] != value[0]:
        return value
    unquoted = value[1:-1]
    if value[0] == '"':
        return unquoted.replace('\\"', '"').replace("\\\\", "\\")
    return unquoted


def get_config_value(values: dict[str, str], key: str, default: str) -> str:
    return values.get(key) or os.getenv(key, default)


def main() -> None:
    values = read_env_file(ENV_FILE)
    https_enabled = get_config_value(values, "HTTPS_ENABLED", "false").lower() == "true"
    certificate_source = get_config_value(
        values,
        "HTTPS_CERTIFICATE_SOURCE",
        "self-signed",
    ).lower()
    https = https_enabled and certificate_source != "acme"
    scheme = "https" if https else "http"
    port_key = "HTTPS_PORT" if https else "HTTP_PORT"
    port = get_config_value(values, port_key, "8443" if https else "8000")
    context = ssl._create_unverified_context() if https else None
    urllib.request.urlopen(
        f"{scheme}://127.0.0.1:{port}/",
        timeout=3,
        context=context,
    ).read()


if __name__ == "__main__":
    main()
