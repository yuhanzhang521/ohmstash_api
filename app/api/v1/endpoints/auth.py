from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.models.api_key import ApiKey
from app.models.auth_user import AuthUser
from app.services import auth as auth_service

router = APIRouter()


@router.post("/login", response_model=schemas.LoginResponse)
def login(
    *,
    db: Session = Depends(deps.get_db),
    login_in: schemas.LoginRequest,
) -> Any:
    user = auth_service.authenticate_user(
        db,
        username=login_in.username,
        password=login_in.password,
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return schemas.LoginResponse(
        token=auth_service.create_session_token(user),
        username=user.username,
    )


@router.get("/me", response_model=schemas.CurrentUserResponse)
def read_current_user(
    principal: auth_service.AuthPrincipal = Depends(deps.get_current_principal),
) -> Any:
    return schemas.CurrentUserResponse(username=principal.name)


@router.put("/password", response_model=schemas.CurrentUserResponse)
def change_password(
    *,
    db: Session = Depends(deps.get_db),
    principal: auth_service.AuthPrincipal = Depends(deps.get_current_user_principal),
    password_in: schemas.PasswordChangeRequest,
) -> Any:
    user = db.query(AuthUser).filter(AuthUser.id == principal.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not auth_service.verify_password(
        password_in.current_password,
        user.password_hash,
    ):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = auth_service.hash_password(password_in.new_password)
    db.add(user)
    db.commit()
    return schemas.CurrentUserResponse(username=user.username)


@router.get("/api_keys", response_model=List[schemas.ApiKeyResponse])
def read_api_keys(
    db: Session = Depends(deps.get_db),
    _principal: auth_service.AuthPrincipal = Depends(deps.get_current_user_principal),
) -> Any:
    return db.query(ApiKey).order_by(ApiKey.created_at.desc(), ApiKey.id.desc()).all()


@router.post("/api_keys", response_model=schemas.ApiKeyCreateResponse)
def create_api_key(
    *,
    db: Session = Depends(deps.get_db),
    _principal: auth_service.AuthPrincipal = Depends(deps.get_current_user_principal),
    api_key_in: schemas.ApiKeyCreateRequest,
) -> Any:
    api_key, raw_key = auth_service.create_api_key(db, name=api_key_in.name)
    return schemas.ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        api_key=raw_key,
        created_at=api_key.created_at,
    )


@router.delete("/api_keys/{api_key_id}", response_model=schemas.ApiKeyResponse)
def delete_api_key(
    *,
    db: Session = Depends(deps.get_db),
    _principal: auth_service.AuthPrincipal = Depends(deps.get_current_user_principal),
    api_key_id: int,
) -> Any:
    api_key = db.query(ApiKey).filter(ApiKey.id == api_key_id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    response = schemas.ApiKeyResponse.model_validate(api_key, from_attributes=True)
    db.delete(api_key)
    db.commit()
    return response
