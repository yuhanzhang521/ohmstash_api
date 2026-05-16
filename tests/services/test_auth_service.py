from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.auth_user import AuthUser
from app.services import auth


INITIAL_PASSWORD = "initial-test-password"
RESET_PASSWORD = "reset-test-password"


def test_default_admin_consumes_initial_password(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ADMIN_USERNAME=admin\n"
        f"ADMIN_INITIAL_PASSWORD={INITIAL_PASSWORD}\n"
        "ADMIN_PASSWORD_RESET=\n",
        encoding="utf-8",
    )
    runtime_settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        SERVER_HOST="127.0.0.1",
        ADMIN_INITIAL_PASSWORD=INITIAL_PASSWORD,
    )
    monkeypatch.setattr("app.services.auth.settings", runtime_settings)
    monkeypatch.setattr("app.core.service_config.ENV_FILE", env_file)

    user = auth.ensure_default_admin(db)

    assert user.username == "admin"
    assert user.password_hash != INITIAL_PASSWORD
    assert auth.verify_password(INITIAL_PASSWORD, user.password_hash)
    assert "ADMIN_INITIAL_PASSWORD=\n" in env_file.read_text(encoding="utf-8")
    assert runtime_settings.ADMIN_INITIAL_PASSWORD == ""


def test_default_admin_consumes_reset_password(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ADMIN_USERNAME=admin\n"
        "ADMIN_INITIAL_PASSWORD=\n"
        f"ADMIN_PASSWORD_RESET={RESET_PASSWORD}\n",
        encoding="utf-8",
    )
    user = AuthUser(
        username="admin",
        password_hash=auth.hash_password(INITIAL_PASSWORD),
        is_active=True,
    )
    db.add(user)
    db.commit()
    runtime_settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        SERVER_HOST="127.0.0.1",
        ADMIN_INITIAL_PASSWORD="",
        ADMIN_PASSWORD_RESET=RESET_PASSWORD,
    )
    monkeypatch.setattr("app.services.auth.settings", runtime_settings)
    monkeypatch.setattr("app.core.service_config.ENV_FILE", env_file)

    auth.ensure_default_admin(db)
    db.refresh(user)

    assert auth.verify_password(RESET_PASSWORD, user.password_hash)
    assert not auth.verify_password(INITIAL_PASSWORD, user.password_hash)
    assert "ADMIN_PASSWORD_RESET=\n" in env_file.read_text(encoding="utf-8")
    assert runtime_settings.ADMIN_PASSWORD_RESET == ""


def test_missing_initial_password_rejected_before_first_start(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        SERVER_HOST="127.0.0.1",
        ADMIN_INITIAL_PASSWORD="",
    )
    monkeypatch.setattr("app.services.auth.settings", runtime_settings)

    with pytest.raises(ValueError, match="ADMIN_INITIAL_PASSWORD"):
        auth.ensure_default_admin(db)


def test_default_initial_password_rejected_in_production(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        ADMIN_INITIAL_PASSWORD="password",
    )
    monkeypatch.setattr("app.services.auth.settings", runtime_settings)

    with pytest.raises(ValueError, match="Default admin initial password"):
        auth.ensure_default_admin(db)


def test_default_reset_password_rejected_in_production(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = AuthUser(
        username="admin",
        password_hash=auth.hash_password(INITIAL_PASSWORD),
        is_active=True,
    )
    db.add(user)
    db.commit()
    runtime_settings = Settings(
        DATABASE_URL="postgresql://user:password@host/db",
        ADMIN_INITIAL_PASSWORD="changed-password",
        ADMIN_PASSWORD_RESET="password",
    )
    monkeypatch.setattr("app.services.auth.settings", runtime_settings)

    with pytest.raises(ValueError, match="Default admin reset password"):
        auth.ensure_default_admin(db)
