from pathlib import Path
from typing import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.main import app
from app.models.auth_session import AuthSession


def test_protected_endpoint_requires_auth(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    env_file = tmp_path / ".env"
    env_file.write_text(
        "ADMIN_INITIAL_PASSWORD=password\n"
        "ADMIN_PASSWORD_RESET=\n",
        encoding="utf-8",
    )
    settings.ADMIN_INITIAL_PASSWORD = "password"
    monkeypatch.setattr("app.core.service_config.ENV_FILE", env_file)

    app.dependency_overrides[deps.get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            response = test_client.get(f"{settings.API_V1_STR}/components/")
    finally:
        del app.dependency_overrides[deps.get_db]

    assert response.status_code == 401


def test_default_admin_login_and_api_key_access(client: TestClient) -> None:
    login_response = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"username": "admin", "password": "password"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["username"] == "admin"

    key_response = client.post(
        f"{settings.API_V1_STR}/auth/api_keys",
        json={"name": "External Test"},
    )
    assert key_response.status_code == 200
    api_key = key_response.json()["api_key"]

    client.headers.update({"Authorization": f"Bearer {api_key}"})
    health_response = client.get(f"{settings.API_V1_STR}/system/health")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}


def test_user_session_token_is_persisted(client: TestClient, db: Session) -> None:
    login_response = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"username": "admin", "password": "password"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["token"]

    assert db.query(AuthSession).count() >= 1
    client.headers.update({"Authorization": f"Bearer {token}"})
    response = client.get(f"{settings.API_V1_STR}/auth/me")

    assert response.status_code == 200
    assert response.json()["username"] == "admin"


def test_decode_box_code_endpoint_reads_data_matrix(client: TestClient) -> None:
    image_path = Path("tests/barcode_box_labels.jpg")
    with image_path.open("rb") as image_file:
        response = client.post(
            f"{settings.API_V1_STR}/system/decode_box_code",
            files={"file": ("barcode_box_labels.jpg", image_file, "image/jpeg")},
        )

    assert response.status_code == 200
    assert response.json()["raw_codes"] == ["DataMatrix Content Is Here!"]


def test_clear_database_preserves_provider_and_account_config(
    client: TestClient,
) -> None:
    suffix = uuid4().hex[:8]
    ai_response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": f"AI {suffix}",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "vision-model",
        },
    )
    assert ai_response.status_code == 200
    search_response = client.post(
        f"{settings.API_V1_STR}/search/providers/",
        json={
            "name": f"Search {suffix}",
            "provider": "duckduckgo",
            "is_default": True,
        },
    )
    assert search_response.status_code == 200
    key_response = client.post(
        f"{settings.API_V1_STR}/auth/api_keys",
        json={"name": f"Key {suffix}"},
    )
    assert key_response.status_code == 200

    template_response = client.post(
        f"{settings.API_V1_STR}/box_templates/",
        json={
            "name": f"Template {suffix}",
            "layout_type": "grid",
            "layout_definition": {"rows": 1, "cols": 1},
        },
    )
    assert template_response.status_code == 200
    box_response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        json={
            "readable_id": f"BOX-CLEAR-{suffix}",
            "name": "Clear Box",
            "template_id": template_response.json()["id"],
        },
    )
    assert box_response.status_code == 200
    component_response = client.post(
        f"{settings.API_V1_STR}/components/",
        json={"name": f"Clear Component {suffix}", "tag_ids": []},
    )
    assert component_response.status_code == 200

    clear_response = client.request(
        "DELETE",
        f"{settings.API_V1_STR}/system/database",
        json={
            "confirmation": "CLEAR DATABASE",
            "database_name": make_url(settings.DATABASE_URL).database,
        },
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["deleted_boxes"] >= 1
    assert clear_response.json()["deleted_components"] >= 1

    assert client.get(f"{settings.API_V1_STR}/boxes/").json() == []
    assert client.get(f"{settings.API_V1_STR}/components/").json() == []
    assert client.get(f"{settings.API_V1_STR}/ai/vlm_configs/").json()
    assert client.get(f"{settings.API_V1_STR}/search/providers/").json()
    assert client.get(f"{settings.API_V1_STR}/auth/api_keys").json()


def test_clear_database_rejects_wrong_database_name(client: TestClient) -> None:
    response = client.request(
        "DELETE",
        f"{settings.API_V1_STR}/system/database",
        json={
            "confirmation": "CLEAR DATABASE",
            "database_name": "wrong_database",
        },
    )

    assert response.status_code == 400

    key_response = client.post(
        f"{settings.API_V1_STR}/auth/api_keys",
        json={"name": f"Search Management {uuid4().hex[:8]}"},
    )
    assert key_response.status_code == 200

    client.headers.update({"Authorization": f"Bearer {key_response.json()['api_key']}"})
    response = client.post(
        f"{settings.API_V1_STR}/search/providers/",
        json={
            "name": f"Blocked Search {uuid4().hex[:8]}",
            "provider": "duckduckgo",
        },
    )

    assert response.status_code == 403
