from typing import Any

import uvicorn

from app.core.config import settings
from app.core.service_config import get_effective_ssl_files


def build_uvicorn_config() -> dict[str, Any]:
    config: dict[str, Any] = {
        "app": "app.main:app",
        "host": settings.SERVER_HOST,
        "port": settings.backend_port,
    }
    certfile, keyfile, _ = get_effective_ssl_files(settings)
    if certfile and keyfile:
        config["ssl_certfile"] = certfile
        config["ssl_keyfile"] = keyfile
    return config


def main() -> None:
    uvicorn.run(**build_uvicorn_config())


if __name__ == "__main__":
    main()
