from typing import List, Optional

from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    host: str
    http_port: int
    https_enabled: bool
    https_port: int
    certificate_source: str
    scheme: str
    active_port: int
    ssl_certfile: Optional[str]
    ssl_keyfile: Optional[str]
    ssl_configured: bool
    using_self_signed_certificate: bool
    acme_challenge_type: str
    acme_domain: Optional[str]
    acme_email: Optional[str]
    acme_cloudflare_api_token_configured: bool
    caddy_config_path: str
    restart_required: bool


class ServerConfigUpdate(BaseModel):
    host: str = Field(min_length=1)
    http_port: int = Field(ge=1, le=65535)
    https_enabled: bool
    https_port: int = Field(ge=1, le=65535)
    certificate_source: str = "self-signed"
    ssl_certfile: Optional[str] = None
    ssl_keyfile: Optional[str] = None
    ssl_cert_pem: Optional[str] = None
    ssl_key_pem: Optional[str] = None
    acme_challenge_type: Optional[str] = None
    acme_domain: Optional[str] = None
    acme_email: Optional[str] = None
    acme_cloudflare_api_token: Optional[str] = None


class ServerRestartResponse(BaseModel):
    restarting: bool
    message: str


class LoggingConfig(BaseModel):
    level: str
    log_file_path: str


class LoggingConfigUpdate(BaseModel):
    level: str


class LogLinesResponse(BaseModel):
    level: str
    log_file_path: str
    total_lines: int
    lines: List[str]


class DatabaseClearResponse(BaseModel):
    deleted_boxes: int
    deleted_components: int
    deleted_tags: int
    deleted_templates: int


class CodeDecodeResponse(BaseModel):
    raw_codes: List[str]
    box_codes: List[str]
