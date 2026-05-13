from pathlib import Path
from typing import Generator
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.main import app


def test_protected_endpoint_requires_auth(db: Session) -> None:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

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


def test_decode_box_code_endpoint_reads_data_matrix(client: TestClient) -> None:
    image_path = Path("tests/dm_test.jpg")
    with image_path.open("rb") as image_file:
        response = client.post(
            f"{settings.API_V1_STR}/system/decode_box_code",
            files={"file": ("dm_test.jpg", image_file, "image/jpeg")},
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

    clear_response = client.delete(f"{settings.API_V1_STR}/system/database")
    assert clear_response.status_code == 200
    assert clear_response.json()["deleted_boxes"] >= 1
    assert clear_response.json()["deleted_components"] >= 1

    assert client.get(f"{settings.API_V1_STR}/boxes/").json() == []
    assert client.get(f"{settings.API_V1_STR}/components/").json() == []
    assert client.get(f"{settings.API_V1_STR}/ai/vlm_configs/").json()
    assert client.get(f"{settings.API_V1_STR}/search/providers/").json()
    assert client.get(f"{settings.API_V1_STR}/auth/api_keys").json()
