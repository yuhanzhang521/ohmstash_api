from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.box_template import BoxTemplateCreate


def test_create_box_template(client: TestClient, db: Session) -> None:
    data = {
        "name": "Test Grid Template",
        "layout_type": "grid",
        "layout_definition": {"rows": 8, "cols": 12}
    }
    response = client.post(
        f"{settings.API_V1_STR}/box_templates/",
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["layout_type"] == data["layout_type"]
    assert "id" in content


def test_read_box_template(client: TestClient, db: Session) -> None:
    data = {
        "name": "Test Grid Template for Reading",
        "layout_type": "grid",
        "layout_definition": {"rows": 5, "cols": 5}
    }
    response = client.post(
        f"{settings.API_V1_STR}/box_templates/",
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    template_id = content["id"]

    response = client.get(f"{settings.API_V1_STR}/box_templates/{template_id}")
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["id"] == template_id
