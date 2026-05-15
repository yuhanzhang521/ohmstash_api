from typing import Generator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services import auth


ADMIN_REQUIRED_DETAIL = "Administrator user session required"


def get_db() -> Generator[Session, None, None]:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_current_principal(
    request: Request,
    db: Session = Depends(get_db),
) -> auth.AuthPrincipal:
    auth.ensure_default_admin(db)
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    principal = auth.get_session_principal(db, token)
    if principal:
        return principal

    principal = auth.get_api_key_principal(db, token)
    if principal:
        return principal

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication token",
    )


def get_current_user_principal(
    principal: auth.AuthPrincipal = Depends(get_current_principal),
) -> auth.AuthPrincipal:
    if principal.kind != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ADMIN_REQUIRED_DETAIL,
        )
    return principal
