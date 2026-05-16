import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.service_config import clear_admin_secret
from app.models.api_key import ApiKey
from app.models.auth_session import AuthSession
from app.models.auth_user import AuthUser

PASSWORD_ITERATIONS = 260_000
SESSION_TOKEN_BYTES = 32
API_KEY_BYTES = 32
API_KEY_PREFIX = "ohm"
SESSION_TOKEN_TTL_HOURS = 12
logger = logging.getLogger(__name__)


@dataclass
class AuthPrincipal:
    kind: str
    id: int
    name: str


def hash_password(password: str, *, salt: Optional[bytes] = None) -> str:
    password_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        password_salt,
        PASSWORD_ITERATIONS,
    )
    return (
        f"pbkdf2_sha256${PASSWORD_ITERATIONS}$"
        f"{password_salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_hex, digest_hex = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations_text),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def ensure_default_admin(db: Session) -> AuthUser:
    user = db.query(AuthUser).order_by(AuthUser.id).first()
    if user:
        reset_default_admin_password(db, user)
        return user
    initial_password = settings.ADMIN_INITIAL_PASSWORD
    if not initial_password:
        raise ValueError("ADMIN_INITIAL_PASSWORD must be set before first startup")
    if settings.is_production_mode and initial_password == "password":
        raise ValueError("Default admin initial password cannot be used in production mode")
    user = AuthUser(
        username=settings.ADMIN_USERNAME,
        password_hash=hash_password(initial_password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    consume_admin_secret("ADMIN_INITIAL_PASSWORD")
    return user


def reset_default_admin_password(db: Session, user: AuthUser) -> None:
    reset_password = settings.ADMIN_PASSWORD_RESET
    if not reset_password:
        return
    if settings.is_production_mode and reset_password == "password":
        raise ValueError("Default admin reset password cannot be used in production mode")
    user.password_hash = hash_password(reset_password)
    db.add(user)
    db.commit()
    consume_admin_secret("ADMIN_PASSWORD_RESET")


def consume_admin_secret(secret_key: str) -> None:
    setattr(settings, secret_key, "")
    try:
        clear_admin_secret(secret_key)
    except OSError:
        logger.warning("Unable to clear %s from env file", secret_key, exc_info=True)


def authenticate_user(
    db: Session,
    *,
    username: str,
    password: str,
) -> Optional[AuthUser]:
    ensure_default_admin(db)
    user = db.query(AuthUser).filter(AuthUser.username == username).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_session_token(db: Session, user: AuthUser) -> str:
    token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TOKEN_TTL_HOURS)
    session = AuthSession(
        user_id=int(user.id),
        token_hash=hash_session_token(token),
        is_active=True,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    return token


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_session_principal(db: Session, token: str) -> Optional[AuthPrincipal]:
    session = (
        db.query(AuthSession)
        .filter(
            AuthSession.token_hash == hash_session_token(token),
            AuthSession.is_active.is_(True),
        )
        .first()
    )
    if not session:
        return None
    if session.expires_at <= datetime.now(timezone.utc):
        session.is_active = False
        db.add(session)
        db.commit()
        return None
    user = db.query(AuthUser).filter(AuthUser.id == session.user_id).first()
    if not user or not user.is_active:
        session.is_active = False
        db.add(session)
        db.commit()
        return None
    return AuthPrincipal(kind="user", id=user.id, name=user.username)


def create_api_key(db: Session, *, name: str) -> tuple[ApiKey, str]:
    raw_key = f"{API_KEY_PREFIX}_{secrets.token_urlsafe(API_KEY_BYTES)}"
    api_key = ApiKey(
        name=name,
        key_hash=hash_api_key(raw_key),
        prefix=raw_key[:12],
        is_active=True,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key, raw_key


def get_api_key_principal(db: Session, token: str) -> Optional[AuthPrincipal]:
    key_hash = hash_api_key(token)
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
        .first()
    )
    if not api_key:
        return None
    api_key.last_used_at = datetime.now(timezone.utc)
    db.add(api_key)
    db.commit()
    return AuthPrincipal(kind="api_key", id=api_key.id, name=api_key.name)
