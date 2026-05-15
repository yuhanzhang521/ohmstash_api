from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app import models
from app import schemas
from app.api import deps
from app.core.config import settings
from app.core.logging_config import (
    VALID_LOG_LEVELS,
    get_log_file_path,
    get_runtime_log_level,
    read_log_lines,
    set_runtime_log_level,
)
from app.core.service_config import (
    get_effective_ssl_files,
    is_restart_required,
    save_server_config,
    schedule_restart,
)
from app.services import auth, barcode_decoder
from app.services.image_upload import read_limited_upload

router = APIRouter()


def build_server_config_response() -> schemas.ServerConfig:
    certfile, keyfile, using_self_signed = get_effective_ssl_files(settings)
    return schemas.ServerConfig(
        host=settings.SERVER_HOST,
        http_port=settings.HTTP_PORT,
        https_enabled=settings.HTTPS_ENABLED,
        https_port=settings.HTTPS_PORT,
        certificate_source=settings.HTTPS_CERTIFICATE_SOURCE,
        scheme=settings.service_scheme,
        active_port=settings.service_port,
        ssl_certfile=certfile,
        ssl_keyfile=keyfile,
        ssl_configured=bool(certfile and keyfile),
        using_self_signed_certificate=using_self_signed,
        acme_challenge_type=settings.ACME_CHALLENGE_TYPE,
        acme_domain=settings.ACME_DOMAIN,
        acme_email=settings.ACME_EMAIL,
        acme_cloudflare_api_token_configured=bool(settings.ACME_CLOUDFLARE_API_TOKEN),
        caddy_config_path=settings.CADDY_CONFIG_PATH,
        restart_required=is_restart_required(),
        deployment_mode=settings.DEPLOYMENT_MODE,
        behind_reverse_proxy=settings.behind_reverse_proxy,
        public_base_url=settings.PUBLIC_BASE_URL,
    )


@router.get("/health")
def read_system_health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/config", response_model=schemas.ServerConfig)
def read_system_config(
    _principal: auth.AuthPrincipal = Depends(deps.get_current_user_principal),
) -> object:
    return build_server_config_response()


@router.put("/config", response_model=schemas.ServerConfig)
def update_system_config(
    config_in: schemas.ServerConfigUpdate,
    _principal: auth.AuthPrincipal = Depends(deps.get_current_user_principal),
) -> object:
    try:
        save_server_config(
            host=config_in.host,
            http_port=config_in.http_port,
            https_enabled=config_in.https_enabled,
            https_port=config_in.https_port,
            certificate_source=config_in.certificate_source,
            ssl_certfile=config_in.ssl_certfile,
            ssl_keyfile=config_in.ssl_keyfile,
            ssl_cert_pem=config_in.ssl_cert_pem,
            ssl_key_pem=config_in.ssl_key_pem,
            acme_challenge_type=config_in.acme_challenge_type,
            acme_domain=config_in.acme_domain,
            acme_email=config_in.acme_email,
            acme_cloudflare_api_token=config_in.acme_cloudflare_api_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return build_server_config_response()


@router.post("/restart", response_model=schemas.ServerRestartResponse)
def restart_system(
    _principal: auth.AuthPrincipal = Depends(deps.get_current_user_principal),
) -> object:
    schedule_restart()
    return schemas.ServerRestartResponse(
        restarting=True,
        message="服务正在重启，请稍后刷新页面。",
    )


@router.get("/logs/config", response_model=schemas.LoggingConfig)
def read_logging_config(
    _principal: auth.AuthPrincipal = Depends(deps.get_current_user_principal),
) -> object:
    return schemas.LoggingConfig(
        level=get_runtime_log_level(),
        log_file_path=str(get_log_file_path()),
    )


@router.put("/logs/config", response_model=schemas.LoggingConfig)
def update_logging_config(
    config_in: schemas.LoggingConfigUpdate,
    _principal: auth.AuthPrincipal = Depends(deps.get_current_user_principal),
) -> object:
    requested_level = config_in.level.strip().upper()
    if requested_level not in VALID_LOG_LEVELS:
        raise HTTPException(status_code=400, detail="Unsupported log level")
    level = set_runtime_log_level(requested_level)
    return schemas.LoggingConfig(
        level=level,
        log_file_path=str(get_log_file_path()),
    )


@router.get("/logs", response_model=schemas.LogLinesResponse)
def read_logs(
    limit: int = Query(300, ge=1, le=2000),
    _principal: auth.AuthPrincipal = Depends(deps.get_current_user_principal),
) -> object:
    lines, total_lines = read_log_lines(limit)
    return schemas.LogLinesResponse(
        level=get_runtime_log_level(),
        log_file_path=str(get_log_file_path()),
        total_lines=total_lines,
        lines=lines,
    )


@router.post("/decode_box_code", response_model=schemas.CodeDecodeResponse)
def decode_box_code(file: UploadFile = File(...)) -> object:
    try:
        content = read_limited_upload(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not content:
        raise HTTPException(status_code=400, detail="Image file is required")

    try:
        raw_codes = barcode_decoder.decode_barcodes_from_image(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return schemas.CodeDecodeResponse(
        raw_codes=raw_codes,
        box_codes=barcode_decoder.extract_box_codes(raw_codes),
    )


@router.delete("/database", response_model=schemas.DatabaseClearResponse)
def clear_database(
    clear_in: schemas.DatabaseClearRequest | None = None,
    db: Session = Depends(deps.get_db),
    _principal: auth.AuthPrincipal = Depends(deps.get_current_user_principal),
) -> object:
    if clear_in is None:
        raise HTTPException(status_code=400, detail="Database clear confirmation is required")
    deleted_boxes = db.query(models.Box).count()
    deleted_components = db.query(models.Component).count()
    deleted_tags = db.query(models.Tag).count()
    deleted_templates = db.query(models.BoxTemplate).count()

    db.query(models.Inventory).delete()
    db.query(models.SubBox).delete()
    db.query(models.Box).delete()
    db.execute(models.components_tags_association_table.delete())
    db.query(models.Component).delete()
    db.query(models.AttributeDefinition).delete()
    db.query(models.Tag).delete()
    db.query(models.BoxTemplate).delete()
    db.commit()

    return schemas.DatabaseClearResponse(
        deleted_boxes=deleted_boxes,
        deleted_components=deleted_components,
        deleted_tags=deleted_tags,
        deleted_templates=deleted_templates,
    )
