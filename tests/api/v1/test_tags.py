from fastapi.testclient import TestClient

from app.core.config import settings


def test_seed_default_tags(client: TestClient) -> None:
    response = client.post(f"{settings.API_V1_STR}/tags/defaults/seed")
    assert response.status_code == 200
    content = response.json()
    created_names = [tag["name"] for tag in content["created"]]
    skipped_names = [tag["name"] for tag in content["skipped_duplicates"]]
    assert "电阻/贴片电阻" in created_names + skipped_names

    response = client.get(f"{settings.API_V1_STR}/tags/")
    assert response.status_code == 200
    names = [tag["name"] for tag in response.json()]
    assert "IC/MCU" in names
