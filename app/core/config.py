from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine.url import URL


class Settings(BaseSettings):
    PROJECT_NAME: str = "OhmStash API"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: Optional[str] = None
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "password"
    SERVER_HOST: str = "0.0.0.0"
    HTTP_PORT: int = 8000
    HTTPS_ENABLED: bool = False
    HTTPS_PORT: int = 8443
    HTTPS_CERTIFICATE_SOURCE: str = "self-signed"
    SSL_CERTFILE: Optional[str] = None
    SSL_KEYFILE: Optional[str] = None
    ACME_CHALLENGE_TYPE: str = "http-01"
    ACME_DOMAIN: Optional[str] = None
    ACME_EMAIL: Optional[str] = None
    ACME_CLOUDFLARE_API_TOKEN: Optional[str] = None
    CADDY_CONFIG_PATH: str = "caddy/Caddyfile"
    CADDY_BACKEND_HOST: str = "127.0.0.1"
    DEPLOYMENT_MODE: str = "standalone"
    PUBLIC_BASE_URL: Optional[str] = None
    POSTGRES_SERVER: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        extra="ignore",
    )

    @property
    def behind_reverse_proxy(self) -> bool:
        return (self.DEPLOYMENT_MODE or "").strip().lower() == "reverse_proxy"

    @property
    def service_scheme(self) -> str:
        if self.behind_reverse_proxy:
            return "http"
        return "https" if self.HTTPS_ENABLED else "http"

    @property
    def service_port(self) -> int:
        if self.behind_reverse_proxy:
            return self.HTTP_PORT
        return self.HTTPS_PORT if self.HTTPS_ENABLED else self.HTTP_PORT

    @property
    def ssl_enabled(self) -> bool:
        if self.behind_reverse_proxy:
            return False
        return self.HTTPS_CERTIFICATE_SOURCE.lower() != "acme" and bool(
            self.SSL_CERTFILE and self.SSL_KEYFILE,
        )

    @property
    def uses_caddy_acme(self) -> bool:
        if self.behind_reverse_proxy:
            return False
        return self.HTTPS_ENABLED and self.HTTPS_CERTIFICATE_SOURCE.lower() == "acme"

    @property
    def backend_scheme(self) -> str:
        return "http" if self.uses_caddy_acme else self.service_scheme

    @property
    def backend_port(self) -> int:
        return self.HTTP_PORT if self.uses_caddy_acme else self.service_port

    @property
    def is_production_mode(self) -> bool:
        return self.behind_reverse_proxy or bool(self.PUBLIC_BASE_URL or self.ACME_DOMAIN)

    def validate_runtime_security(self) -> None:
        if not self.is_production_mode:
            return
        if self.DEFAULT_ADMIN_USERNAME == "admin" and self.DEFAULT_ADMIN_PASSWORD == "password":
            raise ValueError("Default admin credentials cannot be used in production mode")

    @model_validator(mode="after")
    def assemble_database_url(self) -> "Settings":
        if self.DATABASE_URL:
            return self

        missing_fields = [
            field_name
            for field_name in (
                "POSTGRES_SERVER",
                "POSTGRES_USER",
                "POSTGRES_PASSWORD",
                "POSTGRES_DB",
            )
            if not getattr(self, field_name)
        ]
        if missing_fields:
            missing = ", ".join(missing_fields)
            raise ValueError(f"Missing database configuration: {missing}")

        self.DATABASE_URL = URL.create(
            drivername="postgresql+psycopg2",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            database=self.POSTGRES_DB,
            query={"client_encoding": "utf8"},
        ).render_as_string(
            hide_password=False,
        )
        return self


settings = Settings()
settings.validate_runtime_security()
