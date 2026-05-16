from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.models.vlm_provider_config import VlmProviderConfig
from app.services import vlm_client


def ensure_unique_config_name(
    db: Session,
    *,
    name: str,
    current_config_id: Optional[int] = None,
) -> None:
    existing_config = crud.vlm_provider_config.get_by_name(db=db, name=name)
    if existing_config and existing_config.id != current_config_id:
        raise HTTPException(status_code=400, detail="VLM config name already exists")


def get_required_default_config(db: Session) -> VlmProviderConfig:
    config = crud.vlm_provider_config.get_default(db=db)
    if not config:
        raise HTTPException(status_code=404, detail="Default VLM config not found")
    return config


def get_config_for_use(
    db: Session,
    *,
    config_id: Optional[int] = None,
) -> VlmProviderConfig:
    if config_id is None:
        return get_required_default_config(db=db)

    config = crud.vlm_provider_config.get(db=db, id=config_id)
    if not config:
        raise HTTPException(status_code=404, detail="VLM config not found")
    return config


def build_transient_config(
    config_in: schemas.VlmProviderConfigCreate,
) -> VlmProviderConfig:
    return VlmProviderConfig(**config_in.model_dump())


def run_connection_test(
    config: VlmProviderConfig,
    *,
    prompt: str,
) -> schemas.VlmConnectionTestResult:
    try:
        response, latency_ms = vlm_client.request_chat_completion(
            config=config,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=64,
        )
    except vlm_client.VlmClientError as exc:
        return schemas.VlmConnectionTestResult(
            ok=False,
            provider=config.provider,
            model_name=config.model_name,
            status_code=exc.status_code,
            message=exc.message,
            response_text=exc.response_body,
        )

    response_text = vlm_client.extract_message_text(response)
    return schemas.VlmConnectionTestResult(
        ok=True,
        provider=config.provider,
        model_name=config.model_name,
        latency_ms=latency_ms,
        message="VLM config test succeeded",
        response_text=response_text,
    )


def upsert_default_config(
    db: Session,
    *,
    config_in: schemas.VlmProviderConfigCreate,
) -> VlmProviderConfig:
    default_config = crud.vlm_provider_config.get_default(db=db)
    if default_config:
        ensure_unique_config_name(
            db=db,
            name=config_in.name,
            current_config_id=default_config.id,
        )
        config_data = config_in.model_dump()
        if "api_key" not in config_in.model_fields_set:
            config_data.pop("api_key", None)
        config_data["is_default"] = True
        update_data = schemas.VlmProviderConfigUpdate(**config_data)
        return crud.vlm_provider_config.update(
            db=db,
            db_obj=default_config,
            obj_in=update_data,
        )

    ensure_unique_config_name(db=db, name=config_in.name)
    config_data = config_in.model_dump()
    config_data["is_default"] = True
    create_data = schemas.VlmProviderConfigCreate(**config_data)
    return crud.vlm_provider_config.create(db=db, obj_in=create_data)
