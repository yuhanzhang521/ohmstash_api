import os
import sys
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.api import deps
from app.core.config import settings

TEST_DATABASE_NAME_SUFFIX = "_test"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or settings.DATABASE_URL


def _ensure_safe_test_database(database_url: str) -> None:
    database_name = make_url(database_url).database or ""
    if not database_name.endswith(TEST_DATABASE_NAME_SUFFIX):
        raise RuntimeError("Test database name must end with '_test'")


_ensure_safe_test_database(TEST_DATABASE_URL)
settings.DATABASE_URL = TEST_DATABASE_URL
settings.SERVER_HOST = "127.0.0.1"

from app.core.migrations import reset_database_with_migrations
from app.main import app

engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return TEST_DATABASE_URL


@pytest.fixture(scope="session", autouse=True)
def db_lifecycle() -> Generator[None, None, None]:
    reset_database_with_migrations(TEST_DATABASE_URL, engine=engine)
    yield


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    db_session = TestingSessionLocal(bind=connection)

    try:
        yield db_session
    finally:
        db_session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[deps.get_db] = override_get_db
    settings.ADMIN_INITIAL_PASSWORD = settings.ADMIN_INITIAL_PASSWORD or "password"
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"ADMIN_INITIAL_PASSWORD={settings.ADMIN_INITIAL_PASSWORD}\n"
        "ADMIN_PASSWORD_RESET=\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.core.service_config.ENV_FILE", env_file)
    try:
        test_client = TestClient(app)
        response = test_client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={"username": "admin", "password": settings.ADMIN_INITIAL_PASSWORD},
        )
        assert response.status_code == 200
        test_client.headers.update(
            {"Authorization": f"Bearer {response.json()['token']}"}
        )
        yield test_client
    finally:
        del app.dependency_overrides[deps.get_db]
