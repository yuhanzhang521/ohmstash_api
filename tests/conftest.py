import sys
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.api import deps
from app.core.config import settings
from app.database import Base, ensure_schema_compatibility
from app.main import app

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def db_lifecycle() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()
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
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[deps.get_db] = override_get_db
    try:
        test_client = TestClient(app)
        response = test_client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={"username": "admin", "password": "password"},
        )
        assert response.status_code == 200
        test_client.headers.update(
            {"Authorization": f"Bearer {response.json()['token']}"}
        )
        yield test_client
    finally:
        del app.dependency_overrides[deps.get_db]
